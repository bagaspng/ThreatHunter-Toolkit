#catatan untuk test ke claudflare bypass belum di test secara extensif

import re
import sys
import ssl
import time
import json
import socket
import random
import shutil
import ipaddress
import subprocess
import requests
import urllib3
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from Wappalyzer import Wappalyzer, WebPage

HAS_NMAP = shutil.which('nmap') is not None
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
USER_AGENTS_FALLBACK = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15']
try:
    import undetected_chromedriver as uc
    HAS_UC = True
    _original_uc_del = uc.Chrome.__del__

    def _safe_uc_del(self):
        try:
            _original_uc_del(self)
        except Exception:
            pass
    uc.Chrome.__del__ = _safe_uc_del
except ImportError:
    HAS_UC = False
    print('[i] undetected-chromedriver tidak tersedia, fallback bypass Cloudflare dilewati.')
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False
try:
    from fake_useragent import UserAgent
    _UA_GENERATOR = UserAgent()
    HAS_FAKE_USERAGENT = True
except Exception as e:
    _UA_GENERATOR = None
    HAS_FAKE_USERAGENT = False
    print(f'[i] fake-useragent tidak tersedia ({e}), pakai UA fallback manual.')

def random_headers():
    if HAS_FAKE_USERAGENT:
        try:
            return {'User-Agent': _UA_GENERATOR.random}
        except Exception:
            pass
    return {'User-Agent': random.choice(USER_AGENTS_FALLBACK)}
