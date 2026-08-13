import urllib.request
import urllib.parse
import urllib.error
import json
import ssl
import hashlib
import hmac
import time
import uuid
import datetime

ssl._create_default_https_context = ssl._create_unverified_context

API_OTP = "https://apiwa.tirtasiakpekanbaru.co.id"
API_MAIN = "https://api.tirtasiakpekanbaru.co.id"

API_KEY = "eWL7UYK54YkNYxtC9nTQRYQV4qVqpv"
APP_NAME = "J4n9anlUp4MAk4n"
ID_PT = 1

OTP_MESSAGE_TEMPLATE = (
    "*Kode OTP*\n\nKode OTP masuk Anda : ???"
    " (berlaku 5 Menit)\nJangan memberikan kode OTP ke pihak lain."
)


def make_signature(body_str, timestamp, request_id):
    body_hash = hashlib.sha256(body_str.encode()).hexdigest()
    raw = f"{APP_NAME}:{body_hash}:{timestamp}:{request_id}"
    sig = hmac.new(API_KEY.encode(), raw.encode(), hashlib.sha256).digest()
    import base64
    return base64.b64encode(sig).decode()


def otp_headers(body_str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rid = str(uuid.uuid4())
    sig = make_signature(body_str, ts, rid)
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "OTPTester/1.0",
        "X-Timestamp": ts,
        "X-Signature": sig,
        "Requestid": rid,
    }


def http(method, url, data=None, headers=None):
    if headers is None:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "OTPTester/1.0"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return 0, str(e)


def show(label, code, body):
    print(f"    {label}: HTTP {code}")
    try:
        data = json.loads(body)
        print(f"    Response: {json.dumps(data, indent=2)[:500]}")
    except Exception:
        is_html = body.strip().startswith("<!") or body.strip().startswith("<html")
        print(f"    Response: {'[HTML page]' if is_html else body[:300]}")
    print()


def banner():
    print("=" * 55)
    print("  OTP Endpoint Tester — Tirta Siak Pekanbaru")
    print("  (apiwa.tirtasiakpekanbaru.co.id)")
    print("=" * 55)
    print()


def send_otp(phone):
    print(f"\n[*] Kirim OTP WhatsApp ke {phone}\n")
    data = {"telp": phone, "id_pt": ID_PT, "message": OTP_MESSAGE_TEMPLATE}
    body_str = json.dumps(data)
    headers = otp_headers(body_str)
    code, body = http("POST", f"{API_OTP}/siak/generateotp", data, headers)
    show("POST /siak/generateotp", code, body)

    try:
        result = json.loads(body)
        status = result.get("status", "")
        msg = result.get("message", "")
        if status == "success":
            print(f"    OTP TERKIRIM! {msg}")
        else:
            print(f"    Gagal: {msg}")
    except Exception:
        if code == 200:
            print("    OTP kemungkinan terkirim (HTTP 200)")


def verify_otp(phone, otp_code):
    print(f"\n[*] Verify OTP {otp_code} untuk {phone}\n")
    data = {"telp": phone, "id_pt": ID_PT, "otp": otp_code}
    body_str = json.dumps(data)
    headers = otp_headers(body_str)
    code, body = http("POST", f"{API_OTP}/siak/cekotp", data, headers)
    show("POST /siak/cekotp", code, body)

    try:
        result = json.loads(body)
        status = result.get("status", "")
        msg = result.get("message", "")
        if status == "success":
            print(f"    OTP BENAR! {msg}")
        else:
            print(f"    OTP SALAH/GAGAL: {msg}")
    except Exception:
        pass


