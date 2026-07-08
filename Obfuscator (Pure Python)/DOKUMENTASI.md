# Dokumentasi — Obfuscator (Pure Python)

Toolkit keamanan berbasis teks yang ditulis murni dengan Python standard
library. Menyediakan dua kelompok fitur:

1. **Utilitas teks** — encode, decode, hashing, deteksi encoding, dan batch.
2. **Obfuscator file** — menyamarkan berkas HTML, CSS, JavaScript, dan Python
   menjadi payload satu-baris yang men-decode dirinya sendiri saat dijalankan.

Tidak butuh dependency eksternal — 100% Python standard library (tanpa Node.js).

---

## 1. Titik Masuk (Entry Point)

### `main.py` — menu interaktif
Program menu berbasis terminal. Jalankan:

    python3 main.py

Menu utama:
1. Encode
2. Decode
3. Hashing
4. Deteksi Encoding
5. Batch Processing
6. Obfuscate File (HTML/CSS/JS/PY)
7. Keluar

Untuk obfuscate, kode dapat ditempel langsung atau dibaca dari file, dan hasil
dapat ditampilkan atau disimpan ke file (masuk ke folder `Result/`).

### `obfuscate.py` — CLI non-interaktif
Cocok untuk automasi / pipeline. Contoh:

    python3 obfuscate.py -i Example/csstester.css -o Result/cssresult.css
    python3 obfuscate.py -i app.js -t js -o app.obf.js
    cat app.py | python3 obfuscate.py -t py -o app.obf.py

Opsi:
- `-i, --input`   : file input (kosong = baca stdin).
- `-o, --output`  : file output (kosong = cetak ke stdout).
- `-t, --type`    : paksa tipe (`auto|html|css|js|py`), default `auto` dari ekstensi.
- `--map-output`  : path JSON mapping nama class/id (khusus CSS).
- `--no-verify`   : lewati verifikasi round-trip (khusus HTML).

---

## 2. Struktur Direktori

    Obfuscator (Pure Python)/
    ├── main.py               # menu interaktif
    ├── obfuscate.py          # CLI non-interaktif
    ├── requirements.txt      # kosong — tidak ada dependency eksternal
    ├── Example/              # contoh input (css/html/js/py tester)
    ├── Result/               # folder output default (dibuat otomatis)
    └── modules/              # seluruh modul (lihat bab 5)

---

## 3. Konsep Inti: Packer

Modul `packer.py` adalah jantung ketiga obfuscator HTML/CSS/JS. Ia mengubah
sumber JavaScript apa pun menjadi **satu baris "rimba simbol"** yang men-decode
dirinya sendiri saat runtime lalu mengeksekusinya. Seluruh identifier hanya
berupa `$`/`_`, tanpa angka atau string yang terbaca.

Alur tiap lapis:

    source → UTF-16 → rolling cipher (berumpan-balik) → deret angka
           → String.fromCharCode(...) → decode loop → Function(src)()

Hal yang menyulitkan analisis statis:

1. **Angka tanpa digit** — dibangun dari primitive `+[]`=0, `+!![]`=1,
   `!![]+!![]`=2, ...; lalu disimpan pada objek digit yang nama propertinya
   dikodekan lewat jumlah underscore (mirip `_.__` pada obfuscator sejenis).
2. **Rolling cipher berumpan-balik** — payload dienkripsi sebelum diubah jadi
   angka, jadi membaca deret `String.fromCharCode` secara statis hanya
   menghasilkan ciphertext; pemulihan wajib menjalankan loop decode.
3. **Nama API disembunyikan** — `constructor` dan `charCodeAt` dibangun dari
   kode karakter (tidak bisa di-`grep`/di-hook). Eksekusi lewat
   `[]["constructor"]["constructor"](src)()` (Function-constructor). Hanya
   `String.fromCharCode` yang tetap terbaca sebagai "benih".
