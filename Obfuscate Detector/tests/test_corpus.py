import json
import os

import detect

_CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def test_corpus_regression():
    with open(os.path.join(_CORPUS, "manifest.json")) as fh:
        expected = json.load(fh)
    results = {os.path.basename(r["file"]): r["verdict"]["obfuscated"]
               for r in detect.scan_path(_CORPUS)}
    for fname, want in expected.items():
        assert fname in results, "corpus file hilang: %s" % fname
        assert results[fname] is want, (
            "%s: harap obfuscated=%s, dapat %s" % (fname, want, results[fname]))
