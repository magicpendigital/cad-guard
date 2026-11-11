"""Dòng phiên bản của một bản vẽ: bản gốc (chỉ đọc) → các tệp mới do từng lệnh sửa tạo ra (Unicode, Dịch, Sửa hàng
loạt, áp đề xuất…). Người dùng thấy MỘT bản vẽ có lịch sử, không phải nhiều tệp rời phải tự chọn.

- Quan hệ cha → con đọc từ nhật ký áp dụng `.cadguard/changesets/*.apply.json` (nguồn, tệp ra, thời điểm, thao tác).
- "Bản đang dùng" của mỗi dòng: mặc định bản mới nhất còn trên đĩa; người dùng chọn lại được (Hoàn tác = về bản cha,
  Làm lại = sang bản con vừa rời). Lưu ở `.cadguard/versions.json`; KHÔNG xoá hay ghi đè tệp nào.
- Áp lệnh lên một bản không phải bản mới nhất tạo nhánh mới; nhánh cũ vẫn giữ và xem được trong lịch sử.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STORE = ".cadguard/versions.json"
OP_VI = {"convert_unicode": "Chuẩn hoá Unicode", "add_texts": "Dịch (thêm chữ)", "rename_layer": "Đổi tên layer",
         "merge_layers": "Gộp layer", "purge": "Dọn rác", "set_attrib": "Sửa thuộc tính", "split": "Tách tờ",
         "apply_template": "Áp template"}


def _edges(root: Path) -> list[dict]:
    out = []
    for p in sorted((root / ".cadguard" / "changesets").glob("*.apply.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        src, dst = (d.get("source") or {}).get("path"), (d.get("output") or {}).get("path")
        if not src or not dst or d.get("undone_at"):
            continue
        ops = [o.get("op") for o in d.get("ops") or [] if o.get("op")]
        names = list(dict.fromkeys(OP_VI.get(o, o) for o in ops))
        out.append({"from": src, "to": dst, "at": d.get("applied_at", ""), "changeset": d.get("changeset_id", ""),
                    "summary": ", ".join(names[:4]) + ("…" if len(names) > 4 else "")})
    return out


def _load(root: Path) -> dict:
    p = root / STORE
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(root: Path, data: dict) -> None:
    p = root / STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def families(root: Path) -> dict[str, dict]:
    """{bản gốc: {root, versions: [...theo thời gian], current, latest}} — chỉ những dòng có ≥ 2 bản."""
    edges = _edges(root)
    parent = {e["to"]: e for e in edges}

    def top(p: str) -> str:
        seen = set()
        while p in parent and p not in seen:
            seen.add(p)
            p = parent[p]["from"]
        return p

    fam: dict[str, list[str]] = {}
    for e in edges:
        r = top(e["to"])
        fam.setdefault(r, [r])
        for p in (e["from"], e["to"]):
            if p not in fam[r]:
                fam[r].append(p)
    state = _load(root)
    out = {}
    for r, paths in fam.items():
        vers = []
        for p in paths:
            e = parent.get(p)
            vers.append({"path": p, "parent": e["from"] if e else None, "at": e["at"] if e else "", "summary": e["summary"] if e else "Bản gốc",
                         "changeset": e["changeset"] if e else "", "exists": (root / p).is_file()})
        vers.sort(key=lambda v: (v["parent"] is not None, v["at"]))
        alive = [v["path"] for v in vers if v["exists"]]
        latest = alive[-1] if alive else r
        cur = (state.get("current") or {}).get(r)
        current = cur if cur in alive else latest
        out[r] = {"root": r, "versions": vers, "latest": latest, "current": current,
                  "redo": [p for p in (state.get("redo") or {}).get(r, []) if p in alive]}
    return out


def info(root: Path, rel: str) -> dict:
    """Vị trí của một tệp trong dòng phiên bản: state = single | current | old."""
    for f in families(root).values():
        if any(v["path"] == rel for v in f["versions"]):
            return {**f, "file": rel, "state": "current" if f["current"] == rel else "old"}
    return {"file": rel, "state": "single", "versions": [], "current": rel, "latest": rel, "root": rel, "redo": []}


def overview(root: Path) -> dict[str, dict]:
    """{tệp: {state, root, current, n}} cho danh sách tệp."""
    out = {}
    for f in families(root).values():
        for v in f["versions"]:
            out[v["path"]] = {"state": "current" if v["path"] == f["current"] else "old", "root": f["root"],
                              "current": f["current"], "n": sum(1 for x in f["versions"] if x["exists"])}
    return out


def set_current(root: Path, rel: str, target: Any, *, _redo: list | None = None) -> dict:
    f = info(root, rel)
    if f["state"] == "single":
        raise ValueError("Bản vẽ này chưa có phiên bản nào khác.")
    alive = {v["path"] for v in f["versions"] if v["exists"]}
    if target not in alive:
        raise ValueError("Phiên bản không thuộc dòng của bản vẽ này hoặc không còn trên đĩa.")
    st = _load(root)
    st.setdefault("current", {})[f["root"]] = target
    st.setdefault("redo", {})[f["root"]] = _redo if _redo is not None else []
    _save(root, st)
    return info(root, target)


def undo(root: Path, rel: str) -> dict:
    """Về bản cha của bản đang dùng (tệp vẫn còn, chỉ đổi bản đang dùng)."""
    f = info(root, rel)
    cur = next((v for v in f["versions"] if v["path"] == f["current"]), None)
    if cur is None or not cur["parent"]:
        raise ValueError("Đang ở bản gốc: không còn bước nào để hoàn tác.")
    return set_current(root, rel, cur["parent"], _redo=[f["current"]] + f.get("redo", []))


def redo(root: Path, rel: str) -> dict:
    f = info(root, rel)
    if not f.get("redo"):
        raise ValueError("Không có bước nào để làm lại.")
    return set_current(root, rel, f["redo"][0], _redo=f["redo"][1:])


__all__ = ["families", "info", "overview", "redo", "set_current", "undo"]
