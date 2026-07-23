# Streaming & Proxy Tools

Folder ini berisi kumpulan _tools_ dan proyek yang berfokus pada web scraping, video proxying, bypass WAF, dan manajemen HLS (HTTP Live Streaming). Proyek-proyek ini dikembangkan secara spesifik untuk kebutuhan ekstraksi streaming dan diagnostik jaringan.

## Daftar Proyek

Berikut adalah penjelasan singkat untuk masing-masing direktori proyek di dalam folder ini:

### 1. [hls-cookies](./hls-cookies)

**HLS Cookies Proxy for CCTV Portal.** Aplikasi Python (Flask + Selenium) untuk mengakses stream CCTV berbasis HLS yang dilindungi cookie sesi. Proyek ini mampu melakukan _scraping_ dan _refresh_ cookie secara otomatis (mengakali perlindungan lintas subdomain) untuk menjaga stream tetap dapat diputar secara lokal.

### 2. [hls-juicycode](./hls-juicycode)

**Proxy Film & JuicyCodes Decoder.** Alat otomasi _all-in-one_ untuk melakukan bypass enkripsi pada pemutar video bajakan (seperti JuicyCodes). Menggunakan **Node.js Sandbox** untuk mendekode _payload_ terenkripsi secara aman.

### 3. [hls-proxy](./hls-proxy)

**HLS Reverse-Proxy (Educational).** Server reverse-proxy yang berfokus pada bypass anti-scraping, referrer validation, dan perlindungan bot. Proyek ini menggunakan `curl_cffi` untuk meniru sidik jari TLS (TLS Fingerprint) Google Chrome sehingga _request_ terlihat otentik.

### 4. [proxy-m3u8](./proxy-m3u8)

**Proxy Film Diagnostic App.** Aplikasi diagnostik dengan dukungan HLS `.m3u8` dan Direct Stream (Raw MP4/MKV). Dilengkapi dengan **Byte-Range Proxy** untuk fitur _seek_ yang instan serta antarmuka (UI) untuk memantau log jaringan secara langsung (real-time).

### 5. [public-cam](./public-cam)

**Public Camera Tool.** Direktori untuk alat _scraper_ / _viewer_ yang berkaitan dengan kamera-kamera CCTV atau kamera IP publik yang dapat diakses dari internet.

### 6. [stream-scraper](./stream-scraper)

**Stream Scraper.** Sekumpulan script/API (berbasis Flask) untuk melakukan _scraping_ dan mengekstrak link-link sumber media (stream URL) dari berbagai platform atau web.

---

still watching
