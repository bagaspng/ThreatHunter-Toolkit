import base64

from detectors.encoding import detect_encoding, next_layer


def test_single_layer_base64_detected_no_plaintext():
    payload = base64.b64encode(b"hello world").decode()
    findings = detect_encoding(payload)
    assert len(findings) == 1
    f = findings[0]
    assert f.name == "base64"
    assert f.category == "encoding"
    assert f.confidence >= 60
    assert f.layers == 1
    # zero-decode invariant: plaintext must not appear anywhere
    assert "hello world" not in f.evidence
    assert "hello world" not in f.clue


def test_double_layer_base64_counts_two():
    inner = base64.b64encode(b"attack at dawn").decode()
    outer = base64.b64encode(inner.encode()).decode()
    findings = detect_encoding(outer)
    assert findings[0].layers == 2
    assert "attack at dawn" not in findings[0].evidence


def test_plain_text_no_encoding_finding():
    assert detect_encoding("halo dunia biasa saja") == []


def test_next_layer_returns_none_for_plain():
    assert next_layer("just normal words here") is None


def test_base64_of_gzip_flagged_as_encoded_binary():
    import gzip
    blob = base64.b64encode(gzip.compress(b"secret payload bytes here")).decode()
    findings = detect_encoding(blob)
    names = [f.name for f in findings]
    assert "encoded_binary" in names
    eb = [f for f in findings if f.name == "encoded_binary"][0]
    assert "gzip" in eb.evidence
    assert "secret payload" not in eb.evidence  # zero-decode holds
