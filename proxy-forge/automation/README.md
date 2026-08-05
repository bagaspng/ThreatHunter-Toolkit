# 🤖 Form Automation & Captcha Solver Module

Modul orkestrasi automasi form *headless* menggunakan arsitektur hibrida modern (**curl_cffi**, **selectolax**, dan **Playwright**) dengan struktur datar (*flat layout*) tanpa *subfolder* berlapis.

---

## 🛠️ Komponen & Struktur Modul (Flat Layout)

```text
automation/
├── automation.py        # Phase 3: Pure Async Orchestrator + Fault Tolerance Loop
├── probe.py             # Phase 1: Lightweight HTTP Probe (curl_cffi + selectolax) -> PageProfile
├── router.py            # Phase 2: Route Dispatcher (Static vs SPA) -> SubmissionResult
├── static.py            # Static Route Handler (curl_cffi POST)
├── spa.py               # SPA Route Handler (Playwright Async + Resource Blocking)
├── solver.py            # Existing Captcha Regex Solver
├── config.py            # Configuration & Selectors
├── contracts.py         # Data Contracts (PageProfile, SubmissionResult) & Custom Exceptions
└── README.md            # Dokumentasi Modul
```

---

## 💻 Cara Menjalankan

### Option A: Melalui CLI Utama (Rekomendasi)
Dapat dijalankan langsung dari direktori *root* menggunakan perintah ringkas `main.py`:

```bash
# Menjalankan 5 siklus pengujian (5 IP proxy berbeda secara bergantian)
python main.py test-captcha --iterations 5

# Menjalankan pengujian dengan target URL kustom
python main.py test-captcha --iterations 3 --url "https://example.com"
```

### Option B: Eksekusi Langsung dari Folder Modul
Dapat juga dijalankan langsung sebagai modul standalone:

```bash
python automation/automation.py --iterations 5
```
