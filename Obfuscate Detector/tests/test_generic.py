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
