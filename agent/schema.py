"""
Ticket categories, confidence thresholds, and routing map.
"""

# Labels sent to BART zero-shot — phrased as specific intents, not generic topics.
# "product question" was too broad and absorbed everything; these are tighter.
TICKET_CATEGORIES = [
    "warranty claim or defective product",
    "technical troubleshooting or product not working",
    "pre-purchase question about product features or compatibility",
    "return or refund request",
]

# Short names for display and routing
CATEGORY_SHORT = {
    "warranty claim or defective product": "warranty_claim",
    "technical troubleshooting or product not working": "troubleshooting",
    "pre-purchase question about product features or compatibility": "product_question",
    "return or refund request": "return_request",
}

CONFIDENCE_THRESHOLDS = {
    "auto_route": 0.65,
    "flagged": 0.50,
}

def confidence_tier(score: float) -> str:
    if score >= CONFIDENCE_THRESHOLDS["auto_route"]:
        return "auto_route"
    if score >= CONFIDENCE_THRESHOLDS["flagged"]:
        return "flagged"
    return "escalate"

TEAM_ROUTING = {
    "warranty_claim": "Warranty Ops",
    "troubleshooting": "Tech Support",
    "product_question": "Sales",
    "return_request": "Returns",
}

AGENT_ACTIONS = ["classify", "draft", "escalate", "clarify"]

AGENT_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": AGENT_ACTIONS},
        "reasoning": {"type": "string"},
    },
    "required": ["action"],
}
