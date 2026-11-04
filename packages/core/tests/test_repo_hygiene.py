"""Test scripts/check_repo_hygiene.py: repo thật phải sạch; repo git tạm có vi phạm phải bị bắt từng loại.

Chuỗi giống khoá và từ cấm được GHÉP lúc chạy để chính tệp test này không chứa nguyên văn.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_repo_hygiene.py"

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="không có lệnh git trong PATH")


def _run(root: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CADGUARD_FORBIDDEN_TERMS"}
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, env=env, timeout=120, stdin=subprocess.DEVNULL
    )


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")


@needs_git
def test_repo_is_clean():
    if not (ROOT / ".git").exists():
        pytest.skip("không chạy trong bản sao git của repo")
    proc = _run(ROOT)
    assert proc.returncode == 0, _out(proc)
    assert "Repo sạch" in _out(proc)


@pytest.fixture()
def dirty_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)

    def put(rel: str, data: bytes) -> None:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    put("fixtures/synthetic/ok.dxf", b"0\nEOF\n")  # được phép
    put("drawings/khach.dxf", b"0\nEOF\n")
    put("fixtures/synthetic/ban.dwg", b"AC1032\0\0binary")
    put("docs/old_dir.md", ("Xem thư mục " + "Data" + " sample" + "/ cũ.\n").encode("utf-8"))
    put("docs/env_term.md", "Bản vẽ của CÔNG TY ZETA-ENV ở đây.\n".encode("utf-8"))
    put("docs/file_term.md", "nhắc tới omega-file-term\n".encode("utf-8"))
    put("cfg/sk.txt", ("key = " + "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0k1L2" + "\n").encode())
    put("cfg/akia.txt", ("id = " + "AK" + "IA" + "ABCDEFGHIJKLMNOP" + "\n").encode())
    put("cfg/ghp.txt", ("t = " + "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123" + "\n").encode())
    put("cfg/pem.txt", ("-----" + "BEGIN RSA " + "PRIVATE KEY-----\nabc\n").encode())
    put("docs/bom.md", b"\xef\xbb\xbf# Tieu de\n")
    put("bin/blob.bin", b"\0\0" + ("sk" + "-" + "z" * 30).encode() + b"\xef\xbb\xbf")  # nhị phân: bỏ qua
    put("docs/clean.md", "Sạch sẽ.\n".encode("utf-8"))
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    # Danh sách từ cấm cục bộ: KHÔNG được git theo dõi.
    (repo / ".cadguard-forbidden.txt").write_text("# chú thích\nOMEGA-FILE-TERM\n", encoding="utf-8")
    return repo


@needs_git
def test_dirty_repo_each_kind_caught(dirty_repo: Path):
    proc = _run(dirty_repo, {"CADGUARD_FORBIDDEN_TERMS": "công ty zeta-env;"})
    out = _out(proc)
    assert proc.returncode == 1, out
    expected = [
        ("drawings/khach.dxf", "[dxf]"),
        ("fixtures/synthetic/ban.dwg", "[dwg]"),
        ("docs/old_dir.md", "[forbidden]"),
        ("docs/env_term.md", "[forbidden]"),
        ("docs/file_term.md", "[forbidden]"),
        ("cfg/sk.txt", "[secret:sk]"),
        ("cfg/akia.txt", "[secret:akia]"),
        ("cfg/ghp.txt", "[secret:ghp]"),
        ("cfg/pem.txt", "[secret:private-key]"),
        ("docs/bom.md", "[bom]"),
    ]
    lines = [line for line in out.splitlines() if line.startswith("- ")]
    for path, code in expected:
        assert any(line.startswith(f"- {path}") and code in line for line in lines), (path, code, out)
    assert len(lines) == len(expected), out
    for clean in ("fixtures/synthetic/ok.dxf", "bin/blob.bin", "docs/clean.md"):
        assert clean not in out
    # Từ cấm không bao giờ được in nguyên văn.
    assert "zeta" not in out.lower() and "omega" not in out.lower()
    assert "vi phạm" in out


@needs_git
def test_forbidden_file_in_env_absent_means_clean(tmp_path: Path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    (repo / "a.md").write_text("công ty zeta-env\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    assert _run(repo).returncode == 0
    assert _run(repo, {"CADGUARD_FORBIDDEN_TERMS": "Zeta-Env"}).returncode == 1


TEST_RUNNER = ROOT / "scripts" / "test.py"


def _load_runner():
    import importlib.util

    spec = importlib.util.spec_from_file_location("cadguard_scripts_test_runner", TEST_RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_msix_hint():
    runner = _load_runner()
    venv = Path("C:/x/cad-guard/venv")
    hint = runner.pip_failure_hint("ValueError: Resource name escapes package.", venv)
    assert hint and "CADGUARD_VENV" in hint and "MSIX" in hint
    assert runner.pip_failure_hint("ERROR: No matching distribution found", venv) is None


def test_runner_prints_vietnamese_on_legacy_codepage():
    code = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('r', {str(TEST_RUNNER)!r});"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
        "m._utf8_console(); m._say('cài phụ thuộc...')"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update({"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "[cad-guard] cài phụ thuộc..." in proc.stderr.decode("utf-8")


@needs_git
def test_not_a_git_repo_exits_2(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    proc = _run(plain, {"GIT_CEILING_DIRECTORIES": str(tmp_path)})
    assert proc.returncode == 2, _out(proc)
    assert "Không kiểm được repo" in _out(proc)
