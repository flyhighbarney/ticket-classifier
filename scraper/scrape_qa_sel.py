"""
Selenium-based Amazon Q&A scraper (requires logged-in session).
"""

import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.browser import rate_limit, save_html
from scraper.config import MAX_QA_PAGES, QA_URL_TEMPLATE


def _parse_qa(driver, product: tuple) -> list[dict]:
    asin, product_name, brand, category = product
    records = []
    seen = set()

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".a-section"))
        )
    except Exception:
        return records

    import time
    time.sleep(1.5)

    # Try structured Q&A containers
    containers = driver.find_elements(
        By.CSS_SELECTOR,
        'div.a-fixed-left-grid-inner, div[id^="question-"], div.askInlineWidget'
    )

    for el in containers:
        try:
            text = el.text.strip()
            if len(text) < 15 or text in seen:
                continue
            lower = text.lower()
            if any(skip in lower for skip in [
                "sign in", "add to cart", "see all answers",
                "next page", "customer review", "report",
                "showing", "sort by"
            ]):
                continue

            seen.add(text)
            records.append({
                "id": str(uuid.uuid4()),
                "product_asin": asin,
                "product_name": product_name,
                "brand": brand,
                "category": category,
                "source_type": "qa",
                "text": text,
                "star_rating": None,
                "date": None,
                "verified_purchase": None,
            })
        except Exception:
            continue

    # Fallback: question-like text
    if not records:
        for el in driver.find_elements(By.CSS_SELECTOR, "span, a, div.a-size-base"):
            try:
                text = el.text.strip()
                if len(text) < 15 or len(text) > 500 or text in seen:
                    continue
                if "?" not in text and not any(
                    text.lower().startswith(p)
                    for p in ["does ", "can ", "will ", "is ", "how ", "what ", "do ", "are "]
                ):
                    continue
                lower = text.lower()
                if any(skip in lower for skip in ["sign in", "add to cart", "customer reviews"]):
                    continue

                seen.add(text)
                records.append({
                    "id": str(uuid.uuid4()),
                    "product_asin": asin,
                    "product_name": product_name,
                    "brand": brand,
                    "category": category,
                    "source_type": "qa",
                    "text": text,
                    "star_rating": None,
                    "date": None,
                    "verified_purchase": None,
                })
            except Exception:
                continue

    return records


def scrape_qa(driver, product: tuple) -> list[dict]:
    asin, product_name, *_ = product
    all_records = []
    print(f"\n[Q&A] {product_name} ({asin})")

    for page in range(1, MAX_QA_PAGES + 1):
        url = QA_URL_TEMPLATE.format(asin=asin, page=page)
        rate_limit()
        driver.get(url)
        save_html(driver, f"qa_{asin}_p{page}")

        if "ap/signin" in driver.current_url or "validateCaptcha" in driver.current_url:
            print(f"  Page {page}: session expired or captcha, stopping")
            break

        records = _parse_qa(driver, product)
        print(f"  Page {page}: {len(records)} entries")

        if not records:
            break

        all_records.extend(records)

    print(f"  Total: {len(all_records)} Q&A entries")
    return all_records