4. **Acak per-jalan** — nama global, pemetaan digit→underscore, seed, dan
   pengali cipher diacak tiap kali, sehingga dua hasil berbeda total dan sulit
   dicocokkan oleh deobfuscator berbasis pola.

Bisa dilapis (`layers`), tetapi ekspansinya besar sehingga default 1 lapis.

Obfuscator Python (`py_obfuscator.py`) memakai ide serupa (rolling cipher +
nama tersembunyi + self-decode satu baris) — lihat bab 4.4 dan 5.

---

## 4. Alur Kerja per Fitur

### 4.1 Obfuscate CSS
Modul: `css_obfuscator.py` → `packer.py`

1. Selektor `.class` / `#id` di-rename jadi nama acak `._xxxxxxx` (mapping
   disimpan agar HTML bisa diselaraskan).
2. CSS di-minify (buang komentar, whitespace, `;` terakhir sebelum `}`),
   string literal dilindungi agar isinya tidak rusak.
3. Hasil minify dibungkus dalam **injector JS** yang membuat elemen `<style>`
   dan menyuntikkan CSS ke halaman saat runtime.
4. Injector di-`pack()` → satu baris rimba-simbol self-decoding.

Output: satu baris JS. Saat dijalankan browser, CSS asli disuntik ke DOM.
Mapping nama class dikembalikan terpisah (untuk `--map-output`).

### 4.2 Obfuscate JavaScript
Modul: `js_obfuscator.py` → `packer.py`

1. Tokenisasi source, lalu **rename** identifier lokal jadi `_0x......`.
2. **Encode string** literal jadi pemanggilan `String.fromCharCode(...)`.
3. (level `high`) **Sisipkan dead-code** dan control-flow noise.
4. Hasilnya di-`pack()` → satu baris rimba-simbol self-decoding (lapisan luar).

Output: satu baris JS yang tetap ekuivalen secara fungsional.

### 4.3 Obfuscate HTML
Modul: `html_obfuscator.py` → `substitution_cipher`, `zwsp_delimiter`,
`anti_tamper`, `packer.py`

1. Seluruh dokumen di-encode dengan **substitution cipher** → menghasilkan
   payload base64 + tabel invers base64.
2. Kedua bagian digabung memakai **delimiter zero-width** (karakter tak
   tampak).
3. Dihitung **checksum anti-tamper**; loader menolak berjalan bila payload
   diubah (charset atau checksum tidak cocok).
4. Loader menyusun dokumen (`document.write`) lalu **membersihkan jejak**
   (menghapus tag `<script>` dan komentar dari DOM).
5. Loader dibungkus `pack()` dan ditempel dalam kerangka HTML minimal
   **satu baris**.

Verifikasi round-trip otomatis (`verifier.py`) memastikan hasil decode identik
dengan input sebelum output dianggap sah.

### 4.4 Obfuscate Python
Modul: `py_obfuscator.py`

1. Source di-`zlib` compress, lalu `base64`.
2. Hasilnya lewat **rolling cipher berumpan-balik** ke rentang printable
   (33–126) sehingga blob tampil sebagai satu string "teks sampah".
3. Dibungkus **satu baris** `lambda` (identifier hanya underscore) yang membalik
   cipher → base64 → zlib → teks source → `exec(source, globals())`.
4. Nama `exec`, `zlib`, `base64`, `b64decode`, `decompress`, `builtins` semua
   dibangun via `chr(...)` sehingga tidak muncul sebagai literal (tidak bisa
   di-`grep`).

Default 2 lapis (satu baris di dalam satu baris). Berbasis teks source (bukan
bytecode), jadi **portabel antar-versi Python** dan tidak terkunci ke CPython
tertentu.

Catatan: tetap bisa dibalik dengan menjalankan lalu menangkap hasil decode.
Untuk proteksi nyata gunakan kompilasi native (Nuitka/Cython) atau PyArmor.

