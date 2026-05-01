import time
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import re

# ─── CONFIG ───────────────────────────────────────────────
# Reads from environment variables (set as GitHub Secrets),
# falls back to hardcoded values for local use.
USER_KEY  = os.environ.get("PUSHOVER_USER_KEY",  "u59n2iudcmwkqau5ihi5xdrxscrw1y")
APP_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN", "avh1sfs8sywhxisar7mxcvku5v9guk")
CHECK_INTERVAL = 5 * 60  # seconds between checks when running locally
# ──────────────────────────────────────────────────────────


def send_pushover(message):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": APP_TOKEN,
            "user": USER_KEY,
            "message": message,
            "title": "ENGR 2302 ALERT"
        }
    )


def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=9222")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def check_seat():
    driver = make_driver()
    wait = WebDriverWait(driver, 30)

    try:
        # 1. Open class search
        driver.get("https://lum010.alamo.edu:8010/StudentRegistrationSsb/ssb/classSearch/classSearch")
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # 2. Click Browse Classes
        browse = wait.until(EC.element_to_be_clickable((By.ID, "classSearchLink")))
        browse.click()
        wait.until(lambda d: "termSelection" in d.current_url)

        # 3. Select term — Summer 2026
        wait.until(EC.presence_of_element_located((By.ID, "select2-drop-mask")))
        wait.until(EC.invisibility_of_element_located((By.ID, "select2-drop-mask")))
        dropdown = driver.find_element(By.ID, "s2id_txt_term")
        driver.execute_script("arguments[0].click();", dropdown)
        time.sleep(1)

        search = driver.find_element(By.CSS_SELECTOR, "input.select2-input")
        search.clear()
        search.send_keys("Summer 2026")
        time.sleep(1)
        search.send_keys(Keys.ENTER)

        time.sleep(2)
        wait.until(EC.invisibility_of_element_located((By.ID, "select2-drop-mask")))

        continue_btn = wait.until(EC.presence_of_element_located((By.ID, "term-go")))
        driver.execute_script("arguments[0].click();", continue_btn)

        # 4. Fill in subject + course number
        time.sleep(2)
        subject_box = driver.find_element(By.ID, "s2id_autogen1")
        subject_box.click()
        time.sleep(0.5)
        subject_box.send_keys("ENGR")
        time.sleep(1)
        subject_box.send_keys(Keys.ENTER)
        time.sleep(1)

        course_box = driver.find_element(By.ID, "txt_courseNumber")
        course_box.clear()
        course_box.send_keys("2302")

        try:
            keyword = driver.find_element(By.ID, "txt_keywordlike")
            keyword.clear()
        except Exception:
            pass

        search_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Search')]")
        driver.execute_script("arguments[0].click();", search_btn)

        # 5. Wait for results and parse seats
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'seats remain')]")))
        time.sleep(2)

        page = driver.page_source
        match_block = re.search(r"(ENGR.*?2302.*?seats remain\.)", page, re.DOTALL)

        if not match_block:
            print("Course not found in page.")
            return

        block = match_block.group(1)
        match = re.search(r"(\d+)\s*of\s*(\d+)\s*seats remain", block)

        if match:
            remaining = int(match.group(1))
            capacity  = int(match.group(2))
            print(f"Remaining: {remaining} / {capacity}")

            if remaining > 0:
                print("🔥 SEAT OPEN — sending notification!")
                send_pushover(f"ENGR 2302 has {remaining} seat(s) open!")
            else:
                print("❌ Full — checking again later.")

    except Exception as e:
        print(f"Error during check: {e}")

    finally:
        driver.quit()


# ─── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    # If running in GitHub Actions (CI env var is always 'true' there),
    # just do one check and exit. Otherwise loop locally.
    in_github = os.environ.get("CI", "false") == "true"

    if in_github:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] GitHub Actions — running single check.")
        check_seat()
    else:
        print("Local mode — looping. Press Ctrl+C to stop.")
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking ENGR 2302...")
            check_seat()
            print(f"Sleeping {CHECK_INTERVAL // 60} minutes...")
            time.sleep(CHECK_INTERVAL)
