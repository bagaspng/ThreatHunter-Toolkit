# HLS Cookie Proxy

HLS Cookie Proxy adalah backend Python untuk mem-proxy stream CCTV berbasis HLS (`.m3u8` dan segment seperti `.ts`, `.m4s`, `.mp4`, `.aac`) yang membutuhkan cookie lintas subdomain. Setelah migrasi, runtime HTTP utama adalah Django: Django melayani halaman player lokal, daftar kamera, dan endpoint proxy HLS. Flask di `app.py` masih dipertahankan sebagai legacy compatibility layer, tetapi bukan entrypoint utama.

## Status Arsitektur Saat Ini

Komponen utama proyek:

- `django_config/`: konfigurasi Django, URL root, ASGI/WSGI, dan Celery app.
- `proxy_api/`: endpoint DRF, wiring service, serializer, dan Celery task refresh cookie.
- `core/`: logika framework-agnostic untuk cookie store, handshake kamera, playlist rewrite, HLS client, segment cache, Range parser, dan validasi URL.
- `upstream_auth/`: Selenium refresher importable untuk mengambil base cookies.
- `scraper/` dan `main.py`: camera discovery/prober, tetap opsional.
- `templates/player.html`: halaman player yang dirender oleh Django di `/player`.
- `app.py`: legacy Flask compatibility surface.
- `tests/`: unit dan integration tests dengan mocked upstream, fake Redis, dan task Celery eager/apply.

## Endpoint Publik Utama

Django mengekspos halaman player, daftar kamera, dan tiga endpoint proxy utama:

- `GET /player`
- `GET /api/cameras`
- `GET /proxy/playlist?url=...`
- `GET /proxy/segment?url=...`
- `POST /api/refresh-cookies`

Route Flask legacy untuk endpoint proxy yang sama diberi header `Deprecation: true` dan sebaiknya tidak dipakai sebagai runtime produksi.

## Alur Kerja Singkat

1. Base cookies (`cctv_access`, `stream_token`) diperoleh oleh Celery task yang menjalankan Selenium refresher.
2. Base cookies, camera cookies, refresh status, version, dan refresh lock disimpan di Redis jika `COOKIE_STORE_BACKEND=redis`.
3. Saat playlist diminta, service membangun `requests.Session` dari cookie snapshot, melakukan handshake kamera, lalu rewrite URL playlist agar browser tetap lewat proxy lokal.
4. Saat segment diminta, service meneruskan header penting seperti `Range`, menjaga status/header upstream aman, dan memakai cache disk lokal untuk response penuh `200`.
5. Jika base cookie belum tersedia atau sedang refresh, playlist dapat mengembalikan `503` dengan `Retry-After`.

## Struktur Folder

```text
.
├── core/                    # Domain logic tanpa Flask/DRF coupling
├── django_config/           # Django settings, urls, ASGI/WSGI, Celery app
├── proxy_api/               # DRF views, service wiring, serializers, Celery tasks
├── scraper/                 # Camera scraping/probing helpers
├── templates/               # Django player template
├── tests/                   # Unit + integration tests mocked upstream
├── upstream_auth/           # Selenium base-cookie refresher
├── app.py                   # Legacy Flask compatibility layer
├── cookies-exp.py           # Optional one-shot Selenium refresh CLI
├── main.py                  # Optional camera discovery/prober
├── manage.py                # Django management entrypoint
├── config.py                # Konstanta upstream dan default runtime
├── requirements.txt         # Python dependencies
├── README.md                # Dokumentasi operasional
```

Folder/file runtime yang sengaja tidak dilacak git:

- `cache_segments/`
- `output/`
- `cookies.json`
- `.env*`
- `venv/`
- `__pycache__/`

## Instalasi

Gunakan virtual environment lokal.

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Di PowerShell, aktivasi opsional:

```powershell
.\venv\Scripts\Activate.ps1
```

## Environment Variables

Untuk development, default di `django_config/settings.py` masih bisa berjalan dengan fallback JSON. Untuk production-like setup gunakan Redis.

