"""
Agent loop — local instruct model reads ticket, picks action, executes.

The agent receives a constrained prompt and must output JSON with an action.
If output doesn't parse, falls back to scripted pipeline.

Supports two backends:
  1. flan-t5 via transformers (lighter, less reliable action selection)
  2. Ollama (Mistral-7B-Instruct) for better reasoning (if available)
"""

import json
import re
import time

from agent.actions import classify, draft_reply
from agent.fallback import scripted_pipeline
from agent.models import generate_text
from agent.schema import AGENT_ACTIONS, TEAM_ROUTING, confidence_tier

AGENT_SYSTEM_PROMPT = """You are a customer support triage agent for SharkNinja.
Read the customer message and decide what action to take.

Available actions:
- classify: The message needs to be classified into a support category
- draft: The message is clear enough to draft a response
- escalate: The message is too complex, ambiguous, or sensitive for automated handling
- clarify: You need more information from the customer before proceeding

Respond with ONLY a JSON object:
{{"action": "classify", "reasoning": "brief explanation"}}

Customer message: {}"""

OLLAMA_AVAILABLE = None


def _check_ollama():
    global OLLAMA_AVAILABLE
    if OLLAMA_AVAILABLE is not None:
        return OLLAMA_AVAILABLE
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            OLLAMA_AVAILABLE = any("mistral" in m or "llama" in m for m in models)
            if OLLAMA_AVAILABLE:
                print("[agent] Ollama detected with instruct model")
            else:
                print("[agent] Ollama running but no instruct model found")
        else:
            OLLAMA_AVAILABLE = False
    except Exception:
        OLLAMA_AVAILABLE = False
    return OLLAMA_AVAILABLE


def _ollama_generate(prompt: str) -> str:
    import requests
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral", "prompt": prompt, "stream": False},
        timeout=30,
    )
    return resp.json()["response"]


def _get_agent_action(text: str) -> dict | None:
    """
    Ask local model to decide an action. Returns parsed dict or None on failure.
    """
    prompt = AGENT_SYSTEM_PROMPT.format(text[:400])

    try:
        if _check_ollama():
            raw = _ollama_generate(prompt)
        else:
            raw = generate_text(prompt)
    except Exception as exc:
        print("[agent] Model call failed: {}".format(exc))
        return None

    return _parse_action(raw)


def _parse_action(raw: str) -> dict | None:
    """Extract JSON action from model output. Tolerant of extra text."""
    # Try direct parse
    try:
        data = json.loads(raw.strip())
        if data.get("action") in AGENT_ACTIONS:
            return data
    except (json.JSONDecodeError, AttributeError):
        pass

    # Try extracting JSON from mixed output
    match = re.search(r'\{[^}]+\}', raw)
    if match:
        try:
            data = json.loads(match.group())
            if data.get("action") in AGENT_ACTIONS:
                return data
        except json.JSONDecodeError:
            pass

    # Try keyword match as last resort
    raw_lower = raw.lower()
    for action in AGENT_ACTIONS:
        if action in raw_lower:
            return {"action": action, "reasoning": "extracted from raw output"}

    return None


def process_ticket_agent(text: str) -> dict:
    """
    Full agent loop: decide action -> execute -> possibly retry.
    Falls back to scripted pipeline on any failure.
    """
    trace = []
    start = time.time()

    # Step 1: Agent decides action
    decision = _get_agent_action(text)

    if decision is None:
        trace.append({"step": "agent_decision", "result": "parse_failed"})
        result = scripted_pipeline(text)
        result["agent_trace"] = trace + result["agent_trace"]
        result["processing_time"] = round(time.time() - start, 2)
        return result

    action = decision["action"]
    reasoning = decision.get("reasoning", "")
    trace.append({
        "step": "agent_decision",
        "action": action,
        "reasoning": reasoning,
    })

    # Step 2: Execute action
    if action == "escalate":
        result = {
            "category": "unknown",
            "confidence": 0.0,
            "tier": "escalate",
            "team": "Manual Review",
            "all_scores": {},
            "draft_reply": "",
            "agent_trace": trace,
            "fallback_used": False,
            "processing_time": round(time.time() - start, 2),
        }
        return result

    if action == "clarify":
        clarifying_q = generate_text(
            "Write a short clarifying question for this customer message. "
            "Ask for the specific detail needed to help them. "
            "Customer: " + text[:300]
        )
        result = {
            "category": "needs_clarification",
            "confidence": 0.0,
            "tier": "escalate",
            "team": "Manual Review",
            "all_scores": {},
            "draft_reply": clarifying_q,
            "agent_trace": trace + [{"step": "clarify", "question": clarifying_q}],
            "fallback_used": False,
            "processing_time": round(time.time() - start, 2),
        }
        return result

    # classify or draft — both start with classification
    classification = classify(text)
    trace.append({
        "step": "classify",
        "category": classification["category"],
        "confidence": classification["confidence"],
        "tier": classification["tier"],
    })

    category = classification["category"]
    conf = classification["confidence"]
    tier = classification["tier"]

    # Retry on low confidence
    if tier == "escalate":
        trace.append({"step": "low_confidence_retry", "original_conf": conf})
        # Re-classify with hint
        hint_text = "This is likely a {} issue. {}".format(category, text[:300])
        retry = classify(hint_text)
        trace.append({
            "step": "retry_classify",
            "category": retry["category"],
            "confidence": retry["confidence"],
            "tier": retry["tier"],
        })
        if retry["confidence"] > conf:
            classification = retry
            category = retry["category"]
            conf = retry["confidence"]
            tier = confidence_tier(conf) if conf >= 0.50 else "escalate"

    # Draft reply if not escalated
    draft = ""
    if tier != "escalate" or action == "draft":
        draft = draft_reply(text, category)
        trace.append({"step": "draft", "length": len(draft)})

    result = {
        "category": category,
        "confidence": conf,
        "tier": tier,
        "team": TEAM_ROUTING.get(category, "Manual Review"),
        "all_scores": classification.get("all_scores", {}),
        "draft_reply": draft,
        "agent_trace": trace,
        "fallback_used": False,
        "processing_time": round(time.time() - start, 2),
    }
    return result
