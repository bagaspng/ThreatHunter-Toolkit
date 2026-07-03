"""Orchestrator obfuscation HTML (termasuk file hybrid inline <style>/<script>).

Meniru gaya phpkobo (tanpa opsi) tapi dengan pipeline berlapis sesuai
spesifikasi:

  1. Parse dokumen dengan BeautifulSoup(lxml); tiap <script> inline
     diobfuscate lewat javascript-obfuscator (subprocess Node.js).
  2. Dokumen hasil (HTML + CSS + JS-yang-sudah-diobfuscate) di-encode utuh:
        substitution cipher (Python)  -> payload base64 + tabel invers
        zero-width delimiter (Python) -> gabung payload & tabel jadi 1 string
  3. Dibungkus jadi loader script berisi: guard anti-tamper (charset+checksum),
     decoder zero-width, decoder substitution cipher, lalu document.write().
  4. Loader LENGKAP diproses ulang lewat javascript-obfuscator (lapis luar).
  5. Loader terobfuscate ditanam dalam kerangka HTML minimal.

Tanpa opsi level / format payload / hapus-dari-DOM (sesuai keluhan pengguna):
loader otomatis lenyap begitu document.write() mengganti isi halaman.
"""

import json

from bs4 import BeautifulSoup

from modules import js_engine
from modules import substitution_cipher
from modules import zwsp_delimiter
from modules import anti_tamper


def _obfuscate_inline_scripts(html):
    """Obfuscate isi tiap <script> inline, kembalikan HTML dengan script
    yang sudah diganti. Memakai BeautifulSoup hanya untuk *menemukan* isi
    script, penggantian dilakukan pada string asli agar sisa dokumen
    (emoji, whitespace, atribut) tetap utuh."""
    soup = BeautifulSoup(html, "lxml")
    result = html
    for tag in soup.find_all("script"):
        if tag.get("src"):
            continue
        code = tag.string if tag.string is not None else tag.get_text()
        if not code or not code.strip():
            continue
        obf = js_engine.obfuscate(code)
        result = result.replace(code, obf, 1)
    return result


def _build_loader(combined, expected_checksum):
    """Susun loader JS (lapis dalam, sebelum diobfuscate lapis luar)."""
    ck = "_ck"
    dec = "_dec"
    split = "_split"
    payload_literal = json.dumps(combined)  # ASCII-safe (​ dst.)

    return (
        "(function(){"
        + anti_tamper.js_checksum_function(ck)
        + substitution_cipher.js_decoder_function(dec)
        + zwsp_delimiter.js_split_function(split)
        + "var P=" + payload_literal + ";"
        + anti_tamper.js_guard("P", ck, expected_checksum)
        + "var parts=" + split + "(P);"
        + "var h=" + dec + "(parts[0],parts[1]);"
        + "document.open();document.write(h);document.close();"
        # Ala phpkobo (dua-duanya default, bukan opsional): pembersihan ditunda
        # lewat setTimeout(0) supaya script asli sempat dieksekusi parser dulu.
        + "setTimeout(function(){try{"
        # 1) Remove all script blocks: hapus semua tag <script> dari DOM.
        + "var ss=document.querySelectorAll('script');"
        + "for(var i=ss.length-1;i>=0;i--){"
        + "if(ss[i].parentNode){ss[i].parentNode.removeChild(ss[i]);}}"
        # 2) Remove all comment blocks: telusuri DOM, kumpulkan node komentar,
        #    lalu hapus (kumpulkan dulu supaya TreeWalker tidak rusak).
        + "var wk=document.createTreeWalker(document,NodeFilter.SHOW_COMMENT,null,false);"
        + "var cm=[],cn;"
        + "while((cn=wk.nextNode())){cm.push(cn);}"
        + "for(var j=0;j<cm.length;j++){"
        + "if(cm[j].parentNode){cm[j].parentNode.removeChild(cm[j]);}}"
        + "}catch(e){}},0);"
        + "})();"
    )


def _wrap_page(loader_js):
    return (
        "<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\"></head>\n"
        "<body>\n<script>\n" + loader_js + "\n</script>\n</body>\n</html>\n"
    )


def build(html):
    """Jalankan pipeline penuh.

    Return (final_html, rendered) di mana `rendered` adalah dokumen tepat
    sebelum di-cipher (HTML dengan inline script sudah diobfuscate) — dipakai
    verifier untuk memastikan decode runtime menghasilkan string yang sama.
    """
    rendered = _obfuscate_inline_scripts(html)

    payload_b64, inverse_b64 = substitution_cipher.encode(rendered)
    combined = zwsp_delimiter.combine([payload_b64, inverse_b64])
    expected_checksum = anti_tamper.checksum(combined)

    inner_loader = _build_loader(combined, expected_checksum)
    outer_loader = js_engine.obfuscate(inner_loader)  # lapis luar
    return _wrap_page(outer_loader), rendered


def obfuscate_html(html):
    """Obfuscate satu dokumen HTML utuh (ala phpkobo, tanpa opsi)."""
    return build(html)[0]
