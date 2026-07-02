import re
import sys
import shutil
import subprocess
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

HAS_NMAP = shutil.which("nmap") is not None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"
}
TIMEOUT = 10

COMMON_PATHS = ["", "contact", "contact-us", "kontak", "about", "about-us", "tentang-kami"]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(
    r"(?:\+62|62|0)8[1-9][0-9]{6,10}|"
    r"(?:\+62|62|0)[2-9][0-9]{1,2}[\s\-]?[0-9]{3,4}[\s\-]?[0-9]{3,4}"
)
EMAIL_OBFUSCATED_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+\s*[\[\(]\s*at\s*[\]\)]\s*[a-zA-Z0-9.\-]+\s*[\[\(]\s*dot\s*[\]\)]\s*[a-zA-Z]{2,}(?:\s*[\[\(]\s*dot\s*[\]\)]\s*[a-zA-Z]{2,})*",
    re.IGNORECASE,
)

TECH_SIGNATURES = {
    "WordPress": [r"wp-content", r"wp-includes", r'name="generator" content="WordPress'],
    "Joomla": [r"/media/jui/", r'name="generator" content="Joomla'],
    "Drupal": [r"sites/default/files", r'name="generator" content="Drupal'],
    "Shopify": [r"cdn\.shopify\.com", r"Shopify\.theme"],
    "Wix": [r"static\.wixstatic\.com", r"wix\.com"],
    "Laravel": [r"laravel_session"],
    "React": [r"react-dom", r"__REACT_DEVTOOLS"],
    "Vue.js": [r"vue\.js", r"__VUE__"],
    "Next.js": [r"__NEXT_DATA__", r"_next/static"],
    "Bootstrap": [r"bootstrap(\.min)?\.css", r"bootstrap(\.min)?\.js"],
    "jQuery": [r"jquery(\.min)?\.js"],
    "Google Analytics": [r"gtag\('config'", r"google-analytics\.com/analytics\.js", r"googletagmanager\.com/gtag"],
    "Google Tag Manager": [r"googletagmanager\.com/gtm\.js"],
    "Cloudflare": [r"cloudflare"],
    "Font Awesome": [r"font-awesome"],
}


def fetch(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return resp, soup, None, None
    except requests.exceptions.SSLError as e:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            ssl_warning = f"Diakses TANPA verifikasi SSL karena sertifikat bermasalah: {e}"
            return resp, soup, None, ssl_warning
        except requests.RequestException as e2:
            return None, None, str(e2), None
    except requests.RequestException as e:
        return None, None, str(e), None


def playwright_fallback(urls):
    emails_found, phones_found, tech_found = set(), set(), set()
    logs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        for url in urls:
            logs.append(f"[*] Merender (Playwright): {url}")
            try:
                page.goto(url, timeout=20000, wait_until="networkidle")
                html = page.content()
            except Exception as e:
                logs.append(f"  [!] Gagal merender {url} -> {e}")
                continue

            soup = BeautifulSoup(html, "html.parser")
            emails, phones = extract_contacts(soup, html)
            tech = detect_technologies_from_html(html)

            if emails:
                logs.append(f"  [+] Email ditemukan (JS-rendered): {', '.join(sorted(emails))}")
            if phones:
                logs.append(f"  [+] Telepon ditemukan (JS-rendered): {', '.join(sorted(phones))}")
            if tech:
                logs.append(f"  [+] Teknologi tambahan terdeteksi (JS-rendered): {', '.join(sorted(tech))}")

            emails_found.update(emails)
            phones_found.update(phones)
            tech_found.update(tech)

        browser.close()

    return emails_found, phones_found, tech_found, logs


def detect_technologies_from_html(html_text):
    found = set()
    for tech, patterns in TECH_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, html_text, re.IGNORECASE):
                found.add(tech)
                break
    return found


def nmap_scan(domain):
    if not HAS_NMAP:
        return None, "nmap tidak ditemukan di sistem (pastikan sudah terinstall dan ada di PATH)"
    try:
        result = subprocess.run(
            ["nmap", "-F", "-T4", domain],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        if not output:
            return None, result.stderr.strip() or "nmap tidak mengembalikan output."
        return output, None
    except subprocess.TimeoutExpired:
        return None, "nmap timeout (>120 detik)."
    except Exception as e:
        return None, str(e)


def extract_contacts(soup, raw_html=""):
    emails = set()
    phones = set()

    for a in soup.select('a[href^="mailto:"]'):
        email = a["href"].replace("mailto:", "").split("?")[0].strip()
        if email:
            emails.add(email)

    for a in soup.select('a[href^="tel:"]'):
        phone = a["href"].replace("tel:", "").strip()
        if phone:
            phones.add(phone)

    text = soup.get_text(separator=" ")
    emails.update(EMAIL_REGEX.findall(text))
    phones.update(PHONE_REGEX.findall(text))

    obfuscated = EMAIL_OBFUSCATED_REGEX.findall(text)
    for match in obfuscated:
        emails.add(match)

    if raw_html:
        emails.update(EMAIL_REGEX.findall(raw_html))
        phones.update(PHONE_REGEX.findall(raw_html))

    return emails, phones


def detect_technologies(resp, soup):
    found = set()

    header_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
    html_str = str(soup)
    cookie_str = " ".join(resp.cookies.keys())

    haystack = f"{header_str}\n{html_str}\n{cookie_str}"

    for tech, patterns in TECH_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, haystack, re.IGNORECASE):
                found.add(tech)
                break

    server = resp.headers.get("Server")
    powered_by = resp.headers.get("X-Powered-By")
    if server:
        found.add(f"Server: {server}")
    if powered_by:
        found.add(f"X-Powered-By: {powered_by}")

    return found