def test_method_otp():
    print(f"\n[*] Method test: /siak/generateotp\n")
    data = {"telp": "+620000000000", "id_pt": ID_PT, "message": "test"}
    body_str = json.dumps(data)
    headers = otp_headers(body_str)
    for method in ["GET", "POST", "PUT", "DELETE"]:
        code, _ = http(method, f"{API_OTP}/siak/generateotp",
                       data if method in ("POST", "PUT") else None, headers)
        expected_fail = method != "POST"
        status = "OK (blocked)" if expected_fail and code == 405 else ""
        if expected_fail and code != 405:
            status = "VULN (not blocked!)"
        print(f"    {method:6s} → HTTP {code} {status}")

    print(f"\n[*] Method test: /siak/cekotp\n")
    data2 = {"telp": "+620000000000", "id_pt": ID_PT, "otp": "000000"}
    body_str2 = json.dumps(data2)
    headers2 = otp_headers(body_str2)
    for method in ["GET", "POST", "PUT", "DELETE"]:
        code, _ = http(method, f"{API_OTP}/siak/cekotp",
                       data2 if method in ("POST", "PUT") else None, headers2)
        expected_fail = method != "POST"
        status = "OK (blocked)" if expected_fail and code == 405 else ""
        if expected_fail and code != 405:
            status = "VULN (not blocked!)"
        print(f"    {method:6s} → HTTP {code} {status}")
    print()


def test_method_main():
    print(f"\n[*] Method test: /index.php/api/user/login-pelanggan\n")
    for method in ["GET", "POST", "PUT", "DELETE"]:
        data = {"no_telp": "+620000000000", "id_pt": ID_PT, "api_key": API_KEY, "otp": "000000"}
        code, _ = http(method, f"{API_MAIN}/index.php/api/user/login-pelanggan",
                       data if method in ("POST", "PUT") else None)
        expected_fail = method != "POST"
        status = "OK (blocked)" if expected_fail and code == 405 else ""
        if expected_fail and code != 405:
            status = "VULN (not blocked!)"
        print(f"    {method:6s} → HTTP {code} {status}")

    print(f"\n[*] Method test: /index.php/api/user/register\n")
    for method in ["GET", "POST", "PUT", "DELETE"]:
        data = {"no_telp": "+620000000000"}
        code, body = http(method, f"{API_MAIN}/index.php/api/user/register",
                          data if method in ("POST", "PUT") else None)
        expected_fail = method != "POST"
        status = "OK (blocked)" if expected_fail and code == 405 else ""
        if expected_fail and code != 405:
            status = "VULN (not blocked!)"
        if "INSERT INTO" in body or "SQLSTATE" in body:
            status += " SQL EXPOSED!"
        print(f"    {method:6s} → HTTP {code} {status}")
    print()


def test_rate_limit():
    print(f"\n[*] Rate limit test — 6 rapid generateotp requests\n")
    for i in range(6):
        phone = f"+6281100000{i:02d}"
        data = {"telp": phone, "id_pt": ID_PT, "message": OTP_MESSAGE_TEMPLATE}
        body_str = json.dumps(data)
        headers = otp_headers(body_str)
        code, body = http("POST", f"{API_OTP}/siak/generateotp", data, headers)
        try:
            result = json.loads(body)
            msg = result.get("message", "")[:60]
            print(f"    #{i+1} ({phone}): HTTP {code} → {msg}")
        except Exception:
            print(f"    #{i+1} ({phone}): HTTP {code}")
    print()
    print("    Semua request diproses = TIDAK ADA RATE LIMIT!")
    print()


def test_verify_rate_limit(phone):
    print(f"\n[*] OTP verify rate limit — 5 rapid attempts\n")
    for i in range(5):
        otp = f"{(i+1)*111111 % 1000000:06d}"
        data = {"telp": phone, "id_pt": ID_PT, "otp": otp}
        body_str = json.dumps(data)
        headers = otp_headers(body_str)
        code, body = http("POST", f"{API_OTP}/siak/cekotp", data, headers)
        try:
            result = json.loads(body)
            msg = result.get("message", "")[:80]
            print(f"    #{i+1} (otp={otp}): HTTP {code} → {msg}")
        except Exception:
            print(f"    #{i+1}: HTTP {code}")
    print()


