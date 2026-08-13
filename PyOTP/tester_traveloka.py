import urllib.request
import urllib.parse
import urllib.error
import json
import ssl
import time

ssl._create_default_https_context = ssl._create_unverified_context

BASE = "https://www.traveloka.com"
HEADERS_BASE = {
    "Content-Type": "application/json",
    "x-domain": "user",
    "tv-language": "id_ID",
    "tv-country": "ID",
    "tv-currency": "IDR",
    "x-client-interface": "desktop",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}


def http(method, path, data=None, extra_headers=None):
    url = f"{BASE}{path}"
    headers = dict(HEADERS_BASE)
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status, resp.read().decode(errors="replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace"), dict(e.headers)
    except Exception as e:
        return 0, str(e), {}


def show(label, code, body):
    print(f"    {label}: HTTP {code}")
    try:
        data = json.loads(body)
        print(f"    Response: {json.dumps(data, indent=2)[:500]}")
    except Exception:
        is_html = "<html" in body[:200].lower() or "<!doctype" in body[:200].lower()
        if is_html:
            if "Human Verification" in body:
                print("    Response: [AWS WAF CAPTCHA — Human Verification Required]")
            elif "challenge.js" in body:
                print("    Response: [AWS WAF Challenge Page]")
            else:
                print("    Response: [HTML page]")
        else:
            print(f"    Response: {body[:300]}")
    print()


def banner():
    print("=" * 55)
    print("  OTP Endpoint Tester — Traveloka")
    print("  (www.traveloka.com)")
    print("  OTP Type: Missed Call OTP")
    print("=" * 55)
    print()
    print("  CATATAN: Traveloka menggunakan binary protocol")
    print("  + AWS WAF + Sentinel anti-bot. Test endpoint")
    print("  auth via curl TERBATAS. Gunakan opsi Playwright")
    print("  untuk full test.")
    print()


def test_method(path):
    print(f"\n[*] Method test: {path}\n")
    for method in ["GET", "POST", "PUT", "DELETE"]:
        data = {} if method in ("POST", "PUT") else None
        code, body, _ = http(method, path, data)
        if code == 403:
            status = "BLOCKED"
        elif code == 405:
            status = "BLOCKED (binary required)"
        elif code == 401:
            status = "AUTH REQUIRED"
        else:
            status = ""
        print(f"    {method:6s} → HTTP {code} {status}")
    print()


def test_all_methods():
    print("\n[*] Method test — semua endpoint\n")
    endpoints = [
        "/api/v2/user/whoami",
        "/api/v2/user/useridchecking",
        "/api/v2/user/signup",
        "/api/v2/user/signin",
        "/api/v2/user/emaildomainlist",
        "/api/v2/user/updatedevice",
        "/api/v2/user/requestsignuptoken",
    ]
    for ep in endpoints:
        test_method(ep)


def test_whoami():
    print("\n[*] Test /api/v2/user/whoami\n")
    code, body, headers = http("POST", "/api/v2/user/whoami",
                                {"fields": [], "data": {}, "clientInterface": "desktop"})
    show("POST /api/v2/user/whoami", code, body)
    if code == 401:
        print("    → Cookie session diperlukan (proteksi BAIK)")
    print()


def test_auth_endpoints():
    print("\n[*] Test endpoint auth (binary protocol)\n")
    endpoints = {
        "/api/v2/user/useridchecking": "Cek nomor HP terdaftar",
        "/api/v2/user/signup": "Register + trigger OTP",
        "/api/v2/user/signin": "Login",
    }
    for ep, desc in endpoints.items():
        print(f"  --- {ep} ({desc}) ---")

        code_json, body_json, _ = http("POST", ep, {"data": {"phone": "+620000000000"}})
        print(f"    JSON payload  → HTTP {code_json}", end="")
        if code_json == 405:
            print(" (DITOLAK — butuh binary protocol)")
        elif "Human Verification" in body_json:
            print(" (AWS WAF CAPTCHA triggered!)")
        else:
            print()

        code_bin, body_bin, _ = http("POST", ep, None,
                                      {"Content-Type": "application/octet-stream"})
        print(f"    Binary empty  → HTTP {code_bin}", end="")
        if code_bin == 405:
            print(" (DITOLAK — butuh WAF cookie + sentinel)")
        elif "Human Verification" in body_bin:
            print(" (AWS WAF CAPTCHA triggered!)")
        else:
            print()
        print()