Minimal production-like:

```powershell
$env:DJANGO_DEBUG = "0"
$env:DJANGO_SECRET_KEY = "ganti-dengan-secret-lokal"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1"
$env:COOKIE_STORE_BACKEND = "redis"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:CELERY_BROKER_URL = "redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

Opsional:

- `COOKIE_BASE_TTL_SECONDS`
- `COOKIE_CAMERA_TTL_SECONDS`
- `COOKIE_REFRESH_LOCK_TTL_SECONDS`
- `REFRESH_WAIT_TIMEOUT_SECONDS`

Nilai upstream, referer, allowlist host, timeout, dan lokasi output default berada di `config.py`.

## Menjalankan Django API

```bash
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Endpoint akan tersedia di `http://localhost:8000`. Buka player di `http://localhost:8000/player`.

## Menjalankan Redis

Redis diperlukan untuk shared state produksi. Jalankan Redis sebagai service internal, bukan port publik internet.

Contoh dengan Docker:

```bash
docker run --rm -p 6379:6379 redis:7
```

Jika tidak memakai Docker, jalankan Redis sesuai OS/deployment masing-masing lalu sesuaikan `REDIS_URL`.

## Menjalankan Celery Worker

Worker menjalankan Selenium refresh dan tidak membuka HTTP port publik.

```bash
venv\Scripts\celery.exe -A django_config worker -l info
```

Di environment Linux/macOS biasanya:

```bash
celery -A django_config worker -l info
```

## Refresh Cookie

Trigger refresh:

```bash
curl -X POST http://localhost:8000/api/refresh-cookies ^
  -H "Content-Type: application/json" ^
  -d "{\"force\":true,\"wait\":false}"
```

Kontrak response utama:

- `200 ready`: cookie sudah tersedia dan masih valid.
- `202 refreshing`: task refresh sedang berjalan atau baru dibuat.
- `503 failed`: refresh tidak berhasil atau belum siap dipakai.

## Mengakses Playlist dan Segment

Contoh playlist:

```text
http://localhost:8000/proxy/playlist?url=https%3A%2F%2Fstream-newseribuwajah.bandarlampungkota.go.id%2Fcctv_18%2Findex.m3u8
```

Playlist yang dikembalikan akan rewrite URL child playlist dan binary resource agar tetap melewati `/proxy/playlist` atau `/proxy/segment`.

## Camera Discovery Opsional

Camera discovery masih dipertahankan sebagai tooling opsional. Django `/api/cameras` akan membaca `output/cameras.json` jika ada; jika belum ada, endpoint ini mencoba mengambil daftar kamera dari API CCTV dan menyimpannya ke file tersebut.

```bash
venv\Scripts\python.exe main.py --probe 50 --workers 10
```

Output runtime akan masuk ke `output/cameras.json` dan tidak dilacak git.

## Legacy Flask Layer

`app.py` masih bisa dijalankan untuk kompatibilitas route lama:

```bash
venv\Scripts\python.exe app.py
```

Namun player dan API utama proyek sekarang berjalan lewat Django di port 8000. Route Flask untuk `POST /api/refresh-cookies`, `GET /proxy/playlist`, dan `GET /proxy/segment` diberi header deprecation.

## Materi Belajar

Untuk memahami proyek dari dasar, baca `docs/MATERI_BELAJAR_PROYEK.md`. Dokumen itu menjelaskan HTTP, HLS, cookie, session, handshake, Django, Redis, Celery, Selenium, dan peta folder/source code proyek ini secara bertahap.
## Menjalankan Test

```bash
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test tidak membutuhkan internet, Redis server nyata, atau browser nyata karena memakai mocked upstream, fake Redis, dan task Celery eager/apply.

## Keamanan

Jangan commit data runtime sensitif:

- `cookies.json`
- `output/cookies_cache.json`
- isi `cache_segments/`
- `.env*`

Dokumentasi dan test hanya boleh memakai nilai dummy seperti `base`, `token`, atau `task-id`, bukan cookie/token nyata.


