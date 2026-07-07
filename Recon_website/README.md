# Website Recon Tool

Script recon website (fetch halaman, deteksi teknologi, cari subdomain, cari origin IP di balik Cloudflare, scan port, cek TLS/SSL) dengan bypass Cloudflare via [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr).

## Requirement

- Python 3.9+
- Docker (untuk menjalankan FlareSolverr)
- [nmap](https://nmap.org/download.html) terinstall dan ada di PATH (untuk Tahap 5, port scan)

## Instalasi

1. Clone repo ini:
   ```bash
   git clone https://github.com/bagaspng/ThreatHunter-Toolkit.git
   cd Recon_website
   ```

2. Buat virtual environment (opsional tapi disarankan):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
   ```

3. Install dependency Python:
   ```bash
   pip install -r requirements.txt
   ```

4. Install nmap:
   - **Ubuntu/Debian**: `sudo apt install nmap`
   - **macOS**: `brew install nmap`
   - **Windows**: download installer dari https://nmap.org/download.html

5. Jalankan FlareSolverr lewat Docker (wajib jalan sebelum menjalankan script):
   ```bash
   docker run -d --name flaresolverr -p 8191:8191 -e LOG_LEVEL=info --restart unless-stopped ghcr.io/flaresolverr/flaresolverr:latest
   ```
   Pastikan sudah jalan dengan `docker ps | grep flaresolverr`.

## Cara pakai

Buat file teks berisi daftar target, satu URL per baris:

```
https://target1.com
target2.com
```

Lalu jalankan:

```bash
python recon_website_final.py daftar_url.txt
```

Hasil recon disimpan sebagai `<nama_file>_results.json`, dan log proses lengkap di-append ke `log.txt`.

## Catatan

- Script ini melakukan port scan (nmap) dan brute-force subdomain, jadi hanya gunakan pada domain yang memang milikmu sendiri atau yang kamu punya izin untuk di-scan.
- FlareSolverr wajib berjalan di `http://localhost:8191` (default). Kalau di-deploy di host/port lain, ubah `FLARESOLVERR_URL` di `flaresolverr_client.py`.
