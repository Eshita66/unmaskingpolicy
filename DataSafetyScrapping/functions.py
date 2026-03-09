
import os
import requests
from bs4 import BeautifulSoup
import json
import logging
import csv
import re
from langdetect import detect

def is_english_app_name(name: str) -> bool:
    """
    Very simple filter:
    - Keep names that are mostly ASCII letters (Latin script).
    - Drop names that are mostly non-ASCII (e.g., Bengali, Chinese, Arabic).
    """
    if not name:
        return False

    # Count letters
    ascii_letters = 0
    non_ascii_letters = 0

    for ch in name:
        if ch.isalpha():
            if ord(ch) < 128:
                ascii_letters += 1
            else:
                non_ascii_letters += 1

    total_letters = ascii_letters + non_ascii_letters

    if total_letters == 0:
        return True

    non_ascii_ratio = non_ascii_letters / total_letters
    return non_ascii_ratio < 0.3

def save_as_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)



def extract_app_name_from_soup(soup):
    # 1) Main app page: <h1 class="Fd93Bb">App Name</h1>
    h1 = soup.find('h1', class_='Fd93Bb')
    if h1:
        txt = h1.get_text(strip=True)
        if txt:
            return txt

    # 2) Open Graph meta
    og = soup.find('meta', attrs={'property': 'og:title'})
    if og and og.get('content'):
        return og['content'].strip()

    # 3) Data Safety page title: <div class="ylijCc">App Name</div>
    div = soup.find('div', class_='ylijCc')
    if div:
        txt = div.get_text(strip=True)
        if txt:
            return txt

    # 4) JSON-LD fallback
    ld = soup.find('script', type='application/ld+json')
    if ld and ld.string:
        try:
            data = json.loads(ld.string)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('name'):
                        return item['name'].strip()
            elif isinstance(data, dict) and data.get('name'):
                return data['name'].strip()
        except Exception:
            pass

    return "Unknown"

def scrape_data_safety(app_url):
    """
    :param app_url: Data Safety page URL.
    :return: (data_safety_info: dict, app_title: str)
    """
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36')
    }
    response = requests.get(app_url, headers=headers, timeout=30)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        data_safety_info = {}

        try:
            # DS page app title
            app_title = soup.find('div', class_="ylijCc").get_text(strip=True)
        except AttributeError:
            print(f"Title not found, check if URL is valid:\n{app_url}")
            return None, "Unknown"

        sections = soup.find_all('div', class_='Mf2Txd', jslog=True)
        logging.info(f"Scraping data safety info for: {app_title}")

        for section in sections:
            header = section.find('h2', class_='q1rIdc')
            if not header:
                continue

            section_title = header.get_text(strip=True)  # e.g., Data shared / Data collected
            section_data = {}

            subcategories = section.find_all('div', class_='Vwijed')
            for subcategory in subcategories:
                sub_title_el = subcategory.find('h3', class_='aFEzEb')
                sub_desc_el = subcategory.find('div', class_='fozKzd')
                if not sub_title_el or not sub_desc_el:
                    continue

                subcategory_title = sub_title_el.get_text(strip=True)
                subcategory_description = sub_desc_el.get_text(strip=True)

                section_data[subcategory_title] = subcategory_description

            data_safety_info[section_title] = section_data

        return data_safety_info, app_title

    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return None, "Unknown"


