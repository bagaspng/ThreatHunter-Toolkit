from detectors.base import all_detectors
from detectors import encoding, generic, javascript, python_code  # noqa: F401

AMBANG = 60
_MAX_FIELD = 2000


def assert_no_decode(findings):
    for f in findings:
        assert len(f.evidence) < _MAX_FIELD, "evidence terlalu panjang"
        assert len(f.clue) < _MAX_FIELD, "clue terlalu panjang"


def analyze(text, type_hint=None):
    text = text or ""
    findings = []
    for fn in all_detectors():
        try:
            findings.extend(fn(text) or [])
        except Exception:
            continue
    findings.sort(key=lambda f: f.confidence, reverse=True)
    assert_no_decode(findings)

    obfuscated = any(f.confidence >= AMBANG for f in findings)
    dominant = findings[0].name if findings else None
    score = findings[0].confidence if findings else 0
    return {
        "input_len": len(text),
        "verdict": {"obfuscated": obfuscated, "dominant": dominant,
                    "score": score},
        "findings": [f.to_dict() for f in findings],
    }