def test_rate_limit():
    print("\n[*] Rate limit test — 8 rapid requests ke whoami\n")
    results = []
    for i in range(8):
        code, _, _ = http("POST", "/api/v2/user/whoami",
                           {"fields": [], "data": {}, "clientInterface": "desktop"})
        results.append(code)
        print(f"    #{i+1}: HTTP {code}")
    print()
    if all(c == 401 for c in results):
        print("    Semua request mendapat 401 (auth required)")
        print("    Rate limit TIDAK terdeteksi di layer ini")
        print("    (WAF + sentinel mencegah abuse di layer atas)")
    elif any(c == 429 for c in results):
        print("    RATE LIMIT AKTIF! (429 Too Many Requests)")
    print()


def test_security_headers():
    print("\n[*] Security headers analysis\n")
    headers = {}
    try:
        req = urllib.request.Request(f"{BASE}/id-id",
                                      headers={"User-Agent": HEADERS_BASE["User-Agent"]})
        resp = urllib.request.urlopen(req, timeout=15)
        headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        headers = dict(e.headers)
    except Exception:
        print("    Gagal mengambil headers")
        return

    checks = {
        "strict-transport-security": ("HSTS", True),
        "x-frame-options": ("Clickjacking Protection", True),
        "x-content-type-options": ("MIME Sniffing Protection", True),
        "referrer-policy": ("Referrer Policy", True),
        "permissions-policy": ("Permissions Policy", True),
        "content-security-policy": ("CSP", True),
        "x-powered-by": ("Server Info Disclosure", False),
    }

    for header, (name, should_exist) in checks.items():
        val = None
        for k, v in headers.items():
            if k.lower() == header:
                val = v
                break
        if val:
            if should_exist:
                preview = val[:80] + "..." if len(str(val)) > 80 else val
                print(f"    + {name}: {preview}")
            else:
                print(f"    ! {name}: {val} (SEHARUSNYA TIDAK ADA)")
        else:
            if should_exist:
                print(f"    - {name}: TIDAK ADA")
            else:
                print(f"    + {name}: Tidak terexpose (BAGUS)")
    print()


def test_waf():
    print("\n[*] AWS WAF detection test\n")
    code, body, _ = http("POST", "/api/v2/user/signup",
                          {"data": {"phone": "+620000000000"}})
    if "Human Verification" in body or "challenge.js" in body:
        print("    AWS WAF CAPTCHA AKTIF!")
        print("    Request tanpa WAF cookie → Human Verification page")
        print("    Ini mencegah automated abuse secara efektif")
    elif code == 405:
        print("    Request ditolak (405) — binary protocol required")
        print("    AWS WAF mungkin aktif tapi belum trigger captcha")
    else:
        print(f"    HTTP {code} — response: {body[:200]}")

    print(f"\n    WAF domain: d9253bf4bdfd.edge.sdk.awswaf.com")
    print(f"    WAF verify: /d9253bf4bdfd/1fcfec27aa97/mp_verify")
    print()


