# obfuscate.py — CLI Obfuscator HTML / CSS / JS (Python + Node.js)

CLI untuk meng-obfuscate file **HTML, CSS, JS** (termasuk HTML *hybrid* dengan
inline `<style>`/`<script>`). **Python** berperan sebagai *orchestrator*, dan
bagian JavaScript diobfuscate lewat **`javascript-obfuscator` (Node.js)** yang
dipanggil sebagai *subprocess*.

Mode HTML mengikuti gaya [phpkobo HTML Obfuscator](https://www.phpkobo.com/
html-obfuscator): **tanpa opsi apa pun**. Tidak ada pilihan level, format
payload, maupun "hapus loader dari DOM" — cukup masukkan HTML, keluar HTML
terobfuscate.

> ⚠️ **Untuk pembelajaran, bukan proteksi produksi.** Obfuscation ≠ enkripsi.
> Siapa pun yang menjalankan halaman di browser bisa mengambil hasil decode-nya.
> Jangan andalkan ini untuk menyembunyikan rahasia.

## Arsitektur & Pipeline (mode HTML)

```
HTML asli
  │  1. Parse (BeautifulSoup + lxml), tiap <script> inline diobfuscate
  │     lewat javascript-obfuscator (subprocess Node.js)
  ▼
Dokumen (HTML+CSS+JS-terobfuscate)
  │  2. Substitution cipher (Python, level byte UTF-8) -> payload base64 + tabel invers
  │  3. Zero-width unicode delimiter (Python) -> gabung payload & tabel jadi 1 string
  │  4. Bungkus jadi loader script:
  │        - guard anti-tamper (cek charset + checksum djb2)
  │        - decoder zero-width  + decoder substitution cipher
  │        - document.write() untuk merakit ulang halaman
  │        - "Remove all script blocks" + "Remove all comment blocks":
  │          setelah script asli dieksekusi, semua tag <script> DAN node
  │          komentar <!--...--> dihapus dari DOM (setTimeout 0)
  │  5. Loader LENGKAP diproses ulang lewat javascript-obfuscator (LAPIS LUAR)
  ▼
HTML minimal berisi <script> loader terobfuscate
  │  6. Verifikasi otomatis: jalankan loader di sandbox jsdom (Node), tangkap
  │     document.write(), pastikan identik dengan dokumen input (emoji/unicode)
  ▼
Output
```

Karena seluruh dokumen ikut ter-encode, bagian inline `<script>`/`<style>`
otomatis tersembunyi di dalam payload. Loader juga hilang sendiri begitu
`document.write()` mengganti isi halaman — jadi tidak ada opsi "hapus dari DOM".

**Remove all script blocks + Remove all comment blocks (bawaan, ala phpkobo —
dua-duanya default, bukan opsional).** Setelah halaman dirakit ulang, loader
lewat `setTimeout(…,0)` menghapus dari DOM: **semua** tag `<script>` dan
**semua** node komentar `<!--...-->`. Script asli tetap **dieksekusi** dulu,
baru jejaknya lenyap dari tab Elements/DevTools. Perilaku tetap (tanpa prompt).

> Catatan jujur: ini hanya membersihkan *tag* `<script>` dari DOM hidup dan
> menyembunyikan HTML dari **View Source (Ctrl+U)**. HTML hasil render **tetap**
> terlihat penuh di **DevTools → Elements** — batas yang berlaku untuk semua
> obfuscator HTML, phpkobo sekalipun.

## Struktur file

| File | Peran |
|------|-------|
| `obfuscate.py` | CLI orchestrator (file/stdin), `check_dependencies()`. |
| `modules/html_obfuscator.py` | Pipeline HTML lengkap (build + verify). |
| `modules/js_engine.py` | Wrapper subprocess `javascript-obfuscator`. |
| `modules/substitution_cipher.py` | Cipher substitusi byte (encoder Python + decoder JS). |
| `modules/zwsp_delimiter.py` | Delimiter zero-width unicode. |
| `modules/anti_tamper.py` | Guard charset + checksum (snippet JS di-generate Python). |
| `modules/css_obfuscator.py` | Obfuscator CSS (rename `.class`/`#id`). |
| `modules/verifier.py` + `modules/verify.js` | Verifikasi jsdom. |
| `requirements.txt` / `package.json` | Dependensi Python / Node.js. |

## Instalasi

Butuh **Python 3.9+** dan **Node.js 16+** (dengan `npm`).

