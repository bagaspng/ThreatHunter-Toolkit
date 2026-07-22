import base64
import json

import pytest

import engine

_SECRET = "TOPSECRET_marker_9f3a"

_CASES = [
    base64.b64encode(_SECRET.encode()).decode(),
    base64.b64encode(base64.b64encode(_SECRET.encode())).decode(),
    _SECRET.encode().hex(),
    "".join("%%%02X" % b for b in _SECRET.encode()),
]


@pytest.mark.parametrize("payload", _CASES)
def test_no_secret_marker_in_response(payload):
    blob = json.dumps(engine.analyze(payload))
    assert _SECRET not in blob
