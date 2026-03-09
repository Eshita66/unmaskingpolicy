

# gp_policy_scraper_selenium.py  (dedupe-safe)
import sys
from pathlib import Path
from time import sleep
from urllib.parse import urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


DS_URLS_PATH = Path(r"\Recent_ds_urls.txt")
OUT_PATH     = Path("privacy_policy_links_test.txt")


# ------- Helpers -------
def play_id_from_ds_url(u: str):
    """Extract ?id=... from a Play Data Safety URL."""
    try:
        return parse_qs(urlparse(u).query).get("id", [None])[0]
    except Exception:
        return None

def load_existing_pairs(path: Path):
    """
    Load existing (title, link) pairs from OUT_PATH written as:
      title\n
      link\n
    Returns a set of normalized pairs to skip duplicates on reruns.
    """
    seen = set()
    if not path.exists():
        return seen
    try:
        lines = [ln.rstrip("\n") for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
        # The file is title/link pairs; iterate in steps of 2
        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                title = lines[i].strip()
                link  = lines[i + 1].strip()
                seen.add((title.casefold(), link))
    except Exception:
        pass
    return seen


# ------- Selenium setup -------
def build_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        # Use new headless for Chrome 109+
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=en-US")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def get_policy_link_from_ds_page(driver: webdriver.Chrome, ds_url: str, timeout: int = 15):
    """
    Navigate to a Google Play Data Safety page URL and extract:
      - app title (div.ylijCc)
      - privacy policy link (2nd 'a.GO2pB' if present), else fallback text
    Returns: (title, link_str)
    """
    driver.get(ds_url)

    wait = WebDriverWait(driver, timeout)

    # Wait for the app title container on the DS page
    try:
        title_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.ylijCc")))
        app_title = title_el.text.strip()
    except Exception:
        app_title = "Unknown"

    # Find policy anchors; Play typically shows 2 items in that section, the second is the policy URL
    link_elems = driver.find_elements(By.CSS_SELECTOR, "a.GO2pB")
    policy_link = None
    if len(link_elems) > 1:
        try:
            policy_link = link_elems[1].get_attribute("href")
        except Exception:
            policy_link = None

    if not policy_link:
        policy_link = f"no policy found for: {ds_url}"

    return app_title, policy_link


def main():
    if not DS_URLS_PATH.exists():
        print(f"Input file not found: {DS_URLS_PATH}")
        sys.exit(1)

    # Dedupers
    seen_ds_urls = set()            # per-run DS URL dedupe
    seen_app_ids = set()            # per-run Play app id dedupe
    seen_title_link = load_existing_pairs(OUT_PATH)  # cross-run title+link dedupe

    driver = build_driver(headless=True)
    processed = 0
    skipped = 0
    errors = 0

    try:
        with OUT_PATH.open("a", encoding="utf-8") as out_fp:
            with DS_URLS_PATH.open("r", encoding="utf-8") as in_fp:
                for raw in in_fp:
                    ds_url = raw.strip()
                    if not ds_url:
                        continue

                    # Per-run DS URL dedupe
                    if ds_url in seen_ds_urls:
                        print(f"[SKIP] Duplicate DS URL this run: {ds_url}")
                        skipped += 1
                        continue
                    seen_ds_urls.add(ds_url)

                    
                    app_id = play_id_from_ds_url(ds_url)
                    if app_id:
                        if app_id in seen_app_ids:
                            print(f"[SKIP] Duplicate app id this run: {app_id} ({ds_url})")
                            skipped += 1
                            continue
                        seen_app_ids.add(app_id)

                    try:
                        print(f"[INFO] Processing DS URL: {ds_url}")
                        title, link = get_policy_link_from_ds_page(driver, ds_url, timeout=20)

                        # Cross-run dedupe by (title, link)
                        pair_key = (title.strip().casefold(), link.strip())
                        if pair_key in seen_title_link:
                            print(f"[SKIP] Already stored pair: {title} -> {link}")
                            skipped += 1
                            continue
                        seen_title_link.add(pair_key)

                        # === DO NOT CHANGE STORAGE FORMAT ===
                        out_fp.write(f"{title}\n{link}\n")
                        out_fp.flush()

                        print(f"[OK] Stored: {title} -> {link}")
                        processed += 1

                        # gentle pacing to avoid rate limits
                        sleep(0.3)

                    except Exception as e:
                        print(f"[ERR] Failed on {ds_url}: {e}")
                        errors += 1
                        continue

        print(f"\nDone. Processed: {processed}, Skipped: {skipped}, Errors: {errors}. Output: {OUT_PATH.resolve()}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
