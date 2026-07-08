import random
import re
import string

from modules import packer

JS_KEYWORDS = {
    "break", "case", "catch", "class", "const", "continue", "debugger",
    "default", "delete", "do", "else", "export", "extends", "finally",
    "for", "function", "if", "import", "in", "instanceof", "new", "return",
    "super", "switch", "this", "throw", "try", "typeof", "var", "void",
    "while", "with", "yield", "let", "static", "async", "await", "of",
    "get", "set", "enum", "implements", "interface", "package", "private",
    "protected", "public",
}

JS_GLOBALS = {
    "window", "document", "console", "Math", "JSON", "Object", "Array",
    "String", "Number", "Boolean", "Date", "RegExp", "Error", "Function",
    "Promise", "Symbol", "Map", "Set", "WeakMap", "WeakSet", "parseInt",
    "parseFloat", "isNaN", "isFinite", "encodeURIComponent",
    "decodeURIComponent", "encodeURI", "decodeURI", "setTimeout",
    "setInterval", "clearTimeout", "clearInterval", "alert", "prompt",
    "confirm", "fetch", "undefined", "null", "true", "false", "NaN",
    "Infinity", "globalThis", "navigator", "location", "history",
    "localStorage", "sessionStorage", "event", "arguments", "require",
    "module", "exports", "process", "Uint8Array", "TextDecoder",
    "TextEncoder", "atob", "btoa", "self", "top", "parent", "name",
    "length", "prototype", "constructor",
}

RESERVED = JS_KEYWORDS | JS_GLOBALS

_REGEX_PREFIX_WORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "do", "else", "case", "yield", "await",
}
_REGEX_PREFIX_CHARS = set("(,=:[!&|?{};+-*%<>~^")

_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
    "0": "\0", "\\": "\\", "'": "'", '"': '"', "`": "`", "/": "/",
}

def _rand_name(used):
    while True:
        name = "_0x" + "".join(random.choice("0123456789abcdef") for _ in range(6))
        if name not in used:
            used.add(name)
            return name

def _tokenize(code):
    tokens = []
    buf = []
    i = 0
    n = len(code)

    def flush():
        if buf:
            tokens.append(("code", "".join(buf)))
            buf.clear()

    def last_significant():
        for ch in reversed(buf):
            if not ch.isspace():
                return ch
        return None

    def trailing_word():
        m = re.search(r"([A-Za-z_$][\w$]*)\s*$", "".join(buf[-16:]))
        return m.group(1) if m else ""

    while i < n:
        c = code[i]
        two = code[i:i + 2]

        if two == "//":
            flush()
            j = code.find("\n", i)
            j = n if j == -1 else j
            tokens.append(("comment", code[i:j]))
            i = j
        elif two == "/*":
            flush()
            j = code.find("*/", i + 2)
            j = n if j == -1 else j + 2
            tokens.append(("comment", code[i:j]))
            i = j
        elif c in "\"'":
            flush()
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == c:
                    j += 1
                    break
                if code[j] == "\n":
                    break
                j += 1
            tokens.append(("string", code[i:j]))
            i = j
        elif c == "`":
            flush()
            j = i + 1
            while j < n:
                if code[j] == "\\":
                    j += 2
                    continue
                if code[j] == "`":
                    j += 1
                    break
                j += 1
            tokens.append(("template", code[i:j]))
            i = j
        elif c == "/":
            prev = last_significant()
            if prev is None or prev in _REGEX_PREFIX_CHARS or \
                    trailing_word() in _REGEX_PREFIX_WORDS:
                flush()
                j = i + 1
                in_class = False
                ok = False
                while j < n:
                    ch = code[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "\n":
                        break
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        j += 1
                        ok = True
                        break
                    j += 1
                if ok:
                    while j < n and code[j].isalpha():
                        j += 1
                    tokens.append(("regex", code[i:j]))
                    i = j
                else:
                    buf.append(c)
                    i += 1
            else:
                buf.append(c)
                i += 1
        else:
            buf.append(c)
            i += 1

    flush()
    return tokens

def _js_string_value(tok):
    inner = tok[1:-1]
    out = []
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c == "\\" and i + 1 < n:
            nxt = inner[i + 1]
            if nxt == "u":
                if i + 2 < n and inner[i + 2] == "{":
                    j = inner.find("}", i + 3)
                    out.append(chr(int(inner[i + 3:j], 16)))
                    i = j + 1
                    continue
                out.append(chr(int(inner[i + 2:i + 6], 16)))
                i += 6
                continue
            if nxt == "x":
                out.append(chr(int(inner[i + 2:i + 4], 16)))
                i += 4
                continue
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)

