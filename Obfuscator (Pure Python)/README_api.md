# Web API — Obfuscator (Pure Python)

`app.py` adalah **entry point ketiga** dari toolkit ini, melengkapi:

| File | Bentuk | Untuk |
|------|--------|-------|
| `main.py` | Menu interaktif terminal | manusia |
| `obfuscate.py` | CLI (stdin/stdout) | automasi/pipeline |
| `stego_umum.py` | CLI ekstraktor pesan LSB pada PNG | analisis gambar |
| `jwt_umum.py` | CLI JWT (decode/verify/encode) | analisis/pembuatan token |
| **`app.py`** | **Web API + halaman form** | akses lewat HTTP/browser |

Semua logika tetap memakai modul di `modules/` — API hanya membungkusnya.

---

## Menjalankan

```bash
cd "Obfuscator (Pure Python)"
./venv/bin/pip install -r requirements.txt   # sekali saja (flask)
./venv/bin/python app.py
```

Server jalan di **http://127.0.0.1:8000/**. Buka di browser untuk memakai form,
atau panggil endpoint langsung dengan `curl`/Postman.

Berkas halaman web dipisah dari `app.py`:
`templates/index.html` (struktur), `static/style.css` (tampilan),
`static/app.js` (interaksi).

---

## Fitur Halaman Web

- **Encode & Decode** per-metode dengan tombol **Salin** selektif tiap metode,
  plus tombol **→ input** untuk mengirim hasil kembali ke input (chaining).
- **Petunjuk decode berlapis** — kalau sebuah hasil decode masih tampak ter-encode
  (mis. base64 di dalam base64), muncul pil **"↻ mungkin masih {jenis}"** dengan
  tombol **Decode lagi** (kupas selapis) dan **Kupas semua** (tampilkan seluruh
  rantai sampai pesan akhir). Bersifat heuristik ("mungkin"), hanya pada hasil decode.
- **Live mode** (default aktif) — hasil diperbarui otomatis saat mengetik.
- Metode **decode yang gagal disembunyikan** secara default (label menampilkan
  jumlah berhasil/gagal); ada toggle **"Tampilkan yang gagal"**.
- **Obfuscate** dengan **unggah file** atau **seret & lepas (drag & drop)** file
  (tipe auto dari ekstensi) dan **unduh hasil**.
- **Steganografi** — sisipkan/ekstrak pesan pada bit LSB gambar PNG, dengan
  pratinjau sebelum/sesudah.
- **JWT** (bergaya *jwt.io*) — tempel token untuk melihat **header**, **payload**,
  dan **klaim standar** (exp/iat/nbf ditafsirkan jadi tanggal + status berlaku),
  **verifikasi signature** dengan secret, serta mode **buat token** baru.
  Bagian token diwarnai (header merah · payload ungu · signature biru).
- **Counter** karakter/byte, tombol **Bersihkan**, dan pintasan **Ctrl/Cmd+Enter**.
- Indikator **loading**, notifikasi **toast**, pesan **error** berstyle, dan
  tampilan **responsif** (mobile).

---

## Daftar Endpoint

### `GET /`
Halaman web berisi form Encode/Decode dan Obfuscate. Mengembalikan HTML.

### `POST /api/translate`
Meng-encode **dan** decode sekaligus dari satu input (seperti *dencode*). Dipakai
oleh form web: satu input, dua hasil langsung muncul.

- **Input** (JSON): `{"text": "halo"}`
- **Output**:
  ```json
  {
    "input": "halo",
    "encode": { "base64": { "ok": true, "value": "aGFsbw==" } },
    "decode": { "base64": { "ok": false, "error": "..." } }
  }
  ```
- Tiap hasil **decode** yang berhasil diberi field `hint` bila hasilnya masih bisa
  di-decode lagi: `"hint": { "again": true, "guess": "base64" }` (atau
  `{ "again": false }`).

### `POST /api/encode`
Meng-encode teks ke **semua** metode sekaligus.

- **Input** (JSON): `{"text": "halo"}`
- **Metode**: base64, base32, hex, binary, url, unicode, ascii
- **Output**:
  ```json
  {
    "input": "halo",
    "results": {
      "base64": { "ok": true, "value": "aGFsbw==" },
      "hex":    { "ok": true, "value": "68616c6f" }
    }
  }
  ```

### `POST /api/decode`
Kebalikan dari encode, dengan bentuk input/output yang sama. Metode yang tidak
cocok dengan input ditandai `"ok": false` dan pesan error-nya, tanpa meng-crash.

- **Input** (JSON): `{"text": "aGFsbw=="}`
- **Output**: `results.base64 = { "ok": true, "value": "halo" }` (tiap hasil berhasil
  juga memuat `hint`, lihat `/api/translate`).

### `POST /api/peel`
Mengupas encoding **berlapis** sampai habis (dipakai tombol **Kupas semua**).
Secara serakah mendeteksi & men-decode lapis demi lapis (base64/base32/hex/biner/
url/unicode/ascii) sampai hasilnya bukan encoding lagi.

