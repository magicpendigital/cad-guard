"""Điểm vào in tiếng Việt không được sập khi console là cp1252 (Windows, không đặt PYTHONIOENCODING=utf-8).

Mỗi điểm vào chạy trong tiến trình con với PYTHONIOENCODING=cp1252 và PYTHONUTF8=0, phải thoát 0 và in ra UTF-8.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "packages" / "core"

ENTRY_POINTS = {
    "bench --help": [str(ROOT / "scripts" / "bench.py"), "--help"],
    "check_repo_hygiene --help": [str(ROOT / "scripts" / "check_repo_hygiene.py"), "--help"],
    "test.py --help": [str(ROOT / "scripts" / "test.py"), "--help"],
    "cadguard --help": ["-m", "cadguard", "--help"],
    "cadguard rules": ["-m", "cadguard", "rules"],
}


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_entry_point_survives_cp1252_console(name):
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0",
               PYTHONPATH=str(CORE) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    env.pop("CADGUARD_BENCH_CHILD", None)
    proc = subprocess.run([sys.executable, *ENTRY_POINTS[name]], capture_output=True, env=env, timeout=120,
                          stdin=subprocess.DEVNULL, cwd=str(ROOT))
    err = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0, err
    assert "UnicodeEncodeError" not in err
    out = proc.stdout.decode("utf-8")  # đầu ra là UTF-8 hợp lệ
    assert out.strip()