TIMEOUT = 10
MAX_PATHS_PER_DOMAIN = 15
EMAIL_REGEX = re.compile('[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile('(?:\\+62|62|0)8[1-9][0-9]{6,10}|(?:\\+62|62|0)[2-9][0-9]{1,2}[\\s\\-]?[0-9]{3,4}[\\s\\-]?[0-9]{3,4}')
EMAIL_OBFUSCATED_REGEX = re.compile('[a-zA-Z0-9._%+\\-]+\\s*[\\[\\(]\\s*at\\s*[\\]\\)]\\s*[a-zA-Z0-9.\\-]+\\s*[\\[\\(]\\s*dot\\s*[\\]\\)]\\s*[a-zA-Z]{2,}(?:\\s*[\\[\\(]\\s*dot\\s*[\\]\\)]\\s*[a-zA-Z]{2,})*', re.IGNORECASE)
try:
    WAPPALYZER = Wappalyzer.latest(update=True)
    HAS_WAPPALYZER = True
except Exception as e:
    print(f'[i] Gagal update database Wappalyzer ({e}), pakai database bawaan package.')
    try:
        WAPPALYZER = Wappalyzer.latest(update=False)
        HAS_WAPPALYZER = True
    except Exception as e2:
        WAPPALYZER = None
        HAS_WAPPALYZER = False
        print(f'[!] Gagal load Wappalyzer sama sekali: {e2}')

def is_cloudflare_challenge(resp_or_html):
    if resp_or_html is None:
        return False
    if isinstance(resp_or_html, str):
        html = resp_or_html
        status_code = None
    else:
        html = resp_or_html.text
        status_code = resp_or_html.status_code
    markers = ['just a moment', 'cf-browser-verification', 'cf-chl', 'challenges.cloudflare.com', 'checking your browser before accessing', 'cf-mitigated']
    html_lower = html.lower()
    if any((m in html_lower for m in markers)):
        return True
    if status_code in (403, 503) and 'cloudflare' in html_lower:
        return True
    return False

def detect_installed_chrome_major_version():
    candidates = []
    if sys.platform.startswith('win'):
        try:
            import winreg
            for hive, path in [(winreg.HKEY_CURRENT_USER, 'Software\\Google\\Chrome\\BLBeacon'), (winreg.HKEY_LOCAL_MACHINE, 'Software\\Google\\Chrome\\BLBeacon')]:
                try:
                    key = winreg.OpenKey(hive, path)
                    version, _ = winreg.QueryValueEx(key, 'version')
                    candidates.append(version)
                except FileNotFoundError:
                    continue
        except Exception:
            pass
    if not candidates:
        for cmd in (['google-chrome', '--version'], ['chrome', '--version'], ['chromium', '--version'], ['chromium-browser', '--version']):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if out.stdout:
                    candidates.append(out.stdout.strip())
            except Exception:
                continue
    for text in candidates:
        match = re.search('(\\d+)\\.\\d+\\.\\d+\\.\\d+', text)
        if match:
            return int(match.group(1))
    return None

def fetch_with_undetected_chromedriver(url, log_fn, timeout=30, max_wait=25, wait_for_contact=True):
    if not HAS_UC:
        log_fn('  [!] undetected-chromedriver belum terinstall, fallback dilewati.')
        log_fn('      Install dengan: pip install undetected-chromedriver')
        return (None, 'undetected-chromedriver tidak tersedia')
    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        chrome_major = detect_installed_chrome_major_version()
        if chrome_major:
            log_fn(f'  [i] Terdeteksi Chrome versi {chrome_major}, menyesuaikan driver...')
            driver = uc.Chrome(options=options, version_main=chrome_major)
        else:
            driver = uc.Chrome(options=options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        waited = 0
        while waited < max_wait:
            time.sleep(1)
            waited += 1
            title = (driver.title or '').lower()
            html_snapshot = driver.page_source
            still_challenge = is_cloudflare_challenge(html_snapshot) or 'just a moment' in title
            if not still_challenge:
                log_fn(f'  [i] Challenge kelar setelah ~{waited} detik.')
                break
        else:
            log_fn(f'  [!] Setelah {max_wait} detik, halaman masih terlihat seperti challenge page.')
        if wait_for_contact:
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                try:
                    WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "a[href^='tel:'], a[href^='mailto:'], footer"))
                    log_fn('  [i] Elemen kontak/footer terdeteksi di DOM.')
                except Exception:
                    log_fn('  [i] Tidak ada elemen kontak/footer eksplisit dalam 10 detik, lanjut scroll manual.')
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                time.sleep(2)
            except ImportError:
                log_fn("  [i] Package 'selenium' tidak lengkap, lewati tunggu elemen kontak eksplisit.")
        html_parts = [driver.page_source]
        try:
            from selenium.webdriver.common.by import By
            iframes = driver.find_elements(By.TAG_NAME, 'iframe')
            for frame in iframes:
                try:
                    driver.switch_to.frame(frame)
                    html_parts.append(driver.page_source)
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
                    continue
            if iframes:
                log_fn(f'  [i] Menggabungkan konten dari {len(iframes)} iframe untuk ekstraksi kontak.')
        except Exception:
            pass
        html = '\n'.join(html_parts)
        return (html, None)
    except Exception as e:
        return (None, str(e))
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def fetch(url):
    try:
        resp = requests.get(url, headers=random_headers(), timeout=TIMEOUT, verify=True)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return (resp, soup, None, None)
    except requests.exceptions.SSLError as e:
        try:
            resp = requests.get(url, headers=random_headers(), timeout=TIMEOUT, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            ssl_warning = f'Diakses TANPA verifikasi SSL karena sertifikat bermasalah: {e}'
            return (resp, soup, None, ssl_warning)
        except requests.RequestException as e2:
            return (None, None, str(e2), None)
    except requests.RequestException as e:
        return (None, None, str(e), None)
COMMON_SUBDOMAIN_WORDS = ['www', 'mail', 'webmail', 'admin', 'portal', 'dev', 'test', 'staging', 'api', 'cpanel', 'ftp', 'blog', 'shop', 'app', 'sso', 'vpn', 'cloud', 'dashboard', 'panel', 'server', 'ns1', 'ns2', 'smtp', 'pop', 'm', 'mobile', 'beta', 'demo', 'support', 'helpdesk', 'crm', 'erp', 'hr', 'intranet', 'internal', 'backend', 'cdn', 'static', 'assets', 'media', 'download', 'upload', 'secure', 'login', 'account', 'billing', 'direct', 'origin', 'origin-www', 'orig']

def get_subdomains_crtsh(domain, log_fn):
    subdomains = set()
    try:
        url = f'https://crt.sh/?q=%25.{domain}&output=json'
        resp = requests.get(url, headers=random_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for entry in data:
            name_value = entry.get('name_value', '')
            for name in name_value.split('\n'):
                name = name.strip().lower()
                if name and '*' not in name and name.endswith(domain):
                    subdomains.add(name)
    except Exception as e:
        log_fn(f'  [!] crt.sh gagal/timeout: {e}')
    return subdomains

def get_subdomains_hackertarget(domain, log_fn):
    subdomains = set()
    try:
        url = f'https://api.hackertarget.com/hostsearch/?q={domain}'
        resp = requests.get(url, headers=random_headers(), timeout=20)
        resp.raise_for_status()
        if 'error' not in resp.text.lower() and ',' in resp.text:
            for line in resp.text.strip().split('\n'):
                name = line.split(',')[0].strip().lower()
                if name and name.endswith(domain):
                    subdomains.add(name)
    except Exception as e:
        log_fn(f'  [!] HackerTarget API gagal/timeout: {e}')
    return subdomains

def get_subdomains_dns_bruteforce(domain, wordlist=COMMON_SUBDOMAIN_WORDS):
    subdomains = set()
    for word in wordlist:
        candidate = f'{word}.{domain}'
        try:
            socket.gethostbyname(candidate)
            subdomains.add(candidate)
        except socket.gaierror:
            continue
    return subdomains

def find_subdomains(domain, log_fn):
    log_fn(f'  [*] Sumber 1/3: crt.sh (Certificate Transparency)...')
    subs = set()
    subs |= get_subdomains_crtsh(domain, log_fn)
    log_fn(f'  [*] Sumber 2/3: HackerTarget API...')
    subs |= get_subdomains_hackertarget(domain, log_fn)
    log_fn(f'  [*] Sumber 3/3: DNS brute-force wordlist umum...')
    subs |= get_subdomains_dns_bruteforce(domain)
    return sorted(subs)

def resolve_ip(domain, log_fn):
    try:
        ip = socket.gethostbyname(domain)
        return (ip, None)
    except socket.gaierror as e:
        log_fn(f'  [!] Gagal resolve IP dari {domain}: {e}')
        return (None, str(e))

def get_ip_whois(ip, log_fn):
    url = f'https://ipwho.is/{ip}'
    try:
        resp = requests.get(url, headers=random_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get('success', True):
            log_fn(f'  [!] ipwho.is gagal untuk {ip}: {data.get('message')}')
        return data
    except Exception as e:
        log_fn(f'  [!] Gagal ambil data ipwho.is untuk {ip}: {e}')
        return None
CLOUDFLARE_IP_RANGES = None

def get_cloudflare_ip_ranges(log_fn):
    global CLOUDFLARE_IP_RANGES
    if CLOUDFLARE_IP_RANGES is not None:
        return CLOUDFLARE_IP_RANGES
    try:
        resp = requests.get('https://www.cloudflare.com/ips-v4', timeout=10)
        resp.raise_for_status()
        ranges = [ipaddress.ip_network(line.strip()) for line in resp.text.strip().split('\n') if line.strip()]
        CLOUDFLARE_IP_RANGES = ranges
        return ranges
    except Exception as e:
        log_fn(f'  [!] Gagal ambil range IP Cloudflare: {e}')
        CLOUDFLARE_IP_RANGES = []
        return []

def is_cloudflare_ip(ip, log_fn):
    ranges = get_cloudflare_ip_ranges(log_fn)
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any((ip_obj in net for net in ranges))
    except Exception:
        return False

def find_origin_ip_via_mx(domain, log_fn):
    candidates = {}
    if not HAS_DNSPYTHON:
        log_fn("  [i] Package 'dnspython' tidak terinstall, lewati cek MX record.")
        log_fn('      Install dengan: pip install dnspython')
        return candidates
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        mx_hosts = sorted((str(r.exchange).rstrip('.') for r in answers))
        if not mx_hosts:
            log_fn('  [!] Tidak ada MX record ditemukan.')
            return candidates
        log_fn(f'  [+] MX record ditemukan: {', '.join(mx_hosts)}')
        for mx_host in mx_hosts:
            try:
                ip = socket.gethostbyname(mx_host)
            except socket.gaierror:
                continue
            if is_cloudflare_ip(ip, log_fn):
                continue
            candidates[mx_host] = ip
        if candidates:
            log_fn('  [+] Kandidat origin IP dari MX record (bukan Cloudflare):')
            for host, ip in candidates.items():
                log_fn(f'      - {host} -> {ip}')
        else:
            log_fn('  [!] IP dari MX record juga terdeteksi sebagai Cloudflare / tidak resolve.')
    except Exception as e:
        log_fn(f'  [!] Gagal query MX record: {e}')
    return candidates

def find_origin_ip_via_txt(domain, log_fn):
    candidates = {}
    if not HAS_DNSPYTHON:
        return candidates
    try:
        answers = dns.resolver.resolve(domain, 'TXT')
        for r in answers:
            txt = ''.join((part.decode() if isinstance(part, bytes) else part for part in r.strings)) if hasattr(r, 'strings') else str(r)
            if 'spf' not in txt.lower() and 'v=spf1' not in txt.lower():
                continue
            log_fn(f'  [i] SPF record ditemukan: {txt}')
            for ip_match in re.findall('ip4:(\\d+\\.\\d+\\.\\d+\\.\\d+)', txt):
                if not is_cloudflare_ip(ip_match, log_fn):
                    candidates[f'spf-ip4:{ip_match}'] = ip_match
            for host_match in re.findall('a:([a-zA-Z0-9.\\-]+)', txt):
                try:
                    ip = socket.gethostbyname(host_match)
                    if not is_cloudflare_ip(ip, log_fn):
                        candidates[f'spf-a:{host_match}'] = ip
                except socket.gaierror:
                    continue
        if candidates:
            log_fn('  [+] Kandidat origin IP dari SPF/TXT record:')
            for label, ip in candidates.items():
                log_fn(f'      - {label} -> {ip}')
    except Exception as e:
        log_fn(f'  [!] Gagal query TXT record: {e}')
    return candidates
FINGERPRINT_ENDPOINTS = {'WordPress': [('/wp-login.php', ['wp-login', 'wordpress']), ('/wp-json/', ['"namespace"', 'wp/v2']), ('/wp-includes/', ['wp-includes'])], 'Joomla': [('/administrator/', ['joomla']), ('/administrator/manifests/files/joomla.xml', ['<?xml', 'joomla'])], 'Drupal': [('/CHANGELOG.txt', ['drupal']), ('/core/misc/drupal.js', ['drupal'])], 'cPanel': [(':2082', ['cpanel']), (':2083', ['cpanel']), (':2096', ['webmail', 'cpanel'])], 'Laravel': [('/.env', ['APP_NAME', 'DB_CONNECTION', 'APP_KEY'])], 'Git exposed': [('/.git/HEAD', ['ref:', 'refs/heads'])], 'phpMyAdmin': [('/phpmyadmin/', ['phpmyadmin']), ('/phpMyAdmin/', ['phpmyadmin'])]}

def fingerprint_via_endpoints(base_url_or_ip, log_fn, use_host_header=None):
    found = {}
    headers = random_headers()
    if use_host_header:
        headers['Host'] = use_host_header
    for tech_name, checks in FINGERPRINT_ENDPOINTS.items():
        for path, markers in checks:
            if path.startswith(':'):
                port = path.lstrip(':')
                url = f'https://{use_host_header or base_url_or_ip}:{port}/'
            else:
                url = base_url_or_ip.rstrip('/') + path
            try:
                resp = requests.get(url, headers=headers, timeout=6, verify=False, allow_redirects=True)
                if resp.status_code >= 400:
                    continue
                body_lower = resp.text.lower()
                if any((marker.lower() in body_lower for marker in markers)):
                    found.setdefault(tech_name, []).append(path)
            except Exception:
                continue
    if found:
        log_fn('  [+] Fingerprint endpoint ditemukan:')
        for tech_name, paths in found.items():
            log_fn(f'      - {tech_name} (terdeteksi via: {', '.join(paths)})')
    return found

def find_origin_ip_candidates_dns(domain, subdomains, log_fn):
    log_fn(f'  [*] Mengecek IP dari {len(subdomains)} subdomain untuk cari kandidat origin non-Cloudflare...')
    candidates = {}
    for sd in subdomains:
        try:
            ip = socket.gethostbyname(sd)
        except socket.gaierror:
            continue
        if is_cloudflare_ip(ip, log_fn):
            continue
        candidates[sd] = ip
    if candidates:
        log_fn(f'  [+] Kandidat origin IP dari DNS subdomain (bukan Cloudflare):')
        for sd, ip in candidates.items():
            log_fn(f'      - {sd} -> {ip}')
    else:
        log_fn('  [!] Tidak ada kandidat origin IP dari subdomain yang ada.')
    return candidates

def fetch_via_origin_ip(domain, origin_ip, log_fn, use_https=True):
    scheme = 'https' if use_https else 'http'
    url = f'{scheme}://{origin_ip}/'
    headers = random_headers()
    headers['Host'] = domain
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
        log_fn(f'  [+] Berhasil akses origin IP {origin_ip} langsung (status {resp.status_code}).')
        log_fn(f'  [i] Header Server dari origin: {resp.headers.get('Server', '(tidak ada)')}')
        log_fn(f'  [i] Header X-Powered-By dari origin: {resp.headers.get('X-Powered-By', '(tidak ada)')}')
        return resp
    except Exception as e:
        log_fn(f'  [!] Gagal akses origin IP {origin_ip} langsung ({scheme}): {e}')
        if use_https:
            return fetch_via_origin_ip(domain, origin_ip, log_fn, use_https=False)
        return None

def discover_paths(base_url, base_soup, log_fn, max_paths=MAX_PATHS_PER_DOMAIN):
    base_netloc = urlparse(base_url).netloc
    discovered = []
    seen = {base_url.rstrip('/')}
    for a in base_soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#'):
            continue
        if href.startswith(('mailto:', 'tel:', 'sms:', 'javascript:')):
            continue
        full_url = urljoin(base_url + '/', href)
        full_url_no_frag = full_url.split('#')[0].rstrip('/')
        parsed = urlparse(full_url_no_frag)
        if parsed.netloc != base_netloc:
            continue
        if not parsed.scheme.startswith('http'):
            continue
        if full_url_no_frag in seen:
            continue
        seen.add(full_url_no_frag)
        discovered.append(full_url_no_frag)
        if len(discovered) >= max_paths:
            break
    log_fn(f'  [i] Ditemukan {len(discovered)} path internal via BeautifulSoup (maks {max_paths}).')
    return discovered
EXTRA_TECH_SIGNATURES = {'WordPress': ['wp-content', 'wp-includes'], 'React': ['react-dom', '__REACT_DEVTOOLS', 'id="root"'], 'Vue.js': ['vue\\.js', '__VUE__', 'id="app"'], 'Next.js': ['__NEXT_DATA__', '_next/static'], 'Angular': ['ng-version'], 'Bootstrap': ['bootstrap(\\.min)?\\.css'], 'jQuery': ['jquery(\\.min)?\\.js'], 'Google Analytics': ["gtag\\('config'", 'googletagmanager\\.com/gtag'], 'Cloudflare': ['cloudflare']}

def detect_technologies_from_html(html_text):
    found = set()
    for tech, patterns in EXTRA_TECH_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, html_text, re.IGNORECASE):
                found.add(tech)
                break
    return found

def detect_technologies_wappalyzer(url, resp, log_fn):
    found = {}
    if not HAS_WAPPALYZER:
        log_fn('  [!] Wappalyzer tidak tersedia, deteksi teknologi dilewati.')
        return found
    try:
        webpage = WebPage(url, resp.text, dict(resp.headers))
        techs_with_versions = WAPPALYZER.analyze_with_versions(webpage)
        for tech_name, tech_info in techs_with_versions.items():
            versions = tech_info.get('versions', []) if isinstance(tech_info, dict) else []
            found[tech_name] = versions
    except Exception as e:
        log_fn(f'  [!] Wappalyzer gagal menganalisis {url} -> {e}')
    return found

def nmap_scan(domain):
    if not HAS_NMAP:
        return (None, 'nmap tidak ditemukan di sistem (pastikan sudah terinstall dan ada di PATH)')
    try:
        result = subprocess.run(['nmap', '-F', '-T4', domain], capture_output=True, text=True, timeout=120)
        output = result.stdout.strip()
        if not output:
            return (None, result.stderr.strip() or 'nmap tidak mengembalikan output.')
        return (output, None)
    except subprocess.TimeoutExpired:
        return (None, 'nmap timeout (>120 detik).')
    except Exception as e:
        return (None, str(e))

def check_ssl_tls_info(hostname, port=443, timeout=TIMEOUT):
    info = {'tls_version': None, 'cipher': None, 'cert_issuer': None, 'cert_not_after': None, 'cert_expired': None, 'handshake_ms': None, 'error': None}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        start = time.perf_counter()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as tls_sock:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                info['tls_version'] = tls_sock.version()
                cipher = tls_sock.cipher()
                if cipher:
                    info['cipher'] = cipher[0]
                info['handshake_ms'] = elapsed_ms
                der_cert = tls_sock.getpeercert(binary_form=True)
                if der_cert:
                    try:
                        from cryptography import x509
                        cert_obj = x509.load_der_x509_certificate(der_cert)
                        issuer_cn = cert_obj.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
                        issuer_org = cert_obj.issuer.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATION_NAME)
                        info['cert_issuer'] = issuer_org[0].value if issuer_org else issuer_cn[0].value if issuer_cn else None
                        not_after_dt = getattr(cert_obj, 'not_valid_after_utc', None) or cert_obj.not_valid_after
                        info['cert_not_after'] = not_after_dt.strftime('%Y-%m-%d %H:%M:%S')
                        now_ref = datetime.now(timezone.utc)
                        if not_after_dt.tzinfo is None:
                            not_after_dt = not_after_dt.replace(tzinfo=timezone.utc)
                        info['cert_expired'] = not_after_dt < now_ref
                    except ImportError:
                        info['error'] = "Library 'cryptography' tidak terinstall, tidak bisa parse detail sertifikat (pip install cryptography)."
                    except Exception as parse_err:
                        info['error'] = f'Gagal parse sertifikat: {parse_err}'
    except Exception as e:
        info['error'] = str(e)
    return info

def measure_http_speed(url, timeout=TIMEOUT):
    try:
        start = time.perf_counter()
        resp = requests.get(url, headers=random_headers(), timeout=timeout, verify=False)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {'total_ms': elapsed_ms, 'status_code': resp.status_code, 'error': None}
    except requests.RequestException as e:
        return {'total_ms': None, 'status_code': None, 'error': str(e)}

def extract_contacts(soup, raw_html):
    emails = set()
    phones = set()
    for a in soup.select('a[href^="mailto:"]'):
        email = a['href'].replace('mailto:', '').split('?')[0].strip()
        if email:
            emails.add(email)
    for a in soup.select('a[href^="tel:"]'):
        phone = a['href'].replace('tel:', '').strip()
        if phone:
            phones.add(phone)
    text = soup.get_text(separator=' ')
    emails.update(EMAIL_REGEX.findall(text))
    phones.update(PHONE_REGEX.findall(text))
    obfuscated = EMAIL_OBFUSCATED_REGEX.findall(text)
    for match in obfuscated:
        emails.add(match)
    if raw_html:
        emails.update(EMAIL_REGEX.findall(raw_html))
        phones.update(PHONE_REGEX.findall(raw_html))
    return (emails, phones)

def read_urls_from_file(file_path):
    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parsed = urlparse(line)
            if not parsed.scheme:
                line = 'https://' + line
            urls.append(line.rstrip('/'))
    return urls

def format_tech_for_log(tech_dict):
    parts = []
    for name, versions in sorted(tech_dict.items()):
        versions = sorted((v for v in versions if v))
        if versions:
            parts.append(f'{name} {'/'.join(versions)}')
        else:
            parts.append(name)
    return ', '.join(parts)

def recon_single_target(base_url, log_fn):
    result = {'target': base_url, 'scanned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'emails': [], 'phones': [], 'technologies': [], 'subdomains': [], 'origin_ip_candidates': {}, 'ip_info': {}, 'pages_scanned': [], 'ssl_tls': {}, 'http_speed': {}, 'nmap': {'output': None, 'error': None}, 'errors': []}
    all_emails = set()
    all_phones = set()
    all_tech = {}

    def merge_tech(target_dict, new_dict):
        for name, versions in new_dict.items():
            if name not in target_dict:
                target_dict[name] = set(versions)
            else:
                target_dict[name].update(versions)
    log_fn(f'\n=== Recon target: {base_url} ===')
    log_fn('--- Tahap 1: Fetch halaman utama ---')
    resp, soup, err, ssl_warning = fetch(base_url)
    status_blocked = bool(resp) and resp.status_code in (401, 403, 429, 503)
    cf_detected = is_cloudflare_challenge(resp) if resp else False
    need_uc_fallback = not resp or cf_detected or status_blocked
    if need_uc_fallback:
        if cf_detected:
            log_fn('  [!] Terdeteksi halaman Cloudflare challenge, mencoba fallback undetected-chromedriver...')
        elif status_blocked:
            log_fn(f'  [!] Diblokir dengan status {resp.status_code}, mencoba fallback undetected-chromedriver...')
        else:
            log_fn(f'  [!] Gagal mengakses {base_url} -> {err}')
            log_fn('  [*] Mencoba fallback undetected-chromedriver (siapa tahu diblokir Cloudflare)...')
        uc_html, uc_err = fetch_with_undetected_chromedriver(base_url, log_fn)
        if uc_html:
            log_fn('  [+] Berhasil mengakses lewat undetected-chromedriver (bypass Cloudflare).')
            result['errors'].append('Halaman utama diakses via fallback undetected-chromedriver (Cloudflare bypass)')
            soup = BeautifulSoup(uc_html, 'html.parser')
            emails, phones = extract_contacts(soup, uc_html)
            all_emails.update(emails)
            all_phones.update(phones)
            result['pages_scanned'].append(base_url)
            if emails:
                log_fn(f'  [+] Email ditemukan (via bypass): {', '.join(sorted(emails))}')
            if phones:
                log_fn(f'  [+] Telepon ditemukan (via bypass): {', '.join(sorted(phones))}')
            if resp:
                tech = detect_technologies_wappalyzer(base_url, resp, log_fn)
                merge_tech(all_tech, tech)
            extra_tech = detect_technologies_from_html(uc_html)
            if extra_tech:
                merge_tech(all_tech, {name: [] for name in extra_tech})
            if all_tech:
                log_fn(f'  [+] Teknologi terdeteksi: {format_tech_for_log(all_tech)}')
        else:
            msg = f'Gagal mengakses {base_url} (termasuk lewat fallback Cloudflare bypass) -> {uc_err or err}'
            log_fn(f'  [!] {msg}')
            result['errors'].append(msg)
            if not resp:
                return result
    else:
        if ssl_warning:
            log_fn(f'  [!!] TEMUAN KEAMANAN: {ssl_warning}')
            result['errors'].append(ssl_warning)
        emails, phones = extract_contacts(soup, resp.text)
        tech = detect_technologies_wappalyzer(base_url, resp, log_fn)
        all_emails.update(emails)
        all_phones.update(phones)
        merge_tech(all_tech, tech)
        result['pages_scanned'].append(base_url)
        if emails:
            log_fn(f'  [+] Email ditemukan: {', '.join(sorted(emails))}')
        if phones:
            log_fn(f'  [+] Telepon ditemukan: {', '.join(sorted(phones))}')
        if tech:
            log_fn(f'  [+] Teknologi terdeteksi (Wappalyzer): {format_tech_for_log(tech)}')
    log_fn('\n--- Tahap 2: Cari path internal (BeautifulSoup) ---')
    internal_paths = discover_paths(base_url, soup, log_fn)
    for path_url in internal_paths:
        log_fn(f'[*] Mengecek: {path_url}')
        p_resp, p_soup, p_err, p_ssl_warning = fetch(path_url)
        p_status_blocked = bool(p_resp) and p_resp.status_code in (401, 403, 429, 503)
        p_cf_detected = is_cloudflare_challenge(p_resp) if p_resp else False
        if not p_resp or p_cf_detected or p_status_blocked:
            if p_cf_detected:
                log_fn('  [!] Terdeteksi Cloudflare challenge, mencoba fallback undetected-chromedriver...')
            elif p_status_blocked:
                log_fn(f'  [!] Diblokir dengan status {p_resp.status_code}, mencoba fallback undetected-chromedriver...')
            else:
                log_fn(f'  [!] Gagal mengakses {path_url} -> {p_err}, mencoba fallback undetected-chromedriver...')
            p_uc_html, p_uc_err = fetch_with_undetected_chromedriver(path_url, log_fn)
            if not p_uc_html:
                log_fn(f'  [!] Fallback juga gagal -> {p_uc_err or p_err}')
                continue
            log_fn('  [+] Berhasil lewat fallback undetected-chromedriver (bypass Cloudflare).')
            p_soup = BeautifulSoup(p_uc_html, 'html.parser')
            p_emails, p_phones = extract_contacts(p_soup, p_uc_html)
            p_tech = detect_technologies_wappalyzer(path_url, p_resp, log_fn) if p_resp else {}
            p_extra_tech = detect_technologies_from_html(p_uc_html)
            if p_extra_tech:
                for name in p_extra_tech:
                    p_tech.setdefault(name, [])
        else:
            if p_ssl_warning:
                log_fn(f'  [!!] TEMUAN KEAMANAN: {p_ssl_warning}')
                result['errors'].append(p_ssl_warning)
            p_emails, p_phones = extract_contacts(p_soup, p_resp.text)
            p_tech = detect_technologies_wappalyzer(path_url, p_resp, log_fn)
        if p_emails:
            log_fn(f'  [+] Email ditemukan: {', '.join(sorted(p_emails))}')
        if p_phones:
            log_fn(f'  [+] Telepon ditemukan: {', '.join(sorted(p_phones))}')
        if p_tech:
            log_fn(f'  [+] Teknologi terdeteksi: {format_tech_for_log(p_tech)}')
        all_emails.update(p_emails)
        all_phones.update(p_phones)
        merge_tech(all_tech, p_tech)
        result['pages_scanned'].append(path_url)
    domain_only = urlparse(base_url).netloc.replace('www.', '')
    log_fn(f'\n--- Tahap 3: Mencari subdomain dari {domain_only} ---')
    subdomains = find_subdomains(domain_only, log_fn)
    if subdomains:
        log_fn(f'  [+] Ditemukan {len(subdomains)} subdomain:')
        for sd in subdomains:
            log_fn(f'      - {sd}')
    else:
        log_fn('  [!] Tidak ada subdomain yang ditemukan.')
    result['subdomains'] = subdomains
    is_using_cf = 'Cloudflare' in all_tech
    if is_using_cf or cf_detected:
        log_fn(f'\n--- Tahap 3b: Cari origin IP asli di balik Cloudflare ---')
        origin_candidates = find_origin_ip_candidates_dns(domain_only, subdomains, log_fn)
        log_fn('  [*] Cek MX record (mail server sering share IP dengan hosting web)...')
        mx_candidates = find_origin_ip_via_mx(domain_only, log_fn)
        origin_candidates.update(mx_candidates)
        log_fn('  [*] Cek SPF/TXT record...')
        txt_candidates = find_origin_ip_via_txt(domain_only, log_fn)
        origin_candidates.update(txt_candidates)
        result['origin_ip_candidates'] = origin_candidates
        for label, origin_ip in origin_candidates.items():
            log_fn(f'  [*] Mencoba akses origin via {label} ({origin_ip})...')
            origin_resp = fetch_via_origin_ip(domain_only, origin_ip, log_fn)
            if origin_resp:
                origin_tech = detect_technologies_wappalyzer(f'https://{origin_ip}/', origin_resp, log_fn)
                if origin_tech:
                    log_fn(f'  [+] Teknologi origin terdeteksi via {label}: {format_tech_for_log(origin_tech)}')
                    merge_tech(all_tech, origin_tech)
                origin_soup = BeautifulSoup(origin_resp.text, 'html.parser')
                o_emails, o_phones = extract_contacts(origin_soup, origin_resp.text)
                if o_emails or o_phones:
                    log_fn(f'  [+] Kontak tambahan ditemukan dari origin: email={len(o_emails)}, telepon={len(o_phones)}')
                all_emails.update(o_emails)
                all_phones.update(o_phones)
                log_fn(f'  [*] Menjalankan fingerprint endpoint khas (WP/Joomla/cPanel/dll) ke origin...')
                endpoint_tech = fingerprint_via_endpoints(f'https://{origin_ip}', log_fn, use_host_header=domain_only)
                for tech_name in endpoint_tech:
                    merge_tech(all_tech, {tech_name: []})
                break
        if not origin_candidates:
            log_fn('  [*] Tidak ada origin IP ketemu, coba fingerprint endpoint langsung ke domain (via Cloudflare)...')
            endpoint_tech = fingerprint_via_endpoints(base_url, log_fn)
            for tech_name in endpoint_tech:
                merge_tech(all_tech, {tech_name: []})
    else:
        result['origin_ip_candidates'] = {}
    log_fn(f'\n--- Tahap 4: Resolve IP & lookup info IP ({domain_only}) ---')
    ip_address, ip_err = resolve_ip(domain_only, log_fn)
    if ip_address:
        log_fn(f'  [+] IP address: {ip_address}')
        whois_url = f'https://ipwho.is/{ip_address}'
        log_fn(f'  [*] Cek info IP via: {whois_url}')
        ip_data = get_ip_whois(ip_address, log_fn)
        if ip_data:
            log_fn(f'  [+] ISP: {ip_data.get('connection', {}).get('isp')}')
            log_fn(f'  [+] Negara: {ip_data.get('country')}')
            log_fn(f'  [+] Kota: {ip_data.get('city')}')
            log_fn(f'  [+] ASN: {ip_data.get('connection', {}).get('asn')}')
        result['ip_info'] = {'ip': ip_address, 'whois_url': whois_url, 'data': ip_data}
    else:
        result['ip_info'] = {'ip': None, 'whois_url': None, 'data': None, 'error': ip_err}
    log_fn(f'\n--- Tahap 5: Nmap scan pada {domain_only} ---')
    nmap_output, nmap_err = nmap_scan(domain_only)
    if nmap_err:
        log_fn(f'  [!] Nmap gagal: {nmap_err}')
        result['nmap']['error'] = nmap_err
    else:
        nmap_lines = nmap_output.splitlines()
        for line in nmap_lines:
            log_fn(f'  {line}')
        result['nmap']['output'] = nmap_lines
    log_fn(f'\n--- Tahap 6: Cek TLS/SSL & kecepatan koneksi pada {domain_only} ---')
    ssl_info = check_ssl_tls_info(domain_only)
    if ssl_info['error']:
        log_fn(f'  [!] Gagal cek TLS/SSL: {ssl_info['error']}')
    else:
        log_fn(f'  [+] Versi TLS: {ssl_info['tls_version']}')
        log_fn(f'  [+] Cipher: {ssl_info['cipher']}')
        log_fn(f'  [+] Handshake TLS: {ssl_info['handshake_ms']} ms')
        log_fn(f'  [+] Sertifikat issuer: {ssl_info['cert_issuer']}')
        log_fn(f'  [+] Sertifikat expired: {ssl_info['cert_not_after']}{(' (SUDAH EXPIRED)' if ssl_info['cert_expired'] else '')}')
        if ssl_info['cert_expired']:
            result['errors'].append(f'Sertifikat SSL sudah expired sejak {ssl_info['cert_not_after']}')
    result['ssl_tls'] = ssl_info
    speed_info = measure_http_speed(base_url)
    if speed_info['error']:
        log_fn(f'  [!] Gagal ukur kecepatan HTTP: {speed_info['error']}')
    else:
        log_fn(f'  [+] Waktu response HTTP penuh: {speed_info['total_ms']} ms (status {speed_info['status_code']})')
    result['http_speed'] = speed_info
    result['emails'] = sorted(all_emails)
    result['phones'] = sorted(all_phones)
    result['technologies'] = [{'name': name, 'versions': sorted((v for v in versions if v))} for name, versions in sorted(all_tech.items())]
    return result

def main():
    if len(sys.argv) < 2:
        print('Cara pakai:')
        print('  python recon_website_final_v2.py daftar_url.txt')
        print('')
        print('  daftar_url.txt berisi satu URL per baris, contoh:')
        print('    https://target1.com')
        print('    target2.com')
        print('    # ini komentar, akan diabaikan')
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f'[!] File tidak ditemukan: {input_path}')
        sys.exit(1)
    urls = read_urls_from_file(input_path)
    if not urls:
        print(f'[!] Tidak ada URL valid di dalam {input_path}')
        sys.exit(1)
    print(f'=== Bulk recon: {len(urls)} target dari {input_path.name} ===\n')
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)
    all_results = []
    for i, url in enumerate(urls, start=1):
        log(f'\n############################################')
        log(f'# Target {i}/{len(urls)}: {url}')
        log(f'############################################')
        target_result = recon_single_target(url, log)
        all_results.append(target_result)
    output_data = {'input_file': str(input_path.name), 'scanned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'total_targets': len(urls), 'results': all_results}
    result_filename = f'{input_path.stem}_results.json'
    with open(result_filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    log_filename = 'log.txt'
    with open(log_filename, 'a', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
        f.write('\n\n' + '=' * 70 + '\n\n')
    print(f'\n[✓] Hasil recon (JSON) disimpan ke: {result_filename}')
    print(f'[✓] Log proses lengkap disimpan (append) ke file: {log_filename}')
if __name__ == '__main__':
    main()