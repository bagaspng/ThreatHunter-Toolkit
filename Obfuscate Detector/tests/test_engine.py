import base64

import engine


def test_analyze_reports_base64_verdict():
    payload = base64.b64encode(b"secret message here").decode()
    result = engine.analyze(payload)
    assert result["verdict"]["obfuscated"] is True
    assert result["verdict"]["dominant"] == "base64"
    assert result["verdict"]["score"] >= 60
    assert result["input_len"] == len(payload)


def test_analyze_never_leaks_plaintext():
    secret = "the launch code is 42"
    payload = base64.b64encode(secret.encode()).decode()
    import json
    blob = json.dumps(engine.analyze(payload))
    assert secret not in blob
    assert "launch code" not in blob


def test_analyze_clean_text_not_obfuscated():
    result = engine.analyze("halo, ini teks biasa untuk dibaca manusia.")
    assert result["verdict"]["obfuscated"] is False
    assert result["findings"] == []


def test_findings_sorted_by_confidence_desc():
    code = "eval(function(p,a,c,k,e,d){return p}('0',1,1,['x'],0,{}))"
    result = engine.analyze(code)
    confs = [f["confidence"] for f in result["findings"]]
    assert confs == sorted(confs, reverse=True)
