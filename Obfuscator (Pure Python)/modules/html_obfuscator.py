import json

from modules import substitution_cipher
from modules import zwsp_delimiter
from modules import anti_tamper
from modules import packer

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
        # Pembersih jejak tahan-async: jalan setelah semua script (termasuk
        # eksternal/CDN yang parser-blocking) selesai dieksekusi, lalu memantau
        # script yang muncul belakangan. Script dihapus SETELAH sempat jalan,
        # supaya fungsionalitas halaman tidak rusak.
        + "var _cl=false;"
        + "function _rm(n){if(n&&n.parentNode){n.parentNode.removeChild(n);}}"
        + "function _sweep(){try{"
        + "var ss=document.getElementsByTagName('script');"
        + "for(var i=ss.length-1;i>=0;i--){_rm(ss[i]);}"
        + "var wk=document.createTreeWalker(document,NodeFilter.SHOW_COMMENT,null,false);"
        + "var cm=[],cn;while((cn=wk.nextNode())){cm.push(cn);}"
        + "for(var j=0;j<cm.length;j++){_rm(cm[j]);}"
        + "}catch(e){}}"
        + "function _watch(s){if(s.src){"
        + "s.addEventListener('load',function(){_rm(s);});"
        + "s.addEventListener('error',function(){_rm(s);});"
        + "}else{setTimeout(function(){_rm(s);},0);}}"
        + "function _finalize(){if(_cl){return;}_cl=true;_sweep();try{"
        + "var mo=new MutationObserver(function(ms){for(var a=0;a<ms.length;a++){"
        + "var ad=ms[a].addedNodes;for(var b=0;b<ad.length;b++){"
        + "if(ad[b].tagName==='SCRIPT'){_watch(ad[b]);}}}});"
        + "mo.observe(document.documentElement,{childList:true,subtree:true});"
        + "setTimeout(function(){_sweep();mo.disconnect();},1500);"
        + "}catch(e){_sweep();}}"
        + "if(document.readyState==='complete'){setTimeout(_finalize,0);}"
        + "else{window.addEventListener('load',_finalize);}"
        + "})();"
    )

def _wrap_page(loader_js):
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head>"
        "<body><script>" + loader_js + "</script></body></html>"
    )

def build(html):
    rendered = html
    payload_b64, inverse_b64 = substitution_cipher.encode(rendered)
    combined = zwsp_delimiter.combine([payload_b64, inverse_b64])
    expected_checksum = anti_tamper.checksum(combined)
    inner_loader = _build_loader(combined, expected_checksum)
    outer_loader = packer.pack(inner_loader)
    return _wrap_page(outer_loader), rendered

def obfuscate_html(html):
    return build(html)[0]
