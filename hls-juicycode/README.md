# Proxy Film & JuicyCodes Decoder (Flask Backend)

Proyek ini adalah platform automasi ekstraksi dan streaming lokal berbasis **Flask** yang dirancang khusus untuk mem-bypass enkripsi pemutar video (seperti JuicyCodes) serta WAF (Web Application Firewall) pada situs-situs *streaming* film.

Aplikasi ini bertindak sebagai alat *All-In-One*: mengambil URL Iframe video bajakan, memecahkan (men-dekode) *payload* enkripsi menggunakan sandboxing Node.js, mengekstrak URL m3u8 asli, dan langsung memutarnya di dalam local proxy player untuk melewati pembatasan `403 Forbidden`.

---

## 🚀 Fitur Utama

1. **Automated JuicyCodes Decoder**:
   * Melakukan *scraping* HTML pemutar video secara *stealth* untuk melewati perlindungan Cloudflare.
   * Menjalankan script rahasia pembuka enkripsi (seperti `player.js`) di dalam **Node.js Sandbox** yang aman (Mock DOM Environment).
   * Mencegat (melakukan penyadapan fungsi `eval`) untuk menangkap URL konfigurasi aslinya tanpa harus membuka tab Network secara manual.
2. **Dual Stream Proxy Support**: 
   * **HLS Mode**: Memutar file playlist `.m3u8` dengan melakukan proxy ulang pada file Master, Variant, dan Segmen Video (`.ts`) ke server lokal `127.0.0.1`.
   * **Direct Stream Mode**: Memutar file video mentah (MP4/MKV) menggunakan *Byte-Range Proxy* yang mendukung fitur maju/mundur waktu (seeking) instan.
3. **WAF Bypass (Chrome Fingerprint Emulation)**:
   * Menggunakan pustaka `curl_cffi` untuk meniru sidik jari koneksi TLS dari browser Google Chrome secara otentik, membiarkan server asal mengira request datang dari peramban nyata.
4. **Premium UI & Real-time Diagnostic Log**:
   * Memiliki antarmuka grafis ramah pengguna (Dark Mode). Cukup tempel URL Iframe -> Klik Extract -> Video akan diputar otomatis disertai *Diagnostic Log* langsung di layar Anda.

---

## 🛠️ Arsitektur Sistem

Berikut adalah alur kerja *end-to-end* yang terjadi saat Anda memasukkan URL Iframe video (contoh: `https://199.87.../player/XYZ`):

1. **Extraction (Python + Node.js)**
   * Flask meminta HTML dari server Iframe menggunakan simulasi TLS.
   * Python menemukan payload `_juicycodes("...")` dan URL dekoder `player.js`.
   * Python menjalankan Node.js Sandbox di background untuk men-dekode string tersebut dan mendapatkan link mentah `.m3u8`.
2. **Proxying (HLS Interception)**
   * Front-end melempar link `.m3u8` ke API Proxy (`/api/v1/hls/master`).
   * API akan mengunduh `.m3u8` dan memodifikasi semua isi path di dalamnya untuk menunjuk ke server Flask (`localhost:8000`).
3. **Streaming**
   * Pemutar video HLS.js memutar video dari `localhost`, namun di balik layar, Flask mengalirkan potongan video asli (*chunked streaming*) dari server pusat secara berkelanjutan dan anonim.

---

## 📁 File Penting dalam Repositori Ini

Saat melakukan proses `push` ke GitHub, file-file penting yang menyusun inti dari sistem ini adalah:
* **`app.py`**: Mengatur lalu lintas API (Extractor, Master HLS, Segment Proxy) sekaligus menyediakan antarmuka (UI/HTML) utama.
* **`juicy_decoder.py`**: Berisi logika cerdas pembuatan Node.js Sandbox dan intersepsi (penyadapan) *JuicyCodes*.
* **`requirements.txt`**: Daftar ketergantungan modul Python yang harus di-install.

*(Catatan: Folder `venv/`, `__pycache__/`, dan file `.py` bekas debugging lainnya telah di-ignore dalam `.gitignore`)*.

---

## 💻 Cara Menjalankan Proyek di Lokal

### Prasyarat:
1. **Python** (Versi 3.8 - 3.11).
2. **Node.js** (Sangat wajib di-install karena sistem akan memanggil perintah `node` di background untuk dekripsi).

### Langkah-langkah Menjalankan:
1. **Buka Terminal** dan arahkan ke direktori proyek ini.
2. **Buat dan Aktifkan Virtual Environment** (Hanya untuk pertama kali):
   ```bash
   python -m venv venv
   
   # Untuk Windows:
   call venv\Scripts\activate
   
   # Untuk Linux/macOS:
   source venv/bin/activate
   ```
3. **Instal Dependensi**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Jalankan Server Flask**:
   ```bash
   python app.py
   ```
5. Buka Browser dan akses: **`http://127.0.0.1:8000`**. Masukkan link Iframe video yang dituju dan saksikan mesin ini bekerja!
