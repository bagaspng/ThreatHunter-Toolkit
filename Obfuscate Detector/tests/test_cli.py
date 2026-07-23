import base64
import os

import detect


def _b64(s):
    return base64.b64encode(s.encode()).decode()


def test_scan_file_detects(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text(_b64("hello world sample data payload"))
    res = detect.scan_path(str(f))
    assert len(res) == 1
    assert res[0]["verdict"]["obfuscated"] is True


def test_scan_directory_mixed(tmp_path):
    (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "bad.txt").write_text(_b64("payload data here sample xyz"))
    res = detect.scan_path(str(tmp_path))
    by = {os.path.basename(r["file"]): r["verdict"]["obfuscated"] for r in res}
    assert by["clean.py"] is False
    assert by["bad.txt"] is True


def test_skips_binary_extension(tmp_path):
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n" + b"\x00" * 100)
    res = detect.scan_path(str(tmp_path))
    assert res == []


def test_csv_header(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("halo teks biasa saja tanpa apa-apa")
    out = detect.to_csv(detect.scan_path(str(f)))
    assert out.splitlines()[0] == (
        "file,obfuscated,level,keyakinan,dominant,signals")


def test_fail_on_detect_exit_code(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text(_b64("data payload sample marker here"))
    assert detect.main([str(f), "--fail-on-detect", "--format", "csv"]) == 1


def test_clean_exit_zero(tmp_path):
    f = tmp_path / "c.py"
    f.write_text("print('halo dunia')\n")
    assert detect.main([str(f), "--fail-on-detect"]) == 0


def test_missing_path_exit_two():
    assert detect.main(["/nonexistent/path/xyz", "--format", "csv"]) == 2