```bash
# 1. Dependensi Python
pip install -r requirements.txt          # beautifulsoup4 + lxml

# 2. Dependensi Node.js (lokal di folder project — disarankan)
npm install                              # javascript-obfuscator + jsdom
```

`obfuscate.py` otomatis menemukan `javascript-obfuscator` dari
`node_modules/.bin` lokal, atau dari PATH global kalau kamu memasangnya dengan
`npm install -g javascript-obfuscator`.

## Cara Pakai

### Mode file

```bash
python obfuscate.py --input page.html --output page.obf.html
python obfuscate.py -i app.js  -o app.obf.js
python obfuscate.py -i style.css -o style.obf.css     # + style.obf.css.map.json
```

### Mode paste / stdin

Jalankan tanpa `--input`, tempel kode, lalu tekan **Ctrl+D** (EOF).

```bash
python obfuscate.py --type html -o out.html
printf '<div>Halo 🌍</div>' | python obfuscate.py --type html
```

### Lewat menu interaktif

`python main.py` → menu **9. Obfuscate File Web (HTML/CSS/JS)**. Alur HTML
langsung: pilih sumber input → hasil (tanpa pertanyaan opsi).

## Flag

| Flag | Nilai | Fungsi |
|------|-------|--------|
| `--input`, `-i` | path | File input. Kosong = baca stdin. |
| `--output`, `-o` | path | File output. Kosong = cetak ke stdout. |
| `--type`, `-t` | `auto`/`html`/`js`/`css` | Paksa tipe (default `auto` dari ekstensi). |
| `--map-output` | path | Lokasi file JSON mapping untuk mode CSS. |
| `--no-verify` | — | Lewati verifikasi jsdom (mode HTML). |

Tidak ada `--level`, `--encode`, atau `--remove-script`: mode HTML mengikuti
gaya phpkobo (tanpa opsi), obfuscation JS memakai satu preset tetap.

## Apa yang dilakukan tiap tipe

**HTML** (termasuk hybrid) — pipeline berlapis di atas, tanpa opsi.

**JS** (`.js` atau `--type js`):
- Diobfuscate langsung oleh `javascript-obfuscator` (stringArray + base64,
  control-flow flattening, self-defending, dll). Karena memakai parser JS asli,
  konstruksi modern (template literal, arrow function, dsb) aman.

**CSS** (`.css`):
- Nama `.class` / `#id` di *selector* diacak; nilai deklarasi (mis. warna
  `#fff`) tidak diubah. Menghasilkan `*.map.json` (mapping `.orig` → `.baru`).

## Verifikasi otomatis (jsdom)

Untuk mode HTML, tool menjalankan loader hasil obfuscation di sandbox **jsdom**,
menangkap string `document.write()`, dan membandingkannya **byte-exact** dengan
dokumen yang di-encode. Kalau cocok:

```
[verify] OK Verifikasi OK: decode runtime identik dengan input.
```

Ini khusus memastikan karakter emoji / unicode kompleks (mis. `🌍`, `中文`,
`𝕏`) kembali persis setelah melewati cipher + delimiter + 2 lapis obfuscation.
Lewati dengan `--no-verify` bila jsdom belum terpasang.

## Troubleshooting

**`javascript-obfuscator tidak ditemukan` / dependency belum lengkap**
- Pastikan Node.js ada: `node --version`.
- Pasang tool-nya: `npm install` (di folder project) atau
  `npm install -g javascript-obfuscator`.
- Cek: `npx javascript-obfuscator --version` atau
  `ls node_modules/.bin/javascript-obfuscator`.
- Bisa juga arahkan manual lewat env: `JS_OBFUSCATOR_BIN=/path/ke/binary`.

**`Mode HTML butuh beautifulsoup4 + lxml`**
- `pip install -r requirements.txt`.

**`jsdom belum terpasang, verifikasi dilewati`**
- `npm install jsdom`, atau jalankan dengan `--no-verify`.

**Output HTML tidak menampilkan apa-apa di browser**
- Loader butuh JavaScript aktif (pakai `document.write`). Pastikan JS enabled.

## Catatan

Tool ini dibuat untuk **belajar** teknik obfuscation web (delegasi subprocess,
cipher substitusi, steganografi zero-width, anti-tamper ringan, obfuscation
berlapis) — **bukan** mekanisme keamanan kriptografis untuk produksi.
