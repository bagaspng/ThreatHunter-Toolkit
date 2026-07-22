# Obfuscate Detector

Web pure-Python + Flask untuk **mendeteksi** obfuscate dan memberi **clue** cara
deobfuscate — tanpa pernah menampilkan hasil decode.

## Jalankan
```
pip install -r requirements.txt
python app.py
# buka http://127.0.0.1:8001
```

## Test
```
python -m pytest -v
```

## Deteksi
- Encoding: base64/base32/hex/binary/ascii-desimal/url/unicode (termasuk berlapis).
- JavaScript: packer, obfuscator.io, fromCharCode, escape \xNN, array-index, eval(atob).
- Python: marshal/exec, eval/compile, base64+zlib+exec, chr+join (via `ast`, parse-only).
- Generik: entropy Shannon, entropi nama identifier, rasio printable.

Jaminan: response API tidak pernah memuat teks hasil decode.
