# Obfuscate Detector

Web pure-Python + Flask untuk **mendeteksi** obfuscate dan memberi **clue** cara
deobfuscate — tanpa pernah menampilkan hasil decode.

## Jalankan (web)
```
pip install -r requirements.txt
python app.py
# buka http://127.0.0.1:8001
```

## CLI (pindai file/folder)
```
python detect.py suspicious.js              # tabel
python detect.py ./samples --format csv     # CSV
python detect.py ./samples --format json    # JSON
python detect.py ./repo --fail-on-detect    # exit 1 bila ada temuan (CI)
```

## Test
```
python -m pytest -v
```

## Deteksi
- Encoding: base64/base32/hex/binary/ascii-desimal/url/unicode (termasuk
  berlapis), plus `encoded_binary` (base64/hex membungkus gzip/zlib/PE/ELF/... via magic-bytes).
- JavaScript: packer (Dean Edwards), obfuscator.io, fromCharCode, escape \xNN,
  array-index, eval(atob), serta simbolik: JSFuck, AAencode, JJencode.
- Python (via `ast`, parse-only): marshal/exec, eval/compile, base64+zlib+exec,
  chr+join, dan gaya lambda/pyfuscate (underscore_mangle).
- PHP: eval/assert atas base64/gzinflate/str_rot13 (webshell), preg_replace /e,
  dispatch `$GLOBALS`/variable-variable.
- PowerShell: -EncodedCommand/-enc, Deflate/Gzip+FromBase64String, -join+[char],
  -f+backtick, IEX.
- Unicode smuggling: bidi override (Trojan Source), zero-width, homoglyph.
- Generik: entropy Shannon (global + sliding-window untuk blob tersembunyi),
  entropi nama identifier, rasio printable.

Verdict memakai tingkat keyakinan (Bersih/Rendah/Sedang/Tinggi): satu sinyal
kuat, atau beberapa sinyal lemah yang menumpuk, sama-sama menandai obfuscated.
Setiap temuan disertai clue berbahasa awam tentang cara membukanya.

Tanpa batas ukuran masukan (hanya dibatasi memori yang tersedia).

Jaminan: response API / output CLI tidak pernah memuat teks hasil decode.
