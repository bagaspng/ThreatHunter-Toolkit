# Static File Threat Scanner

Static File Threat Scanner adalah perkakas baris perintah (CLI) berbasis Python untuk menganalisis dokumen dan gambar secara statis guna mendeteksi indikator ancaman keamanan (malware indicators). Scanner ini dirancang untuk membaca byte, struktur, metadata, dan string dalam file secara aman tanpa mengeksekusi file tersebut.

## Struktur Direktori

```txt
├── config/              # Konfigurasi batas skor dan keparahan rules
│   ├── rules.yaml
│   └── thresholds.yaml
├── src/                 # Source code utama aplikasi
│   ├── analyzers/       # Parser spesifik file (pdf, png, jpg, svg, generic)
│   ├── core/            # Logika inti (file_info, entropy, magic_detector, scoring, scanner)
│   ├── detectors/       # Pendeteksi pola (url, base64, apk, suspicious_keyword)
│   ├── reports/         # Pembangun format output (console, json, text)
│   └── utils/           # Helper fungsi pembaca file & ekstraksi teks aman
├── tests/               # Unit testing program
├── main.py              # Titik masuk utama program (CLI Entry Point)
├── requirements.txt     # Daftar dependensi modul Python
└── .gitignore           # File pengabaian git
```

---

## Fitur Utama

- **Deteksi Ketidaksesuaian Ekstensi**: Memeriksa kesesuaian antara ekstensi file dengan tipe aslinya (magic bytes).
- **Deteksi Penyamaran Berbahaya**: Mengidentifikasi jika file executable (EXE) atau package Android (APK) disamarkan sebagai gambar atau dokumen.
- **Analisis Struktur Khusus**:
  - **PDF**: Menganalisis objek mencurigakan di dalam file PDF.
  - **SVG**: Mendeteksi elemen aktif atau tag `<script>` yang berpotensi memicu Stored XSS.
  - **PNG/JPG**: Memeriksa keberadaan data tambahan setelah penanda akhir file (EOF/Extra data after image EOF).
- **Deteksi Pola & String Mencurigakan**:
  - Pengecekan URL, alamat IP, dan domain di dalam file.
  - Deteksi string base64 berukuran panjang yang sering digunakan untuk menyembunyikan payload.
  - Deteksi indikator APK tersembunyi.
- **Perhitungan Entropi Shannon**: Mengukur tingkat keacakan data untuk menemukan enkripsi, obfuscation, atau kompresi tinggi.
- **Skor Risiko Heuristik**: Mengkalkulasi tingkat bahaya (Risk Score) dan menentukan status penilaian (`Clean`, `Suspicious`, atau `Malicious Indicator`).
- **Pilihan Laporan**:
  - Output default berupa format **JSON** yang terstruktur, ideal untuk integrasi dengan sistem lain.
  - Output teks (console-friendly) yang menarik menggunakan pustaka `rich`.
  - Opsi penyimpanan report otomatis ke file JSON maupun TXT.

---

## Kebutuhan Sistem

- **Python**: Versi 3.10 atau yang lebih baru.
- **Pustaka Dependensi** (tertera di `requirements.txt`):
  - `pillow`
  - `pypdf`
  - `pyyaml`
  - `defusedxml`
  - `rich`
  - `pytest`

---

## Instalasi

1. Pastikan Python 3.10+ sudah terinstal di sistem Anda.
2. Pasang pustaka dependensi yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```

---

## Cara Penggunaan

### 1. Pindai File (Output JSON - Default)
Secara default, scanner akan menampilkan hasil analisis dalam format JSON terstruktur ke `stdout`.
```bash
python main.py scan <path_ke_file>
```
Contoh:
```bash
python main.py scan samples/benign/popup.svg
```

### 2. Pindai File (Output Teks Tampilan Console)
Gunakan opsi `--text` jika ingin melihat laporan ramah terminal dengan visualisasi tabel dan panel warna.
```bash
python main.py scan <path_ke_file> --text
```

### 3. Menyimpan Laporan ke File
- Simpan dalam bentuk JSON dan TXT sekaligus:
  ```bash
  python main.py scan <path_ke_file> --save
  ```
- Simpan hanya JSON:
  ```bash
  python main.py scan <path_ke_file> --save-json
  ```
- Simpan hanya TXT:
  ```bash
  python main.py scan <path_ke_file> --save-txt
  ```
- Mengatur folder penyimpanan laporan (default: `output/reports`):
  ```bash
  python main.py scan <path_ke_file> --save --output-dir path/folder/custom
  ```

### 4. Opsi Lanjutan
- **Batas Ukuran File**: Batasi ukuran file maksimum yang diizinkan untuk dipindai (default: 100 MB).
  ```bash
  python main.py scan <path_ke_file> --max-size-mb 50
  ```
- **Integrasi Otomasi / CI-CD**: Mengembalikan exit code `2` jika file terdeteksi sebagai `Suspicious` atau `Malicious Indicator`.
  ```bash
  python main.py scan <path_ke_file> --fail-on-risk
  ```

---



## Keamanan & Aturan Keselamatan

1. **Static Only**: Scanner ini tidak akan pernah mengeksekusi file yang sedang dianalisis.
2. **Safe Parsing**: Menggunakan parser XML aman (`defusedxml`) untuk mencegah kerentanan XXE saat memindai dokumen SVG.
3. **No Network Call**: Tidak mengirim data file ke server pihak ketiga selama proses scanning.
