"""Giải mã chữ tiếng Việt mã cũ (TCVN3/ABC, VNI) để HIỂN THỊ và LẬP CHỈ MỤC. Không sửa bản vẽ.

Bản vẽ cũ gõ bằng phông `.VnTime`, `VNI-Times`… lưu chữ dưới dạng ký tự Latin-1 (vd. "néi thÊt tÇng 7" là
"nội thất tầng 7" mã TCVN3). Chữ chỉ đọc đúng trên máy có phông đó; cad-guard, trợ lý AI và ô tìm kiếm đọc sai.

Chỉ giải mã khi biết chắc mã (kiểu chữ dùng phông TCVN3/VNI), hoặc khi nội dung rất giống TCVN3 (`guess=True`:
nhiều ký tự đặc trưng, không có chữ Unicode tiếng Việt thật). Kết quả kèm nguồn ("font" | "guess") để giao diện ghi rõ.
Luật VS-07 (design-hygiene) vẫn đọc chữ GỐC: giải mã không làm mất cảnh báo phông cũ.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath

# ---------- TCVN3 (TCVN 5712:1993, bảng VN3 dùng cho .VnTime) ----------
_TCVN3 = {
    0xA1: "Ă", 0xA2: "Â", 0xA3: "Ê", 0xA4: "Ô", 0xA5: "Ơ", 0xA6: "Ư", 0xA7: "Đ",
    0xA8: "ă", 0xA9: "â", 0xAA: "ê", 0xAB: "ô", 0xAC: "ơ", 0xAD: "ư", 0xAE: "đ",
    0xB5: "à", 0xB6: "ả", 0xB7: "ã", 0xB8: "á", 0xB9: "ạ",
    0xBB: "ằ", 0xBC: "ẳ", 0xBD: "ẵ", 0xBE: "ắ", 0xC6: "ặ",
    0xC7: "ầ", 0xC8: "ẩ", 0xC9: "ẫ", 0xCA: "ấ", 0xCB: "ậ",
    0xCC: "è", 0xCE: "ẻ", 0xCF: "ẽ", 0xD0: "é", 0xD1: "ẹ",
    0xD2: "ề", 0xD3: "ể", 0xD4: "ễ", 0xD5: "ế", 0xD6: "ệ",
    0xD7: "ì", 0xD8: "ỉ", 0xDC: "ĩ", 0xDD: "í", 0xDE: "ị",
    0xDF: "ò", 0xE1: "ỏ", 0xE2: "õ", 0xE3: "ó", 0xE4: "ọ",
    0xE5: "ồ", 0xE6: "ổ", 0xE7: "ỗ", 0xE8: "ố", 0xE9: "ộ",
    0xEA: "ờ", 0xEB: "ở", 0xEC: "ỡ", 0xED: "ớ", 0xEE: "ợ",
    0xEF: "ù", 0xF1: "ủ", 0xF2: "ũ", 0xF3: "ú", 0xF4: "ụ",
    0xF5: "ừ", 0xF6: "ử", 0xF7: "ữ", 0xF8: "ứ", 0xF9: "ự",
    0xFA: "ỳ", 0xFB: "ỷ", 0xFC: "ỹ", 0xFD: "ý", 0xFE: "ỵ",
}
_TCVN3_TABLE = {k: v for k, v in _TCVN3.items()}

# ---------- VNI (VNI-Times…): chữ gốc + ký tự dấu đứng sau ----------
_GRAVE, _ACUTE, _TILDE, _HOOK, _DOT = "̀", "́", "̃", "̉", "̣"
_CIRC, _BREVE, _HORN = "̂", "̆", "̛"
# dấu thanh sau nguyên âm thường (a e o u y, ơ, ư)
_VNI_TONE = {"ø": _GRAVE, "ù": _ACUTE, "õ": _TILDE, "û": _HOOK, "ï": _DOT,
             "Ø": _GRAVE, "Ù": _ACUTE, "Õ": _TILDE, "Û": _HOOK, "Ï": _DOT}
# mũ (â ê ô) kèm/không kèm thanh
_VNI_CIRC = {"â": "", "à": _GRAVE, "á": _ACUTE, "ã": _TILDE, "å": _HOOK, "ä": _DOT,
             "Â": "", "À": _GRAVE, "Á": _ACUTE, "Ã": _TILDE, "Å": _HOOK, "Ä": _DOT}
# trăng (ă) kèm/không kèm thanh
_VNI_BREVE = {"ê": "", "è": _GRAVE, "é": _ACUTE, "ü": _TILDE, "ú": _HOOK, "ë": _DOT,
              "Ê": "", "È": _GRAVE, "É": _ACUTE, "Ü": _TILDE, "Ú": _HOOK, "Ë": _DOT}
# ký tự đứng một mình
_VNI_SINGLE = {"ô": "ơ", "ö": "ư", "ñ": "đ", "Ô": "Ơ", "Ö": "Ư", "Ñ": "Đ",
               "í": "í", "ì": "ì", "æ": "ỉ", "ó": "ĩ", "ò": "ị", "Í": "Í", "Ì": "Ì", "Æ": "Ỉ", "Ó": "Ĩ", "Ò": "Ị"}
_VOWELS = set("aeouyAEOUY")


def _decode_vni(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if ch in _VOWELS:
            if ch in "aAeEoO" and nxt in _VNI_CIRC:
                out.append(unicodedata.normalize("NFC", ch + _CIRC + _VNI_CIRC[nxt]))
                i += 2
                continue
            if ch in "aA" and nxt in _VNI_BREVE:
                out.append(unicodedata.normalize("NFC", ch + _BREVE + _VNI_BREVE[nxt]))
                i += 2
                continue
            if nxt in _VNI_TONE:
                out.append(unicodedata.normalize("NFC", ch + _VNI_TONE[nxt]))
                i += 2
                continue
            out.append(ch)
            i += 1
            continue
        if ch in _VNI_SINGLE:
            base = _VNI_SINGLE[ch]
            if base in "ơưƠƯ" and nxt in _VNI_TONE:
                out.append(unicodedata.normalize("NFC", base + _VNI_TONE[nxt]))
                i += 2
                continue
            out.append(base)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _decode_tcvn3(s: str, upper: bool = False) -> str:
    out = "".join(_TCVN3_TABLE.get(ord(c), c) for c in s)
    return out.upper() if upper else out


# ---------- nhận diện mã theo phông ----------
_VNI_FONT = re.compile(r"^vni[-_ ]", re.IGNORECASE)
_TCVN3_FONT = re.compile(r"^\.?vn(?!i[-_ ])[a-z]", re.IGNORECASE)


def font_encoding(font: str) -> str | None:
    """'vni' | 'tcvn3' | 'tcvn3-upper' | None theo tên tệp phông của kiểu chữ (vd. '.VnTime', 'VNTIMEH.TTF', 'VNI-Times')."""
    if not font:
        return None
    stem = PurePath(font.replace("\\", "/")).name
    if stem.lower().endswith((".ttf", ".shx", ".otf", ".ttc")):
        stem = stem[: stem.rfind(".")]
    if _VNI_FONT.match(stem):
        return "vni"
    if _TCVN3_FONT.match(stem):
        return "tcvn3-upper" if stem.endswith(("H", "h")) and len(stem) > 4 else "tcvn3"
    return None


def _hits(s: str) -> int:
    return sum(1 for c in s if ord(c) >= 0xB5 and ord(c) in _TCVN3_TABLE)


def looks_tcvn3(s: str, min_hits: int = 2) -> bool:
    """Đoán chữ mã TCVN3: ≥ `min_hits` ký tự đặc trưng, mọi ký tự trong Latin-1 (chữ Unicode tiếng Việt thật có ký
    tự ngoài Latin-1 như ă đ ơ ư ạ…), ký tự đặc trưng chiếm phần đáng kể trong chữ cái."""
    if not s or any(ord(c) > 0xFF for c in s):
        return False
    hits = _hits(s)
    letters = sum(1 for c in s if c.isalpha())
    return hits >= min_hits and hits * 6 >= letters


def drawing_looks_tcvn3(texts) -> bool:
    """Cả bản vẽ có vẻ gõ TCVN3: ít nhất 3 chữ đoán chắc (≥ 2 ký tự đặc trưng) và không có chữ Unicode tiếng Việt."""
    sure = 0
    for t in texts:
        if t and any(ord(c) > 0xFF for c in t) and _VI_REAL.search(t):
            return False
        if looks_tcvn3(t or ""):
            sure += 1
    return sure >= 3


_VI_REAL = re.compile(r"[ăđơưĂĐƠƯẠ-ỹ]")


def decode(text: str, encoding: str | None, guess: bool | str = False) -> tuple[str, str | None]:
    """Trả (chữ đã giải mã, nguồn) với nguồn 'font' | 'guess' | None (giữ nguyên).

    `guess`: False = chỉ theo phông; True = đoán từng chữ (≥ 2 ký tự đặc trưng); "drawing" = cả bản vẽ đã được nhận
    là TCVN3 (`drawing_looks_tcvn3`), chữ có 1 ký tự đặc trưng cũng giải mã."""
    if not text:
        return text, None
    if encoding == "vni":
        out = _decode_vni(text)
        return (out, "font") if out != text else (text, None)
    if encoding in ("tcvn3", "tcvn3-upper"):
        out = _decode_tcvn3(text, upper=encoding == "tcvn3-upper")
        return (out, "font") if out != text else (text, None)
    if guess and looks_tcvn3(text, min_hits=1 if guess == "drawing" else 2):
        return _decode_tcvn3(text), "guess"
    return text, None


def style_encodings(model) -> dict[str, str]:
    """{tên kiểu chữ (chữ thường): mã} cho các kiểu dùng phông TCVN3/VNI trong mô hình."""
    out: dict[str, str] = {}
    for st in getattr(model, "styles", []) or []:
        enc = font_encoding(st.font) or font_encoding(getattr(st, "family", "") or "") or font_encoding(st.name)
        if enc:
            out[st.name.lower()] = enc
    return out


def entity_text(entity, encodings: dict[str, str], guess: bool | str = True) -> tuple[str, str | None]:
    """Chữ hiển thị của một TEXT/MTEXT trong mô hình, đã giải mã nếu cần."""
    raw = entity.text or ""
    enc = encodings.get((entity.text_style or "").lower())
    return decode(raw, enc, guess=guess)


__all__ = ["decode", "drawing_looks_tcvn3", "entity_text", "font_encoding", "looks_tcvn3", "style_encodings"]
