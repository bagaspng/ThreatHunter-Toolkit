import base64
import html
import urllib.parse


def url_encode_payload(payload):
    """Percent-encode a payload while keeping parentheses readable.

    Example: '<script>alert(1)</script>'
          -> '%3Cscript%3Ealert(1)%3C%2Fscript%3E'
    """
    return urllib.parse.quote(payload, safe="()")


def html_escape(payload):
    """HTML-escape special characters (&, <, >, quotes)."""
    return html.escape(payload)


def unicode_escape_payload(payload):
    """Escape only non-alphanumeric characters as \\uXXXX sequences.

    Example: '<script>' -> '\\u003cscript\\u003e'
    """
    result = []
    for char in payload:
        if char.isalnum():
            result.append(char)
        else:
            result.append("\\u{:04x}".format(ord(char)))
    return "".join(result)


def base64_wrapper(payload):
    """Wrap a payload in Base64.

    Example: 'alert("XSS")' -> 'YWxlcnQoIlhTUyIp'
    """
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def js_charcode_obfuscator(payload):
    """Convert a payload into a JavaScript String.fromCharCode() call.

    Example: 'alert(1)'
          -> 'String.fromCharCode(97,108,101,114,116,40,49,41)'
    """
    codes = ",".join(str(ord(char)) for char in payload)
    return f"String.fromCharCode({codes})"
