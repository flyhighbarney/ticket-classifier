"""
Dataset builder for SharkNinja ticket classifier.

Pulls real Amazon appliance reviews from HuggingFace (McAuley Lab dataset
via debolut/amazon-reviews-2023-sampled-appliances), filters for home
appliances similar to Shark/Ninja product lines (vacuums, blenders, air
fryers, coffee makers), and maps them into the support ticket schema.

This is REAL customer text — messy, unstructured, authentic — reshaped into
the ticket classifier's format. No synthetic generation.

Usage:
    python -m scraper.scrape_amazon [--limit 1000] [--shark-only]

The Amazon review text is naturally messy:
  - Typos, abbreviations, slang
  - Missing punctuation, run-on sentences
  - Mixed product references
  - Variable length (3 words to 3 paragraphs)
"""

import argparse
import csv
import re
import uuid
from pathlib import Path

from datasets import load_dataset

from scraper.config import DATA_DIR, RAW_CSV_PATH

CSV_FIELDNAMES = [
    "id", "product_asin", "product_name", "brand", "category",
    "source_type", "text", "star_rating", "date", "verified_purchase",
]

# Keywords for filtering to SharkNinja-relevant product categories
CATEGORY_KEYWORDS = {
    "vacuum": [
        "vacuum", "vac ", "hoover", "sweeper", "carpet cleaner",
        "dust buster", "dustbuster", "roomba", "mop", "floor cleaner",
    ],
    "blender": [
        "blender", "smoothie", "food processor", "chopper", "mixer",
        "nutribullet", "vitamix", "immersion", "puree",
    ],
    "air_fryer": [
        "air fryer", "airfryer", "air fry", "toaster oven",
        "convection", "pressure cooker", "instant pot", "multicooker",
    ],
    "coffee_maker": [
        "coffee", "espresso", "keurig", "k-cup", "brew", "latte",
        "cappuccino", "grinder", "drip maker",
    ],
}

SHARK_NINJA_KEYWORDS = ["shark", "ninja", "sharkninja"]

# Map generic brands to SharkNinja equivalents for realism
PRODUCT_MAPPING = {
    "vacuum": [
        "Shark Navigator Lift-Away Upright Vacuum",
        "Shark Vertex Pro Powered Lift-Away Vacuum",
        "Shark Cordless Pro Stick Vacuum",
        "Shark Rotator Lift-Away Upright Vacuum",
        "Shark Robot Vacuum",
    ],
    "blender": [
        "Ninja Professional 72 Oz Countertop Blender",
        "Ninja Detect Duo Power Blender Pro",
        "Ninja Foodi Power Nutri DUO Blender",
        "Ninja Professional Countertop Blender BL610",
    ],
    "air_fryer": [
        "Ninja Air Fryer AF101",
        "Ninja Foodi DualZone Air Fryer DZ201",
        "Ninja Combi All-in-One Multicooker",
        "Ninja Foodi DualZone FlexBasket Air Fryer",
    ],
    "coffee_maker": [
        "Ninja DualBrew Coffee Maker",
        "Ninja Specialty Coffee Maker",
        "Ninja Hot & Cold Brewed System",
    ],
}


def _classify_category(title: str, description: str, categories: str) -> str | None:
    """Determine product category from title/description/categories."""
    combined = f"{title} {description} {categories}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return category
    return None


def _is_shark_ninja(title: str, brand: str) -> bool:
    combined = f"{title} {brand}".lower()
    return any(kw in combined for kw in SHARK_NINJA_KEYWORDS)


def _map_product_name(category: str, index: int) -> tuple[str, str]:
    """Map to a SharkNinja product name. Returns (product_name, brand)."""
    products = PRODUCT_MAPPING.get(category, PRODUCT_MAPPING["vacuum"])
    product = products[index % len(products)]
    brand = "Shark" if "shark" in product.lower() else "Ninja"
    return product, brand


def _build_ticket_text(row: dict) -> str:
    """Combine review title + body into raw ticket text. Keep it messy."""
    title = (row.get("review_title") or "").strip()
    body = (row.get("review_text") or "").strip()

    if title and body:
        return f"{title} - {body}"
    return body or title


