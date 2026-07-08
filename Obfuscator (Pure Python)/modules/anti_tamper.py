_CHARSET_REGEX = "/^[A-Za-z0-9+/=\\u200b\\u200c\\u2060\\u200d\\ufeff]*$/"

def checksum(s):
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return h

def js_checksum_function(fn_name):
    return (
        "function " + fn_name + "(s){var h=5381;"
        "for(var i=0;i<s.length;i++){h=((h*33)^s.charCodeAt(i))>>>0;}"
        "return h;}"
    )

def js_guard(payload_var, ck_fn, expected):
    return (
        "if(!" + _CHARSET_REGEX + ".test(" + payload_var + ")){"
        "throw new Error('tamper: charset');}"
        "if(" + ck_fn + "(" + payload_var + ")!==" + str(expected) + "){"
        "throw new Error('tamper: checksum');}"
    )
