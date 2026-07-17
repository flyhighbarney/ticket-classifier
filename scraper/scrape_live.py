"""
Live Amazon scraper — opens Edge, waits for you to log in, then scrapes
reviews and Q&A for all configured Shark/Ninja products.

Uses a persistent browser profile so you only need to log in once.
Merges results with the existing HuggingFace dataset if present.

Usage:
    python -m scraper.scrape_live [--reviews-only] [--qa-only] [--products 0,1,2] [--merge]

Flags:
    --reviews-only   Skip Q&A
    --qa-only        Skip reviews
    --products       Comma-separated product indices from config.py (default: all)
    --merge          Merge with existing data/raw_scraped.csv instead of overwriting
    --headless       Run headless (only works if cookies are already saved)
"""

import argparse
import csv
from pathlib import Path

from scraper.browser import make_driver, wait_for_login
from scraper.config import DATA_DIR, PRODUCTS, RAW_CSV_PATH
from scraper.scrape_reviews_sel import scrape_reviews
from scraper.scrape_qa_sel import scrape_qa

CSV_FIELDNAMES = [
    "id", "product_asin", "product_name", "brand", "category",
    "source_type", "text", "star_rating", "date", "verified_purchase",
]


def _deduplicate(records: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for r in records:
        key = (r["product_asin"], r["source_type"], r["text"][:200])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(records: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description="Live Amazon scraper (login required)")
    parser.add_argument("--reviews-only", action="store_true")
    parser.add_argument("--qa-only", action="store_true")
    parser.add_argument("--products", type=str, default=None)
    parser.add_argument("--merge", action="store_true",
                        help="Merge with existing raw_scraped.csv")
    parser.add_argument("--headless", action="store_true",
                        help="Run headless (requires prior login for cookies)")
    args = parser.parse_args()

    # Select products
    if args.products:
        indices = [int(i.strip()) for i in args.products.split(",")]
        products = [PRODUCTS[i] for i in indices]
    else:
        products = PRODUCTS

    print(f"Products: {len(products)}")
    for i, p in enumerate(products):
        print(f"  [{i}] {p[1]} ({p[0]})")

    # Launch browser and log in
    driver = make_driver(headless=args.headless)
    all_records = []

    try:
        if not args.headless:
            wait_for_login(driver)
        else:
            print("[headless] Skipping login — using saved cookies")

        # Scrape
        if not args.qa_only:
            print("\n" + "=" * 60)
            print("SCRAPING REVIEWS")
            print("=" * 60)
            for product in products:
                records = scrape_reviews(driver, product)
                all_records.extend(records)

        if not args.reviews_only:
            print("\n" + "=" * 60)
            print("SCRAPING Q&A")
            print("=" * 60)
            for product in products:
                records = scrape_qa(driver, product)
                all_records.extend(records)

    finally:
        driver.quit()

    # Merge with existing data if requested
    if args.merge:
        existing = _load_existing(RAW_CSV_PATH)
        print(f"\nMerging with {len(existing)} existing records")
        all_records = existing + all_records

    # Deduplicate and write
    before = len(all_records)
    all_records = _deduplicate(all_records)
    after = len(all_records)

    if before != after:
        print(f"Deduplication: {before} -> {after} ({before - after} removed)")

    _write_csv(all_records, RAW_CSV_PATH)

    # Summary
    print("\n" + "=" * 60)
    print("SCRAPE COMPLETE")
    print("=" * 60)
    print(f"Total records: {after}")
    print(f"Output: {RAW_CSV_PATH}")

    reviews = [r for r in all_records if r["source_type"] == "review"]
    qa = [r for r in all_records if r["source_type"] == "qa"]
    print(f"  Reviews: {len(reviews)}")
    print(f"  Q&A:     {len(qa)}")

    for cat in sorted(set(r["category"] for r in all_records)):
        count = len([r for r in all_records if r["category"] == cat])
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
