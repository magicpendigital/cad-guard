"""Dịch chữ trong bản vẽ sang Tiếng Anh hoặc Tiếng Trung (kế hoạch sheets-presentation mục 3, Đợt E).

Chuỗi xử lý (dịch là CÔNG CỤ có lệnh riêng; chat chỉ là một cách gọi):
1. Giải mã chữ TCVN3/VNI sang Unicode (cùng bộ `unicode_convert`, chạy trên bản sao trong bộ nhớ).
2. Nhận ngôn ngữ nguồn của bản vẽ theo NỘI DUNG (`detect_language`): Việt / Trung / Anh.
3. Tách phần không dịch: số + đơn vị, mã vật liệu/mã bản vẽ, mã định dạng MTEXT → ký hiệu giữ chỗ ⟦n⟧.
4. Tra bảng thuật ngữ (có sẵn + `<dự án>/.cadguard/glossary.yaml`) và bộ nhớ dịch (`.cadguard/translation-memory.json`).
5. LLM dịch phần còn lại theo lô (chỉ ĐỀ XUẤT); thiếu LLM thì chỉ dùng bảng thuật ngữ + bộ nhớ dịch.
6. Kiểm tất định: ký hiệu giữ chỗ đủ (số/đơn vị/mã không đổi), thuật ngữ khớp bảng, chuỗi chưa dịch, chữ có thể tràn
   khung, phông đích có ký tự (Trung: kiểu chữ CJK riêng).
7. Changeset → xem trước → áp dụng ra tệp mới → hoàn tác. Hai chế độ:
   - `copy` (mặc định): `convert_unicode` + `set_texts`, chữ thay tại chỗ, ra `<tên>.<ngôn ngữ>.dxf`;
   - `layer`: chữ gốc GIỮ NGUYÊN (kể cả mã cũ), `add_texts` thêm chữ dịch trên layer `CG-DICH-EN`/`CG-DICH-ZH`, đặt
     ngay dưới chữ gốc; bật/tắt layer để xem một hoặc hai ngôn ngữ; ra `<tên>.<ngôn ngữ>layer.dxf`.

Dịch gửi NỘI DUNG chữ cho LLM: được phép mặc định (công cụ nội bộ); dự án bật ẩn danh (NDA) thì bị khoá.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .unicode_convert import _MTEXT_CODE, convert_doc, iter_text_entities, raw_text

TARGETS = {"en": "Tiếng Anh", "zh": "Tiếng Trung"}
LANG_NAMES = {"vi": "Tiếng Việt", "en": "Tiếng Anh", "zh": "Tiếng Trung"}
CJK_FONT = ("msyh.ttc", "Microsoft YaHei")  # có sẵn trên Windows; Be Vietnam Pro không có chữ Hán
CJK_STYLE = "CG-ZH"
LAYER_FONT = ("BeVietnamPro-Regular.ttf", "Be Vietnam Pro")  # phông Unicode công ty (như convert_unicode)
LAYER_STYLE = "CG-DICH"
BATCH = 60
MAX_ITEMS = 20000
GLOSSARY_FILE = Path(".cadguard") / "glossary.yaml"
TM_FILE = Path(".cadguard") / "translation-memory.json"
MODES = ("copy", "layer")
LAYER_PREFIX = "CG-DICH-"
LINE_GAP = 1.4  # khoảng dời chữ dịch xuống dưới chữ gốc, theo số lần chiều cao chữ (một dòng)

_CJK = re.compile(r"[㐀-鿿豈-﫿]")
_VI_MARK = re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
                      r"ÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌỒỐỔỖỘỜỚỞỠỢÙÚỦŨỤỪỨỬỮỰỲÝỶỸỴ]")
_EN_WORDS = frozenset("""the and of for with to in on at by from door drawer cabinet wardrobe kitchen shelf glass wood
panel plan section detail elevation ceiling floor wall light table chair bed sofa room living dining bath toilet
mirror handle hinge paint white black finish top bottom side front back view scale note see ref typ level""".split())
# số + đơn vị, phép nhân kích thước; mã có chữ hoa + số hoặc viết tắt in hoa (MDF, PU, NT-01, FUR.64)
_PROTECT = re.compile(
    r"\d+(?:[.,]\d+)?(?:\s*[x×*]\s*\d+(?:[.,]\d+)?)*\s*(?:mm|cm|m2|m²|m|kg|°|%|ly)?(?![A-Za-z])"
    r"|\b[A-Z]{2,}[A-Z0-9]*(?:[-./][A-Z0-9]+)*\b"
    r"|\b[A-Za-z]+[-./]?\d[\w.\-/]*\b")
_PH = re.compile(r"⟦(\d+)⟧")

# Bảng thuật ngữ có sẵn (nội thất). Dự án ghi đè/bổ sung bằng .cadguard/glossary.yaml.
BUILTIN_GLOSSARY = [
    ("tủ bếp", "kitchen cabinet", "橱柜"), ("tủ áo", "wardrobe", "衣柜"), ("tủ rượu", "wine cabinet", "酒柜"),
    ("kệ tivi", "TV cabinet", "电视柜"), ("cánh tủ", "cabinet door", "柜门"), ("ngăn kéo", "drawer", "抽屉"),
    ("mặt bằng", "floor plan", "平面图"), ("mặt đứng", "elevation", "立面图"), ("mặt cắt", "section", "剖面图"),
    ("chi tiết", "detail", "详图"), ("trần thạch cao", "gypsum ceiling", "石膏板吊顶"), ("đèn hắt", "cove light", "灯带"),
    ("nẹp chỉ", "trim strip", "装饰线条"), ("nhôm", "aluminium", "铝"), ("kính cường lực", "tempered glass", "钢化玻璃"),
    ("chống ẩm", "moisture-resistant", "防潮"), ("sơn", "paint", "油漆"), ("màu trắng", "white", "白色"),
    ("tầng", "floor", "层"), ("phòng khách", "living room", "客厅"), ("phòng ngủ", "bedroom", "卧室"),
    ("phòng bếp", "kitchen", "厨房"), ("vệ sinh", "toilet", "卫生间"), ("sảnh", "lobby", "大堂"),
    ("ghi chú", "note", "备注"), ("tỉ lệ", "scale", "比例"), ("bản vẽ", "drawing", "图纸"), ("dự án", "project", "项目"),
    ("khoang hở", "open compartment", "开放格"), ("tủ cánh kính", "glass door cabinet", "玻璃门柜"),
    ("veneer", "veneer", "木皮"), ("gỗ", "wood", "木"), ("tay nắm", "handle", "拉手"), ("bản lề", "hinge", "铰链"),
]


class TranslateError(ValueError):
    """Lỗi dịch (tiếng Việt)."""


# ---------- nhận ngôn ngữ ----------

def detect_language(text: str) -> str | None:
    """'vi' | 'zh' | 'en' | None (không chắc: chỉ số/mã, hoặc chữ không dấu không rõ)."""
    if not text:
        return None
    if _CJK.search(text):
        return "zh"
    if _VI_MARK.search(text):
        return "vi"
    words = re.findall(r"[A-Za-z]{2,}", text)
    if words and sum(w.lower() in _EN_WORDS for w in words) * 2 >= len(words):
        return "en"
    return None


def detect_drawing_language(texts) -> dict:
    counts = {"vi": 0, "en": 0, "zh": 0, "unknown": 0}
    for t in texts:
        counts[detect_language(t) or "unknown"] += 1
    known = {k: v for k, v in counts.items() if k != "unknown" and v}
    lang = max(known, key=known.get) if known else None
    return {"language": lang, "language_name": LANG_NAMES.get(lang or "", "chưa rõ"), "counts": counts}


# ---------- tách phần không dịch ----------

def plain_of(e_type: str, raw: str) -> str:
    """Chữ hiển thị (bỏ mã định dạng MTEXT) để nhận ngôn ngữ."""
    if e_type in ("MTEXT", "MULTILEADER"):
        return _MTEXT_CODE.sub(lambda m: " " if m.group(0) in ("\\P", "\\N") else "", raw).strip()
    return raw


def protect(raw: str, mtext: bool) -> tuple[str, list[str]]:
    """Thay mã MTEXT, số + đơn vị, mã vật liệu bằng ⟦n⟧. Trả (chuỗi có giữ chỗ, danh sách phần gốc)."""
    kept: list[str] = []

    def keep(s: str) -> str:
        kept.append(s)
        return f"⟦{len(kept) - 1}⟧"

    out = []
    pos = 0
    pieces = list(_MTEXT_CODE.finditer(raw)) if mtext else []
    for m in pieces:
        if m.start() > pos:
            out.append(_PROTECT.sub(lambda x: keep(x.group(0)), raw[pos:m.start()]))
        out.append(keep(m.group(0)))
        pos = m.end()
    out.append(_PROTECT.sub(lambda x: keep(x.group(0)), raw[pos:]))
    return "".join(out), kept


def restore(text: str, kept: list[str]) -> str:
    return _PH.sub(lambda m: kept[int(m.group(1))] if int(m.group(1)) < len(kept) else m.group(0), text)


def placeholders_ok(src: str, dst: str) -> bool:
    return sorted(_PH.findall(src)) == sorted(_PH.findall(dst))


# ---------- bảng thuật ngữ, bộ nhớ dịch ----------

def load_glossary(workspace: Path | None) -> list[dict]:
    terms = [{"vi": vi, "en": en, "zh": zh} for vi, en, zh in BUILTIN_GLOSSARY]
    if workspace is not None:
        p = Path(workspace) / GLOSSARY_FILE
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError, UnicodeDecodeError):
            data = {}
        extra = [t for t in (data.get("terms") or []) if isinstance(t, dict) and isinstance(t.get("vi"), str)]
        keys = {t["vi"].casefold() for t in extra}
        terms = [t for t in terms if t["vi"].casefold() not in keys] + extra
    return sorted(terms, key=lambda t: -len(t["vi"]))


def load_tm(workspace: Path | None) -> dict:
    if workspace is None:
        return {}
    try:
        data = json.loads((Path(workspace) / TM_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_tm(workspace: Path, tm: dict) -> None:
    p = Path(workspace) / TM_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tm, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def glossary_hits(text: str, glossary: list[dict], src: str) -> list[dict]:
    low = text.casefold()
    return [t for t in glossary if t.get(src) and t[src].casefold() in low]


# ---------- dịch ----------

SYSTEM = """You translate short texts from interior-furniture shop drawings (AutoCAD). Return ONLY JSON:
{"items": [{"id": "<id>", "text": "<translation>"}]}.
Rules: keep every placeholder like ⟦0⟧ exactly once and unchanged; do not translate or alter codes, numbers, units;
use the glossary terms exactly; keep it as short as the source (labels on a drawing); keep ALL CAPS if the source is ALL CAPS;
translate into {target}. Do not add explanations."""


@dataclass
class Item:
    handle: str
    type: str
    raw: str  # chữ sau giải mã mã cũ (định dạng gốc, kể cả mã MTEXT)
    plain: str
    masked: str = ""
    kept: list[str] = field(default_factory=list)
    target: str | None = None
    source: str = ""  # glossary | tm | llm | same
    issues: list[str] = field(default_factory=list)


def collect(doc, handles: set[str] | None = None) -> list[Item]:
    items = []
    for e in iter_text_entities(doc, include_blocks=False):
        t = e.dxftype()
        h = str(e.dxf.get("handle", ""))
        if handles is not None and h not in handles and not (t == "ATTRIB" and str(e.dxf.get("owner", "")) in handles):
            continue
        raw = raw_text(e)
        plain = plain_of(t, raw)
        if not re.search(r"[^\W\d_]{2,}", plain):  # không có chữ để dịch (chỉ số, ký hiệu)
            continue
        items.append(Item(handle=h, type=t, raw=raw, plain=plain))
    return items


def _llm_batch(backend, batch: list[Item], target: str, glossary: list[dict], src: str) -> dict[str, str]:
    gl = {}
    for it in batch:
        for t in glossary_hits(it.plain, glossary, src):
            if t.get(target):
                gl[t[src]] = t[target]
    payload = {"glossary": gl, "items": [{"id": str(i), "text": it.masked} for i, it in enumerate(batch)]}
    reply = backend.complete(SYSTEM.replace("{target}", LANG_NAMES[target] + f" ({target})"),
                             [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    m = re.search(r"\{.*\}", reply or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    out = {}
    for x in data.get("items") or []:
        if isinstance(x, dict) and str(x.get("id", "")).isdigit() and isinstance(x.get("text"), str):
            i = int(x["id"])
            if 0 <= i < len(batch):
                out[batch[i].handle] = x["text"]
    return out


def translate_items(items: list[Item], target: str, *, source_lang: str, backend=None,
                    glossary: list[dict] | None = None, tm: dict | None = None) -> dict:
    if target not in TARGETS:
        raise TranslateError("Ngôn ngữ đích phải là 'en' (Tiếng Anh) hoặc 'zh' (Tiếng Trung).")
    glossary = glossary if glossary is not None else load_glossary(None)
    tm_lang = tm.setdefault(f"{source_lang}>{target}", {}) if tm is not None else {}
    by_key = {t[source_lang].casefold(): t for t in glossary if t.get(source_lang) and t.get(target)}
    todo: list[Item] = []
    for it in items:
        lang = detect_language(it.plain)
        if lang == target:
            it.source = "same"
            continue
        it.masked, it.kept = protect(it.raw, it.type in ("MTEXT", "MULTILEADER"))
        if not re.search(r"[^\W\d_]{2,}", _PH.sub("", it.masked)):
            it.source = "same"  # chỉ còn số, đơn vị, mã sau khi bảo vệ: không có gì để dịch
            continue
        g = by_key.get(it.plain.strip().casefold())
        if g is not None and it.type in ("TEXT", "ATTRIB"):
            out = g[target]
            it.target = out.upper() if it.plain.isupper() and target == "en" else out
            it.source = "glossary"
        elif it.masked in tm_lang:
            it.target = restore(tm_lang[it.masked], it.kept)
            it.source = "tm"
        else:
            todo.append(it)
    llm_calls = 0
    if backend is not None and todo:
        uniq: dict[str, Item] = {}
        for it in todo:
            uniq.setdefault(it.masked, it)
        reps = list(uniq.values())
        got: dict[str, str] = {}
        for i in range(0, len(reps), BATCH):
            got.update(_llm_batch(backend, reps[i:i + BATCH], target, glossary, source_lang))
            llm_calls += 1
        by_masked = {r.masked: got.get(r.handle) for r in reps}
        for it in todo:
            out = by_masked.get(it.masked)
            if out is None:
                continue
            if not placeholders_ok(it.masked, out):
                it.issues.append("mất/đổi số, đơn vị hoặc mã")
                continue
            tm_lang[it.masked] = out
            it.target = restore(out, it.kept)
            it.source = "llm"
    # kiểm tất định
    for it in items:
        if it.target is None or it.source == "same":
            continue
        for t in glossary_hits(it.plain, glossary, source_lang):
            want = t.get(target)
            if want and want.casefold() not in it.target.casefold():
                it.issues.append(f"lệch thuật ngữ '{t[source_lang]}' → '{want}'")
        if _width(it.target, target) > 1.3 * _width(it.plain, source_lang) and len(it.plain) >= 4:
            it.issues.append("chữ dịch dài hơn nhiều: có thể tràn khung")
    return {"llm_calls": llm_calls}


def _width(s: str, lang: str) -> float:
    return sum(1.0 if _CJK.match(c) else 0.6 for c in s)


# ---------- ghép thành changeset ----------

def layer_name(target: str) -> str:
    return LAYER_PREFIX + target.upper()


def _below(e, raw: str) -> tuple[float, float]:
    """Độ dời (WCS) để đặt chữ dịch ngay dưới chữ gốc: một khối chữ cao + khoảng cách, theo hướng xoay của chữ."""
    import math

    t = e.dxftype()
    if t == "MULTILEADER":
        h = float(e.context.char_height or 2.5)
        lines, rot = raw.count("\\P") + 1, 0.0
    elif t == "MTEXT":
        h = float(e.dxf.get("char_height", 2.5) or 2.5)
        lines = raw.count("\\P") + 1
        rot = float(e.dxf.get("rotation", 0.0) or 0.0)
        if e.dxf.hasattr("text_direction"):
            d = e.dxf.text_direction
            rot = math.degrees(math.atan2(d.y, d.x))
    else:
        h = float(e.dxf.get("height", 2.5) or 2.5)
        lines, rot = 1, float(e.dxf.get("rotation", 0.0) or 0.0)
    dist = (lines - 1) * 1.67 * h + LINE_GAP * h
    a = math.radians(rot)
    return (round(math.sin(a) * dist, 9), round(-math.cos(a) * dist, 9))


def build(path: Path, target: str, *, workspace: Path, handles: set[str] | None = None, backend=None,
          update_tm: bool = True, overrides: dict[str, str] | None = None, mode: str = "copy") -> dict:
    """Đọc bản vẽ, dịch, trả {"ops", "report"}. Không ghi bản vẽ (ghi bộ nhớ dịch nếu `update_tm`)."""
    from . import privacy
    from .changeset.engine import read_doc

    if privacy.effective(workspace):
        raise TranslateError("Dự án đang bật ẩn danh (NDA): chức năng dịch bị khoá vì phải gửi nội dung chữ cho LLM.")
    if mode not in MODES:
        raise TranslateError("Chế độ dịch phải là 'copy' (thay tại chỗ) hoặc 'layer' (thêm chữ dịch trên layer riêng).")
    doc = read_doc(path)
    original = {str(e.dxf.get("handle", "")): (raw_text(e), e) for e in iter_text_entities(doc, include_blocks=False)}
    conv = convert_doc(doc)  # cùng kết quả với thao tác convert_unicode đứng trước trong changeset
    items = collect(doc, handles)
    if len(items) > MAX_ITEMS:
        raise TranslateError(f"Quá {MAX_ITEMS} chuỗi chữ; hãy dịch theo tờ (--sheets).")
    det = detect_drawing_language([it.plain for it in items])
    src = det["language"] or "vi"
    if src == target:
        raise TranslateError(f"Bản vẽ đã viết bằng {LANG_NAMES[target]}.")
    glossary = load_glossary(workspace)
    tm = load_tm(workspace)
    reviewed = []
    if overrides:  # bản dịch người duyệt sửa trong bảng CSV: dùng nguyên văn, không gọi LLM cho các chuỗi này
        reviewed = [it for it in items if it.handle in overrides]
        for it in reviewed:
            it.target, it.source = overrides[it.handle], "review"
        items_llm = [it for it in items if it.handle not in overrides]
    else:
        items_llm = items
    stats = translate_items(items_llm, target, source_lang=src, backend=backend, glossary=glossary, tm=tm)
    if update_tm and stats["llm_calls"]:
        save_tm(workspace, tm)
    done = [it for it in items if it.target is not None and it.source != "same" and it.target != it.raw]
    ops: list[dict] = []
    skipped_layer = []
    if mode == "layer":
        new_items = []
        for it in done:
            raw0, e = original.get(it.handle, (None, None))
            if e is None or e.dxftype() not in ("TEXT", "MTEXT", "ATTRIB", "MULTILEADER"):
                skipped_layer.append(it.handle)  # chữ ghi đè kích thước: không thêm chữ rời, giữ nguyên
                continue
            dx, dy = _below(e, it.raw)
            new_items.append({"source": it.handle, "text": it.target, "offset": [dx, dy], "expect": raw0})
        if new_items:
            # chữ dịch dùng kiểu chữ Unicode riêng (chữ gốc có thể dùng phông TCVN3/VNI): Anh -> Be Vietnam Pro, Trung -> CJK
            font = CJK_FONT if target == "zh" else LAYER_FONT
            op = {"op": "add_texts", "layer": layer_name(target), "items": new_items,
                  "style": CJK_STYLE if target == "zh" else LAYER_STYLE, "style_font": font[0], "style_family": font[1]}
            ops.append(op)
    else:
        if conv.converted:
            ops.append({"op": "convert_unicode"})
        if done:
            op = {"op": "set_texts", "items": [{"handle": it.handle, "text": it.target, "expect": it.raw} for it in done]}
            if target == "zh":
                op.update({"style": CJK_STYLE, "style_font": CJK_FONT[0], "style_family": CJK_FONT[1]})
            ops.append(op)
    pending = [it for it in items if it.target is None and it.source != "same"]
    report = {
        "source_language": det, "target": target, "target_name": TARGETS[target], "strings": len(items),
        "translated": len(done), "by_source": _count(it.source for it in done),
        "untranslated": len(pending), "untranslated_handles": [it.handle for it in pending][:200],
        "issues": [{"handle": it.handle, "issues": it.issues} for it in items if it.issues][:200],
        "issue_count": sum(1 for it in items if it.issues), "legacy_converted": conv.converted if mode == "copy" else 0,
        "mode": mode, "layer": layer_name(target) if mode == "layer" else None,
        "layer_skipped": len(skipped_layer), "layer_skipped_handles": skipped_layer[:200],
        "llm": getattr(backend, "name", None), "llm_calls": stats["llm_calls"],
        "rows": [{"handle": it.handle, "type": it.type, "source": it.plain[:200], "target": (it.target or "")[:200],
                  "from": it.source, "masked": it.masked} for it in items][:MAX_ITEMS],
    }
    return {"ops": ops, "report": report}


class DictBackend:
    """Bản dịch do người/trợ lý đưa sẵn theo chuỗi nguồn có ký hiệu giữ chỗ ⟦n⟧ (không gọi LLM)."""
    name = "assistant"

    def __init__(self, by_masked: dict[str, str]):
        self.by_masked = by_masked

    def complete(self, system: str, messages: list[dict]) -> str:
        data = json.loads(messages[0]["content"])
        return json.dumps({"items": [{"id": x["id"], "text": self.by_masked[x["text"]]} for x in data["items"]
                                     if x["text"] in self.by_masked]}, ensure_ascii=False)


def _count(xs) -> dict:
    out: dict[str, int] = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def export_review(rows: list[dict], dst: Path) -> None:
    """Bảng duyệt bản dịch (CSV UTF-8 có BOM, mở được bằng Excel): handle, loại, nguồn, bản dịch."""
    import csv

    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["handle", "type", "source", "target", "from"])
        for r in rows:
            w.writerow([r["handle"], r["type"], r["source"], r["target"], r["from"]])


def import_review(src: Path) -> dict[str, str]:
    import csv

    with open(src, encoding="utf-8-sig", newline="") as f:
        return {r["handle"]: r["target"] for r in csv.DictReader(f) if r.get("handle") and r.get("target")}


__all__ = ["MODES", "TARGETS", "layer_name", "TranslateError", "build", "detect_drawing_language", "detect_language", "export_review",
           "import_review", "load_glossary", "placeholders_ok", "protect", "restore", "translate_items"]