def _parse_timestamp(ts: str) -> str | None:
    """Convert millisecond timestamp to date string."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Build ticket dataset from Amazon reviews")
    parser.add_argument("--limit", type=int, default=1000,
                        help="Max records to collect (default: 1000)")
    parser.add_argument("--shark-only", action="store_true",
                        help="Only include actual Shark/Ninja products (much smaller)")
    parser.add_argument("--max-per-category", type=int, default=None,
                        help="Max records per category for balancing (default: limit/num_categories)")
    args = parser.parse_args()

    num_categories = len(CATEGORY_KEYWORDS)
    max_per_cat = args.max_per_category or (args.limit // num_categories + 50)

    print("Loading Amazon appliance reviews from HuggingFace...")
    print("Dataset: debolut/amazon-reviews-2023-sampled-appliances")
    ds = load_dataset(
        "debolut/amazon-reviews-2023-sampled-appliances",
        split="train",
        streaming=True,
    )

    records = []
    scanned = 0
    skipped_no_text = 0
    skipped_no_category = 0
    skipped_too_short = 0
    category_counts = {cat: 0 for cat in CATEGORY_KEYWORDS}
    product_counter = {cat: 0 for cat in CATEGORY_KEYWORDS}

    print(f"Target: {args.limit} records")
    print(f"Shark-only mode: {args.shark_only}")
    print()

    for row in ds:
        scanned += 1

        if len(records) >= args.limit:
            break

        # Extract fields
        title = row.get("product_title") or ""
        description = row.get("product_description") or ""
        categories = row.get("product_categories") or ""
        brand = row.get("product_brand") or ""
        review_text = _build_ticket_text(row)

        if not review_text or len(review_text.strip()) < 10:
            skipped_too_short += 1
            continue

        # Filter: shark-only mode
        if args.shark_only and not _is_shark_ninja(title, brand):
            continue

        # Classify into our categories
        category = _classify_category(title, description, categories)
        if not category:
            skipped_no_category += 1
            continue

        # Balance categories
        if category_counts[category] >= max_per_cat:
            continue

        # Map to SharkNinja product
        if _is_shark_ninja(title, brand):
            product_name = title[:100]
            mapped_brand = "Shark" if "shark" in title.lower() else "Ninja"
        else:
            product_counter[category] += 1
            product_name, mapped_brand = _map_product_name(
                category, product_counter[category]
            )

        # Parse metadata
        star_rating = None
        try:
            star_rating = int(float(row.get("rating", 0)))
        except (ValueError, TypeError):
            pass

        date = _parse_timestamp(row.get("timestamp", ""))
        verified = str(row.get("verified_purchase", "")).lower() == "true"

        records.append({
            "id": str(uuid.uuid4()),
            "product_asin": row.get("parent_asin", ""),
            "product_name": product_name,
            "brand": mapped_brand,
            "category": category,
            "source_type": "review",
            "text": review_text,
            "star_rating": star_rating,
            "date": date,
            "verified_purchase": verified,
        })

        category_counts[category] += 1

        if scanned % 5000 == 0:
            print(f"  Scanned {scanned}, collected {len(records)}...")

    # ── Write output ───────────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DATASET BUILD COMPLETE")
    print("=" * 60)
    print(f"Scanned:  {scanned} Amazon reviews")
    print(f"Skipped:  {skipped_too_short} too short, {skipped_no_category} no matching category")
    print(f"Collected: {len(records)} records")
    print(f"Output:   {RAW_CSV_PATH}")
    print()
    print("Category breakdown:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = (count / len(records) * 100) if records else 0
        print(f"  {cat}: {count} ({pct:.1f}%)")

    # Show star rating distribution
    ratings = [r["star_rating"] for r in records if r["star_rating"]]
    if ratings:
        print("\nStar rating distribution:")
        for star in range(1, 6):
            count = ratings.count(star)
            pct = count / len(ratings) * 100
            print(f"  {star}*: {count} ({pct:.1f}%)")

    # Show sample texts
    print("\nSample records:")
    import random
    samples = random.sample(records, min(5, len(records)))
    for s in samples:
        print(f"  [{s['star_rating']}*] [{s['category']}] {s['text'][:100]}...")


if __name__ == "__main__":
    main()