### 4.5 Utilitas Teks (Encode/Decode/Hash/Detect/Batch)
Modul: `encoder`, `decoder`, `hasher`, `detector`, `batch_processor`

- **Encode/Decode**: Base64, Base32, Hex, Binary, URL, Unicode-escape, ASCII.
- **Hash**: MD5, SHA1, SHA256, SHA512, CRC32.
- **Detect**: menebak kemungkinan encoding dari sebuah string.
- **Batch**: menerapkan satu metode encode/decode ke banyak baris sekaligus
  (dari input manual atau file), dengan penanganan error per baris.

---

## 5. Referensi Modul & Fungsi

### `__init__.py`
Penanda package (kosong). Membuat folder `modules/` bisa di-`import`.

### `encoder.py`
Mengubah teks menjadi berbagai representasi.
- `to_base64(text)` — Base64.
- `to_base32(text)` — Base32.
- `to_hex(text)` — heksadesimal.
- `to_binary(text)` — deretan biner 8-bit dipisah spasi.
- `to_url(text)` — URL/percent-encoding.
- `to_unicode_escape(text)` — bentuk `\uXXXX`.
- `to_ascii(text)` — kode ASCII/ordinal dipisah spasi.

### `decoder.py`
Kebalikan `encoder.py`.
- `from_base64(text)`, `from_base32(text)`, `from_hex(text)`,
  `from_binary(text)`, `from_url(text)`, `from_unicode_escape(text)`,
  `from_ascii(text)`.

### `hasher.py`
Menghitung hash/checksum dari teks.
- `md5(text)`, `sha1(text)`, `sha256(text)`, `sha512(text)` — hex digest.
- `crc32(text)` — CRC32 8 digit hex.

### `detector.py`
Menebak encoding sebuah string.
- `is_base64(data)`, `is_base32(data)`, `is_hex(data)`, `is_binary(data)`,
  `is_url_encoded(data)` — pengecekan boolean per format.
- `detect(data)` — kembalikan dict `{nama_format: bool}`.

### `batch_processor.py`
Memproses banyak baris sekaligus.
- `ENCODE_METHODS`, `DECODE_METHODS` — pemetaan nama metode → fungsi.
- `batch_process(lines, func)` — terapkan `func` tiap baris, tangani error
  per baris (hasil `(baris, output/Error)`).
- `batch_encode(lines, method)` / `batch_decode(lines, method)` — pembungkus
  untuk metode encode/decode tertentu.

### `file_handler.py`
Baca/tulis file dengan basis folder proyek.
- `resolve_path(filename)` — path input relatif terhadap folder proyek.
- `resolve_output_path(filename)` — path output; nama relatif diarahkan ke
  folder `Result/` (dibuat otomatis).
- `read_file(filename)` — baca isi file (error jelas bila tak ada).
- `read_lines(filename)` — baca file jadi list baris (baris kosong dibuang).
- `write_file(filename, data)` — tulis output ke `Result/`, kembalikan path.

### `utils.py`
Utilitas antarmuka terminal.
- `clear_screen()`, `pause()`, `print_header(title)`, `print_menu(title, options)`
  — tampilan menu.
- `get_input(prompt)` — input satu baris (tolak kosong).
- `get_multiline(prompt)` — input banyak baris hingga baris kosong.
- `get_pasted_code(end_marker)` — tempel kode hingga penanda akhir / Ctrl+D.
- `get_text_source()` — pilih sumber input: teks manual atau file.

### `css_obfuscator.py`
Obfuscator CSS (lihat alur 4.1).
- `obfuscate_css(css, mapping=None, pack=True)` — fungsi utama;
  kembalikan `(output, mapping)`. `pack=False` → hanya CSS ter-rename + minify.
- `apply_mapping_to_html_attrs(class_value, mapping)` — terjemahkan atribut
  `class` HTML memakai mapping hasil rename.
- Internal: `_rename_and_minify`, `_rename_selectors`, `_rand_class`,
  `_minify`, `_css_injector`.

