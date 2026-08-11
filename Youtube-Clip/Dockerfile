# ---------- stage 1: build frontend ----------
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---------- stage 2: runtime ----------
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# Subtitle support (heavy). Comment out if you never use subtitles.
RUN pip install --no-cache-dir faster-whisper

COPY backend/ ./backend/
COPY fonts/ ./fonts/
COPY --from=frontend /fe/dist ./frontend/dist

ENV DATA_DIR=/data
VOLUME /data
EXPOSE 5100

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "5100"]
