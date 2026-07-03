# HTML / CSS / JS Obfuscator

CLI obfuscator untuk file HTML, CSS, dan JavaScript. Python sebagai orchestrator,
`javascript-obfuscator` (Node.js) untuk bagian JS.

## Instalasi

Butuh **Python 3.9+** dan **Node.js 16+** (beserta `npm`).

```bash
# Dependensi Python (beautifulsoup4 + lxml)
pip install -r requirements.txt

# Dependensi Node.js (javascript-obfuscator + jsdom)
npm install
```

## Pemakaian

### 1. Lewat CLI (`obfuscate.py`)

Mode file:

```bash
python obfuscate.py -i page.html  -o page.obf.html
python obfuscate.py -i app.js     -o app.obf.js
python obfuscate.py -i style.css  -o style.obf.css
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
| `-t`, `--type` | `auto` / `html` / `js` / `css` (default: `auto` dari ekstensi) |
| `--map-output` | Lokasi file JSON mapping (mode CSS) |
| `--no-verify` | Lewati verifikasi (mode HTML) |

### 2. Lewat menu interaktif (`main.py`)

```bash
python main.py
```

Pilih menu **6. Obfuscate File Web (HTML/CSS/JS)**, lalu pilih HTML / JavaScript /
CSS, dan masukkan nama file yang mau diobfuscate.
