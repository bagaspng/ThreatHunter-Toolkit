# File Hidder — Script Sembunyikan & Ekstrak File

Script Python sederhana untuk menyembunyikan satu atau beberapa file di dalam file lain (foto, video, dokumen, dll), dengan opsi proteksi password.

## Cara Kerja

1. File-file rahasia dikemas jadi satu paket (nama, ukuran, dan isi masing-masing file).
2. Paket tersebut dienkripsi dengan **Fernet** (AES + HMAC). Kunci enkripsi diturunkan dari password lewat **PBKDF2-HMAC-SHA256** (480.000 iterasi + salt acak) — atau kunci tetap bawaan jika tidak memakai password.
3. Hasil enkripsi ditempel di **belakang** file cover, diawali marker unik + flag penanda password + salt + panjang data.
4. Karena kebanyakan format file (JPG, PDF, MP4, dll) mengabaikan data tambahan setelah penanda akhir mereka sendiri, file cover tetap bisa dibuka/diputar seperti biasa meski sudah ditambahkan data rahasia.
5. Saat ekstraksi, script mencari marker dari belakang file, membaca flag untuk tahu apakah perlu meminta password, lalu mendekripsi dan mengembalikan file-file asli ke folder tujuan.

## Instalasi

```bash
pip install -r requirements.txt
```

Hanya butuh satu library eksternal: `cryptography`. Sisanya bawaan Python 3.7+.

## Cara Pakai

### Menyembunyikan file (`hide`)

**Tanpa password:**
```bash
python script.py hide -c foto.jpg -s dokumen.pdf -o hasil.jpg
```

**Dengan password (tambahkan flag `-p`):**
```bash
python script.py hide -c foto.jpg -s dokumen.pdf -o hasil.jpg -p
```
Script akan meminta password dua kali (input tidak ditampilkan di layar).

**Menyembunyikan beberapa file sekaligus:**
```bash
python script.py hide -c video.mp4 -s rahasia1.txt rahasia2.docx rahasia3.pdf -o video_tersembunyi.mp4 -p
```

> **Penting:** ekstensi file `-o` (output) harus sama dengan ekstensi file `-c` (cover). Kalau berbeda, script akan menolak dan menampilkan error.

### Mengekstrak file (`extract`)

```bash
python script.py extract -i hasil.jpg -o folder_output
```

Script **otomatis mendeteksi** apakah file tersebut memakai password atau tidak:
- Jika **tidak** memakai password → langsung diekstrak tanpa perlu input apa pun.
- Jika **memakai** password → otomatis muncul prompt untuk memasukkan password yang sama seperti saat `hide`.

Tidak perlu flag tambahan apa pun saat extract — cukup `-i` dan `-o`.

## Argumen

| Mode | Flag | Wajib | Keterangan |
|------|------|-------|------------|
| `hide` | `-c`, `--cover` | Ya | File cover (mis. `foto.jpg`) |
| `hide` | `-s`, `--secret` | Ya | Satu atau lebih file yang ingin disembunyikan |
| `hide` | `-o`, `--output` | Ya | Nama file hasil (ekstensi harus sama dengan cover) |
| `hide` | `-p`, `--password` | Tidak | Aktifkan proteksi password |
| `extract` | `-i`, `--input` | Ya | File yang berisi data tersembunyi |
| `extract` | `-o`, `--output` | Ya | Folder tujuan hasil ekstraksi |

## Contoh Workflow Lengkap

```bash
# Siapkan file
echo "data rahasia" > secret.txt

# Sembunyikan dengan password
python script.py hide -c foto.jpg -s secret.txt -o foto_rahasia.jpg -p

# Ekstrak kembali (password akan diminta otomatis)
python script.py extract -i foto_rahasia.jpg -o hasil_extract

# Cek isinya
cat hasil_extract/secret.txt
```

## Batasan & Catatan Keamanan

- Teknik yang dipakai adalah **menempelkan data terenkripsi di akhir file**, bukan steganografi tingkat lanjut (seperti menyisipkan bit di piksel gambar/LSB). File hasil tetap bisa dibuka normal, tapi ukurannya jadi sedikit lebih besar dari cover aslinya — dan siapa pun yang memeriksa file dengan tool forensik atau membandingkan ukuran file bisa mendeteksi ada data tambahan.
- Mode **tanpa password** memakai kunci enkripsi tetap yang tertanam di script ini (`NO_PASSWORD_DEFAULT`). Artinya siapa pun yang punya salinan script ini bisa membongkar file yang disembunyikan tanpa password — mode ini lebih untuk *menyembunyikan dari orang awam*, bukan mengamankan dari orang yang paham cara kerja script.
- Jika lupa password yang dipakai saat `hide`, **tidak ada cara memulihkan** file yang disembunyikan — password tidak disimpan di mana pun.

## Requirements

Lihat [`requirements.txt`](./requirements.txt).
