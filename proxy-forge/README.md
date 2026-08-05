# 🛡️ ProxyForge

**Automated Proxy Validation, Sticky Rotation Engine & Hybrid Form Automation Engine**

ProxyForge adalah sistem (_pipeline_) berbasis Python yang dirancang untuk mengambil, memvalidasi, menyimpan, dan merotasi _public proxies_ secara otomatis. Sistem ini dilengkapi dengan modul pengujian automasi _Form & Native Captcha Solver_ hibrida (**curl_cffi**, **selectolax**, **Playwright**) yang mendukung rotasi IP dinamis _Sticky-Session Exhaustion_ secara _fault-tolerant_.

---

## ✨ Fitur Utama

- **Multi-Source Aggregation**: Agregasi proxy publik dari 8 sumber terpercaya sekaligus (hingga 9000+ proxy mentah).
- **High-Concurrency Validation**: Menguji ratusan proksi secara bersamaan (paralel) menggunakan `asyncio` & `aiohttp`.
- **Sticky-Session Exhaustion**: Mengunci 1 IP proxy hingga terbukti terbakar (_burned_) oleh target, lalu otomatis di-evict dan digantikan oleh proxy baru tanpa kehilangan progres siklus.
- **Hybrid Automation Engine (Probe + Playwright)**:
  - **Phase 1 Lightweight Probe (`curl_cffi` + `selectolax`)**: Deteksi cepat SPA Score & Honeypot tanpa muka peramban.
  - **Phase 2 SPA Submitter (`Playwright Async`)**: Membuka peramban headless dengan pemblokiran gambar, CSS, font, & domain _tracker_ untuk menghemat RAM dan kuota.
- **In-Memory PageProfile Caching & Fast Ping**: Menghindari ekstraksi HTML berulang dengan _caching_ profil halaman dan pengujian koneksi proxy kilat ($\approx 0.5$ detik).
- **Clear 5-Step Progress Output**: Indikator progres CLI 5-tahap transparan (`[1/5]` s/d `[5/5]`) yang memudahkan identifikasi titik kegagalan proxy.
- **Flat Module Layout**: Modul `automation/` disusun rapi tanpa _subfolder_ berlapis.

---

## 🏗️ Arsitektur Sistem

```text
[Sumber Eksternal] (8 Sumber API & Public Proxy List)
       │ (M1: Fetch & Deduplicate)
       ▼
 ┌─────────────────────────┐
 │     ProxyValidator      │
 │  (M2: Async Ping &      │
 │       Filter Anonymity) │
 └─────────────────────────┘
       │
       ▼
 ┌─────────────────────────┐
 │       ProxyPool         │ (M3: Perankingan Skor &
 │  (working_proxies.json) │      Save ke Disk Lokal)
 └─────────────┬───────────┘
               │
    ┌──────────┴────────────────────────────────┐
    ▼                                           ▼
 ┌─────────────────────────┐     ┌─────────────────────────────┐
 │      ProxyRotator       │     │     automation/ Module      │
 │(Sticky-Session Exhaust) │     │ (Probe -> Route -> Submit)  │
 └─────────────┬───────────┘     └──────────────┬──────────────┘
               │                                │
    ┌──────────┼──────────┐                     │
    ▼          ▼          ▼                     ▼
 Terminal   Scrapy      HTTPX /           Form Automation &
   CLI     Middleware   Requests         Captcha Solver Test
```

---

## 🚀 Instalasi & Persiapan

1. **Clone repository ini**:

   ```bash
   git clone https://github.com/yourname/proxyforge.git
   cd proxy-forge-implement
   ```

2. **Gunakan Virtual Environment (Sangat Direkomendasikan)**:

   ```bash
   python -m venv venv

   # Untuk Windows (PowerShell):
   .\venv\Scripts\activate

   # Untuk Linux/Mac:
   source venv/bin/activate
   ```

3. **Install Dependencies & Browser Engine**:
   ```bash
   pip install -r requirements.txt
   pip install curl_cffi selectolax playwright
   playwright install chromium
   ```

---

## 💻 Panduan Perintah CLI (`main.py`)

Seluruh perintah dapat diakses secara terpusat melalui file `main.py`.

### 1. Validasi & Kumpulkan Proxy (`validate`)

Mengambil list proksi terbaru dari internet, mengetesnya secara simultan, dan menyimpan IP yang **hidup** ke file `working_proxies.json`.

```bash
# Validasi paralel (200 konkurrensi):
python main.py validate --concurrency 200 --timeout 6 --anonymity elite anonymous unknown

# Mode Daemon (Auto-refresh di background setiap 30 menit):
python main.py validate --daemon --interval 1800
```

---

### 2. Mengakses URL Target (`fetch`)

Mengirimkan HTTP request ke target menggunakan strategi rotasi _Sticky-Session Exhaustion_.

```bash
python main.py fetch "https://httpbin.org/ip" --count 5
```

---

### 3. Informasi Pool Proxy (`info`)

Melihat statistik ketersediaan proxy, persentil _latency_, dan distribusi negara saat ini:

```bash
python main.py info
```

---

### 4. Uji Automasi Form & Captcha (`test-captcha`)

Menjalankan pengujian automasi _Form & Native Captcha Solver_ hibrida dengan indikator progres 5-tahap.

```bash
# Menjalankan 5 siklus pengujian (5 IP berbeda):
python main.py test-captcha --iterations 5

# Pengujian ke URL target kustom:
python main.py test-captcha --iterations 3 --url "https://example.com"
```

---

## 📂 Struktur Folder Proyek (Flat Layout)

```text
proxy-forge-implement/
├── main.py                    # Entrypoint CLI Utama (validate, fetch, info, test-captcha)
├── working_proxies.json       # Cache Database Proxy Aktif
├── report.json                # Laporan Ringkasan Performa Validasi
├── automation/                # Modul Automasi Form & Captcha (FLAT Layout)
│   ├── automation.py          # Phase 3: Pure Async Orchestrator & Fault-Tolerance Loop
│   ├── probe.py               # Phase 1: Lightweight Probe (curl_cffi + selectolax) + PageProfile Cache
│   ├── router.py              # Phase 2: Route Dispatcher (Static vs SPA)
│   ├── static.py              # Static Submitter Handler (curl_cffi POST)
│   ├── spa.py                 # SPA Submitter Handler (Playwright Async + Resource Blocking)
│   ├── solver.py              # Captcha Regex Solver
│   ├── contracts.py           # Data Contracts (PageProfile, SubmissionResult) & Exceptions
│   ├── config.py              # Konfigurasi Selektor & Target URL
│   └── README.md              # Dokumentasi Spesifik Modul Automasi
└── src/
    └── proxyforge/            # Core Library (ProxyPool, ProxyValidator, ProxyRotator)
```