def _to_charcodes(value):
    codes = []
    for ch in value:
        o = ord(ch)
        if o > 0xFFFF:
            o -= 0x10000
            codes.append(0xD800 + (o >> 10))
            codes.append(0xDC00 + (o & 0x3FF))
        else:
            codes.append(o)
    return codes

def _next_char(tokens, idx):
    for typ, txt in tokens[idx + 1:]:
        for ch in txt:
            if not ch.isspace():
                return ch
    return ""

def _encode_strings(tokens, helper):
    used_helper = False
    for idx, (typ, txt) in enumerate(tokens):
        if typ != "string":
            continue

        if _next_char(tokens, idx) == ":":
            continue
        value = _js_string_value(txt)
        if value == "":
            continue
        codes = ",".join(str(c) for c in _to_charcodes(value))
        tokens[idx] = ("code", "%s([%s])" % (helper, codes))
        used_helper = True
    return used_helper

def _collect_names(code_text):
    names = set()
    for m in re.finditer(r"\b(?:var|let|const)\s+([$A-Za-z_][\w$]*)", code_text):
        names.add(m.group(1))
    for m in re.finditer(
            r"\bfunction\b\s*([$A-Za-z_][\w$]*)?\s*\(([^)]*)\)", code_text):
        if m.group(1):
            names.add(m.group(1))
        for p in m.group(2).split(","):
            p = p.strip().split("=")[0].strip()
            p = re.sub(r"^\.\.\.", "", p).strip()
            if re.match(r"^[$A-Za-z_][\w$]*$", p):
                names.add(p)
    for m in re.finditer(r"\(([^()]*)\)\s*=>", code_text):
        for p in m.group(1).split(","):
            p = p.strip().split("=")[0].strip()
            p = re.sub(r"^\.\.\.", "", p).strip()
            if re.match(r"^[$A-Za-z_][\w$]*$", p):
                names.add(p)
    for m in re.finditer(r"(?:^|[^.\w$])([$A-Za-z_][\w$]*)\s*=>", code_text):
        names.add(m.group(1))
    return names - RESERVED

def _rename(tokens, used):
    code_text = "".join(t for ty, t in tokens if ty == "code")
    names = _collect_names(code_text)
    mapping = {name: _rand_name(used) for name in names}
    for idx, (ty, txt) in enumerate(tokens):
        if ty != "code":
            continue
        for old, new in mapping.items():
            txt = re.sub(
                r"(?<![.\w$])" + re.escape(old) + r"(?![\w$])(?!\s*:)",
                new, txt,
            )
        tokens[idx] = ("code", txt)
    return tokens

def _junk_statement(used):
    a = _rand_name(used)
    v = random.randint(1000, 999999)
    templates = [
        "var {a}={v};while(false){{{a}++;}}",
        "var {a}={v};if({a}<0){{console.log({a});}}",
        "for(var {a}={v};{a}<0;{a}++){{break;}}",
        "var {a}=function(){{return {v}*0;}};",
    ]
    return random.choice(templates).format(a=a, v=v)

def _inject_dead(tokens, used, count):
    result = []
    inserted = 0
    for ty, txt in tokens:
        result.append((ty, txt))
        if ty == "code" and inserted < count:
            if txt.rstrip().endswith((";", "{", "}")) and random.random() < 0.5:
                result.append(("code", "\n" + _junk_statement(used) + "\n"))
                inserted += 1
    while inserted < count:
        result.insert(0, ("code", _junk_statement(used) + "\n"))
        inserted += 1
    return result

def _control_flow_noise(used):
    a = _rand_name(used)
    return ("if((function(){{return ![];}})()){{var {a}=0;"
            "switch({a}){{case 1:{a}++;break;default:break;}}}}").format(a=a)

def obfuscate_js(code, level="medium", pack=True, layers=2):
    used = set()
    helper = _rand_name(used)
    tokens = _tokenize(code)

    if level in ("medium", "high"):
        tokens = _rename(tokens, used)

    used_helper = _encode_strings(tokens, helper)

    if level == "high":
        tokens = _inject_dead(tokens, used, count=6)

    body = "".join(t for _, t in tokens)

    if level == "high":
        noise = "\n".join(_control_flow_noise(used) for _ in range(2))
        body = noise + "\n" + body

    if used_helper:
        prefix = ("function %s(a){return String.fromCharCode.apply(null,a);}\n"
                  % helper)
        body = prefix + body

    if pack:
        return packer.pack(body, layers=layers)
    return body
