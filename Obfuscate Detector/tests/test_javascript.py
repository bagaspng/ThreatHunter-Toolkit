from detectors.javascript import detect_javascript


def test_dean_edwards_packer_detected():
    code = "eval(function(p,a,c,k,e,d){return p}('0',1,1,['x'],0,{}))"
    names = [f.name for f in detect_javascript(code)]
    assert "js_packer" in names


def test_obfuscator_io_array_detected():
    code = ("var _0x1a2b=['\\x68\\x69'];var _0x3c4d=_0x1a2b[0x0];"
            "_0x1a2b[0x1];_0x1a2b[0x2];_0x1a2b[0x3];_0x1a2b[0x4];")
    names = [f.name for f in detect_javascript(code)]
    assert "obfuscator_io" in names


def test_eval_atob_detected():
    findings = detect_javascript("eval(atob('Zm9v'))")
    names = [f.name for f in findings]
    assert "js_eval_atob" in names
    atob = [f for f in findings if f.name == "js_eval_atob"]
    assert atob[0].confidence >= 70


def test_bare_decodeuri_is_weak_signal():
    findings = detect_javascript("const q = decodeURIComponent(params.get('q'));")
    atob = [f for f in findings if f.name == "js_eval_atob"]
    assert len(atob) == 1
    assert atob[0].confidence < 60  # not verdict-triggering on its own


def test_packer_with_whitespace_variant():
    code = ("eval( function ( p , a , c , k , e , d ) { return p }"
            "('0',1,1,['x'],0,{}))")
    names = [f.name for f in detect_javascript(code)]
    assert "js_packer" in names


def test_jsfuck_detected():
    code = "[]+[]+([![]]+[][[]])[+!+[]+[+[]]]+(![]+[])[+!+[]]+(![]+[])[!+[]+!+[]]"
    names = [f.name for f in detect_javascript(code)]
    assert "jsfuck" in names


def test_aaencode_detected():
    code = "ﾟωﾟﾉ= /`m´）ﾉ ~┻━┻   //*´∇｀*/ ['_']; o=(ﾟｰﾟ)  =_=3;"
    names = [f.name for f in detect_javascript(code)]
    assert "aaencode" in names


def test_jjencode_detected():
    code = "$=~[];$={___:++$,$$$$:(![]+\"\")[$],__$:++$,$_$_:(![]+\"\")[$]};"
    names = [f.name for f in detect_javascript(code)]
    assert "jjencode" in names


def test_clean_js_no_findings():
    code = "function add(a, b) { return a + b; }\nconsole.log(add(2, 3));"
    assert detect_javascript(code) == []
