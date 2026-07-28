# 🛡️ ProxyForge

**Automated Proxy Validation & Rotation Engine**

ProxyForge adalah sistem (*pipeline*) berbasis Python yang dirancang untuk secara otomatis mengambil, memvalidasi, menyimpan, dan merotasi *public proxies*. Alat ini sangat berguna untuk keperluan pengambilan data atau integrasi sistem agar identitas IP asli dapat dikelola dan dilindungi secara mandiri melalui *round-robin routing*.

---

## ✨ Fitur Utama
- **Multi-Source Aggregation**: Mengambil proxy dari berbagai sumber publik sekaligus (agregasi hingga 9000+ proxy mentah).
- **Concurrent Validation**: Menguji ratusan proksi secara bersamaan (paralel) dengan kecepatan tinggi menggunakan `asyncio` & `aiohttp`.
- **Auto-Rotation & Lazy Eviction**: Otomatis mengganti proksi yang mati atau mengalami *timeout* di tengah jalan tanpa membuat aplikasi mengalami *crash* (Fault-tolerant).
- **Daemon Mode**: Bisa dijalankan di *background* untuk otomatis memperbarui (*auto-refresh*) daftar proxy aktif setiap beberapa jam.
- **Framework Agnostic**: Menggunakan satu memori file ringan (`.json`) yang siap dibaca oleh *requests*, *httpx*, maupun *Scrapy*.

---

## 🏗️ Arsitektur Sistem

```text
[Sumber Eksternal] (Beragam GitHub List / API)
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
 └─────────────────────────┘
       │
       ▼
 ┌─────────────────────────┐
 │      ProxyRotator       │ (M4 & M5: Rotasi 
 │  (Round-Robin + Evict)  │      Round-Robin & Retry)
 └─────────────┬───────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
 Terminal   Scrapy      HTTPX /
   CLI     Middleware   Requests
```

---

## 🚀 Instalasi

1. **Clone repository ini**:
   ```bash
   git clone https://github.com/yourname/proxyforge.git
   cd proxyforge
   ```

2. **Gunakan Virtual Environment (Sangat Direkomendasikan)**:
   ```bash
   python -m venv venv
   
   # Untuk Windows:
   .\venv\Scripts\activate
   
   # Untuk Linux/Mac:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Panduan Penggunaan (Terminal / CLI)

Semua perintah utama diakses melalui *entry-point* `main.py`.

### 1. Mencari & Memvalidasi Proxy (`validate`)
Perintah ini akan menyedot list proksi terbaru, mengetesnya secara simultan, dan menyimpan IP yang benar-benar **hidup** (beserta informasi statistik latency dan lokasinya) ke dalam file `working_proxies.json`.

```bash
# Contoh pemakaian agresif:
python main.py validate --concurrency 200 --timeout 6 --anonymity elite anonymous unknown
```

**Mode Otomatis (Daemon)**
Bila Anda ingin skrip berjalan diam-diam tanpa henti untuk memperbarui proksi setiap 1 jam (3600 detik):
```bash
python main.py validate --daemon --interval 3600
```

| Parameter | Default | Keterangan |
| --- | --- | --- |
| `--concurrency` | `100` | Jumlah IP maksimal yang di-*ping* secara paralel dalam 1 waktu. |
| `--timeout` | `8` | Batas toleransi waktu tunggu (detik) untuk koneksi *ping*. |
| `--anonymity` | `elite anonymous unknown` | Memfilter tingkat anonimitas. Secara *default* membuang proxy `transparent`. |
| `--daemon` | `False` | Menjalankan program secara rekursif (berulang-ulang) layaknya server *background*. |
| `--interval` | `1800` | Waktu jeda untuk eksekusi ulang daemon (dalam detik). |

---

### 2. Menggunakan Proxy ke Target URL (`fetch`)
Menggunakan proxy yang sudah dikumpulkan tadi untuk mengakses sebuah *website* tujuan secara bergilir.

```bash
python main.py fetch "https://httpbin.org/ip" --count 5
```

| Parameter | Default | Keterangan |
| --- | --- | --- |
| `--count` | `1` | Berapa jumlah siklus permintaan (request) yang akan ditembakkan. Menggunakan proksi yang berbeda-beda. |
| `--retries` | `3` | Apabila proxy putus/mati saat digunakan, sistem akan langsung menendang IP tersebut dan mencari IP pengganti hingga maksimal N retries. |
| `--timeout` | `10` | Batas waktu respon dari web target. |

---

### 3. Memantau Ketersediaan Proxy (`info`)
Melihat ringkasan data, jumlah ketersediaan, kecepatan ping (*latency*), dan distribusi negara (*country distribution*) dari pool saat ini:
```bash
python main.py info
```

---

## 🧩 Integrasi ke dalam Kode Python Anda

Anda dapat menyisipkan `ProxyRotator` ini langsung ke dalam baris kode skrip Python Anda sehari-hari (*bot*, *crawler*, dll).

### A. Integrasi Paling Dasar (Otomatis Retry)
```python
from proxyforge.core.pool import ProxyPool
from proxyforge.core.rotator import ProxyRotator

# 1. Muat database proksi aktif dari file fisik
pool = ProxyPool.load("working_proxies.json")

# 2. Inisialisasi Rotator dengan batas toleransi kegagalan = 3x
rotator = ProxyRotator(pool, max_retries=3)

# 3. Kirim permintaan (Request). 
# Sistem akan mengurus masalah koneksi putus atau pergantian proxy secara otomatis.
target_url = "https://api.ipify.org?format=json"
response = rotator.fetch(target_url, timeout=10)

if response:
    print("Berhasil Terkoneksi menggunakan IP Masking:")
    print(response.json())
```

### B. Menggunakan Scrapy Middleware (Opsional)
Bila *pipeline* ini berada di dalam *project* Scrapy, konfigurasikan *Middleware*-nya pada `settings.py`:
```python
DOWNLOADER_MIDDLEWARES = {
    "proxyforge.adapters.scrapy_middleware.ProxyForgeMiddleware": 750,
}
PROXYFORGE_POOL_PATH = "working_proxies.json"
```

---

## 📝 Catatan Tambahan

- **Daya Tahan Proxy Publik**: Proxy gratisan sering mati secara mendadak atau *down* dalam hitungan menit. Sangat disarankan untuk rutin memperbarui database (melalui fitur `--daemon`) untuk menjaga ketersediaan amunisi.
- **Log Pelaporan**: Setiap kali perintah `validate` selesai berjalan, selain `working_proxies.json`, ia juga merangkum metrik performanya di dalam file `report.json`.
- **Edukasi & Riset**: Alat ini diciptakan khusus untuk riset rekayasa perangkat lunak dan studi akademis terkait jaringan terdistribusi dan reliabilitas koneksi.