- **Input** (JSON): `{"text": "WkZjMWNHSkhSbkZaV0d4bw=="}`
- **Output**:
  ```json
  {
    "input": "WkZjMWNHSkhSbkZaV0d4bw==",
    "steps": [
      { "name": "base64", "value": "ZFc1cGJHRnFZWGxo" },
      { "name": "base64", "value": "dW5pbGFqYXlh" },
      { "name": "base64", "value": "unilajaya" }
    ],
    "final": "unilajaya"
  }
  ```
- Kalau tak ada lapisan yang terdeteksi, `steps` kosong dan `final` = input.

### `POST /api/jwt/decode`
Membaca token JWT (**tanpa** butuh secret) dan, bila secret diberikan, sekaligus
memverifikasi signature. Verifikasi hanya untuk HMAC (**HS256/HS384/HS512**);
algoritma RS/ES tetap bisa di-*decode* tetapi tidak diverifikasi.

- **Input** (JSON): `{"token": "eyJ...", "secret": "your-256-bit-secret"}`
  (field `secret` opsional)
- **Output**:
  ```json
  {
    "header": { "alg": "HS256", "typ": "JWT" },
    "payload": { "sub": "1234567890", "name": "John Doe", "iat": 1516239022 },
    "signature": "SflKxwRJSMe...",
    "algorithm": "HS256",
    "claims": [
      { "key": "iat", "label": "Issued At", "value": 1516239022,
        "note": "2018-01-18 01:30:22 UTC" }
    ],
    "verify": { "verified": true, "algorithm": "HS256",
                "reason": "Signature cocok dengan secret." }
  }
  ```
- `verify` bernilai `null` bila secret tidak diberikan. Klaim waktu (`exp`, `nbf`,
  `iat`) ditafsirkan jadi tanggal UTC; `exp`/`nbf` juga menandai status berlaku.

### `POST /api/jwt/encode`
Membuat & menandatangani token baru (HMAC).

- **Input** (JSON): `{"payload": {"sub":"123"}, "secret": "kunci", "algorithm": "HS256"}`
  (`algorithm` opsional, default `HS256`; `header` opsional untuk field tambahan)
- **Output**: `{"token": "eyJ...", "algorithm": "HS256"}`

### `POST /api/obfuscate`
Meng-obfuscate kode. Mendukung tipe **js, css, py, html**.

- **Input** (salah satu):
  - JSON: `{"code": "print(1)", "type": "py"}`
  - Upload file: field `file` (tipe otomatis dari ekstensi `.js/.css/.py/.html`)
- **Output**: `{"type": "...", "result": "..."}` dengan tambahan:
  - `css` → `mapping` (peta nama class/id lama → baru)
  - `html` → `verify` (`{ok, message}` hasil cek round-trip)

> **Catatan tipe `css`:** `result`-nya adalah **JavaScript** — sebuah *injector*
> yang menyuntik CSS ke DOM saat dijalankan, **bukan** file `.css`. Jadi hasilnya
> dipakai di dalam `<script>`, dan di halaman web diunduh sebagai
> **`obfuscated.css.js`** (bukan `.css`). Tipe js/py/html diunduh sesuai
> ekstensinya masing-masing.

---

## Contoh `curl`

```bash
# Encode + Decode sekaligus (satu input, dua hasil)
curl -X POST http://127.0.0.1:8000/api/translate \
  -H 'Content-Type: application/json' -d '{"text":"halo"}'

# Encode
curl -X POST http://127.0.0.1:8000/api/encode \
  -H 'Content-Type: application/json' -d '{"text":"halo"}'

# Decode
curl -X POST http://127.0.0.1:8000/api/decode \
  -H 'Content-Type: application/json' -d '{"text":"aGFsbw=="}'

# Kupas encoding berlapis sampai habis
curl -X POST http://127.0.0.1:8000/api/peel \
  -H 'Content-Type: application/json' -d '{"text":"WkZjMWNHSkhSbkZaV0d4bw=="}'

# JWT — decode + verifikasi signature
curl -X POST http://127.0.0.1:8000/api/jwt/decode \
  -H 'Content-Type: application/json' \
  -d '{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c","secret":"your-256-bit-secret"}'

# JWT — buat token baru
curl -X POST http://127.0.0.1:8000/api/jwt/encode \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"sub":"123","name":"Ana"},"secret":"kunci","algorithm":"HS256"}'

# Obfuscate via JSON
curl -X POST http://127.0.0.1:8000/api/obfuscate \
  -H 'Content-Type: application/json' -d '{"code":"print(1+1)","type":"py"}'

# Obfuscate via upload file (tipe auto dari ekstensi)
curl -X POST http://127.0.0.1:8000/api/obfuscate -F 'file=@Example/jstester.js'
```

---

## Kode Status

| Kode | Arti |
|------|------|
| `200` | Sukses |
| `400` | Input salah / kosong (mis. `text` kosong, tipe tidak dikenal) |
| `500` | Gagal saat proses obfuscate |

---

## Catatan

- Tanpa autentikasi — ditujukan untuk pemakaian lokal (`127.0.0.1`).
- Endpoint encode/decode menjalankan **semua** metode sekaligus, sejalan dengan
  menu "Encode & Decode" gabungan di `main.py`.
