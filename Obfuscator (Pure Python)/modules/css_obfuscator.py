import json
import random
import re
import string

from modules import packer

_NEST_ATRULES = (
    "media", "supports", "container", "document", "scope", "layer",
    "keyframes", "-webkit-keyframes", "-moz-keyframes", "-o-keyframes",
)

def _rand_class(used):
    while True:
        name = "_" + "".join(random.choice(string.ascii_lowercase) for _ in range(7))
        if name not in used:
            used.add(name)
            return name

def _rename_selectors(text, mapping, used):
    def repl(m):
        key = m.group(0)
        if key not in mapping:
            mapping[key] = m.group(1) + _rand_class(used)
        return mapping[key]

    return re.sub(r"([.#])(-?[_a-zA-Z][\w-]*)", repl, text)

def _minify(text):
    # Collapse whitespace runs to a single space.
    text = re.sub(r"\s+", " ", text)
    # Drop whitespace around structural punctuation.
    text = re.sub(r"\s*([{};,])\s*", r"\1", text)
    # Drop the space after a colon (declarations like `color: red`).
    text = re.sub(r":\s+", ":", text)
    # Drop the trailing semicolon before a closing brace.
    text = re.sub(r";}", "}", text)
    return text.strip()

def _rename_and_minify(css, mapping=None):
    if mapping is None:
        mapping = {}
    used = {v.lstrip(".#") for v in mapping.values()}

    out = []
    prelude = []
    saved = []

    stack = []

    def in_selector_ctx():
        return not stack or stack[-1] == "nest"

    def emit_prelude():
        text = "".join(prelude)
        prelude.clear()
        if in_selector_ctx():
            out.append(_rename_selectors(text, mapping, used))
        else:
            out.append(text)

    i = 0
    n = len(css)
    while i < n:
        c = css[i]
        two = css[i:i + 2]

        if two == "/*":
            # Drop comments entirely.
            j = css.find("*/", i + 2)
            j = n if j == -1 else j + 2
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n:
                if css[j] == "\\":
                    j += 2
                    continue
                if css[j] == c:
                    j += 1
                    break
                j += 1
            # Protect the literal from minification with a sentinel.
            prelude.append("\x00%d\x00" % len(saved))
            saved.append(css[i:j])
            i = j
        elif c == "{":
            text = "".join(prelude)
            selector_ctx = in_selector_ctx()
            emit_prelude()
            out.append("{")
            stripped = text.strip()
            is_nest = stripped.startswith("@") and any(
                stripped[1:].lower().startswith(a) for a in _NEST_ATRULES
            )
            stack.append("nest" if (selector_ctx and is_nest) else "decl")
            i += 1
        elif c == "}":
            emit_prelude()
            out.append("}")
            if stack:
                stack.pop()
            i += 1
        else:
            prelude.append(c)
            i += 1

    emit_prelude()

    result = _minify("".join(out))
    for idx, literal in enumerate(saved):
        result = result.replace("\x00%d\x00" % idx, literal, 1)
    return result, mapping

def _css_injector(css_min):
    # Runtime loader: build a <style> node and inject the CSS into the page
    # when the packed payload runs.
    return (
        "(function(){var d=document,s=d.createElement(\"style\");"
        "s.type=\"text/css\";"
        "s.appendChild(d.createTextNode(" + json.dumps(css_min) + "));"
        "(d.head||d.getElementsByTagName(\"head\")[0]||d.documentElement)"
        ".appendChild(s);})();"
    )

def obfuscate_css(css, mapping=None, pack=True, layers=2):
    """Obfuscate CSS into a self-decoding JS loader.

    Selectors are renamed and the CSS is minified; with pack=True (default)
    the result is wrapped in a self-decoding JS loader that injects the CSS
    at runtime. With pack=False only the renamed + minified CSS is returned.
    """
    css_min, mapping = _rename_and_minify(css, mapping)
    if not pack:
        return css_min, mapping
    payload = packer.pack(_css_injector(css_min), layers=layers)
    return payload, mapping

def apply_mapping_to_html_attrs(class_value, mapping):
    tokens = class_value.split()
    result = []
    for tok in tokens:
        new = mapping.get("." + tok)
        result.append(new[1:] if new else tok)
    return " ".join(result)
