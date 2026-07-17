"""
Deterministic scripted pipeline — no agent reasoning.
Always works. Used when agent output doesn't parse or model unavailable.

Flow: classify -> draft -> route. No retries, no action selection.
"""

from agent.actions import classify, draft_reply
from agent.schema import TEAM_ROUTING


def scripted_pipeline(text: str) -> dict:
    classification = classify(text)
    category = classification["category"]

    draft = ""
    if classification["tier"] != "escalate":
        draft = draft_reply(text, category)

    return {
        "category": category,
        "confidence": classification["confidence"],
        "tier": classification["tier"],
        "team": classification["team"],
        "all_scores": classification["all_scores"],
        "draft_reply": draft,
        "agent_trace": [{"step": "fallback", "reason": "scripted pipeline"}],
        "fallback_used": True,
    }
