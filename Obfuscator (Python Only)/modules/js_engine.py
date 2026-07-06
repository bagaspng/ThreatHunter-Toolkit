from modules import js_obfuscator

_LEVEL = "high"

def is_available():
    return True

def check_dependencies():
    return True, "OK: engine JS murni-Python (js_obfuscator) siap."

def obfuscate(code):
    return js_obfuscator.obfuscate_js(code, level=_LEVEL)
