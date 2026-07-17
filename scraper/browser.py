"""
Selenium browser setup with manual login support.

Launches Edge in visible mode, waits for the user to log in to Amazon,
then continues scraping with the authenticated session.
"""

import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from scraper.config import RAW_HTML_DIR, REQUEST_DELAY

# Persist cookies across runs so you only log in once
PROFILE_DIR = Path(__file__).resolve().parent.parent / ".browser_profile"


def make_driver(headless: bool = False) -> webdriver.Edge:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    # Use a persistent profile so cookies survive between runs
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")

    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    service = Service(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=opts)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    return driver


def wait_for_login(driver: webdriver.Edge):
    """
    Navigate to Amazon and wait for the user to log in.
    Detects login by checking for the nav greeting (\"Hello, Name\").
    """
    driver.get("https://www.amazon.com")
    time.sleep(2)

    # Check if already logged in
    if _is_logged_in(driver):
        print("[OK] Already logged in to Amazon.")
        return

    print()
    print("=" * 60)
    print("  Please log in to Amazon in the browser window.")
    print("  Press ENTER here when you're done.")
    print("=" * 60)
    print()
    input("  Waiting... ")

    if _is_logged_in(driver):
        print("[OK] Login detected. Starting scrape.")
    else:
        print("[WARN] Could not confirm login, but continuing anyway.")


def _is_logged_in(driver: webdriver.Edge) -> bool:
    try:
        page = driver.page_source.lower()
        return "nav-link-accountlist" in page and "sign in" not in driver.find_element(
            "id", "nav-link-accountList"
        ).text.lower()
    except Exception:
        return False


def rate_limit():
    time.sleep(random.uniform(*REQUEST_DELAY))


def save_html(driver, label: str):
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_HTML_DIR / f"{label}.html"
    path.write_text(driver.page_source, encoding="utf-8")
