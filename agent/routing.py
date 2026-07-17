"""
Route processed tickets to team output buckets.
Each ticket written as JSON file in output/<team_name>/.
"""

import json
from pathlib import Path

from agent.schema import TEAM_ROUTING

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

TEAM_DIRS = {
    "Warranty Ops": "warranty_ops",
    "Tech Support": "tech_support",
    "Sales": "sales",
    "Returns": "returns",
    "Manual Review": "manual_review",
}


def route_ticket(ticket_id: str, result: dict, original_text: str):
    team = result.get("team", "Manual Review")
    dir_name = TEAM_DIRS.get(team, "manual_review")
    team_dir = OUTPUT_DIR / dir_name
    team_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "ticket_id": ticket_id,
        "original_text": original_text,
        **result,
    }

    out_path = team_dir / "{}.json".format(ticket_id)
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    return str(out_path)


def get_routing_stats(results: list[dict]) -> dict:
    stats = {
        "total": len(results),
        "by_team": {},
        "by_tier": {},
        "by_category": {},
        "fallback_count": 0,
        "avg_confidence": 0.0,
    }

    for r in results:
        team = r.get("team", "Unknown")
        stats["by_team"][team] = stats["by_team"].get(team, 0) + 1

        tier = r.get("tier", "unknown")
        stats["by_tier"][tier] = stats["by_tier"].get(tier, 0) + 1

        cat = r.get("category", "unknown")
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        if r.get("fallback_used"):
            stats["fallback_count"] += 1

    confs = [r["confidence"] for r in results if r.get("confidence")]
    if confs:
        stats["avg_confidence"] = round(sum(confs) / len(confs), 4)

    auto = stats["by_tier"].get("auto_route", 0)
    stats["auto_route_rate"] = round(100 * auto / len(results), 1) if results else 0
    stats["escalation_rate"] = round(
        100 * stats["by_tier"].get("escalate", 0) / len(results), 1
    ) if results else 0

    return stats
