from detectors.unicode_smuggle import detect_unicode

BIDI_RLO = chr(0x202E)
ZWSP = chr(0x200B)
CYR_A = chr(0x0430)  # Cyrillic small 'а', looks like Latin 'a'


def test_bidi_override_detected():
    code = "const isAdmin = false;" + BIDI_RLO + " // comment"
    names = [f.name for f in detect_unicode(code)]
    assert "bidi_override" in names


def test_zero_width_detected():
    code = "var x" + ZWSP * 5 + " = 1;"
    names = [f.name for f in detect_unicode(code)]
    assert "zero_width" in names


def test_homoglyph_mix_is_weak_signal():
    code = "var p" + CYR_A + "ssword = secret;"  # Latin + one Cyrillic
    fs = detect_unicode(code)
    m = [f for f in fs if f.name == "homoglyph_mix"]
    assert len(m) == 1
    assert m[0].confidence < 60


def test_plain_ascii_no_findings():
    assert detect_unicode("function add(a, b) { return a + b; }") == []
