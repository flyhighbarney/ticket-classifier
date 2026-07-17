"""
Core actions — classify tickets and draft customer replies.
"""

from agent.models import get_classifier, generate_text
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
    # Extract product and issue from text using flan-t5
    product = generate_text(
        "What product is mentioned in this text? Reply with just the product name. "
        "Text: " + text[:300]
    ).strip()
    issue = generate_text(
        "Summarize the customer's problem in one short phrase. "
        "Text: " + text[:300]
    ).strip()

    templates = {
        "warranty_claim": (
            "Thank you for reaching out about your {product}. We're sorry to hear "
            "about {issue}. This may be covered under your SharkNinja warranty. "
            "Please reply with your order number and purchase date so our Warranty "
            "Ops team can look into a replacement for you."
        ),
        "troubleshooting": (
            "We're sorry you're experiencing {issue} with your {product}. "
            "As a first step, please try unplugging the unit for 30 seconds and "
            "checking all connections. If the issue persists, our Tech Support "
            "team is ready to assist — just reply to this message."
        ),
        "product_question": (
            "Great question about the {product}! For detailed specs and "
            "compatibility info, visit sharkninja.com or check the product "
            "listing. Feel free to ask if you have any other questions — "
            "we're happy to help you find the right fit."
        ),
        "return_request": (
            "We're sorry the {product} didn't meet your expectations. "
            "You can initiate a return through the original retailer or at "
            "sharkninja.com/support. If you'd like help with an exchange or "
            "have questions about the process, our Returns team is here for you."
        ),
    }

    template = templates.get(category, templates["troubleshooting"])
    return template.format(product=product or "product", issue=issue or "this issue")


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
