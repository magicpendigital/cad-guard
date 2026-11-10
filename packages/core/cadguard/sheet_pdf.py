"""In PDF hàng loạt theo TỜ bằng `accoreconsole` của AutoCAD đã cài (kế hoạch two-tracks mục 4, Luồng 1).

- Tờ lấy từ chỉ mục tờ (`sheets.py`): khung tên trong không gian mô hình. Mỗi tờ in cửa sổ đúng khung, khổ ISO
  "full bleed" theo khổ nhận được, vừa khổ (Fit = đúng hệ số với khung chuẩn), căn giữa, bảng nét `monochrome.ctb`.
- Tên tệp theo SỐ BẢN VẼ của template (`cg.template/1`, trường vai trò `number`), vd. `NT-01.pdf`; không có template
  hoặc tờ thiếu số thì `To-05.pdf`; trùng số thì thêm hậu tố tờ. Ký tự cấm trong tên tệp đổi thành '-'.
- Một lần mở bản vẽ cho cả bộ tờ (một tệp .scr nhiều lệnh `-PLOT`); tệp nguồn chỉ đọc. Không ghi đè PDF đã có.
- Tờ dạng layout chưa hỗ trợ (báo, không in).
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .model import DrawingModel
from .sheets import PAPERS, build_structure

DEVICE = "DWG To PDF.pc3"
CTB = "monochrome.ctb"
# tên khổ của DWG To PDF.pc3 (cạnh dài trước); A0 chỉ có dạng đứng
MEDIA = {
    "A0": ("ISO full bleed A0 (841.00 x 1189.00 MM)", False),
    "A1": ("ISO full bleed A1 (841.00 x 594.00 MM)", True),
    "A2": ("ISO full bleed A2 (594.00 x 420.00 MM)", True),
    "A3": ("ISO full bleed A3 (420.00 x 297.00 MM)", True),
    "A4": ("ISO full bleed A4 (297.00 x 210.00 MM)", True),
}
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
SECONDS_OPEN = 120.0
SECONDS_PER_SHEET = 30.0


class PdfError(RuntimeError):
    """Không in được PDF (tiếng Việt)."""


def safe_name(value: str) -> str:
    s = _BAD.sub("-", value.strip()).strip(" .-")
    return s[:80]


def paper_by_factor(w: float, h: float, factor: float | None) -> str | None:
    """Khổ ISO của khung có hệ số lạ (vd. 66,87: không khớp tỉ lệ chuẩn): kích thước ÷ hệ số lệch ≤ 2 % một khổ."""
    if not factor:
        return None
    big, small = max(w, h) / factor, min(w, h) / factor
    return next((n for n, (pw, ph) in PAPERS.items() if abs(big - pw) <= 0.02 * pw and abs(small - ph) <= 0.02 * ph), None)


def plan(model: DrawingModel, tpl: dict | None = None, picks: list[int] | None = None) -> tuple[list[dict], list[str]]:
    """Danh sách tờ cần in: {index, name, window, paper, media, landscape, file}. Trả (kế hoạch, ghi chú)."""
    st = build_structure(model)
    by_handle = {e.handle: e for e in model.entities}
    num_tag = None
    if tpl:
        num_tag = next((f["tag"] for f in tpl.get("fields", []) if f.get("role") == "number"), None)
    items: list[dict] = []
    notes: list[str] = []
    used: dict[str, int] = {}
    for i, s in enumerate(st.sheets, 1):
        if picks and i not in picks:
            continue
        if s.kind != "frame" or not s.windows:
            notes.append(f"{s.name}: tờ dạng layout chưa in hàng loạt được; hãy in trong AutoCAD.")
            continue
        x0, y0, x1, y1 = s.windows[0]
        paper = s.paper or paper_by_factor(x1 - x0, y1 - y0, s.factor)
        if paper not in MEDIA:
            notes.append(f"{s.name}: không nhận ra khổ giấy ISO của khung; bỏ qua.")
            continue
        base = ""
        if num_tag and s.frame_handle:
            e = by_handle.get(s.frame_handle)
            attrs = {k.upper(): (v or "").strip() for k, v in ((e.attribs if e else None) or {}).items()}
            base = safe_name(attrs.get(num_tag.upper(), ""))
        if not base:
            base = f"To-{i:02d}"
            if num_tag:
                notes.append(f"{s.name}: thiếu số bản vẽ ({num_tag}); đặt tên {base}.pdf.")
        key = base.casefold()
        used[key] = used.get(key, 0) + 1
        if used[key] > 1:
            notes.append(f"{s.name}: số bản vẽ '{base}' trùng tờ trước; đặt tên {base}-to{i:02d}.pdf.")
            base = f"{base}-to{i:02d}"
        media, long_first = MEDIA[paper]
        wide = (x1 - x0) >= (y1 - y0)
        items.append({"index": i, "name": s.name, "title": s.title, "window": [x0, y0, x1, y1], "paper": paper,
                      "media": media, "landscape": wide if long_first else not wide, "file": base + ".pdf"})
    return items, notes


def _lisp_path(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if '"' in s:
        raise PdfError("Đường dẫn có dấu nháy kép: không in được.")
    return s


def script(items: list[dict], out_dir: Path, ctb: str = CTB) -> str:
    """Tệp lệnh accoreconsole: mỗi tờ một `-PLOT` cửa sổ (trả lời đủ câu hỏi, không tương tác)."""
    lines = ['(setvar "FILEDIA" 0)', '(setvar "CMDDIA" 0)', '(setvar "BACKGROUNDPLOT" 0)']
    for it in items:
        x0, y0, x1, y1 = it["window"]
        out = _lisp_path(Path(out_dir) / it["file"])
        lines.append(
            f'(command "_.-PLOT" "_Y" "Model" "{DEVICE}" "{it["media"]}" "_M" "{"_L" if it["landscape"] else "_P"}" "_N" '
            f'"_W" \'({x0!r} {y0!r}) \'({x1!r} {y1!r}) "_F" "_C" "_Y" "{ctb}" "_Y" "_A" "{out}" "_N" "_Y")')
    return "\r\n".join(lines) + "\r\n"


def plot_sheets(dxf: Path, out_dir: Path, *, tpl: dict | None = None, picks: list[int] | None = None,
                ctb: str = CTB, exe: Path | None = None, timeout: float | None = None) -> dict:
    """In các tờ của `dxf` ra `out_dir/<số bản vẽ>.pdf`. Trả {count, printed[], missing[], notes[], seconds}."""
    from .dwg import DwgError, run_script
    from .reader_select import read_with

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model = read_with(Path(dxf), "ezdxf")
    items, notes = plan(model, tpl, picks)
    if not items:
        raise PdfError("Không có tờ nào in được (" + ("; ".join(notes[:3]) or "không nhận ra tờ") + ").")
    exist = [it["file"] for it in items if (out_dir / it["file"]).exists()]
    if exist:
        raise PdfError(f"Đã có {len(exist)} tệp PDF cùng tên trong thư mục đích (vd. {exist[0]}): không ghi đè; "
                       "chọn thư mục trống.")
    t0 = time.monotonic()
    try:
        log = run_script(Path(dxf).resolve(), script(items, out_dir.resolve(), ctb),
                         timeout or SECONDS_OPEN + SECONDS_PER_SHEET * len(items), exe)
    except DwgError as exc:
        raise PdfError(str(exc)) from None
    printed = [it for it in items if (out_dir / it["file"]).is_file() and (out_dir / it["file"]).stat().st_size > 0]
    missing = [it for it in items if it not in printed]
    if missing and not printed:
        tail = " ".join(re.findall(r"(?:error|invalid)[^\r\n]*", log, re.I)[-2:])
        notes.append("AutoCAD không in được tờ nào" + (f" ({tail})" if tail else "") + ".")
    return {"count": len(items), "printed": [{k: it[k] for k in ("index", "name", "file", "paper")} for it in printed],
            "missing": [{k: it[k] for k in ("index", "name", "file")} for it in missing], "notes": notes,
            "seconds": round(time.monotonic() - t0, 1)}


__all__ = ["PdfError", "plan", "plot_sheets", "safe_name", "script"]
