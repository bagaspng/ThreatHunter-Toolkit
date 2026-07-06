# obfuscate.py — CLI Obfuscator HTML / CSS / JS / Python (murni-Python)

CLI **Python murni** untuk meng-obfuscate file **HTML, CSS, JS, dan Python**,
termasuk file HTML *hybrid* yang punya inline `<style>` dan `<script>`.

Dependensi ringan: hanya `beautifulsoup4` + `lxml` untuk parsing HTML; sisanya
modul bawaan Python (`base64`, `marshal`, `zlib`, `re`, `argparse`, dst).

## Instalasi

```bash
pip install -r requirements.txt
```

## Cara Pakai

### Mode file

```bash
python obfuscate.py --input page.html --output page.obf.html
python obfuscate.py -i app.js   -o app.obf.js
python obfuscate.py -i style.css -o style.obf.css      # + tulis style.obf.css.map.json
python obfuscate.py -i app.py   -o app.obf.py
```

### Mode paste / stdin

Jalankan tanpa `--input`, tempel kode, lalu tekan **Ctrl+D** (EOF).
Hasil tampil di terminal, atau simpan pakai `--output`.

```bash
python obfuscate.py --type js
python obfuscate.py --type py -o out.py
```

## Flag

| Flag | Nilai | Fungsi |
|------|-------|--------|
| `--input`, `-i` | path | File input. Kosong = baca stdin. |
| `--output`, `-o` | path | File output. Kosong = cetak ke stdout. |
| `--type`, `-t` | `auto`/`html`/`js`/`css`/`py` | Paksa tipe (default `auto` dari ekstensi; stdin default `html`). |
| `--map-output` | path | Lokasi file JSON mapping untuk mode CSS. |
| `--no-verify` | — | Lewati verifikasi round-trip untuk mode HTML. |

## Contoh

```bash
# HTML hybrid berlapis + verifikasi otomatis
python obfuscate.py -i index.html -o index.obf.html

# JS murni via paste
printf 'var s="rahasia";function f(x){return x+1}' | python obfuscate.py -t js

# Python (2 lapis default rekomendasi)
python obfuscate.py -i tool.py -o tool.obf.py
```