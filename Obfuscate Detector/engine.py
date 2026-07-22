from detectors.base import all_detectors
from detectors import (  # noqa: F401
    encoding, generic, javascript, php, powershell, python_code,
    unicode_smuggle,
)

AMBANG = 60
_MODERATE = 40  # weak-signal floor for aggregate scoring
_MAX_FIELD = 2000


def assert_no_decode(findings):
    for f in findings:
        assert len(f.evidence) < _MAX_FIELD, "evidence terlalu panjang"
        assert len(f.clue) < _MAX_FIELD, "clue terlalu panjang"


def _risk(findings):
    """Aggregate 0-100: top signal, boosted when several signals co-occur."""
    if not findings:
        return 0
    top = findings[0].confidence
    contributing = sum(1 for f in findings if f.confidence >= _MODERATE)
    return min(100, top + 8 * max(0, contributing - 1))


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

    strong = any(f.confidence >= AMBANG for f in findings)
    moderate = sum(1 for f in findings if _MODERATE <= f.confidence < AMBANG)
    # verdict trips on one strong signal OR several weaker ones stacking up
    obfuscated = strong or moderate >= 3
    dominant = findings[0].name if findings else None
    score = findings[0].confidence if findings else 0
    return {
        "input_len": len(text),
        "verdict": {"obfuscated": obfuscated, "dominant": dominant,
                    "score": score, "risk": _risk(findings),
                    "signals": len(findings)},
        "findings": [f.to_dict() for f in findings],
    }
