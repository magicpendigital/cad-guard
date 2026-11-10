"""dwg.py: kịch bản gửi accoreconsole và đệm; chạy thật chỉ khi máy có AutoCAD bản đầy đủ."""
import os
import sys
from pathlib import Path

import pytest

from cadguard import dwg, fixtures


def _fake_exe(tmp_path: Path) -> Path:
    """accoreconsole giả: đọc /s, tìm đường dẫn đích cuối cùng trong LISP rồi chép /i sang đó."""
    script = tmp_path / "fake_acc.py"
    script.write_text(
        "import re, shutil, sys\n"
        "a = sys.argv[1:]\n"
        "src = a[a.index('/i') + 1]; scr = a[a.index('/s') + 1]\n"
        "dst = re.findall(r'\"([^\"]+)\"\\)', open(scr, encoding='utf-8').read())[-1]\n"
        "shutil.copyfile(src, dst)\n", encoding="utf-8")
    if os.name == "nt":
        exe = tmp_path / "acc.bat"
        exe.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    else:
        exe = tmp_path / "acc.sh"
        exe.write_text(f'#!/bin/sh\n"{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        exe.chmod(0o755)
    return exe


def test_dwg_to_dxf_uses_cache_and_never_touches_source(tmp_path, monkeypatch):
    src = tmp_path / "a.dwg"
    fixtures.make_ok_sheet(tmp_path / "a.dxf")
    src.write_bytes((tmp_path / "a.dxf").read_bytes())  # DWG giả: chỉ kiểm luồng
    exe = _fake_exe(tmp_path)
    monkeypatch.setenv("CADGUARD_ACCORECONSOLE", str(exe))
    before = src.read_bytes()
    out = dwg.dwg_to_dxf(src)
    assert out.parent.name == "cache" and out.read_bytes() == before and src.read_bytes() == before
    out.write_text("dem", encoding="utf-8")
    assert dwg.dwg_to_dxf(src).read_text(encoding="utf-8") == "dem"  # đệm theo băm: không chạy lại


def test_missing_accoreconsole(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_ACCORECONSOLE", str(tmp_path / "khong-co.exe"))
    (tmp_path / "x.dwg").write_bytes(b"x")
    with pytest.raises(dwg.DwgError, match="accoreconsole"):
        dwg.dwg_to_dxf(tmp_path / "x.dwg")


@pytest.mark.skipif(not os.environ.get("CADGUARD_TEST_AUTOCAD"), reason="đặt CADGUARD_TEST_AUTOCAD=1 để chạy với AutoCAD thật")
def test_real_roundtrip(tmp_path):
    from cadguard.dxf_reader import read_dxf
    from cadguard.sheets import build_structure

    fixtures.make_model_sheets(tmp_path / "m.dxf")
    d = dwg.dxf_to_dwg(tmp_path / "m.dxf", tmp_path / "m.dwg")
    back = dwg.dwg_to_dxf(d)
    assert len(build_structure(read_dxf(back)).sheets) == len(fixtures.CO_SHEETS)
