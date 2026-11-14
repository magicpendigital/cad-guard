"""Telemetry cục bộ tối thiểu: chỉ băm nội dung + thời điểm. Không tên tệp, không đường dẫn, không tên người.

Lưu ngoài repo: ``$CADGUARD_HOME`` hoặc ``~/.cadguard/telemetry.jsonl``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("CADGUARD_HOME") or Path.home() / ".cadguard")


def _file() -> Path:
    return home() / "telemetry.jsonl"


def record_audit(file_hash: str) -> None:
    try:
        d = home()
        d.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ev": "audit", "h": file_hash})
        with _file().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # telemetry hỏng không được làm hỏng việc quét


def drawings_audited(days: int = 7) -> int:
    f = _file()
    if not f.is_file():
        return 0
    since = datetime.now(timezone.utc) - timedelta(days=days)
    seen: set[str] = set()
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("ev") == "audit" and datetime.fromisoformat(row["t"]) >= since:
                seen.add(row["h"])
        except (ValueError, KeyError):
            continue
    return len(seen)
