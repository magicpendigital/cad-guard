"""Lịch sử quét cục bộ của một dự án: `<thư mục dự án>/.cadguard/history.jsonl` (mỗi dòng một sự kiện JSON).

Chỉ ghi số liệu tóm tắt: thời điểm, sự kiện, **mã băm** tệp (băm đường dẫn tương đối với muối ngẫu nhiên riêng của dự án
và mã băm nội dung), phòng, chuẩn, đếm theo mức và theo luật. Không ghi tên tệp, tên khách, chữ trong bản vẽ hay đường
dẫn. Giao diện (chỉ trên máy này) đổi mã băm về tên tệp bằng cách băm lại danh sách tệp hiện có của dự án.

Dữ liệu này nuôi màn Việc của tôi và Tổng quan tuần; không gửi đi đâu.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

DIR = ".cadguard"
FILE = "history.jsonl"
SALT_FILE = "history.salt"
MAX_READ = 20000
EVENTS = ("audit", "apply", "undo", "handover")
_ID_RE = re.compile(r"^[0-9a-f]{12}$")
_RULE_RE = re.compile(r"^[A-Za-z0-9.\-]{1,32}$")
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now().astimezone()


class History:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / DIR
        self.path = self.dir / FILE
        self._salt: str | None = None

    # ---------- mã băm ----------

    def salt(self) -> str:
        if self._salt is None:
            p = self.dir / SALT_FILE
            try:
                s = p.read_text(encoding="ascii").strip()
                if not re.fullmatch(r"[0-9a-f]{32}", s):
                    raise ValueError
            except (OSError, ValueError):
                s = secrets.token_hex(16)
                try:
                    self.dir.mkdir(parents=True, exist_ok=True)
                    p.write_text(s, encoding="ascii")
                except OSError:
                    pass
            self._salt = s
        return self._salt

    def file_id(self, rel: str) -> str:
        return hashlib.sha256((self.salt() + "\n" + rel.replace("\\", "/")).encode("utf-8")).hexdigest()[:12]

    def names(self, rels: Iterable[str]) -> dict[str, str]:
        return {self.file_id(r): r for r in rels}

    # ---------- ghi / đọc ----------

    def record(self, event: str, **fields) -> dict:
        if event not in EVENTS:
            raise ValueError(event)
        entry = {"v": 1, "ts": _now().isoformat(timespec="seconds"), "event": event}
        for k, v in fields.items():
            if v is not None:
                entry[k] = v
        line = json.dumps(entry, ensure_ascii=True, separators=(",", ":"))
        with _lock:
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass  # thư mục chỉ đọc: lịch sử là phụ, không làm hỏng việc chính
        return entry

    def read(self, limit: int = MAX_READ) -> list[dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for ln in lines:
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if isinstance(e, dict) and e.get("event") in EVENTS and isinstance(e.get("ts"), str):
                try:
                    e["_t"] = datetime.fromisoformat(e["ts"])
                except ValueError:
                    continue
                out.append(e)
        return out


def audit_entry(file_id: str, content_hash: str, dept: str | None, standard: str, version: str,
                counts: dict, rules: Counter) -> dict:
    return {"file": file_id, "sha": (content_hash or "")[:16] or None, "dept": dept, "standard": standard,
            "version": version, "counts": {k: int(counts.get(k, 0)) for k in ("E", "W", "I")},
            "rules": {r: int(n) for r, n in sorted(rules.items()) if _RULE_RE.fullmatch(r)}}


# ---------- tổng hợp ----------

def _since(events: list[dict], days: int) -> list[dict]:
    t0 = _now() - timedelta(days=days)
    return [e for e in events if e["_t"] >= t0]


def latest_audits(events: list[dict], dept: str | None = None) -> dict[tuple[str, str], dict]:
    """(tệp, chuẩn) -> lần quét mới nhất (lọc theo phòng nếu có)."""
    out: dict[tuple[str, str], dict] = {}
    for e in events:
        if e["event"] != "audit" or (dept is not None and e.get("dept") != dept):
            continue
        out[(e.get("file"), e.get("standard"))] = e
    return out


def file_states(events: list[dict], dept: str, standards: list[str]) -> dict[str, dict]:
    """tệp -> {scanned_all, errors, warnings, open, rules, last_ts, handover} theo các chuẩn của phòng."""
    lat = latest_audits(events, dept)
    hand: dict[str, dict] = {}
    for e in events:
        if e["event"] == "handover" and e.get("dept") == dept:
            hand[e.get("file")] = e
    files = {f for (f, _s) in lat} | set(hand)
    out = {}
    for f in files:
        per = {s: lat.get((f, s)) for s in standards}
        got = [x for x in per.values() if x]
        out[f] = {
            "scanned": bool(got), "scanned_all": bool(standards) and all(per.values()),
            "errors": sum(x["counts"].get("E", 0) for x in got), "warnings": sum(x["counts"].get("W", 0) for x in got),
            "infos": sum(x["counts"].get("I", 0) for x in got),
            "rules": dict(sum((Counter(x.get("rules") or {}) for x in got), Counter())),
            "last_ts": max((x["ts"] for x in got), default=None),
            "handover": hand.get(f, {}).get("ts"),
        }
    return out


def home(events: list[dict], dept: dict, departments: list[dict], name_of: Callable[[str], str | None],
         title_of: Callable[[str], str | None]) -> dict:
    did = dept["id"]
    recent30 = _since(events, 30)
    freq = Counter()
    for e in recent30:
        if e["event"] == "audit" and e.get("dept") == did:
            for r in (e.get("rules") or {}):
                freq[r] += 1
    frequent = [{"rule_id": r, "title": title_of(r) or r, "times": n} for r, n in freq.most_common(5)]

    week = _since(events, 7)
    pipe = {}
    for d in departments:
        st = file_states(week, d["id"], d.get("standards") or [])
        pipe[d["id"]] = {"in_progress": sum(1 for s in st.values() if s["scanned"] and not s["handover"]),
                         "ready": sum(1 for s in st.values() if s["scanned_all"] and s["errors"] == 0),
                         "handed_over": sum(1 for s in st.values() if s["handover"])}

    states = file_states(events, did, dept.get("standards") or [])
    inbox = []
    seen = set()
    for e in reversed(events):
        if e["event"] == "handover" and did in (e.get("to") or []) and e.get("file") not in seen:
            seen.add(e.get("file"))
            name = name_of(e.get("file"))
            if name:
                from_dept = next((d["name"] for d in departments if d["id"] == e.get("dept")), e.get("dept"))
                inbox.append({"file": name, "from": from_dept, "ts": e["ts"],
                              "received": bool(states.get(e.get("file"), {}).get("scanned"))})
    recent = []
    for e in reversed(events):
        if len(recent) >= 8:
            break
        name = name_of(e.get("file")) if e.get("file") else None
        item = {"ts": e["ts"], "event": e["event"], "file": name, "dept": e.get("dept")}
        if e["event"] == "audit":
            c = e.get("counts") or {}
            item["findings"] = int(c.get("E", 0)) + int(c.get("W", 0)) + int(c.get("I", 0))
            item["standard"] = e.get("standard")
        elif e["event"] in ("apply", "undo"):
            item["output"] = name_of(e.get("out")) if e.get("out") else None
            item["ops"] = e.get("ops")
        elif e["event"] == "handover":
            item["to"] = [next((d["name"] for d in departments if d["id"] == t), t) for t in e.get("to") or []]
        recent.append(item)
    return {"frequent_rules": frequent, "pipe": pipe, "inbox": inbox[:6], "recent": recent,
            "files": {name_of(f): s for f, s in states.items() if name_of(f)}}


def overview(events: list[dict], departments: list[dict], title_of: Callable[[str], str | None],
             realtime_of: Callable[[str], bool | None], changesets: list[dict]) -> dict:
    week = _since(events, 7)
    audits = [e for e in week if e["event"] == "audit"]
    files = {e.get("file") for e in audits}
    lat = latest_audits(week)
    open_e = sum(e["counts"].get("E", 0) for e in lat.values())
    rules = Counter()
    for e in lat.values():
        rules.update(e.get("rules") or {})
    t7 = _now() - timedelta(days=7)

    def recent(ts: str | None) -> bool:
        try:
            return ts is not None and datetime.fromisoformat(ts) >= t7
        except ValueError:
            return False

    proposed = [c for c in changesets if recent(c.get("created_at"))]
    applied = [c for c in proposed if c.get("applied") and not c["applied"].get("undone_at")]
    flows = []
    for d in departments:
        nexts = d.get("next") or []
        if not nexts:
            continue
        st = file_states(week, d["id"], d.get("standards") or [])
        flows.append({"from": d["name"], "to": [next((x["name"] for x in departments if x["id"] == n), n) for n in nexts],
                      "handed_over": sum(1 for e in week if e["event"] == "handover" and e.get("dept") == d["id"]),
                      "blocked": sum(1 for s in st.values() if s["scanned"] and s["errors"] > 0)})
    top = [{"rule_id": r, "title": title_of(r) or r, "count": n, "realtime_ok": realtime_of(r)}
           for r, n in rules.most_common(8)]
    return {"files_scanned": len(files), "audits": len(audits), "open_errors": open_e,
            "changesets_proposed": len(proposed), "changesets_applied": len(applied),
            "handovers": sum(1 for e in week if e["event"] == "handover"), "flows": flows, "top_rules": top,
            "has_data": bool(week)}


__all__ = ["History", "audit_entry", "file_states", "home", "latest_audits", "overview"]
