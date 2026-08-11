# Heatmap Clipper 🔥🎬

Cari momen paling **rame** (Most Replayed / heatmap) di video YouTube, potong otomatis
jadi clip vertikal siap Shorts/Reels/TikTok — lengkap subtitle AI, smart crop yang
mengikuti wajah, dan editor clip per-segmen.

**v2** — backend **FastAPI**, frontend **React + Vite + Tailwind v4**,
progress real-time (SSE), riwayat job persistent (SQLite), UI bilingual (ID/EN),
deployable dengan password.

## Fitur

- **Scan heatmap** via yt-dlp native (`heatmap` field, bukan scrape HTML rapuh) → momen paling di-replay.
- **Mode Auto** — kalau video tidak punya data Most Replayed, deteksi momen menarik dari
  *audio energy* (loudness) + *scene change density* (ffmpeg `scdet`), tanpa dependency tambahan.
- **Custom range** — potong dari start/end manual (detik atau `mm:ss`).
- **Smart Crop** — deteksi wajah (MediaPipe `blaze_face` → fallback OpenCV Haar → center)
  lalu crop **mengikuti wajah dari waktu ke waktu** (keyframe trajectory + EMA smoothing
  + scene-cut aware), bukan hanya center statis.
- **3 crop mode**: default (center), split-left / split-right (facecam pojok buat gaming).
- **Ratio**: 9:16, 1:1, 16:9, original.
- **Auto Hook Text** — teks hook di awal clip (0–3s) diambil otomatis dari transkrip.
- **Subtitle AI** (faster-whisper): auto-detect bahasa, 4 preset gaya + live preview.
  Opsional: jalankan transkripsi di **GPU gratis** lewat notebook Colab/Kaggle (lihat di bawah)
  supaya beban CPU/RAM lokal tidak berat.
- **Clip Editor** — re-render per clip tanpa download ulang: geser trim, pilih posisi crop
  (kiri/tengah/kanan), buang range waktu (cuts), ubah hook text / subtitle / ratio.
- **Progress real-time** per clip (download → trim → smart crop → subtitle → burn) lewat SSE.
- **Preview clip inline** (player di halaman) + **download** per clip / **batch ZIP**.
- **Riwayat job** persistent — bertahan walau server restart, bisa dibuka/dihapus.
- **Password proteksi** opsional (env `APP_PASSWORD`) buat deploy publik.

## Requirements

- Python 3.10+ (3.12 disarankan)
- Node 20+ (buat build frontend)
- **FFmpeg** (wajib, harus di PATH — di Windows otomatis dideteksi dari WinGet bila ada)
- `numpy` (dipakai smart crop & auto mode)
- Optional: `faster-whisper` (kalau subtitle ON), `opencv-python` + `mediapipe`
  (smart crop; tanpa itu fallback ke center crop)

## Langkah-langkah Setup & Jalankan (dev)

```bash
# 1) Backend — virtual env
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 2) Install backend deps
python -m pip install -r backend/requirements.txt

# 3) Opsional — subtitle & smart crop (bisa skip kalau fitur itu dimatikan)
python -m pip install faster-whisper
python -m pip install numpy opencv-python mediapipe

# 4) Backend (port 5100)
uvicorn backend.app:app --host 127.0.0.1 --port 5100 --reload

# 5) Terminal lain — frontend dev (port 5173, proxy /api & /clips ke :5100)
cd frontend
npm install
npm run dev
```

Buka **http://127.0.0.1:5173**.

> Catatan: tidak ada `start.bat`/`start.sh` di repo — jalankan dua perintah di atas langsung.

## Build produksi (1 server)

```bash
# 1) Build frontend -> frontend/dist
cd frontend && npm install && npm run build
cd ..

# 2) Jalankan FastAPI (menyajikan API + frontend build di port yang sama)
uvicorn backend.app:app --host 0.0.0.0 --port 5100
```

Buka **http://<host>:5100**.

## Docker

```bash
docker build -t heatmap-clipper .
docker run -p 5100:5100 -v $(pwd)/data:/data -e APP_PASSWORD=rahasia heatmap-clipper
```

Image sudah termasuk FFmpeg + faster-whisper. Data (SQLite + clips) di volume `/data`.

## Environment

Salin `.env.example` ke `.env` lalu sesuaikan.

