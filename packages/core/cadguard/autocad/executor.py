"""Bộ thực thi THỨ HAI của changeset: áp lên bản vẽ đang mở trong AutoCAD qua COM (Đợt F, cổng hướng D đã mở 10/11/2026).

Một changeset, hai nơi thực thi: đường chính ghi DXF mới (`changeset.apply`); đường này đẩy CÙNG kết quả vào bản DWG
đang mở. Cách làm: chạy các thao tác trên bản sao DXF trong bộ nhớ (đúng như đường tệp), so trước/sau để lấy thay đổi
theo handle, rồi gửi từng thay đổi qua COM. Không chạy LISP do trợ lý viết; chỉ đặt thuộc tính COM có tên.

Lưới an toàn (giữ theo quyết định 10/11/2026):
- chỉ nhận thao tác về chữ: `set_texts`, `set_attribs`, `convert_unicode` (thao tác layer/kiểu kích thước đi đường tệp);
- bản vẽ phải ĐÃ LƯU (DBMOD = 0) để sao lưu đúng trạng thái: chép DWG sang `<dự án>/.cadguard/backup/`;
- chỉ áp khi chữ hiện tại của MỌI đối tượng bị đổi khớp lúc xem trước (bản vẽ chưa đổi); lệch một chỗ là dừng, không đổi gì;
- áp trong MỘT nhóm undo: gõ U trong AutoCAD là trả lại nguyên trạng; bản vẽ không tự lưu (người dùng SAVE khi ưng).
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .bridge import BridgeError, _connect_default

SUPPORTED_OPS = {"set_texts", "set_attribs", "convert_unicode"}
TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF", "MULTILEADER", "DIMENSION"}


def _text(e) -> str:
    t = e.dxftype()
    if t == "MTEXT":
        return e.text
    if t == "MULTILEADER":
        m = e.context.mtext
        return (m.default_content or "") if m is not None else ""
    return str(e.dxf.get("text", "") or "")


def plan(ws, ref: str, standards_dir: Path | None = None) -> dict:
    """Từ changeset -> {changeset, source, entities: [{handle, type, before, after, style}], styles: [...]}."""
    from ..changeset.apply import load_for_apply
    from ..changeset.engine import read_doc, run_ops

    cs, ops, _std, prot, src = load_for_apply(ws, ref, None, standards_dir)
    bad = sorted({o.op for o in ops} - SUPPORTED_OPS)
    if bad:
        raise BridgeError(f"Thao tác {', '.join(bad)} chưa áp được trong AutoCAD; hãy dùng đường tệp (cadguard apply).")
    before, after = read_doc(src), read_doc(src)
    run_ops(after, ops, prot)
    ents = []
    for h, e in before.entitydb.items():
        if e.dxftype() not in TEXT_TYPES or not e.is_alive:
            continue
        a = after.entitydb.get(h)
        if a is None:
            continue
        tb, ta = _text(e), _text(a)
        has = e.dxf.is_supported("style")
        sb = str(e.dxf.get("style", "") or "") if has else ""
        sa = str(a.dxf.get("style", "") or "") if has else ""
        if tb != ta or sb != sa:
            ents.append({"handle": h, "type": e.dxftype(), "before": tb, "after": ta, "style": sa if sa != sb else None})
    styles = []
    for st in after.styles:
        name = str(st.dxf.name)
        font_a = str(st.dxf.get("font", "") or "")
        try:
            fam = str(st.get_extended_font_data()[0] or "")
        except Exception:  # noqa: BLE001
            fam = ""
        old = before.styles.get(name) if before.styles.has_entry(name) else None
        font_b = str(old.dxf.get("font", "") or "") if old is not None else None
        if old is None or font_a != font_b:
            styles.append({"name": name, "font": font_a, "family": fam, "new": old is None})
    return {"changeset": cs.id, "source": cs.source.path, "entities": ents, "styles": styles}


def _find_doc(acad, drawing: str):
    for d in acad.Documents:
        if Path(str(d.Name)).stem.lower() == drawing.lower():
            return d
    raise BridgeError("Bản vẽ này chưa mở trong AutoCAD.")


def _com_text(obj, typ: str) -> str:
    if typ == "DIMENSION":
        return str(obj.TextOverride or "")
    return str(obj.TextString or "")


def apply_in_autocad(ws, ref: str, drawing: str, *, confirm: bool = False, connect: Callable[[], Any] | None = None,
                     standards_dir: Path | None = None) -> dict:
    """Áp changeset lên bản `drawing` đang mở. Trả báo cáo; mọi điều kiện không đạt -> BridgeError (không đổi gì)."""
    if not confirm:
        raise BridgeError("Cần người dùng xác nhận trước khi áp dụng vào AutoCAD.")
    p = plan(ws, ref, standards_dir)
    com_init = connect is None and sys.platform == "win32"
    if com_init:
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except ImportError:
            com_init = False
    try:
        acad = (connect or _connect_default)()
        doc = _find_doc(acad, drawing)
        if int(doc.GetVariable("DBMOD") or 0):
            raise BridgeError("Bản vẽ có thay đổi chưa lưu. Hãy SAVE trước (để sao lưu đúng), rồi chạy lại.")
        if int(doc.GetVariable("CMDACTIVE") or 0):
            raise BridgeError("AutoCAD đang chạy một lệnh. Nhấn Esc rồi chạy lại.")
        objs = []
        stale = []
        for c in p["entities"]:
            try:
                obj = doc.HandleToObject(c["handle"])
            except Exception:  # noqa: BLE001
                stale.append(c["handle"])
                continue
            if _com_text(obj, c["type"]) != c["before"]:
                stale.append(c["handle"])
            objs.append((obj, c))
        if stale:
            raise BridgeError(f"Bản vẽ đã khác lúc xem trước ở {len(stale)} đối tượng (vd. handle {', '.join(stale[:5])}): "
                              "không áp dụng. Hãy CGXUAT lại rồi đề xuất lại.")
        backup = _backup(ws.root, Path(str(doc.FullName)))
        doc.StartUndoMark()
        try:
            for s in p["styles"]:
                st = doc.TextStyles.Add(s["name"]) if s["new"] else doc.TextStyles.Item(s["name"])
                if s["family"]:
                    st.SetFont(s["family"], False, False, 0, 0)
                else:
                    st.fontFile = s["font"]
            for obj, c in objs:
                if c["type"] == "DIMENSION":
                    obj.TextOverride = c["after"]
                else:
                    obj.TextString = c["after"]
                if c["style"] and c["type"] in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF"):
                    obj.StyleName = c["style"]
        finally:
            doc.EndUndoMark()
        try:
            doc.Regen(1)
        except Exception:  # noqa: BLE001
            pass
    finally:
        if com_init:
            import pythoncom

            pythoncom.CoUninitialize()
    rep = {"changeset_id": p["changeset"], "drawing": drawing, "entities": len(p["entities"]), "styles": len(p["styles"]),
           "backup": backup.name, "applied_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "undo": "Gõ U trong AutoCAD (một nhóm undo) hoặc mở bản sao lưu."}
    log = ws.root / ".cadguard" / "changesets" / f"{p['changeset']}.autocad.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep


def _backup(ws_root: Path, dwg: Path) -> Path:
    if not dwg.is_file():
        raise BridgeError("Không thấy tệp DWG đã lưu của bản vẽ để sao lưu.")
    d = Path(ws_root) / ".cadguard" / "backup"
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{dwg.stem}.{datetime.now().strftime('%Y%m%d-%H%M%S')}{dwg.suffix}"
    shutil.copyfile(dwg, dst)
    return dst


__all__ = ["SUPPORTED_OPS", "apply_in_autocad", "plan"]
