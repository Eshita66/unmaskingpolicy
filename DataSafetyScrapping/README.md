# Google Play Data Safety Label Scraping Tool

## Overview
This module collects Google Play Data Safety Label URLs, scrapes data safety label information for each app, and extracts app name and privacy policy link pairs for downstream analysis.

## Step 1: Collect Google Play Data Safety Label URLs
Before running the script, set the required paths in `functions.py`:

- `csv_path`
- `txt_path = "ds_urls.txt"`

Also set:
- `queries = category`

Then run:

```bash
python googleplay_collect_urls.py

### Optional duplicate check
Before starting Step 2, you can check for duplicate data safety URLs using:

```bash
python uniqueappcategory.py

Step 2: Collect Data Safety Labels for Each App

Before running the script, set:

JSON_PATH

CSV_PATH = path to the data safety URL file

python googleplay_scrape_ds.py

Step 3: Collect App Name and Privacy Policy Link Pairs

Before running the script, set the following paths in the script:

DS_URLS_PATH

OUT_PATH

python policyLinkCollection.py