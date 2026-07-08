# HTML / CSS / JS / Python Obfuscator

CLI obfuscator untuk file HTML, CSS, JavaScript, dan Python. Murni Python,
tanpa Node.js.

## Instalasi

Butuh **Python 3.9+**.

```bash
# Dependensi Python (beautifulsoup4 + lxml)
pip install -r requirements.txt
```

## Pemakaian

### 1. Lewat CLI (`obfuscate.py`)

Mode file:

```bash
python obfuscate.py -i page.html  -o page.obf.html
python obfuscate.py -i app.js     -o app.obf.js
python obfuscate.py -i style.css  -o style.obf.css
python obfuscate.py -i tool.py    -o tool.obf.py
```

Mode stdin (tempel kode lalu tekan Ctrl+D):

```bash
python obfuscate.py --type html -o out.html
```

Opsi:

| Flag | Fungsi |
|------|--------|
| `-i`, `--input` | File input (kosong = baca stdin) |
| `-o`, `--output` | File output (kosong = cetak ke layar) |
| `-t`, `--type` | `auto` / `html` / `js` / `css` / `py` (default: `auto` dari ekstensi) |
| `--map-output` | Lokasi file JSON mapping (mode CSS) |
| `--no-verify` | Lewati verifikasi (mode HTML) |

### 2. Lewat menu interaktif (`main.py`)

```bash
python main.py
```

Pilih menu **6. Obfuscate File (HTML/CSS/JS/PY)**, lalu pilih HTML / JavaScript /
CSS / Python, dan masukkan nama file yang mau diobfuscate. Hasilnya tersimpan di
dalam folder proyek ini.
