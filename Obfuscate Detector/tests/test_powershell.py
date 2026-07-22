from detectors.powershell import detect_powershell


def test_encoded_command_detected():
    code = "powershell.exe -enc SQBFAFgAKABuAGUAdwAtAG8AYgBqAGUAYwB0ACkA"
    names = [f.name for f in detect_powershell(code)]
    assert "ps_encoded_command" in names


def test_compressed_frombase64_detected():
    code = ("$s=New-Object IO.Compression.DeflateStream;"
            "[Convert]::FromBase64String($blob)")
    names = [f.name for f in detect_powershell(code)]
    assert "ps_compressed" in names


def test_char_join_detected():
    code = "$c = [char]104,[char]105 -join ''"
    names = [f.name for f in detect_powershell(code)]
    assert "ps_char_join" in names


def test_iex_alone_is_weak_signal():
    code = "IEX $someString"
    fs = detect_powershell(code)
    m = [f for f in fs if f.name == "ps_iex"]
    assert len(m) == 1
    assert m[0].confidence < 60


def test_encoding_param_not_false_positive():
    # -Encoding is a legit common param and must not match -enc<base64>
    code = "Get-Content file.txt -Encoding utf8 | Write-Output"
    names = [f.name for f in detect_powershell(code)]
    assert "ps_encoded_command" not in names


def test_clean_powershell_no_findings():
    code = "function Add($a, $b) { return $a + $b }\nWrite-Output (Add 2 3)"
    assert detect_powershell(code) == []