def full_test(phone):
    print(f"\n{'='*55}")
    print(f"  TRAVELOKA FULL AUTO TEST")
    print(f"  Phone: {phone}")
    print(f"{'='*55}\n")

    print("[1/6] Security headers")
    test_security_headers()

    print("[2/6] Whoami (session check)")
    test_whoami()

    print("[3/6] Method restriction test")
    test_all_methods()

    print("[4/6] Binary protocol endpoints")
    test_auth_endpoints()

    print("[5/6] AWS WAF detection")
    test_waf()

    print("[6/6] Rate limit test")
    test_rate_limit()

    print("=" * 55)
    print("  KESIMPULAN")
    print("=" * 55)
    print()
    print("  Traveloka memiliki proteksi BERLAPIS:")
    print("  1. AWS WAF CAPTCHA — mencegah bot")
    print("  2. Sentinel anti-bot — token + signals")
    print("  3. Binary protocol — bukan JSON biasa")
    print("  4. Cookie auth — session required")
    print("  5. Method restriction — hanya POST (403)")
    print()
    print("  OTP Type: Missed Call (4 digit terakhir)")
    print("  Automated abuse: SANGAT SULIT")
    print()
    print("  Untuk test OTP secara interaktif,")
    print("  gunakan opsi [9] Playwright test.")
    print()


