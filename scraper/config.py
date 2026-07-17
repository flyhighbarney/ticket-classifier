"""
Scraper configuration — target products, request settings, output paths.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_HTML_DIR = PROJECT_ROOT / "scraper" / "raw_html"
RAW_CSV_PATH = DATA_DIR / "raw_scraped.csv"

# ── Request settings ───────────────────────────────────────────────────
REQUEST_DELAY = (2.0, 4.0)  # random uniform delay between requests (seconds)
REQUEST_TIMEOUT = 15         # seconds per request
MAX_REVIEW_PAGES = 10        # per product (10 pages × 10 reviews = ~100 reviews)
MAX_QA_PAGES = 5             # per product

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ── Target products ────────────────────────────────────────────────────
# Each entry: (ASIN, product_name, brand, category)
PRODUCTS = [
    # ── Vacuums (kept B07NX8XBMP which worked, replaced 3 dead ASINs) ─
    ("B07NX8XBMP", "Shark Navigator Lift-Away ADV Upright Vacuum", "Shark", "vacuum"),
    ("B005LTJZK4", "Shark Navigator Lift-Away Professional Vacuum NV356E", "Shark", "vacuum"),
    ("B07QXMNF1L", "Shark IZ162H Rocket Pet Pro Cordless Stick Vacuum", "Shark", "vacuum"),
    ("B01IAEQHTE", "Shark Rotator Professional Lift-Away Upright Vacuum NV501", "Shark", "vacuum"),

    # ── Blenders (kept B00939FV8K which worked, replaced 3 dead ASINs) ─
    ("B00939FV8K", "Ninja Professional 72 Oz Countertop Blender", "Ninja", "blender"),
    ("B01MSFTX93", "Ninja Professional Countertop Blender BL610", "Ninja", "blender"),
    ("B015XHKAOQ", "Ninja Mega Kitchen System BL770", "Ninja", "blender"),
    ("B01N7Y0TQ2", "Ninja Professional Blender with Nutri Ninja Cups BL660", "Ninja", "blender"),

    # ── Air Fryers (kept B07FDJMC9Q which worked, replaced 3 dead ASINs)
    ("B07FDJMC9Q", "Ninja Air Fryer AF101", "Ninja", "air_fryer"),
    ("B07S6529VS", "Ninja Foodi Digital Air Fry Oven SP101", "Ninja", "air_fryer"),
    ("B07S85TPLG", "Ninja Foodi 8-Quart Pressure Cooker & Air Fryer FD401", "Ninja", "air_fryer"),
    ("B07PMGSP27", "Ninja Foodi TenderCrisp Pressure Cooker OP301", "Ninja", "air_fryer"),
]

# ── Amazon URL templates ───────────────────────────────────────────────
REVIEW_URL_TEMPLATE = "https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_getr_d_paging_btm_next_{page}?pageNumber={page}&sortBy=recent"
QA_URL_TEMPLATE = "https://www.amazon.com/ask/questions/asin/{asin}/{page}"
PRODUCT_URL_TEMPLATE = "https://www.amazon.com/dp/{asin}"
