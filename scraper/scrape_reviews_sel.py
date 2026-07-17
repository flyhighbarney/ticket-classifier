"""
Selenium-based Amazon review scraper (requires logged-in session).

Navigates to the product page first to discover the correct "See all reviews"
link, then paginates through reviews. This avoids 404s from ASINs that use
non-standard review URL structures.
"""

import uuid

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.browser import rate_limit, save_html
from scraper.config import MAX_REVIEW_PAGES, PRODUCT_URL_TEMPLATE, REVIEW_URL_TEMPLATE


def _find_review_base_url(driver, asin: str) -> str | None:
    """
    Visit the product page and find the "See all reviews" link.
    Returns the base review URL, or None if not found.
    """
    rate_limit()
    driver.get(PRODUCT_URL_TEMPLATE.format(asin=asin))
    save_html(driver, f"product_{asin}")

    if "Page Not Found" in driver.title or "404" in driver.title:
        return None

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#dp"))
        )
    except Exception:
        pass

    # Look for "See all reviews" or "See customer reviews" link
    for selector in [
        'a[data-hook="see-all-reviews-link-foot"]',
        '#reviews-medley-footer a',
        'a[href*="product-reviews"]',
        'a[href*="customerReviews"]',
    ]:
        try:
            link = driver.find_element(By.CSS_SELECTOR, selector)
            href = link.get_attribute("href")
            if href and ("product-reviews" in href or "customerReviews" in href):
                # Extract the base URL up to the ASIN part
                return href.split("?")[0].split("/ref=")[0]
        except Exception:
            continue

    return None


def _parse_reviews(driver, product: tuple) -> list[dict]:
    asin, product_name, brand, category = product
    records = []

    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]'))
        )
    except Exception:
        return records

    for el in driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]'):
        try:
            # Star rating
            star_rating = None
            try:
                star_el = el.find_element(
                    By.CSS_SELECTOR,
                    '[data-hook="review-star-rating"] .a-icon-alt, '
                    '[data-hook="cmps-review-star-rating"] .a-icon-alt'
                )
                star_text = star_el.get_attribute("textContent") or ""
                star_rating = int(float(star_text.strip().split(" ")[0]))
            except Exception:
                pass

            # Body
            text = None
            for sel in ['[data-hook="review-body"] span', '.review-text-content span']:
                try:
                    text = el.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if text:
                        break
                except Exception:
                    pass
            if not text or len(text) < 5:
                continue

            # Title
            title = None
            try:
                title_el = el.find_element(
                    By.CSS_SELECTOR,
                    '[data-hook="review-title"] span:not(.a-letter-space)'
                )
                title = title_el.text.strip()
            except Exception:
                pass

            full_text = f"{title} - {text}" if title else text

            # Date
            date_text = None
            try:
                date_text = el.find_element(
                    By.CSS_SELECTOR, '[data-hook="review-date"]'
                ).text.strip()
            except Exception:
                pass

            # Verified
            verified = False
            try:
                el.find_element(By.CSS_SELECTOR, '[data-hook="avp-badge"]')
                verified = True
            except Exception:
                pass

            records.append({
                "id": str(uuid.uuid4()),
                "product_asin": asin,
                "product_name": product_name,
                "brand": brand,
                "category": category,
                "source_type": "review",
                "text": full_text,
                "star_rating": star_rating,
                "date": date_text,
                "verified_purchase": verified,
            })
        except Exception:
            continue

    return records


def scrape_reviews(driver, product: tuple) -> list[dict]:
    asin, product_name, *_ = product
    all_records = []
    print(f"\n[REVIEWS] {product_name} ({asin})")

    # Step 1: discover the correct review URL from the product page
    review_base = _find_review_base_url(driver, asin)
    if review_base:
        print(f"  Found review link: {review_base}")
    else:
        print(f"  No review link found on product page, using template URL")
        review_base = None

    for page in range(1, MAX_REVIEW_PAGES + 1):
        if review_base:
            url = f"{review_base}?pageNumber={page}&sortBy=recent"
        else:
            url = REVIEW_URL_TEMPLATE.format(asin=asin, page=page)

        rate_limit()
        driver.get(url)
        save_html(driver, f"review_{asin}_p{page}")

        if "ap/signin" in driver.current_url or "validateCaptcha" in driver.current_url:
            print(f"  Page {page}: session expired or captcha, stopping")
            break

        if "Page Not Found" in driver.title:
            print(f"  Page {page}: 404, stopping")
            break

        records = _parse_reviews(driver, product)
        print(f"  Page {page}: {len(records)} reviews")

        if not records:
            break

        all_records.extend(records)

    print(f"  Total: {len(all_records)} reviews")
    return all_records