def main():
    if len(sys.argv) < 2:
        print("Cara pakai:")
        print("  python recon_website.py https://target-website.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = "https://" + base_url

    print(f"=== Recon target: {base_url} ===\n")

    all_emails = set()
    all_phones = set()
    all_tech = set()
    log_lines = []
    summary_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    def summary(msg):
        print(msg)
        summary_lines.append(msg)

    log(f"=== Recon target: {base_url} ===")
    log(f"Waktu recon: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    log("--- Tahap 1: Cek domain utama ---")
    for path in COMMON_PATHS:
        url = urljoin(base_url + "/", path)
        log(f"[*] Mengecek: {url}")
        resp, soup, err, ssl_warning = fetch(url)
        if not resp:
            log(f"  [!] Gagal mengakses {url} -> {err}")
            continue
        if ssl_warning:
            log(f"  [!!] TEMUAN KEAMANAN: {ssl_warning}")

        emails, phones = extract_contacts(soup, resp.text)
        tech = detect_technologies(resp, soup)

        if emails:
            log(f"  [+] Email ditemukan di halaman ini: {', '.join(sorted(emails))}")
        if phones:
            log(f"  [+] Telepon ditemukan di halaman ini: {', '.join(sorted(phones))}")
        if tech:
            log(f"  [+] Teknologi terdeteksi di halaman ini: {', '.join(sorted(tech))}")

        all_emails.update(emails)
        all_phones.update(phones)
        all_tech.update(tech)

    domain_only = urlparse(base_url).netloc.replace("www.", "")
    log(f"\n--- Tahap 2: Nmap scan pada {domain_only} ---")
    nmap_output, nmap_err = nmap_scan(domain_only)
    if nmap_err:
        log(f"  [!] Nmap gagal: {nmap_err}")
    else:
        for line in nmap_output.splitlines():
            log(f"  {line}")

    if not all_emails or not all_phones:
        missing = []
        if not all_emails:
            missing.append("email")
        if not all_phones:
            missing.append("telepon")
        log(f"\n--- Tahap 3: {' & '.join(missing).capitalize()} belum ditemukan, mencoba fallback Playwright (JS rendering) ---")

        if not HAS_PLAYWRIGHT:
            log("  [!] Playwright belum terinstall, fallback dilewati.")
            log("      Install dengan: pip install playwright && playwright install chromium")
        else:
            fallback_targets = [urljoin(base_url + "/", path) for path in COMMON_PATHS]

            pw_emails, pw_phones, pw_tech, pw_logs = playwright_fallback(fallback_targets)

            for line in pw_logs:
                log(line)

            if pw_emails:
                log(f"  [+] Email ditemukan lewat Playwright: {', '.join(sorted(pw_emails))}")
            elif "email" in missing:
                log("  [i] Email tetap tidak ditemukan meski sudah pakai JS rendering.")

            if pw_phones:
                log(f"  [+] Telepon ditemukan lewat Playwright: {', '.join(sorted(pw_phones))}")
            elif "telepon" in missing:
                log("  [i] Telepon tetap tidak ditemukan meski sudah pakai JS rendering.")

            if not pw_emails and not pw_phones:
                log("      Kemungkinan kontak memang tidak dicantumkan di halaman yang dicek.")

            all_emails.update(pw_emails)
            all_phones.update(pw_phones)
            all_tech.update(pw_tech)

    summary(f"=== HASIL RECON: {base_url} ===")
    summary(f"Waktu recon: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    summary("\n[Email ditemukan]")
    summary("\n".join(sorted(all_emails)) if all_emails else "  (tidak ditemukan)")

    summary("\n[Nomor telepon ditemukan]")
    summary("\n".join(sorted(all_phones)) if all_phones else "  (tidak ditemukan)")

    summary("\n[Teknologi terdeteksi]")
    summary("\n".join(sorted(all_tech)) if all_tech else "  (tidak ditemukan)")

    summary("\n[Hasil Nmap scan]")
    if nmap_err:
        summary(f"  (gagal: {nmap_err})")
    else:
        summary(nmap_output)

    domain = urlparse(base_url).netloc.replace("www.", "")
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", domain)

    result_filename = f"{safe_name}_hasilrecon.txt"
    with open(result_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    log_filename = "log.txt"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
        f.write("\n\n" + ("=" * 70) + "\n\n")

    print(f"\n[✓] Ringkasan hasil disimpan ke file: {result_filename}")
    print(f"[✓] Log proses lengkap disimpan (append) ke file: {log_filename}")


if __name__ == "__main__":
    main()