def playwright_test(phone):
    print(f"\n[*] Playwright interactive OTP test — {phone}\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    Playwright belum terinstall!")
        print("    Install: pip install playwright && playwright install chromium")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/150.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()

        captured = []

        def on_request(req):
            if "/api/v2/user/" in req.url:
                captured.append({
                    "method": req.method,
                    "url": req.url,
                    "ct": req.headers.get("content-type", "?"),
                })

        def on_response(resp):
            if "/api/v2/user/" in resp.url:
                try:
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        body = resp.json()
                    else:
                        body = f"[binary {len(resp.body())} bytes]"
                except Exception:
                    body = "[could not read]"
                for c in captured:
                    if c["url"] == resp.url and "response" not in c:
                        c["response"] = {"status": resp.status, "body": body}
                        break

        page.on("request", on_request)
        page.on("response", on_response)

        print("    [1] Navigating to login page...")
        page.goto("https://www.traveloka.com/id-id/login", wait_until="networkidle")
        page.wait_for_timeout(2000)

        print("    [2] Clicking 'Metode lain'...")
        try:
            page.get_by_role("button", name="Metode lain").click()
        except Exception:
            print("    → Tombol 'Metode lain' tidak ditemukan, coba langsung...")
        page.wait_for_timeout(1000)

        print(f"    [3] Entering phone number: {phone}...")
        try:
            page.get_by_test_id("auth-username").fill(phone)
        except Exception:
            inp = page.locator("input[placeholder*='handphone']").first
            inp.fill(phone)
        page.wait_for_timeout(1500)

        btn_text = ""
        for name in ("Daftar", "Lanjutkan"):
            btn = page.get_by_role("button", name=name)
            if btn.count() > 0 and btn.is_visible():
                btn_text = name
                break

        if btn_text == "Daftar":
            print(f"    → Nomor BELUM terdaftar (tombol: {btn_text})")
        elif btn_text == "Lanjutkan":
            print(f"    → Nomor SUDAH terdaftar (tombol: {btn_text})")
        else:
            print("    → Status tidak jelas, mencari tombol submit...")
            for btn_el in page.get_by_role("button").all():
                t = (btn_el.text_content() or "").strip()
                if t and t not in ("Kembali", "Close", "Ke Halaman Utama Traveloka"):
                    btn_text = t
                    break

        if not btn_text:
            print("    → Tidak ada tombol submit! Batal.")
            browser.close()
            return

        print(f"    [4] Clicking '{btn_text}'...")
        page.get_by_role("button", name=btn_text).click()
        page.wait_for_timeout(2000)

        dialog = page.locator("[role='dialog']")
        if dialog.count() > 0 and dialog.is_visible():
            dialog_text = dialog.text_content() or ""
            if "4 angka terakhir" in dialog_text:
                print("\n    ╔══════════════════════════════════════╗")
                print("    ║  MISSED CALL OTP DIALOG DETECTED!    ║")
                print("    ║  'Kode Anda adalah 4 angka terakhir  ║")
                print("    ║  dari nomor yang akan menelepon Anda' ║")
                print("    ╚══════════════════════════════════════╝")

                confirm = input("\n    Kirim missed call ke nomor? (y/n): ").strip().lower()
                if confirm == "y":
                    page.get_by_role("button", name="Verifikasi").click()
                    page.wait_for_timeout(3000)

                    page_text = page.locator("[role='dialog']").text_content() or ""
                    if "Masukkan Kode Verifikasi" in page_text:
                        print("\n    → Halaman verifikasi OTP!")
                        print("    → Missed call sedang dikirim...")

                        h1 = page.locator("h1")
                        if h1.count() > 0:
                            prefix = h1.text_content() or ""
                            if prefix.startswith("62"):
                                print(f"    → Prefix nomor penelepon: {prefix}____")
                                print(f"    → Masukkan 4 digit terakhir dari nomor penelepon")

                        otp = input("\n    Masukkan 4 digit OTP: ").strip()
                        if len(otp) == 4 and otp.isdigit():
                            textbox = page.locator("input").first
                            if textbox.is_visible():
                                textbox.focus()
                                for digit in otp:
                                    page.keyboard.press(digit)
                                    page.wait_for_timeout(200)

                                page.wait_for_timeout(1000)
                                verify_btn = page.get_by_role("button", name="Verifikasi")
                                if verify_btn.is_visible() and verify_btn.is_enabled():
                                    verify_btn.click()
                                    page.wait_for_timeout(3000)
                                    print(f"\n    → OTP {otp} submitted!")

                                    body_text = page.text_content("body") or ""
                                    if "berhasil" in body_text.lower():
                                        print("    → VERIFIKASI BERHASIL!")
                                    elif "salah" in body_text.lower():
                                        print("    → OTP SALAH!")
                                    elif "batas" in body_text.lower():
                                        print("    → RATE LIMIT! Terlalu banyak percobaan")
                                    else:
                                        print(f"    → Page text: {body_text[:200]}")
                                else:
                                    print("    → Tombol Verifikasi masih disabled")
                        else:
                            print("    → OTP harus 4 digit angka")
                    else:
                        print(f"    → Unexpected dialog: {page_text[:200]}")
                else:
                    print("    → Dibatalkan")
            else:
                print(f"    → Dialog non-OTP: {dialog_text[:200]}")

        print("\n    === Captured API Requests ===")
        for c in captured:
            resp = c.get("response", {})
            print(f"    {c['method']} {c['url']}")
            print(f"      Content-Type: {c.get('ct', '?')}")
            if resp:
                status = resp.get("status", "?")
                body = resp.get("body", "")
                print(f"      Status: {status}")
                if isinstance(body, dict):
                    print(f"      Data: {json.dumps(body, indent=2)[:300]}")
                else:
                    print(f"      Data: {str(body)[:200]}")
            print()

        print("\n    Browser tetap terbuka. Tekan Enter untuk menutup...")
        input()
        browser.close()


def main():
    banner()
    while True:
        print("[1] Full auto test (curl-based)")
        print("[2] Security headers")
        print("[3] Method test (semua endpoint)")
        print("[4] Auth endpoint test (binary)")
        print("[5] AWS WAF detection")
        print("[6] Rate limit test")
        print("[7] Whoami test")
        print("[9] Playwright interactive test (FULL OTP)")
        print("[0] Keluar")

        c = input("\nPilih: ").strip()
        if c == "0":
            print("\nSelesai.")
            break

        if c == "1":
            phone = input("Nomor HP (contoh 08892917305): ").strip()
            if not phone.startswith("+62"):
                phone = "+62" + phone.lstrip("0")
            full_test(phone)
        elif c == "2":
            test_security_headers()
        elif c == "3":
            test_all_methods()
        elif c == "4":
            test_auth_endpoints()
        elif c == "5":
            test_waf()
        elif c == "6":
            test_rate_limit()
        elif c == "7":
            test_whoami()
        elif c == "9":
            phone = input("Nomor HP (contoh 08892917305): ").strip()
            if not phone.startswith("0") and not phone.startswith("+"):
                phone = "0" + phone
            playwright_test(phone)
        print()


if __name__ == "__main__":
    main()
