import os
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from pymongo import MongoClient

# ---------- خواندن از Secrets ----------
USERNAME = os.environ.get('APPSERO_USER')
PASSWORD = os.environ.get('APPSERO_PASS')
PROJECTS = json.loads(os.environ.get('PROJECTS', '[]'))

MONGODB_URI = os.environ.get('MONGODB_URI')
MONGODB_DB = os.environ.get('MONGODB_DB', 'appsero')
MONGODB_COLLECTION = os.environ.get('MONGODB_COLLECTION', 'emails')

# ---------- اتصال به MongoDB ----------
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
collection = db[MONGODB_COLLECTION]

# ---------- توابع استخراج ----------
def setup_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    service = Service('/usr/bin/chromedriver')
    return webdriver.Chrome(service=service, options=options)

def login(driver):
    driver.get('https://dashboard.appsero.com/login')
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, 'input#email').send_keys(USERNAME)
    driver.find_element(By.CSS_SELECTOR, 'input#password').send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, 'button.appsero__submit_btn').click()
    WebDriverWait(driver, 20).until(EC.url_contains('dashboard.appsero.com'))
    time.sleep(2)

def extract_page(driver, url):
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.ant-table-row')))
    except:
        return []
    time.sleep(1)
    rows = driver.find_elements(By.CSS_SELECTOR, 'tr.ant-table-row')
    emails = []
    for row in rows:
        try:
            email = row.find_element(By.CSS_SELECTOR, 'td.tcol-admin-email').text.strip()
            if email and re.match(r'[^@]+@[^@]+\.[^@]+', email):
                emails.append(email)
        except:
            continue
    return emails

def has_next_page(driver):
    try:
        next_btn = driver.find_element(By.XPATH, "//button[.//span[text()='Next']]")
        return 'ant-btn-disabled' not in next_btn.get_attribute('class')
    except:
        return False

def extract_all_pages(driver, project_url):
    all_emails = []
    page = 1
    while True:
        url = project_url + ('&' if '?' in project_url else '?') + f'page={page}'
        print(f'📄 در حال خواندن صفحه {page}...')
        emails = extract_page(driver, url)
        if not emails:
            break
        all_emails.extend(emails)
        if not has_next_page(driver):
            break
        page += 1
        time.sleep(1)
    return all_emails

def get_existing_emails():
    return set(doc['email'] for doc in collection.find({}, {'email': 1}))

def save_new_emails(new_emails):
    if new_emails:
        docs = [{'email': email} for email in new_emails]
        collection.insert_many(docs)
        print(f'✅ {len(new_emails)} ایمیل جدید ذخیره شد.')
    else:
        print('ℹ️ هیچ ایمیل جدیدی یافت نشد.')

def main():
    if not PROJECTS:
        print('❌ هیچ پروژه‌ای تعریف نشده است.')
        return
    
    driver = setup_driver()
    try:
        login(driver)
        existing = get_existing_emails()
        all_new = set()
        
        for project in PROJECTS:
            print(f'🌐 پردازش پروژه: {project}')
            emails = extract_all_pages(driver, project)
            new_in_project = set(emails) - existing
            if new_in_project:
                print(f'   ➕ {len(new_in_project)} ایمیل جدید در این پروژه')
                all_new.update(new_in_project)
            else:
                print('   ℹ️ هیچ ایمیل جدیدی در این پروژه یافت نشد.')
        
        if all_new:
            save_new_emails(all_new)
        else:
            print('✅ همه ایمیل‌ها قبلاً ذخیره شده‌اند.')
            
    except Exception as e:
        print(f'❌ خطا: {e}')
    finally:
        driver.quit()

if __name__ == '__main__':
    main()
