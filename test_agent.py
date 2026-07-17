"""
Test agent loop on sample tickets.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.loop import process_ticket_agent
from agent.routing import route_ticket, get_routing_stats


def main():
    data_path = Path(__file__).resolve().parent / "data" / "raw_scraped.csv"
    with open(data_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Pick diverse samples: mix of star ratings
    samples = []
    for star in ["1", "2", "3", "4", "5"]:
        star_rows = [r for r in rows if r["star_rating"] == star]
        samples.extend(star_rows[:2])

    print("Testing agent on {} samples\n".format(len(samples)))

    results = []
    for i, row in enumerate(samples):
        text = row["text"]
        ticket_id = "SN-{:04d}".format(i + 1)

        print("--- {} ---".format(ticket_id))
        print("  Text: {}...".format(text[:80]))

        result = process_ticket_agent(text)
        results.append(result)

        print("  Category: {} ({:.1f}% conf)".format(
            result["category"], result["confidence"] * 100))
        print("  Tier: {} | Team: {}".format(result["tier"], result["team"]))
        print("  Fallback: {}".format(result["fallback_used"]))
        print("  Time: {}s".format(result.get("processing_time", "?")))

        if result["draft_reply"]:
            print("  Draft: {}...".format(result["draft_reply"][:80]))

        trace = result.get("agent_trace", [])
        print("  Trace: {}".format(json.dumps(trace, default=str)[:120]))

        # Route
        path = route_ticket(ticket_id, result, text)
        print("  Routed to: {}".format(path))
        print()

    # Stats
    stats = get_routing_stats(results)
    print("\n=== Routing Stats ===")
    print("  Total: {}".format(stats["total"]))
    print("  Auto-route rate: {}%".format(stats["auto_route_rate"]))
    print("  Escalation rate: {}%".format(stats["escalation_rate"]))
    print("  Fallback count: {}".format(stats["fallback_count"]))
    print("  Avg confidence: {}".format(stats["avg_confidence"]))
    print("\n  By team:")
    for team, count in stats["by_team"].items():
        print("    {}: {}".format(team, count))
    print("\n  By category:")
    for cat, count in stats["by_category"].items():
        print("    {}: {}".format(cat, count))


if __name__ == "__main__":
    main()
