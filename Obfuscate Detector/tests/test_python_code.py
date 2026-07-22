from detectors.python_code import detect_python


def test_marshal_exec_detected():
    code = "import marshal\nexec(marshal.loads(b'data'))"
    names = [f.name for f in detect_python(code)]
    assert "python_marshal_exec" in names


def test_b64_zlib_exec_detected():
    code = ("import base64, zlib\n"
            "exec(zlib.decompress(base64.b64decode('eJx')))")
    names = [f.name for f in detect_python(code)]
    assert "python_b64_zlib_exec" in names


def test_chr_join_detected():
    code = "s = ''.join(chr(c) for c in [104, 105])"
    names = [f.name for f in detect_python(code)]
    assert "python_chr_join" in names


def test_non_python_returns_empty():
    assert detect_python("this is {not valid python !!!") == []


def test_clean_python_no_findings():
    assert detect_python("def add(a, b):\n    return a + b\n") == []


def test_os_path_join_with_chr_not_flagged():
    code = "import os\np = os.path.join('a', 'b')\nx = chr(65)"
    names = [f.name for f in detect_python(code)]
    assert "python_chr_join" not in names


def test_os_path_join_with_nested_chr_not_flagged():
    # chr nested inside os.path.join args must still not fire (receiver not str)
    code = "import os\np = os.path.join(chr(47), 'tmp')"
    names = [f.name for f in detect_python(code)]
    assert "python_chr_join" not in names


def test_exec_without_nested_marshal_not_flagged():
    code = "exec('print(1)')\nimport marshal\nd = marshal.dumps({})"
    names = [f.name for f in detect_python(code)]
    assert "python_marshal_exec" not in names


def test_eval_compile_detected():
    code = "eval(compile('1+1', '<s>', 'eval'))"
    names = [f.name for f in detect_python(code)]
    assert "python_eval_compile" in names
