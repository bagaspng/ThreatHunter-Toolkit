from detectors.generic import detect_generic, shannon


def test_shannon_zero_for_uniform():
    assert shannon("aaaaaaaa") == 0.0


def test_identifier_entropy_flags_hex_names():
    code = "var _0xa1b2 = _0xc3d4[_0xe5f6]; _0x1234(); _0x5678();"
    names = [f.name for f in detect_generic(code)]
    assert "identifier_entropy" in names


def test_plain_prose_no_generic_findings():
    findings = detect_generic("Ini kalimat biasa yang mudah dibaca semua orang.")
    names = [f.name for f in findings]
    assert "identifier_entropy" not in names
    assert "high_entropy" not in names


def test_underscore_mangle_detected():
    # lambda/pyfuscate style: dense all-underscore identifiers + dynamic dispatch
    code = ("_=lambda _:_; __=_(_); ___=__import__(__); ____=___; "
            "_____=____; ______=_____; _______=______")
    names = [f.name for f in detect_generic(code)]
    assert "underscore_mangle" in names


def test_normal_underscores_not_flagged():
    # throwaway names are common and must not trip the signature
    code = "for _ in range(10):\n    pass\n_, __ = (1, 2)\nprint(__name__)"
    names = [f.name for f in detect_generic(code)]
    assert "underscore_mangle" not in names


def test_embedded_high_entropy_blob():
    import base64
    filler = "config ok. " * 220  # ~2400 chars, very low entropy
    blob = base64.b64encode(bytes(range(256))).decode()  # dense high-entropy
    text = filler + blob + filler
    names = [f.name for f in detect_generic(text)]
    assert "embedded_high_entropy" in names
    assert "high_entropy" not in names  # whole-file entropy stays low


def test_uniform_low_entropy_no_embedded_flag():
    text = "config ok. " * 220
    names = [f.name for f in detect_generic(text)]
    assert "embedded_high_entropy" not in names
