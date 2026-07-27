"""
app.py
Production automation orchestrator with mode selection.
"""
import csv
import time
import random
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "turnstile-solver"))
from solver import Solver
from anti_fingerprint import get_stealth_chrome_options

# ==============================================================================
# KONFIGURASI
# ==============================================================================
TARGET_URL = "https://erpskrip.id/kontak"
CSV_FILE = "test_data.csv"

# Execution mode: "gui" (Windows/Mac), "xvfb" (Linux headless with virtual display), "headless" (fallback)
EXECUTION_MODE = "gui"  # Change based on your environment

SELECTORS = {
    "name": "input[name='name']",
    "company": "input[name='company']",
    "email": "input[name='email']",
    "message": "textarea[name='body']",
    "submit": "button[type='submit']"
}

# ==============================================================================
# DRIVER INITIALIZATION
# ==============================================================================
def setup_driver(mode: str) -> webdriver.Chrome:
    """
    Setup driver based on execution mode.
    - gui: Standard GUI with pyautogui (trusted clicks)
    - xvfb: Linux virtual display (run with: xvfb-run python app.py)
    - headless: Pure headless (CDP clicks, less reliable for production)
    """
    options = get_stealth_chrome_options()
    
    if mode == "headless":
        options.add_argument("--headless=new")
        click_method = "cdp"
    else:
        # GUI or Xvfb mode
        click_method = "pyautogui"
    
    driver = webdriver.Chrome(options=options)
    return driver, click_method

def human_type(element, text: str):
    """Simulate human typing with Gaussian delays."""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(abs(random.gauss(0.08, 0.03)))
    time.sleep(abs(random.gauss(0.5, 0.15)))

# ==============================================================================
# MAIN ORCHESTRATION
# ==============================================================================
def execute_automation():
    if not os.path.exists(CSV_FILE):
        print(f"[!] CSV file not found: {CSV_FILE}")
        return
    
    driver, click_method = setup_driver(EXECUTION_MODE)
    wait = WebDriverWait(driver, 15)
    
    try:
        print(f"[*] Navigating to: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(abs(random.gauss(4, 0.5)))
        
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for index, row in enumerate(reader, start=1):
                print(f"\n{'='*60}")
                print(f"[*] Test #{index} | Subject: {row['nama']}")
                print(f"{'='*60}")
                
                # 1. Fill form
                try:
                    human_type(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["name"]))), row['nama'])
                    human_type(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["company"]))), row['perusahaan'])
                    human_type(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["email"]))), row['email'])
                    human_type(wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["message"]))), row['pesan'])
                    print("[+] Form filled with human entropy.")
                except TimeoutException:
                    print("[-] Form elements not found. Reloading...")
                    driver.refresh()
                    time.sleep(3)
                    continue
                
                # 2. Solve Turnstile
                print("[*] Waiting for Turnstile render...")
                time.sleep(abs(random.gauss(3, 0.5)))
                
                solver = Solver(
                    driver=driver,
                    enable_logging=True,
                    theme="auto",
                    grayscale=False,
                    thresh=0.75,
                    click_method=click_method
                )
                
                detected_type = solver.detect(timeout=15, interval=1)
                
                if detected_type:
                    print(f"[*] Turnstile type: {detected_type}")
                    success = solver.solve(timeout=45, interval=1.5, verify=True)
                    
                    if success:
                        print("[+] Turnstile verified successfully.")
                        
                        # 3. Submit
                        print("[*] Triggering submit...")
                        submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["submit"])))
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
                        time.sleep(abs(random.gauss(3, 0.5)))
                        submit_btn.click()
                        
                        print("[+] Message sent. Waiting for response...")
                        time.sleep(5)
                        
                        # Reload for next iteration
                        driver.get(TARGET_URL)
                        time.sleep(abs(random.gauss(3, 0.5)))
                    else:
                        print("[-] Turnstile solve failed. Skipping...")
                        solver.cleanup()
                        driver.get(TARGET_URL)
                        time.sleep(3)
                else:
                    print("[-] No Turnstile detected. Submitting directly...")
                    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["submit"]))).click()
                    time.sleep(3)
                    driver.get(TARGET_URL)
                    time.sleep(3)
                    
    except Exception as e:
        print(f"[!] Critical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[*] Cleanup and closing driver.")
        driver.quit()

if __name__ == "__main__":
    execute_automation()