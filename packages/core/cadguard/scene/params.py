"""P6 — THÔNG SỐ ĐỌC NÉT là dữ liệu của hồ sơ trình bày (`drafting.py`, khoá `params`), không phải hằng số trong code.

Mỗi công ty / người vẽ có thói quen riêng (tấm dày 18 hay 75 vẽ hai nét, chân tủ cao 100 hay 200, ký hiệu nhỏ…). Code
đọc nét lấy số qua `P(tên)`: giá trị của hồ sơ đang dùng (đặt bằng `scope`, khi dựng một hạng mục) hoặc mặc định.
Thêm một kiểu vẽ mới = sửa hồ sơ, không sửa code. Mỗi thông số có khoảng hợp lệ; ngoài khoảng thì không nhận.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

# tên: (mặc định, nhỏ nhất, lớn nhất, nhãn tiếng Việt)
PARAMS: dict[str, tuple[float, float, float, str]] = {
    "stack_gap": (62.0, 10.0, 200.0, "Khe tối đa giữa các nét song song của MỘT tấm (ván + đá, hai mặt tấm kính)"),
    "edge_zone": (150.0, 0.0, 500.0, "Vùng sát đáy/nóc khối không tính là đợt (chân, đáy, nóc, phào)"),
    "board_max": (60.0, 10.0, 200.0, "Dày tối đa của một tấm ván vẽ trên mặt đứng"),
    "piece_min": (150.0, 30.0, 500.0, "Mảnh nhỏ hơn mức này khi tách khối là tấm hông/nóc/chân"),
    "front_min": (150.0, 50.0, 600.0, "Cánh / ngăn kéo nhỏ nhất (cả hai chiều)"),
    "symbol_min": (150.0, 30.0, 600.0, "Ký hiệu mở cánh / ô nhỏ nhất (cả hai chiều)"),
    "callout_r": (50.0, 5.0, 500.0, "Bán kính nhỏ nhất của vòng chú thích"),
    "shelf_max": (40.0, 5.0, 200.0, "Dày tối đa của đợt vẽ bằng hình chữ nhật ở hình bỏ cánh"),
    "glass_max": (14.0, 4.0, 40.0, "Dày tối đa của đợt kính"),
    "note_dist": (400.0, 50.0, 2000.0, "Ghi chú (kính, đá) cách tấm tối đa để gán loại tấm"),
    "hang_min": (800.0, 300.0, 1500.0, "Khoang dưới thanh treo cao tối thiểu (nhận thanh treo khi không có chữ)"),
    "drawer_col_h": (450.0, 150.0, 900.0, "Mặt trước thấp hơn mức này, ≥ 3 cái cùng cột: ngăn kéo"),
}

_cur: ContextVar[dict] = ContextVar("cadguard_params", default={})


def P(name: str) -> float:
    v = _cur.get().get(name)
    return float(v) if v is not None else PARAMS[name][0]


def clean(values: dict | None) -> dict[str, float]:
    """Giữ thông số đã biết, là số, trong khoảng hợp lệ."""
    out = {}
    for k, v in (values or {}).items():
        if k in PARAMS and isinstance(v, (int, float)) and not isinstance(v, bool) and PARAMS[k][1] <= float(v) <= PARAMS[k][2]:
            out[k] = float(v)
    return out


@contextmanager
def scope(values: dict | None):
    """Dùng thông số `values` (của hồ sơ) trong khối lệnh; lồng nhau được."""
    tok = _cur.set({**_cur.get(), **clean(values)})
    try:
        yield
    finally:
        _cur.reset(tok)


def table(values: dict | None = None) -> list[dict]:
    vals = clean(values)
    return [{"name": k, "default": d, "min": lo, "max": hi, "label": lab, "value": vals.get(k, d), "custom": k in vals}
            for k, (d, lo, hi, lab) in PARAMS.items()]


__all__ = ["P", "PARAMS", "clean", "scope", "table"]
