"""Trạng thái chốt tờ và xác nhận cảnh báo, lưu CỤC BỘ trong `<thư mục làm việc>/.cadguard/sheets/<mã tệp>.json`.

Không lưu tên người, không gửi đi đâu. Tờ đã chốt mà nội dung đổi (mã băm nội dung tờ khác lúc chốt) thì coi như
mở lại ("stale"). Lý do "Bỏ qua" là dữ liệu đo tỉ lệ báo sai (P1c), chỉ xuất ra ngoài dưới dạng số tổng hợp.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

SCHEMA = "cg.sheet-state/1"
STATE_DIR = ".cadguard/sheets"
MAX_REASON = 300


def file_id(rel: str) -> str:
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16]


class SheetState:
    def __init__(self, ws_root: Path, rel: str):
        self.path = Path(ws_root) / STATE_DIR / f"{file_id(rel)}.json"
        self.data = {"schema": SCHEMA, "sheets": {}, "acks": {}}
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("schema") == SCHEMA:
                self.data["sheets"] = d.get("sheets") or {}
                self.data["acks"] = d.get("acks") or {}
        except (OSError, ValueError):
            pass

    @property
    def acks(self) -> dict:
        return self.data["acks"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def status(self, sheet_id: str, content_hash: str) -> dict:
        s = self.data["sheets"].get(sheet_id)
        if not s or s.get("status") != "locked":
            return {"status": "open", "stale": False}
        stale = s.get("content_hash") != content_hash
        return {"status": "open" if stale else "locked", "stale": stale, "locked_at": s.get("at")}

    def lock(self, sheet_id: str, content_hash: str, standards: list[str]) -> None:
        self.data["sheets"][sheet_id] = {"status": "locked", "content_hash": content_hash, "standards": standards,
                                         "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.save()

    def unlock(self, sheet_id: str) -> None:
        self.data["sheets"].pop(sheet_id, None)
        self.save()

    def ack(self, key: str, kind: str, reason: str) -> None:
        self.data["acks"][key] = {"kind": kind, "reason": reason[:MAX_REASON], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.save()

    def unack(self, key: str) -> None:
        self.data["acks"].pop(key, None)
        self.save()


__all__ = ["SCHEMA", "SheetState", "file_id"]
