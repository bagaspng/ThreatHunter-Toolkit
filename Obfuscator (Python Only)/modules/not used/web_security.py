import base64
import html
import urllib.parse


def url_encode_payload(payload):
    return urllib.parse.quote(payload, safe="()")


def html_escape(payload):
    return html.escape(payload)


def unicode_escape_payload(payload):
    result = []
    for char in payload:
        if char.isalnum():
            result.append(char)
        else:
            result.append("\\u{:04x}".format(ord(char)))
    return "".join(result)


def base64_wrapper(payload):
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def js_charcode_obfuscator(payload):
    codes = ",".join(str(ord(char)) for char in payload)
    return f"String.fromCharCode({codes})"
