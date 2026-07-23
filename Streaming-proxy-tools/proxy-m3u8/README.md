# Proxy Film Diagnostic App 

Aplikasi Proxy Film Diagnostic adalah platform streaming proxy lokal berbasis **Flask** yang dirancang untuk mengatasi pemblokiran WAF (Web Application Firewall) pada server video streaming (seperti Juicy Codes, Juicy Nginx, Cloudflare, dll.). 

Aplikasi ini bertindak sebagai jembatan cerdas antara browser Anda dengan server video asli, memungkinkan pemutaran video **HLS (HTTP Live Streaming)** dan **Direct Video Stream** secara lancar tanpa hambatan `403 Forbidden`.

---

## 🚀 Fitur Utama

1. **Dual Stream Support**: 
   * **HLS Mode**: Memutar file playlist adaptif `.m3u8` dengan parser otomatis dan proxy segmen.
   * **Direct Stream Mode**: Memutar link video mentah (MP4, MKV, WebM, dll.) secara langsung menggunakan *Byte-Range Proxy*.
2. **WAF Bypass (Chrome Fingerprint Emulation)**:
   * Menggunakan library `curl_cffi` untuk meniru sidik jari TLS (*TLS Fingerprint*) dari browser Google Chrome secara sempurna saat meminta playlist utama.
3. **Byte-Range Seeking & Scrubbing**:
   * Mendukung penuh header `Range` HTTP. Pengguna bisa melakukan *seek* (lompat waktu/maju-mundur) pada video secara instan tanpa perlu menunggu video diunduh penuh.
4. **Premium Dark Mode Player & Real-time Diagnostic Log**:
   * Antarmuka minimalis cinema-style yang menampilkan log jaringan (Network requests, status code, download speed, file size) secara real-time tepat di bawah layar pemutar.
   * Loader buffering cerdas berbasis event media asli HTML5.

---

## 🛠️ Mekanisme Kerja

Aplikasi ini bekerja menggunakan dua mekanisme yang berbeda tergantung pada tipe URL video yang dimasukkan:

### 1. Alur Pemutaran HLS (`.m3u8`)

```
[Browser / Player] 
       │
       ├─► (A) Minta Master Playlist ──► [Flask: /api/v1/hls/master] ──► (Bypass WAF) ──► [Server Asli]
       │                                                                                      │
       ◄─ (D) Kirim Playlist (URL diubah ke Proxy) ◄─ [Ubah URL ke lokal] ◄───────────────────┘
       │
       ├─► (B) Minta Variant Playlist ──► [Flask: /api/v1/hls/variant] ──► (Bypass WAF) ──► [Server Asli]
       │                                                                                      │
       ◄─ (E) Kirim Variant (Segmen diubah ke Proxy) ◄─ [Ubah Segmen ke lokal] ◄──────────────┘
       │
       └─► (C) Minta Segmen (.ts) ──► [Flask: /api/v1/hls/segment] ──► (urllib stream) ──► [CDN Video]
                                                                                              │
       ◄─────────────────────── (F) Alirkan Video (Chunked) ◄────────────────────────────────┘
```

1. **Master & Variant Proxy**: Flask mengambil file manifes `.m3u8` dari server asal dengan emulasi TLS Chrome, memindai isinya, lalu mengubah semua link internal di dalamnya agar mengarah kembali ke server Flask lokal (`127.0.0.1:8000`).
2. **Segment Proxy**: Pemutar video meminta potongan segmen video (.ts) melalui Flask. Flask mengunduh segmen tersebut secara cepat menggunakan `urllib.request` dan langsung menyalurkannya (*piping/streaming*) ke browser.

---

### 2. Alur Pemutaran Direct Stream (MP4 / MKV / Raw Video)

```
[Browser Video Player] ──► [Flask: /api/v1/video/stream] ──► [Server Asli] (Mengirim referer & origin cerdas)
          ▲                                    │                      │
          │                                    ▼                      │
  (Aliran Byte Video) ◄──────────── (Teruskan Header Range) ◄─────────┘
```

1. **Deteksi Otomatis**: JavaScript di frontend mendeteksi bahwa URL tidak mengandung `.m3u8` dan mengalihkan pemutar ke mode Direct Stream.
2. **Byte-Range Proxy**: Browser meminta byte tertentu dari video (misal byte `1000000` - `2000000`). Flask menangkap header `Range` tersebut, mengirimkannya ke server video asli dengan referer yang tepat, menerima potongan biner video (status `206 Partial Content`), dan mengalirkannya kembali ke browser.

---

## 📁 Struktur File Proyek

* **`app.py`**: Berisi backend Flask (penanganan route API dan layout HTML/CSS/JS frontend).
* **`requirements.txt`**: Daftar pustaka Python yang diperlukan (`Flask` dan `curl_cffi`).
* **`run.bat`**: Script Windows sekali klik untuk mengaktifkan virtual environment (`venv`) dan menjalankan server.
* **`diagnose_*.py`**: Script mandiri untuk melakukan uji coba dan diagnosis request jaringan.

---

## 💻 Cara Menjalankan Proyek

### Prasyarat
Pastikan Anda sudah menginstal **Python 3.8 - 3.11** di komputer Anda.

### Langkah-langkah
1. **Buka Folder Proyek** di terminal/command prompt Anda.
2. **Jalankan Setup & Aktifkan venv** (jika pertama kali):
   ```bash
   # Buat virtual environment
   python -m venv venv
   
   # Aktifkan virtual environment
   # Windows:
   call venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   
   # Instal dependensi
   pip install -r requirements.txt
   ```
3. **Jalankan Aplikasi**:
   * Cukup klik dua kali pada file **`run.bat`** (khusus Windows), ATAU
   * Jalankan perintah berikut di terminal yang aktif venv-nya:
     ```bash
     python app.py
     ```
4. **Buka Browser**:
   * Akses alamat **`http://127.0.0.1:8000`**.
   * Tempelkan URL video HLS atau Direct Stream yang ingin diputar pada input box, lalu klik **Play**.