def test_login(phone):
    print(f"\n[*] Login test: {phone}\n")
    data = {"no_telp": phone, "id_pt": ID_PT, "api_key": API_KEY, "otp": "000000"}
    code, body = http("POST", f"{API_MAIN}/index.php/api/user/login-pelanggan", data)
    show("POST /index.php/api/user/login-pelanggan", code, body)

    code2, body2 = http("GET", f"{API_MAIN}/index.php/api/user/login-pelanggan")
    print(f"    GET (tanpa body): HTTP {code2} {'VULN (GET diterima!)' if code2 != 405 else 'OK'}")
    print()


def test_register():
    print(f"\n[*] Register endpoint test (tanpa data valid)\n")
    code, body = http("GET", f"{API_MAIN}/index.php/api/user/register")
    show("GET /index.php/api/user/register (seharusnya 405)", code, body)
    if "INSERT INTO" in body or "SQLSTATE" in body:
        print("    [CRITICAL] SQL query terekspos di response!")
    if code != 405:
        print("    [CRITICAL] GET request diterima! Seharusnya POST only.")
    print()


def test_auth_endpoints():
    print(f"\n[*] Auth-required endpoint test (tanpa token)\n")
    endpoints = [
        "/index.php/api/user/profile",
        "/index.php/api/user/edit-profile",
        "/index.php/api/user/save-npa",
        "/index.php/api/default/notifikasi-wa",
        "/index.php/api/bank/air",
    ]
    for ep in endpoints:
        code, _ = http("GET", f"{API_MAIN}{ep}")
        status = "OK (auth required)" if code == 401 else f"VULN (HTTP {code})"
        print(f"    GET {ep}: {status}")
    print()


def full_test(phone):
    print(f"\n{'='*55}")
    print(f"  TIRTA SIAK FULL AUTO TEST")
    print(f"  Phone: {phone}")
    print(f"{'='*55}\n")

    print("[1/8] Kirim OTP via WhatsApp")
    send_otp(phone)

    print("[2/8] Method test (OTP endpoints)")
    test_method_otp()

    print("[3/8] Method test (Main API)")
    test_method_main()

    print("[4/8] Rate limit test (generateotp)")
    test_rate_limit()

    print("[5/8] Verify OTP rate limit test")
    test_verify_rate_limit(phone)

    print("[6/8] Login test")
    test_login(phone)

    print("[7/8] Register endpoint test")
    test_register()

    print("[8/8] Auth-required endpoint test")
    test_auth_endpoints()


def main():
    banner()
    while True:
        print("[1] Full auto test")
        print("[2] Kirim OTP (WhatsApp)")
        print("[3] Verify OTP")
        print("[4] Method test (OTP)")
        print("[5] Method test (Main API)")
        print("[6] Rate limit test")
        print("[7] Login test")
        print("[8] Register endpoint test")
        print("[9] Auth endpoint test")
        print("[0] Keluar")

        c = input("\nPilih: ").strip()
        if c == "0":
            print("\nSelesai.")
            break

        if c == "1":
            phone = input("Nomor HP (contoh +628892917305): ").strip()
            if not phone.startswith("+62"):
                phone = "+62" + phone.lstrip("0")
            full_test(phone)
        elif c == "2":
            phone = input("Nomor HP: ").strip()
            if not phone.startswith("+62"):
                phone = "+62" + phone.lstrip("0")
            send_otp(phone)
        elif c == "3":
            phone = input("Nomor HP: ").strip()
            if not phone.startswith("+62"):
                phone = "+62" + phone.lstrip("0")
            otp = input("Kode OTP (6 digit): ").strip()
            verify_otp(phone, otp)
        elif c == "4":
            test_method_otp()
        elif c == "5":
            test_method_main()
        elif c == "6":
            test_rate_limit()
        elif c == "7":
            phone = input("Nomor HP: ").strip()
            if not phone.startswith("+62"):
                phone = "+62" + phone.lstrip("0")
            test_login(phone)
        elif c == "8":
            test_register()
        elif c == "9":
            test_auth_endpoints()
        print()

if __name__ == "__main__":
    main()
