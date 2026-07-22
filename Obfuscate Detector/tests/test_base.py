from detectors.base import Finding, register, all_detectors, clear_registry


def test_finding_to_dict():
    f = Finding(name="base64", category="encoding", confidence=90,
                evidence="cocok pola base64", clue="decode base64", layers=2)
    assert f.to_dict() == {
        "name": "base64",
        "category": "encoding",
        "confidence": 90,
        "evidence": "cocok pola base64",
        "clue": "decode base64",
        "layers": 2,
    }


def test_registry_collects_detectors():
    saved = all_detectors()          # snapshot detectors registered at import

    clear_registry()

    @register
    def dummy(text):
        return []

    assert dummy in all_detectors()
    clear_registry()
    assert all_detectors() == []

    for fn in saved:                 # restore so later tests keep their detectors
        register(fn)