### `js_obfuscator.py`
Obfuscator JavaScript (lihat alur 4.2).
- `obfuscate_js(code, level="medium", pack=True)` — fungsi utama.
  Level: `low` (encode string), `medium` (+rename), `high` (+dead-code).
  `pack=False` → keluarkan JS hasil rename tanpa dibungkus packer.
- Internal: tokenizer, `_rename`, `_encode_strings`, `_inject_dead`,
  `_control_flow_noise`, dsb.

### `py_obfuscator.py`
Obfuscator Python (lihat alur 4.4).
- `obfuscate_python(source, layers=2)` — fungsi utama; kembalikan satu baris
  Python self-decoding.
- Internal: `_wrap_once` (satu lapis: zlib+base64+rolling cipher), `_name`
  (bangun string nama via `chr`), `_blob` (rangkai payload printable jadi
  literal).

### `html_obfuscator.py`
Obfuscator HTML (lihat alur 4.3).
- `build(html)` — kembalikan `(final_html, rendered)`; `rendered` dipakai
  verifier.
- `obfuscate_html(html)` — pembungkus yang hanya kembalikan HTML final.
- Internal: `_build_loader` (rakit loader JS + guard), `_wrap_page`
  (kerangka HTML satu baris).

### `packer.py`
Packer inti (lihat bab 3).
- `pack(src, layers=1)` — bungkus source JS jadi satu baris rimba-simbol
  self-decoding; bisa berlapis (1–5).
- Internal: `_pack_once` (satu lapis), `_encrypt` (rolling cipher berumpan-balik),
  `_digit_object`/`_dref`/`_numx` (angka simbolik lewat objek digit), `_strx`/
  `_fcc` (string lewat `String.fromCharCode`), `_rand_name`/`_digit_map` (acak).

### `substitution_cipher.py`
Cipher substitusi byte (untuk HTML).
- `encode(text)` — kembalikan `(payload_b64, inverse_b64)`.
- `decode(payload_b64, inverse_b64)` — kembalikan teks asli.
- `js_decoder_function(fn_name)` — hasilkan sumber fungsi JS decoder.

### `zwsp_delimiter.py`
Delimiter memakai karakter zero-width (tak tampak).
- `combine(parts)` — gabung list string dengan delimiter zero-width.
- `split(s)` — pecah kembali.
- `js_split_function(fn_name)` — hasilkan sumber fungsi JS pemecah.

### `anti_tamper.py`
Proteksi integritas payload HTML.
- `checksum(s)` — hash DJB2 32-bit.
- `js_checksum_function(fn_name)` — versi JS dari checksum.
- `js_guard(payload_var, ck_fn, expected)` — potongan JS yang menolak berjalan
  bila charset atau checksum payload tidak cocok.

### `verifier.py`
Verifikasi hasil obfuscation HTML.
- `verify(final_html, expected_rendered)` — kembalikan `(ok, pesan)`; memastikan
  struktur output benar dan skema decode round-trip identik dengan input.

---

## 6. Catatan Keamanan (Penting)

Obfuscation di toolkit ini **bukan enkripsi**. Tujuannya menaikkan effort dan
menghambat penyalinan/pembacaan kasual, **bukan** menjamin kerahasiaan.

- Kode yang berjalan di klien selalu bisa dibaca oleh mesin yang menjalankannya,
  sehingga selalu bisa dipulihkan (jalankan lalu tangkap hasilnya).
- Rename nama class/variabel dan komentar yang dibuang tidak dapat dikembalikan,
  tetapi struktur & fungsi tetap utuh.
- Cipher + penyembunyian nama mematahkan analisis statis otomatis dan pencocokan
  pola, tetapi kode yang dieksekusi tetap bisa ditangkap hasil decode-nya.

Untuk perlindungan nyata: pindahkan logika/rahasia ke sisi server, atau untuk
Python gunakan kompilasi native (Nuitka/Cython) atau PyArmor.
