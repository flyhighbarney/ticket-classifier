"""
Core actions — classify tickets and draft customer replies.
"""

from agent.models import get_classifier, get_generator
from agent.schema import (
    TICKET_CATEGORIES,
    CATEGORY_SHORT,
    confidence_tier,
    TEAM_ROUTING,
)


def classify(text: str) -> dict:
    """
    Zero-shot classify text into ticket categories.
    Returns {category, confidence, tier, all_scores}.
    """
    clf = get_classifier()
    result = clf(text, candidate_labels=TICKET_CATEGORIES, multi_label=False)

    raw_label = result["labels"][0]
    category = CATEGORY_SHORT[raw_label]
    confidence = result["scores"][0]

    return {
        "category": category,
        "confidence": round(confidence, 4),
        "tier": confidence_tier(confidence),
        "team": TEAM_ROUTING[category],
        "all_scores": {
            CATEGORY_SHORT[label]: round(score, 4)
            for label, score in zip(result["labels"], result["scores"])
        },
    }


def draft_reply(text: str, category: str) -> str:
    """
    Generate customer-facing reply using flan-t5.
    """
    gen = get_generator()

    prompt = (
        "You are a customer support agent for SharkNinja (Shark vacuums, "
        "Ninja kitchen appliances). Write a helpful, empathetic reply to "
        "this customer message.\n\n"
        "Category: {}\n"
        "Customer message: {}\n\n"
        "Reply:"
    ).format(category, text[:500])

    result = gen(prompt)
    return result[0]["generated_text"].strip()


def process_ticket(text: str) -> dict:
    """
    Full pipeline: classify + draft + route.
    """
    classification = classify(text)

    draft = ""
    if classification["tier"] != "escalate":
        draft = draft_reply(text, classification["category"])

    return {
        **classification,
        "draft_reply": draft,
        "fallback_used": False,
    }
