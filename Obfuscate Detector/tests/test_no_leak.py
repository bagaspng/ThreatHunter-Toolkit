import base64
import json

import pytest

import engine

_SECRET = "TOPSECRET_marker_9f3a"

_B64 = base64.b64encode(_SECRET.encode()).decode()

_CASES = [
    _B64,
    base64.b64encode(base64.b64encode(_SECRET.encode())).decode(),
    _SECRET.encode().hex(),
    "".join("%%%02X" % b for b in _SECRET.encode()),
    # PHP webshell: payload must never be decoded into the response
    "<?php eval(gzinflate(base64_decode('%s'))); ?>" % _B64,
    # PowerShell encoded command: base64 blob must not be decoded/echoed
    "powershell -enc %s" % _B64,
]


@pytest.mark.parametrize("payload", _CASES)
def test_no_secret_marker_in_response(payload):
    blob = json.dumps(engine.analyze(payload))
    assert _SECRET not in blob
