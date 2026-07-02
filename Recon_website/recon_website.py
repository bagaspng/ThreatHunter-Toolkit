import re
import sys
import socket
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

try:
    import whois
    HAS_WHOIS = True
except ImportError:
    HAS_WHOIS = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"
}
TIMEOUT = 10

COMMON_PATHS = ["", "contact", "contact-us", "kontak", "about", "about-us", "tentang-kami"]

COMMON_SUBDOMAIN_WORDS = [
    "www", "mail", "webmail", "admin", "portal", "dev", "test", "staging",
    "api", "cpanel", "ftp", "blog", "shop", "app", "sso", "vpn", "cloud",
    "dashboard", "panel", "server", "ns1", "ns2", "smtp", "pop", "m",
    "mobile", "beta", "demo", "support", "helpdesk", "crm", "erp", "hr",
    "intranet", "internal", "backend", "cdn", "static", "assets", "media",
    "download", "upload", "secure", "login", "account", "billing",
]

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
    """
    Ambil HTML + header dari sebuah URL. Return (response, soup, error_msg, ssl_warning).
    ssl_warning berisi pesan kalau ternyata halaman diakses dengan skip verifikasi SSL
    (misal karena sertifikat expired/hostname mismatch) - ini penting dicatat sebagai
    temuan keamanan di laporan.
    """

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
    """
    Fallback terakhir: render tiap URL pakai browser headless (Playwright) supaya
    konten yang di-generate JavaScript (website SPA) ikut kebaca, lalu ekstrak
    email/telepon/teknologi dari HTML hasil render.
    Return (all_emails, all_phones, all_tech, log_lines)
    """
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
    """Versi ringan detect_technologies, khusus dari string HTML mentah (dipakai fallback Playwright)."""
    found = set()
    for tech, patterns in TECH_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, html_text, re.IGNORECASE):
                found.add(tech)
                break
    return found


def whois_lookup(domain):
    """
    Ambil data registrasi domain (WHOIS) - kadang memuat email/telepon pemilik
    domain atau admin teknis. Kalau domain pakai privacy protection, data ini
    akan disamarkan (misal jadi "redacted for privacy").
    """
    if not HAS_WHOIS:
        return None, "Library python-whois belum terinstall (pip install python-whois)"
    try:
        w = whois.whois(domain)
        return w, None
    except Exception as e:
        return None, str(e)


def get_subdomains_crtsh(domain):
    """Sumber 1 (pasif): Certificate Transparency logs via crt.sh"""
    subdomains = set()
    try:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for entry in data:
            name_value = entry.get("name_value", "")
            for name in name_value.split("\n"):
                name = name.strip().lower()
                if name and "*" not in name and name.endswith(domain):
                    subdomains.add(name)
    except Exception as e:
        print(f"  [!] crt.sh gagal/timeout: {e}")
    return subdomains


def get_subdomains_hackertarget(domain):
    """Sumber 2 (pasif): API gratis HackerTarget, agregat dari beberapa sumber DNS publik."""
    subdomains = set()
    try:
        url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        # Format hasil: "subdomain.domain.com,IP" per baris
        if "error" not in resp.text.lower() and "," in resp.text:
            for line in resp.text.strip().split("\n"):
                name = line.split(",")[0].strip().lower()
                if name and name.endswith(domain):
                    subdomains.add(name)
    except Exception as e:
        print(f"  [!] HackerTarget API gagal/timeout: {e}")
    return subdomains


def get_subdomains_dns_bruteforce(domain, wordlist=COMMON_SUBDOMAIN_WORDS):
    """
    Sumber 3 (pasif ke server target, aktif ke DNS resolver): coba resolve
    nama-nama subdomain umum. Ini HANYA query DNS (seperti nslookup biasa),
    bukan scanning/menyerang server webnya.
    """
    subdomains = set()
    for word in wordlist:
        candidate = f"{word}.{domain}"
        try:
            socket.gethostbyname(candidate)
            subdomains.add(candidate)
        except socket.gaierror:
            continue
    return subdomains


def get_subdomains(domain, extra_subdomains=None):
    """Gabungkan semua sumber pasif + subdomain manual yang user tahu."""
    subdomains = set()

    print("  [*] Sumber 1/3: crt.sh (Certificate Transparency)...")
    subdomains |= get_subdomains_crtsh(domain)

    print("  [*] Sumber 2/3: HackerTarget API...")
    subdomains |= get_subdomains_hackertarget(domain)

    print("  [*] Sumber 3/3: DNS brute-force wordlist umum...")
    subdomains |= get_subdomains_dns_bruteforce(domain)

    if extra_subdomains:
        for sd in extra_subdomains:
            sd = sd.strip().lower()
            if sd:
                subdomains.add(sd)

    return sorted(subdomains)


