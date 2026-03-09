
import logging
import os
import json
import csv
import functions

# Paths
JSON_PATH = r"\data_safety_data.json"
CSV_PATH = r"\ds_urls_by_category.csv"

# Logging for scraping
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_progress.log", encoding="utf-8")
    ]
)


def main():
    print("Starting scraping from existing URLs...")

    # 1) Load existing JSON if present, so we don't rescrape those apps
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as jf:
                all_apps_data = json.load(jf)
            if not isinstance(all_apps_data, dict):
                logging.warning("Existing JSON is not a dict, starting fresh.")
                all_apps_data = {}
        except Exception as e:
            logging.warning(f"Failed to load existing JSON ({JSON_PATH}): {e}")
            all_apps_data = {}
    else:
        all_apps_data = {}

    # Set of already-scraped app IDs/names
    existing_apps = set(all_apps_data.keys())
    logging.info(f"Loaded {len(existing_apps)} apps from existing JSON")

    # 2) Read the CSV with (category, app_name, ds_url)
    try:
        with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                app_name = row["app_name"]
                ds_url = row["ds_url"]

                # Skip if we've already scraped this app
                if app_name in existing_apps:
                    logging.info(f"Skipping already-scraped app: {app_name}")
                    continue

                logging.info(f"Processing {app_name} → {ds_url}")
                data_safety, scraped_name = functions.scrape_data_safety(ds_url)
                logging.info(f"Finished scraping for {scraped_name}")

                # Choose a key for JSON (prefer scraped_name if valid)
                key = scraped_name if scraped_name and scraped_name != "Unknown" else app_name

                all_apps_data[key] = data_safety
                existing_apps.add(key)

    except FileNotFoundError:
        logging.error(f"CSV not found: {CSV_PATH}")
        print(f"CSV not found: {CSV_PATH}")
        return

    # 3) Save the combined data to a JSON file (incremental)
    functions.save_as_json(all_apps_data, JSON_PATH)
    logging.info(f"Data saved to {JSON_PATH}")
    print(f"Data saved to {JSON_PATH}")


if __name__ == "__main__":
    main()

