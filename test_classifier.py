"""
Test zero-shot classifier on full scraped dataset.
Prints category distribution, confidence stats, and sample results.
"""

import csv
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.actions import classify, draft_reply


def main():
    data_path = Path(__file__).resolve().parent / "data" / "raw_scraped.csv"
    with open(data_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print("Records:", len(rows))
    print()

    results = []
    start = time.time()

    for i, row in enumerate(rows):
        result = classify(row["text"])
        result["original_text"] = row["text"][:120]
        result["star_rating"] = row["star_rating"]
        result["product_category"] = row["category"]
        results.append(result)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print("  {}/{} done ({:.1f}/sec)".format(i + 1, len(rows), rate))

    elapsed = time.time() - start
    print("\nClassified {} records in {:.1f}s ({:.1f}/sec)".format(
        len(rows), elapsed, len(rows) / elapsed))

    # Category distribution
    print("\n=== Category Distribution ===")
    cats = Counter(r["category"] for r in results)
    for cat, count in cats.most_common():
        pct = 100 * count / len(results)
        print("  {}: {} ({:.1f}%)".format(cat, count, pct))

    # Confidence tiers
    print("\n=== Confidence Tiers ===")
    tiers = Counter(r["tier"] for r in results)
    for tier in ["auto_route", "flagged", "escalate"]:
        count = tiers.get(tier, 0)
        pct = 100 * count / len(results)
        print("  {}: {} ({:.1f}%)".format(tier, count, pct))

    # Confidence stats per category
    print("\n=== Avg Confidence by Category ===")
    for cat in cats:
        scores = [r["confidence"] for r in results if r["category"] == cat]
        avg = sum(scores) / len(scores)
        low = min(scores)
        high = max(scores)
        print("  {}: avg={:.3f} min={:.3f} max={:.3f}".format(cat, avg, low, high))

    # Cross-tab: star rating vs ticket category
    print("\n=== Star Rating vs Ticket Category ===")
    print("  {:>6s}  {:>12s}  {:>15s}  {:>16s}  {:>14s}".format(
        "Stars", "warranty", "troubleshoot", "product_q", "return"))
    for star in ["1", "2", "3", "4", "5"]:
        row_results = [r for r in results if r["star_rating"] == star]
        if not row_results:
            continue
        counts = Counter(r["category"] for r in row_results)
        print("  {:>6s}  {:>12d}  {:>15d}  {:>16d}  {:>14d}".format(
            star,
            counts.get("warranty_claim", 0),
            counts.get("troubleshooting", 0),
            counts.get("product_question", 0),
            counts.get("return_request", 0),
        ))

    # Sample results per category
    print("\n=== Samples (3 per category) ===")
    for cat in cats:
        print("\n--- {} ---".format(cat))
        samples = [r for r in results if r["category"] == cat][:3]
        for s in samples:
            print("  [{:.3f}] [{}*] {}...".format(
                s["confidence"], s["star_rating"], s["original_text"][:100]))

    # Draft reply on a few examples
    print("\n=== Sample Draft Replies ===")
    test_texts = [
        r for r in results
        if r["tier"] == "auto_route"
    ][:3]
    for r in test_texts:
        text = r["original_text"]
        cat = r["category"]
        print("\n  Input [{}]: {}...".format(cat, text[:80]))
        reply = draft_reply(text, cat)
        print("  Reply: {}".format(reply[:200]))

    # Save results
    out_path = Path(__file__).resolve().parent / "data" / "classified_results.csv"
    fieldnames = ["category", "confidence", "tier", "team",
                  "original_text", "star_rating", "product_category"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print("\nResults saved to", out_path)


if __name__ == "__main__":
    main()