| Var | Default | Fungsi |
|-----|---------|--------|
| `APP_PASSWORD` | *(kosong)* | Kalau diisi → wajib login. Kosong = akses bebas (lokal). |
| `DATA_DIR` | `data` | Lokasi SQLite (`jobs.db`) + folder clips. |
| `WHISPER_BASE_URL` | *(kosong)* | URL whisper (GPU notebook / script lokal). Kosong = faster-whisper lokal (CPU). |
| `WHISPER_API_KEY` | *(kosong)* | API key whisper (default notebook: `sk-whisper-local`). |
| `WHISPER_MODEL` | `small` | Model whisper untuk fallback lokal (`tiny`/`base`/`small`/`medium`/`large-v3`). |

## Subtitle di GPU (opsional)

Transkripsi subtitle adalah bagian terberat di lokal (load model + inferensi CPU).
Biar ringan, jalankan whisper di GPU gratis Colab/Kaggle:

1. Buka `notebooks/whisper_server.ipynb` di Google Colab → Runtime → Change runtime type → **GPU**.
2. Jalankan cell, tunggu install + model load (pertama kali ~2-5 menit).
3. Salin `BASE_URL` + `API_KEY` yang dicetak ke `.env`:
   ```
   WHISPER_BASE_URL="https://xxxx.trycloudflare.com"
   WHISPER_API_KEY="sk-whisper-local"
   ```
4. Selesai. Backend otomatis kirim audio tiap clip ke notebook dan terima segmen subtitle.
   Biarkan cell tetap berjalan saat clipping dengan subtitle.

**Alternatif lokal (tanpa Colab):** jalankan `notebooks/whisper_server.py` sebagai script
di mesin yang sama (port 4000), lalu set `WHISPER_BASE_URL="http://127.0.0.1:4000"`.
Backend men-*poll* `/status` dan mem-*stream* progress transkripsi ke UI.

Catatan: URL tunnel sementara — berubah tiap restart notebook. Kalau `WHISPER_BASE_URL`
kosong, backend memakai faster-whisper lokal (CPU) sebagai fallback.

## Arsitektur

```
backend/
  app.py              FastAPI: routes, SSE, auth gate, static serve
  auth.py             password -> signed cookie
  db.py               SQLite job history (stdlib sqlite3)
  jobs.py             job runner + asyncio event queue -> SSE
  models.py           Pydantic schemas -> ClipConfig
  core/
    heatmap.py        yt-dlp native heatmap (+ HTML fallback)
    auto_highlight.py mode "auto": audio energy + scene changes (no new deps)
    smart_crop.py     face tracking: MediaPipe -> Haar -> center, keyframe crop
    clipper.py        download -> trim -> crop -> subtitle -> export (ClipConfig, no globals)
    subtitle.py       faster-whisper local / remote notebook transcribe
    ffmpeg_filters.py scale/crop/split-vstack/cut select builders
    config.py         ClipConfig / SubtitleStyle dataclasses
    test_core.py      self-checks: python -m backend.core.test_core
  models/             blaze_face_short_range.tflite (MediaPipe smart crop)
frontend/             React + Vite + Tailwind v4 SPA (ID/EN)
fonts/                font subtitle (dipakai backend + UI)
notebooks/            whisper_server.ipynb + .py (GPU transcribe)
```

## API

| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/api/login` | password → cookie |
| GET | `/api/health` | status + ffmpeg + auth |
| POST | `/api/preview` | metadata video |
| POST | `/api/scan` | segments heatmap |
| POST | `/api/clip` | buat job → `job_id` |
| POST | `/api/clip/edit` | re-render clip dengan parameter kustom |
| GET | `/api/clip/{job_id}/{clip_index}/source` | source segmen (preview editor, stream-copy cached) |
| GET | `/api/jobs/{id}/events` | **SSE** progress |
| GET | `/api/jobs` · `/api/jobs/{id}` | riwayat |
| DELETE | `/api/jobs/{id}` | hapus job + file |
| GET | `/api/jobs/{id}/download.zip` | batch ZIP |
| GET | `/clips/{job}/{file}` | serve clip |

## Test

```bash
python -m backend.core.test_core
```

## Catatan

- Whisper jalan di CPU (int8). Upgrade path: build GPU faster-whisper atau pakai notebook GPU.
- 1 password buat 1 user; belum ada sistem multi-user (by design).
