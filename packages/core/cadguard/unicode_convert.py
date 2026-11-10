"""Chuyển chữ tiếng Việt mã cũ (TCVN3/ABC, VNI) sang Unicode NGAY TRONG bản vẽ (thao tác changeset `convert_unicode`).

Chỉ chạy khi người dùng bấm (nút trong app, `cadguard unicode`, `CGUNICODE`); không tự chạy khi quét/mở/dịch.
Thứ tự nhận diện bảng mã cho từng chuỗi (kế hoạch sheets-presentation mục 3.1):

1. phông của kiểu chữ (`.Vn*`, `VN*H` chữ hoa → TCVN3; `VNI-*` → VNI);
2. mã phông nội tuyến `\\f` / `\\F` trong MTEXT (theo từng đoạn, có ngoặc `{}` lồng);
3. dấu hiệu ký tự, CHỈ khi cả bản vẽ đã được nhận là TCVN3 (`textcodec.drawing_looks_tcvn3`).

Chuỗi không chắc bảng mã thì KHÔNG đổi, liệt kê trong báo cáo để người dùng chọn tay. Kiểu chữ dùng phông cũ được
trỏ sang phông Unicode của công ty (mặc định Be Vietnam Pro, quyết định 10/11/2026), giữ chiều cao, hệ số rộng, căn lề.
Chạy lần hai không đổi thêm: sau lần một kiểu chữ không còn phông cũ và bản vẽ có chữ Unicode thật.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textcodec import _VI_REAL, _decode_tcvn3, _decode_vni, drawing_looks_tcvn3, font_encoding, looks_tcvn3

DEFAULT_FONT_FILE = "BeVietnamPro-Regular.ttf"
DEFAULT_FONT_FAMILY = "Be Vietnam Pro"
TEXT_TYPES = ("TEXT", "MTEXT", "ATTRIB", "ATTDEF", "MULTILEADER")
MAX_LISTED = 200

# mã định dạng MTEXT: có tham số kết thúc bằng ';' / không tham số / ký tự thoát / ngoặc nhóm
_MTEXT_CODE = re.compile(r"\\[ACcFfHQTWpS][^;]*;|\\[LlOoKkPNX~]|\\\\|\\\{|\\\}|[{}]")


def decode_with(text: str, enc: str | None) -> str:
    if not text or enc is None:
        return text
    if _VI_REAL.search(text) and any(ord(c) > 0xFF for c in text):
        return text  # đã là Unicode tiếng Việt thật: không giải mã lại (chạy hai lần không đổi thêm)
    if enc == "vni":
        return _decode_vni(text)
    if enc in ("tcvn3", "tcvn3-upper"):
        return _decode_tcvn3(text, upper=enc == "tcvn3-upper")
    return text


def convert_mtext(raw: str, base_enc: str | None, guess: bool, family: str) -> tuple[str, bool]:
    """Giải mã nội dung MTEXT theo từng đoạn; đổi tên phông cũ trong `\\f`/`\\F` sang `family`. Trả (mới, có đổi)."""
    out: list[str] = []
    stack: list[str | None] = []
    enc = base_enc
    pos = 0
    changed = False

    def lit(s: str) -> str:
        nonlocal changed
        e = enc if enc is not None else ("tcvn3" if guess and looks_tcvn3(s, min_hits=1) else None)
        new = decode_with(s, e)
        if new != s:
            changed = True
        return new

    for m in _MTEXT_CODE.finditer(raw):
        if m.start() > pos:
            out.append(lit(raw[pos:m.start()]))
        code = m.group(0)
        if code == "{":
            stack.append(enc)
        elif code == "}":
            enc = stack.pop() if stack else base_enc
        elif code[:2] in ("\\f", "\\F"):
            body = code[2:-1]
            name, _, rest = body.partition("|")
            fenc = font_encoding(name)
            enc = fenc
            if fenc is not None:
                new_name = family if code[1] == "f" else family
                code = code[:2] + new_name + ("|" + rest if rest else "") + ";"
                changed = True
        out.append(code)
        pos = m.end()
    if pos < len(raw):
        out.append(lit(raw[pos:]))
    return "".join(out), changed


@dataclass
class ConvertReport:
    converted: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)  # font | inline | guess
    styles: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    skipped_protected: int = 0

    def add(self, t: str, src: str) -> None:
        self.converted += 1
        self.by_type[t] = self.by_type.get(t, 0) + 1
        self.by_source[src] = self.by_source.get(src, 0) + 1

    def to_dict(self) -> dict:
        return {"affected": self.converted, "skipped_protected": self.skipped_protected,
                "details": {"by_type": self.by_type, "by_source": self.by_source, "styles_repointed": self.styles,
                            "uncertain_count": len(self.uncertain), "uncertain_handles": self.uncertain[:MAX_LISTED]}}


def _style_encodings(doc) -> dict[str, str]:
    out = {}
    for st in doc.styles:
        if int(st.dxf.get("flags", 0)) & 1:
            continue
        try:
            family = str(st.get_extended_font_data()[0] or "")
        except Exception:  # noqa: BLE001
            family = ""
        enc = (font_encoding(str(st.dxf.get("font", "") or "")) or font_encoding(family)
               or font_encoding(str(st.dxf.name)))
        if enc:
            out[str(st.dxf.name).casefold()] = enc
    return out


def raw_text(e) -> str:
    t = e.dxftype()
    if t == "MTEXT":
        return e.text
    if t == "MULTILEADER":
        m = e.context.mtext
        return (m.default_content or "") if m is not None else ""
    return str(e.dxf.get("text", "") or "")


def mleader_style(doc, e) -> str:
    m = e.context.mtext
    st = doc.entitydb.get(m.style_handle) if m is not None and m.style_handle else None
    return str(st.dxf.name) if st is not None else "Standard"


def iter_text_entities(doc, include_blocks: bool = True):
    """Mọi chữ trong không gian mô hình/giấy (kèm ATTRIB của INSERT) và, nếu `include_blocks`, trong định nghĩa khối."""
    seen = set()
    for br in doc.block_records:
        name = str(br.dxf.name)
        if name.upper().startswith("*D"):
            continue
        is_layout = br.is_any_layout
        if not is_layout and not include_blocks:
            continue
        block = doc.blocks.get(name)
        if block is None:
            continue
        for e in block:
            items = [e] + (list(e.attribs) if e.dxftype() == "INSERT" else [])
            for x in items:
                if x.dxftype() in TEXT_TYPES and id(x) not in seen and not (
                        x.dxftype() == "MULTILEADER" and x.context.mtext is None):
                    seen.add(id(x))
                    yield x


def convert_doc(doc, *, font_file: str = DEFAULT_FONT_FILE, family: str = DEFAULT_FONT_FAMILY,
                handles: set[str] | None = None, include_blocks: bool = True, is_protected=None) -> ConvertReport:
    """Chuyển chữ trong `doc` (bản sao trong bộ nhớ). `handles`: chỉ những đối tượng này (và ATTRIB của chúng)."""
    rep = ConvertReport()
    enc_of = _style_encodings(doc)
    texts = []
    for e in iter_text_entities(doc, include_blocks):
        texts.append(raw_text(e))
    guess = drawing_looks_tcvn3(texts[:5000])
    used_styles: set[str] = set()
    uni_style: dict[str, str] = {}

    def unicode_style(name: str) -> str:
        """Chuyển một phần (lọc theo tờ): kiểu chữ riêng `<tên>-UNICODE` trỏ phông Unicode, kiểu cũ giữ nguyên."""
        key = name.casefold()
        if key not in uni_style:
            new = f"{name}-UNICODE"
            if not doc.styles.has_entry(new):
                old = doc.styles.get(name)
                st = doc.styles.new(new, dxfattribs={"font": font_file, "height": old.dxf.get("height", 0.0),
                                                      "width": old.dxf.get("width", 1.0),
                                                      "oblique": old.dxf.get("oblique", 0.0)})
                try:
                    st.set_extended_font_data(family=family, italic=False, bold=False)
                except Exception:  # noqa: BLE001
                    pass
                rep.styles.append(new)
            uni_style[key] = new
        return uni_style[key]
    for e in iter_text_entities(doc, include_blocks):
        t = e.dxftype()
        if handles is not None:
            h = str(e.dxf.get("handle", ""))
            owner = str(e.dxf.get("owner", ""))
            if h not in handles and not (t == "ATTRIB" and owner in handles):
                continue
        layer = str(e.dxf.get("layer", "0"))
        if is_protected is not None and is_protected(layer):
            rep.skipped_protected += 1
            continue
        style = mleader_style(doc, e) if t == "MULTILEADER" else str(e.dxf.get("style", "Standard") or "Standard")
        enc = enc_of.get(style.casefold())
        if t in ("MTEXT", "MULTILEADER"):
            raw = raw_text(e)
            new, changed = convert_mtext(raw, enc, guess, family)
            if changed and new != raw:
                if t == "MTEXT":
                    e.text = new
                else:
                    e.context.mtext.default_content = new
                if enc is not None and handles is not None and t == "MTEXT":
                    e.dxf.style = unicode_style(style)
                rep.add(t, "font" if enc else ("inline" if "\\f" in raw.lower() else "guess"))
            elif enc is None and not guess and looks_tcvn3(raw, min_hits=1):
                rep.uncertain.append(str(e.dxf.get("handle", "")))
        else:
            raw = str(e.dxf.get("text", "") or "")
            if enc is not None:
                new = decode_with(raw, enc)
                src = "font"
            elif guess and looks_tcvn3(raw, min_hits=1):
                new, src = decode_with(raw, "tcvn3"), "guess"
            else:
                new, src = raw, ""
                if looks_tcvn3(raw, min_hits=1):
                    rep.uncertain.append(str(e.dxf.get("handle", "")))
            if new != raw:
                e.dxf.text = new
                rep.add(t, src)
                if enc is not None and handles is not None:
                    e.dxf.style = unicode_style(style)
        if enc is not None:
            used_styles.add(style.casefold())
    # trỏ kiểu chữ phông cũ sang phông Unicode: chỉ khi đã xét mọi chữ (không lọc theo handle) để không làm hỏng chữ
    # chưa chuyển còn dùng kiểu đó
    if handles is None:
        for st in doc.styles:
            name = str(st.dxf.name)
            if name.casefold() in enc_of:
                st.dxf.font = font_file
                if st.dxf.hasattr("bigfont"):
                    st.dxf.discard("bigfont")
                try:
                    st.set_extended_font_data(family=family, italic=False, bold=False)
                except Exception:  # noqa: BLE001 - phiên bản DXF cũ không có XDATA phông: bỏ qua
                    pass
                rep.styles.append(name)
    return rep


__all__ = ["DEFAULT_FONT_FAMILY", "DEFAULT_FONT_FILE", "ConvertReport", "convert_doc", "convert_mtext", "decode_with",
           "iter_text_entities"]
