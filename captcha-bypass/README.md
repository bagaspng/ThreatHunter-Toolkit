# CAPTCHA Bypass Modules

Kumpulan tools dan modul otomatisasi untuk melewati berbagai jenis verifikasi CAPTCHA populer seperti **Google reCAPTCHA**, **Cloudflare Turnstile**, dan template untuk **hCaptcha**. 

Repository ini dikonsolidasikan untuk mempermudah integrasi bypass CAPTCHA pada proyek web scraping, testing, dan otomatisasi lainnya di dalam toolkit **ThreatHunter-Toolkit**.

---

## 📁 Struktur Folder

```text
captcha-bypass/
├── hcaptcha/           # Modul bypass hCaptcha (Placeholder / Pengembangan Mendatang)
├── recaptcha/          # Solusi bypass Google reCAPTCHA v2 / v3 menggunakan DrissionPage
│   ├── RecaptchaSolver.py
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── test.py
├── turnstile/          # Solusi bypass Cloudflare Turnstile menggunakan Patchright
│   ├── Docker/
│   ├── api_solver.py
│   ├── async_solver.py
│   ├── sync_solver.py
│   ├── requirements.txt
│   └── main.py
├── .gitignore          # Konfigurasi ignore file git yang lengkap
└── README.md           # Dokumentasi utama (File ini)
```

---

## 🚀 Fitur & Modul

### 1. Cloudflare Turnstile Solver (`/turnstile`)
Bypass verifikasi Turnstile menggunakan pustaka `patchright` dengan performa tinggi.
* **Fitur**:
  * Mendukung eksekusi Multi-threaded.
  * Dilengkapi REST API (Flask) untuk integrasi dengan tool eksternal.
  * Mendukung berbagai browser (`chromium`, `chrome`, `msedge`, `camoufox`).
  * Mendukung RDP / Docker.
* **Instalasi & Penggunaan**: Lihat dokumentasi lengkap di [turnstile/README.md](./turnstile/README.md).

### 2. Google reCAPTCHA Solver (`/recaptcha`)
Bypass reCAPTCHA v2 / v3 dengan memproses tantangan audio menggunakan Google Speech Recognition API dan pustaka browser `DrissionPage` (atau Selenium).
* **Fitur**:
  * Bypass sangat cepat (kurang dari 5 detik).
  * Solusi audio captcha terintegrasi yang andal.
  * Mendukung Chromium melalui DrissionPage yang lebih tahan deteksi bot dibanding Selenium standar.
* **Instalasi & Penggunaan**: Lihat dokumentasi lengkap di [recaptcha/README.md](./recaptcha/README.md).

### 3. hCaptcha Solver (`/hcaptcha`)
Direktori ini disiapkan untuk menyimpan script bypass hCaptcha di masa mendatang.

---

## 🛠️ Panduan Memulai (Setup Umum)

Disarankan untuk menggunakan virtual environment terpisah untuk setiap modul atau satu virtual environment di tingkat atas jika Anda menggabungkan dependensinya.

### Cara Setup Virtual Environment:
1. Masuk ke direktori modul yang diinginkan:
   ```bash
   cd turnstile   # atau recaptcha
   ```
2. Buat virtual environment:
   ```bash
   python -m venv venv
   ```
3. Aktifkan virtual environment:
   * **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   * **Linux/macOS**:
     ```bash
     source venv/bin/activate
     ```
4. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚠️ Disclaimer
Penggunaan tool bypass CAPTCHA ini ditujukan **hanya untuk keperluan edukasi, pengujian penetrasi resmi (authorized pentesting), dan riset keamanan**. Pastikan Anda mematuhi kebijakan ketentuan layanan (Terms of Service) dari situs web target sebelum menjalankan skrip otomatisasi. Penulis tidak bertanggung jawab atas segala bentuk pemblokiran IP, penyalahgunaan, atau konsekuensi hukum yang timbul dari penggunaan modul ini.