def collect_urls():
    base_url = "https://play.google.com"

    queries = ["camping"]
    # queries = ["Auto and Vehicles", "Books and Reference", "Comics", "Communications", "Finance", "Health and Fitness", "House and Home", "Libraries and Demo", "Lifestyle", "Maps and Navigation",
    #     "Medical", "Music and Audio", "News and Magazines", "Personalization", "Travel and Local", "Video Players and Editors", "Weather", "productivity tools", "education technology", 
    #     "virtual reality", "augmented reality", "simulation", "puzzle", "strategy", 
    #     "arcade", "role playing", "casual", "board games", "card games", "music games", "sports games", "casino", "word games",
    #     "idle games", "finance management", "insurance", "real estate", "social impact", "green living", "smart home", "AI assistant", "developer tools", "wearables", "automotive", 
    #     "government", "public services", "transportation", "utilities", "cloud storage", "backup", "file management", "remote desktop", "device cleaner", "battery saver", "emulator", "terminal", "scanner", "barcode", "translation",
    #     "voice assistant", "virtual pet", "kids education", "language learning", "STEM learning", "career", "finance education", 
    #     "productivity planner", "habit tracking", "goal setting", "time management", "finance tracker", 
    #     "budget planner", "crypto wallet", "NFT", "metaverse", "smartwatch", "IoT control", "fitness tracker", "sleep tracker", "mental health", "meditation guide", "volunteering", "eco apps", "quiz", "trivia", "VR experiences", 
    #     "AI photo editor", "AI art generator", "voice changer", "podcast", "live streaming", "radio", "document scanner", "PDF tools", "note taking", "to-do list", "password manager", "finance calculator", "flight booking", "hotel booking",
    #     "translation tools", "virtual tours", "offline maps", "camping", "navigation aid", "transport tracking"]


    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36')
    }

    # De-dupe app pages per run
    seen_app_pages = set()

    csv_path = r"G:\ZDataSafetylabelScript\data\ds_urls_by_category.csv"
    txt_path = r"G:\ZDataSafetylabelScript\data\Recent_ds_urls.txt"

    # Load existing DS URLs from txt file
    
    existing_ds_urls = set()
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url:
                    existing_ds_urls.add(url)

    # This set will contain BOTH old + new URLs
    seen_ds_urls = set(existing_ds_urls)

    # Check if CSV already exists (for header)
    csv_exists = os.path.exists(csv_path)

    # CSV: APPEND each run (no overwrite)
    with open(csv_path, "a", newline="", encoding="utf-8") as csvfile, \
         open(txt_path, "a", encoding="utf-8") as ds_page:

        writer = csv.writer(csvfile)

        # Write header only if file is new or empty
        if (not csv_exists) or os.stat(csv_path).st_size == 0:
            writer.writerow(["category", "app_name", "ds_url"])

        for term in queries:
            logging.info(f"Collecting apps for query: {term}")
            try:
                response = requests.get(
                    f"{base_url}/store/search?q={term}&c=apps",
                    headers=headers,
                    timeout=30
                )
            except Exception as e:
                logging.warning(f"Search request failed for '{term}': {e}")
                continue

            if response.status_code != 200:
                logging.warning(
                    f"Search failed for query={term} (status={response.status_code})"
                )
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            app_links = soup.find_all('a', class_='Si6A0c Gy4nib')

            print(f"[DEBUG] Query '{term}' → found {len(app_links)} app links")

            for a in app_links:
                app_url = f"{base_url}{a.get('href')}"
                if app_url in seen_app_pages:
                    continue
                seen_app_pages.add(app_url)

                try:
                    response2 = requests.get(app_url, headers=headers, timeout=30)
                except Exception as e:
                    logging.debug(f"App page request failed: {app_url} ({e})")
                    continue

                if response2.status_code != 200:
                    logging.debug(
                        f"App page fetch failed ({response2.status_code}): {app_url}"
                    )
                    continue

                soup2 = BeautifulSoup(response2.content, 'html.parser')

                # Data Safety link on the app page
                ds_link_el = soup2.find('a', class_="WpHeLc VfPpkd-mRLv6")
                if not ds_link_el or not ds_link_el.get('href'):
                    continue

                ds_url = f"{base_url}{ds_link_el.get('href')}"

               
                if ds_url in seen_ds_urls:
                    # already in txt or seen this run → skip
                    continue
                seen_ds_urls.add(ds_url)

                app_name = extract_app_name_from_soup(soup2)
                ds_page.write(f"{ds_url}\n")

                # Append new row to CSV
                writer.writerow([term, app_name, ds_url])
                logging.info(f"[{term}] {app_name} → {ds_url}")
def get_link(url):
    """
    :param url: data safety page URL
    :return: (policy_link, app_title)
    """
    headers = {'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/91.0.4472.124 Safari/537.36')}

    res = requests.get(url, headers=headers, timeout=30)

    link = None
    app_title = "Unknown"

    if res.status_code == 200:
        soup = BeautifulSoup(res.content, 'html.parser')
        # App name from DS page
        title_div = soup.find('div', class_="ylijCc")
        if title_div:
            app_title = title_div.get_text(strip=True)

        policy = soup.find_all('a', class_='GO2pB')

        if len(policy) > 1:
            link = policy[1].get('href')
        else:
            link = f"no policy found for: {url}"

    return link, app_title
