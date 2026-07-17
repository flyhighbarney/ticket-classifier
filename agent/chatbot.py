"""
Data-aware chatbot — answers questions about classified ticket data.
Uses Ollama (Llama) if available, falls back to flan-t5.
"""

import csv
import json
from collections import Counter
from pathlib import Path

from agent.models import generate_text

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
CLASSIFIED_PATH = DATA_PATH / "classified_results.csv"

_ollama_model = None


def _detect_ollama():
    global _ollama_model
    if _ollama_model is not None:
        return _ollama_model
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            for m in models:
                if "llama" in m:
                    _ollama_model = m
                    print("[chatbot] Ollama Llama detected: {}".format(m))
                    return m
            for m in models:
                if "mistral" in m or "gemma" in m or "phi" in m:
                    _ollama_model = m
                    print("[chatbot] Ollama model detected: {}".format(m))
                    return m
    except Exception:
        pass
    _ollama_model = ""
    return ""


def _ollama_chat(prompt: str) -> str:
    import requests
    model = _detect_ollama()
    if not model:
        return ""
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 400},
        },
        timeout=60,
    )
    return resp.json().get("response", "")


def _build_data_context() -> str:
    if not CLASSIFIED_PATH.exists():
        return "No classified data available yet."

    with open(CLASSIFIED_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    if total == 0:
        return "Dataset is empty."

    cats = Counter(r.get("category", "") for r in rows)
    tiers = Counter(r.get("tier", "") for r in rows)
    teams = Counter(r.get("team", "") for r in rows)
    stars = Counter(r.get("star_rating", "") for r in rows)
    confs = [float(r["confidence"]) for r in rows if r.get("confidence")]
    avg_conf = sum(confs) / len(confs) if confs else 0

    auto = tiers.get("auto_route", 0)
    flagged = tiers.get("flagged", 0)
    escalate = tiers.get("escalate", 0)

    products = Counter(r.get("product_name", "") for r in rows)

    ctx = """DATASET SUMMARY — SharkNinja Customer Support Tickets
Total tickets: {total}
Source: Amazon product reviews scraped via Selenium

CATEGORY DISTRIBUTION:
{cats}

ROUTING TIERS:
- Auto-routed (confidence >= 65%): {auto} ({auto_pct:.1f}%)
- Flagged (50-64%): {flagged} ({flagged_pct:.1f}%)
- Escalated (< 50%): {escalate} ({esc_pct:.1f}%)

AVERAGE CONFIDENCE: {avg_conf:.1f}%

STAR RATING DISTRIBUTION:
{stars}

TEAM ROUTING:
{teams}

TOP PRODUCTS:
{products}

ML MODELS USED:
- Classification: facebook/bart-large-mnli (zero-shot)
- Text generation: google/flan-t5-base
- Agent reasoning: Ollama Llama (if available) or flan-t5 fallback

SYSTEM NOTES:
- Data scraped from real Amazon reviews for Shark/Ninja products
- Classification uses zero-shot (no fine-tuning, no labeled training data)
- Agent loop: model picks action (classify/draft/escalate/clarify), retries on low confidence
- 74.8% escalation rate due to zero-shot confidence being naturally lower on messy review text""".format(
        total=total,
        cats="\n".join("- {}: {} ({:.1f}%)".format(c, n, 100*n/total) for c, n in cats.most_common()),
        auto=auto, auto_pct=100*auto/total,
        flagged=flagged, flagged_pct=100*flagged/total,
        escalate=escalate, esc_pct=100*escalate/total,
        avg_conf=avg_conf * 100,
        stars="\n".join("- {} star: {}".format(s, n) for s, n in sorted(stars.items())),
        teams="\n".join("- {}: {}".format(t, n) for t, n in teams.most_common()),
        products="\n".join("- {}: {} reviews".format(p, n) for p, n in products.most_common(8)),
    )
    return ctx


SYSTEM_PROMPT = """You are a data analyst assistant for a SharkNinja AI customer support triage system.
You have access to the following dataset information. Answer questions about the data clearly and concisely.
If asked about something not in the data, say so honestly.

{context}

User question: {question}

Answer concisely and specifically using the numbers from the data above:"""

FLAN_PROMPT = """Based on this data summary, answer the question.

{context}

Question: {question}
Answer:"""


def chat(question: str, history: list = None) -> dict:
    context = _build_data_context()

    model_used = "unknown"
    answer = ""

    ollama_model = _detect_ollama()
    if ollama_model:
        prompt = SYSTEM_PROMPT.format(context=context, question=question)
        answer = _ollama_chat(prompt)
        model_used = ollama_model

    if not answer:
        prompt = FLAN_PROMPT.format(
            context=context[:800],
            question=question,
        )
        answer = generate_text(prompt, max_new_tokens=150)
        model_used = "flan-t5-base"

    if not answer.strip():
        answer = "I couldn't generate a response. Try rephrasing your question."

    return {
        "answer": answer.strip(),
        "model": model_used,
    }
