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


def test_verdict_has_risk_and_signals():
    v = engine.analyze("aGVsbG8gd29ybGQgc2FtcGxl")["verdict"]
    assert "risk" in v and "signals" in v
    assert 0 <= v["risk"] <= 100


def test_aggregate_weak_signals_trip_verdict():
    # three moderate (40-59) signals, none individually >= 60
    text = ("decodeURIComponent(x); IEX $y; "
            "$z=chr(1).chr(2).chr(3).chr(4).chr(5).chr(6);")
    v = engine.analyze(text)["verdict"]
    assert v["obfuscated"] is True
    assert v["signals"] >= 3
    assert v["risk"] > v["score"]  # co-occurring signals boost risk above top


def test_single_weak_signal_not_obfuscated():
    v = engine.analyze("const q = decodeURIComponent(location.search);")["verdict"]
    assert v["obfuscated"] is False
