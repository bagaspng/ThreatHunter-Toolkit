import json

from bs4 import BeautifulSoup

from modules import js_obfuscator
from modules import substitution_cipher
from modules import zwsp_delimiter
from modules import anti_tamper

def _obfuscate_inline_scripts(html):
    soup = BeautifulSoup(html, "lxml")
    result = html
    for tag in soup.find_all("script"):
        if tag.get("src"):
            continue
        code = tag.string if tag.string is not None else tag.get_text()
        if not code or not code.strip():
            continue
        obf = js_obfuscator.obfuscate_js(code, "high")
        result = result.replace(code, obf, 1)
    return result

def _build_loader(combined, expected_checksum):
    ck = "_ck"
    dec = "_dec"
    split = "_split"
    payload_literal = json.dumps(combined)

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
        + "setTimeout(function(){try{"
        + "var ss=document.querySelectorAll('script');"
        + "for(var i=ss.length-1;i>=0;i--){"
        + "if(ss[i].parentNode){ss[i].parentNode.removeChild(ss[i]);}}"
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
    rendered = _obfuscate_inline_scripts(html)

    payload_b64, inverse_b64 = substitution_cipher.encode(rendered)
    combined = zwsp_delimiter.combine([payload_b64, inverse_b64])
    expected_checksum = anti_tamper.checksum(combined)

    inner_loader = _build_loader(combined, expected_checksum)
    outer_loader = js_obfuscator.obfuscate_js(inner_loader, "high")
    return _wrap_page(outer_loader), rendered

def obfuscate_html(html):
    return build(html)[0]
