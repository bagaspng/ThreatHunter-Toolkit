ZW_DELIM = "​‌⁠‍﻿"

ZW_DELIM_JS = "'\\u200b\\u200c\\u2060\\u200d\\ufeff'"

def combine(parts):
    return ZW_DELIM.join(parts)

def split(s):
    return s.split(ZW_DELIM)

def js_split_function(fn_name):
    return (
        "function " + fn_name + "(s){return s.split(" + ZW_DELIM_JS + ");}"
    )
