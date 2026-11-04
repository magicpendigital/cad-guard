from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[3]
# The patterns below intentionally contain examples of the corruption being detected.
ALLOWED = {"packages/core/tests/test_source_encoding.py": "Contains the detector patterns themselves."}
PATTERN = re.compile(r"[A-Za-z\u00c0-\u1ef9]\?[a-z\u00e0-\u1ef9]|[A-Za-z\u00c0-\u1ef9]\?\?[A-Za-z\u00c0-\u1ef9]|\ufffd")
FILES = sorted(path for name in ("packages/core/cadguard", "packages/core/tests", "standards", "docs", "knowledge", "bench") for path in (ROOT / name).rglob("*") if path.is_file() and path.suffix in {".py", ".md", ".yaml"})


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_source_encoding(path):
    relative = path.relative_to(ROOT).as_posix()
    if relative in ALLOWED:
        pytest.skip(ALLOWED[relative])
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"{relative}:1: invalid UTF-8: {exc}")
    failures = [f"{relative}:{number}: {line.strip()}" for number, line in enumerate(content.splitlines(), 1) if PATTERN.search(line)]
    assert not failures, "\n" + "\n".join(failures)
