from detectors.php import detect_php


def test_eval_base64_gzinflate_webshell():
    code = "<?php eval(gzinflate(base64_decode('c29tZQ=='))); ?>"
    names = [f.name for f in detect_php(code)]
    assert "php_eval_decode" in names


def test_preg_replace_e_modifier():
    code = "<?php preg_replace('/.*/e', $_GET['x'], ''); ?>"
    names = [f.name for f in detect_php(code)]
    assert "php_preg_e" in names


def test_globals_dispatch():
    code = "<?php $GLOBALS['a']();$GLOBALS['b']();$GLOBALS['c']=1; ?>"
    names = [f.name for f in detect_php(code)]
    assert "php_globals_obf" in names


def test_char_concat_is_weak_signal():
    code = "$x=chr(101).chr(118).chr(97).chr(108).chr(40).chr(41);"
    fs = detect_php(code)
    m = [f for f in fs if f.name == "php_char_concat"]
    assert len(m) == 1
    assert m[0].confidence < 60


def test_clean_php_no_findings():
    code = "<?php function add($a, $b) { return $a + $b; } echo add(2, 3); ?>"
    assert detect_php(code) == []