def extract_contacts(soup, raw_html=""):
    """Ekstrak email & nomor telepon dari sebuah halaman (BeautifulSoup object)."""
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
    """Deteksi teknologi berdasarkan header, HTML, dan cookie (prinsip mirip Wappalyzer)."""
    found = set()

    # Gabungkan sumber yang dicek: headers + html mentah + nama cookie
    header_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
    html_str = str(soup)
    cookie_str = " ".join(resp.cookies.keys())

    haystack = f"{header_str}\n{html_str}\n{cookie_str}"

    for tech, patterns in TECH_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, haystack, re.IGNORECASE):
                found.add(tech)
                break

    # Info langsung dari header (Server, X-Powered-By)
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
        print("  python recon_website.py https://target-website.com admin.target-website.com,dev.target-website.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = "https://" + base_url

    extra_subdomains = []
    if len(sys.argv) >= 3:
        extra_subdomains = sys.argv[2].split(",")

    print(f"=== Recon target: {base_url} ===\n")

    all_emails = set()
    all_phones = set()
    all_tech = set()
    log_lines = []
    summary_lines = []

    def log(msg):
        """Catat proses detail (setiap tahap, request, error) -> masuk ke log.txt"""
        print(msg)
        log_lines.append(msg)

    def summary(msg):
        """Catat baris ringkasan hasil akhir -> masuk ke {domain}_hasilrecon.txt"""
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

    log(f"\n--- Tahap Ekstra: WHOIS lookup domain {domain_only} ---")
    w, whois_err = whois_lookup(domain_only)
    if whois_err:
        log(f"  [!] WHOIS gagal: {whois_err}")
    elif w:
        w_emails = w.get("emails") if isinstance(w, dict) or hasattr(w, "get") else None
        registrant = getattr(w, "name", None) or getattr(w, "org", None)
        raw_whois_text = str(w)

        found_emails = set(EMAIL_REGEX.findall(raw_whois_text))
        found_phones = set(PHONE_REGEX.findall(raw_whois_text))

        if found_emails:
            log(f"  [+] Email dari WHOIS: {', '.join(sorted(found_emails))}")
            all_emails.update(found_emails)
        if found_phones:
            log(f"  [+] Telepon dari WHOIS: {', '.join(sorted(found_phones))}")
            all_phones.update(found_phones)
        if registrant:
            log(f"  [i] Nama registrant/organisasi: {registrant}")
        if not found_emails and not found_phones:
            log("  [i] Data WHOIS didapat, tapi email/telepon di-redact/privacy protected.")

    log(f"\n--- Tahap 2: Mencari subdomain dari {domain_only} ---")
    subdomains = get_subdomains(domain_only, extra_subdomains=extra_subdomains)

    if subdomains:
        log(f"[+] Ditemukan {len(subdomains)} subdomain:")
        for sd in subdomains:
            log(f"    - {sd}")
    else:
        log("[!] Tidak ada subdomain yang ditemukan (atau crt.sh tidak bisa diakses).")

    log("\n--- Tahap 3: Cek kontak & teknologi di tiap subdomain ---")
    for sd in subdomains:
        sub_url = f"https://{sd}"
        log(f"[*] Mengecek subdomain: {sub_url}")
        resp, soup, err, ssl_warning = fetch(sub_url)

        if not resp:
            sub_url_http = f"http://{sd}"
            resp, soup, err2, _ = fetch(sub_url_http)
            if resp:
                sub_url = sub_url_http
            else:
                log(f"  [!] Gagal mengakses {sd} -> {err}")
                continue

        if ssl_warning:
            log(f"  [!!] TEMUAN KEAMANAN: {ssl_warning}")

        emails, phones = extract_contacts(soup, resp.text)
        tech = detect_technologies(resp, soup)

        if emails:
            log(f"  [+] Email ditemukan di {sub_url}: {', '.join(sorted(emails))}")
        if phones:
            log(f"  [+] Telepon ditemukan di {sub_url}: {', '.join(sorted(phones))}")
        if tech:
            log(f"  [+] Teknologi terdeteksi di {sub_url}: {', '.join(sorted(tech))}")

        all_emails.update(emails)
        all_phones.update(phones)
        all_tech.update(tech)


    if not all_emails or not all_phones:
        missing = []
        if not all_emails:
            missing.append("email")
        if not all_phones:
            missing.append("telepon")
        log(f"\n--- Tahap 4: {' & '.join(missing).capitalize()} belum ditemukan, mencoba fallback Playwright (JS rendering) ---")

        if not HAS_PLAYWRIGHT:
            log("  [!] Playwright belum terinstall, fallback dilewati.")
            log("      Install dengan: pip install playwright && playwright install chromium")
        else:
            fallback_targets = [urljoin(base_url + "/", path) for path in COMMON_PATHS]
            for sd in subdomains:
                fallback_targets.append(f"https://{sd}")

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

    # --- Ringkasan hasil: ini yang masuk ke file {domain}_hasilrecon.txt ---
    summary(f"=== HASIL RECON: {base_url} ===")
    summary(f"Waktu recon: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    summary("\n[Email ditemukan]")
    summary("\n".join(sorted(all_emails)) if all_emails else "  (tidak ditemukan)")

    summary("\n[Nomor telepon ditemukan]")
    summary("\n".join(sorted(all_phones)) if all_phones else "  (tidak ditemukan)")

    summary("\n[Teknologi terdeteksi]")
    summary("\n".join(sorted(all_tech)) if all_tech else "  (tidak ditemukan)")

    if subdomains:
        summary(f"\n[Subdomain ditemukan] ({len(subdomains)})")
        summary("\n".join(sorted(subdomains)))

    domain = urlparse(base_url).netloc.replace("www.", "")
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", domain)

    # File hasil: HANYA ringkasan, ditimpa tiap run supaya selalu berisi hasil terbaru
    result_filename = f"{safe_name}_hasilrecon.txt"
    with open(result_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    # File log: proses detail tiap tahap, DI-APPEND supaya riwayat semua run tersimpan
    log_filename = "log.txt"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
        f.write("\n\n" + ("=" * 70) + "\n\n")  # pemisah antar-run

    print(f"\n[✓] Ringkasan hasil disimpan ke file: {result_filename}")
    print(f"[✓] Log proses lengkap disimpan (append) ke file: {log_filename}")


if __name__ == "__main__":
    main()
