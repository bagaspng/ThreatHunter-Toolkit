# File Hider — SFX Builder

Script Python untuk membangun **Self-Extracting Executable (SFX)** — file `.exe` yang saat diklik otomatis mengekstrak semua payload tersembunyi ke folder temp, lalu menjalankan semuanya secara bersamaan. Payload terenkripsi dengan **Fernet** dan disematkan langsung di dalam body executable, persis seperti cara kerja RAR SFX.

---

## Cara Kerja

1. Semua file payload dikemas jadi satu blob dengan metadata nama dan ukuran masing-masing file.
2. Blob tersebut dienkripsi dengan **Fernet** (AES-128-CBC + HMAC-SHA256), menggunakan kunci acak yang di-generate tiap build.
3. Stub Python dikompilasi jadi `.exe` mandiri menggunakan **PyInstaller** — stub ini bertugas membaca dirinya sendiri saat dijalankan, menemukan payload, mendekripsi, dan mengeksekusi.
4. Kunci Fernet dan payload terenkripsi ditempel di **ekor** stub exe, diawali marker unik sebagai penanda posisi.
5. Jika flag `--icon` diberikan, gambar PNG/JPG dikonversi dulu ke `.ico` sebelum dikompilasi — hasilnya ikon exe terlihat seperti foto di Windows Explorer.
6. Saat exe diklik, stub membaca byte dirinya sendiri, mencari marker dari belakang, mendekripsi payload, mengekstrak semua file ke `%TEMP%`, lalu menjalankan semuanya **bersamaan** via `subprocess.Popen()`.

### Struktur Byte File Output

```
output.exe
├── [PyInstaller stub binary]     ← Logic Python terkompilasi
├── "FVEILKEY" + [Fernet Key]     ← Marker + kunci enkripsi (44 byte)
├── "FVEIL01\x00"                 ← Marker payload
├── [token_len] (4 byte)          ← Panjang ciphertext
└── [Encrypted Token]             ← Semua payload terenkripsi di dalam
```

---

## Instalasi

```bash
pip install -r requirements.txt
```

---

## Cara Pakai

**Build SFX dengan satu payload:**
```bash
python script.py -p payload.bat -o output.exe
```

**Build SFX dengan beberapa payload (semua jalan bersamaan saat diklik):**
```bash
python script.py -p file1.bat file2.exe file3.py -o output.exe
```

**Build SFX dengan ikon custom dari gambar PNG/JPG:**
```bash
python script.py -p payload.bat -o output.exe --icon cover.jpg
```

> Ikon dikonversi otomatis dari PNG/JPG ke `.ico` sebelum dikompilasi. File output tetap `.exe` — hanya tampilannya di Windows Explorer yang terlihat seperti foto.

---

## Argumen

| Flag | Wajib | Keterangan |
|------|-------|------------|
| `-p`, `--payload` | Ya | Satu atau lebih file payload (semua dieksekusi bersamaan saat diklik) |
| `-o`, `--output` | Ya | Nama file output `.exe` |
| `--icon` | Tidak | Gambar PNG/JPG untuk ikon exe |

---

## Format Payload yang Didukung

| Ekstensi | Cara Dieksekusi |
|----------|----------------|
| `.bat`, `.cmd` | `cmd.exe /c` |
| `.exe` | Langsung |
| `.py` | Python interpreter |
| `.ps1` | PowerShell |
| `.vbs` | WScript |
| Lainnya | Asosiasi default Windows (`start`) |

---

## Contoh Workflow Lengkap

```bash
# Buat payload test
echo "start calc.exe" > kalkulator.bat
echo "start notepad.exe" > notepad.bat

# Build SFX dengan ikon foto
python script.py -p kalkulator.bat notepad.bat -o demo.exe --icon cover.jpg

# Klik demo.exe → kalkulator dan notepad terbuka bersamaan
```

---

## Batasan & Catatan

- Windows Defender atau antivirus lain mungkin memberi peringatan saat exe dijalankan — ini normal untuk executable buatan sendiri dengan pola SFX.
- Payload diekstrak ke folder sementara di `%TEMP%` dan **tidak dihapus otomatis** setelah selesai.
- Kunci Fernet di-generate baru tiap build — setiap exe yang dihasilkan punya enkripsi yang berbeda.
- File output selalu berekstensi `.exe` meskipun nama output yang diberikan tidak menyertakannya — script menambahkan ekstensi secara otomatis.

---

## Requirements

Lihat [`requirements.txt`](./requirements.txt).
