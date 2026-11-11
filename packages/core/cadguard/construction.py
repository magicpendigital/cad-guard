"""Hồ sơ kết cấu xưởng `cg.construction/1` (P3): thông số để dựng tấm ván, danh sách cắt, bản lề.

Không có TCVN về kết cấu tủ (xem `docs/research/3d-san-xuat-noi-that.md`), nên mỗi xưởng tự khai. CAD Guard có **số
mặc định thường gặp** (có ghi nguồn/độ tin) để dùng ngay; người dùng sửa trên giao diện (màn "Kết cấu xưởng"), lưu ở:
- máy: `<thư mục cấu hình>/construction.yaml` (cả công ty dùng chung trên máy này);
- dự án: `<dự án>/.cadguard/construction.yaml` (ghi đè máy cho riêng dự án).
Thứ tự hiệu lực: dự án > máy > mặc định. Mọi lần lưu ghi nhật ký `construction-log.jsonl` bên cạnh. Bản vẽ không bị sửa.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "cg.construction/1"
FILE = "construction.yaml"

# key: (nhãn, kiểu, mặc định, đơn vị, lựa chọn/khoảng, giải thích, nguồn)
FIELDS: dict[str, dict[str, Any]] = {
    "board_thickness": {"label": "Độ dày ván thùng", "type": "number", "default": 17, "unit": "mm", "min": 6, "max": 50,
                        "help": "Hông, nóc, đáy, đợt, vách.", "source": "Ghi chú phổ biến trên bản vẽ thử: 'MDF 17MM'."},
    "joint": {"label": "Liên kết thùng", "type": "choice", "default": "side_over",
              "options": {"side_over": "Hông trùm nóc/đáy (hông cao bằng tủ)", "top_over": "Nóc/đáy trùm hông (nóc rộng bằng tủ)"},
              "help": "Quyết định kích thước cắt của hông và nóc/đáy.", "source": "Thực hành phổ biến; mỗi xưởng một kiểu."},
    "back_type": {"label": "Kiểu hậu", "type": "choice", "default": "screw",
                  "options": {"screw": "Hậu bắt vít sau thùng", "groove": "Hậu lọt rãnh"},
                  "help": "", "source": "Không có số chuẩn; phần mềm tủ đều để thành tham số."},
    "back_thickness": {"label": "Độ dày hậu", "type": "number", "default": 5, "unit": "mm", "min": 2, "max": 25,
                       "help": "HDF/MDF mỏng thường 3–5 mm; hậu ván dày 17–18 mm.", "source": "Thực hành phổ biến [chưa xác minh]."},
    "back_inset": {"label": "Lùi hậu (hậu rãnh)", "type": "number", "default": 10, "unit": "mm", "min": 0, "max": 60,
                   "help": "Khoảng từ mép sau hông tới mặt sau hậu khi hậu lọt rãnh.", "source": "Phổ biến 10–25 mm [chưa xác minh]."},
    "groove_depth": {"label": "Sâu rãnh hậu", "type": "number", "default": 8, "unit": "mm", "min": 0, "max": 20,
                     "help": "Hậu ăn vào rãnh mỗi bên.", "source": "[chưa xác minh]"},
    "door_overlay": {"label": "Kiểu cánh", "type": "choice", "default": "full",
                     "options": {"full": "Trùm toàn (cánh phủ hết hông)", "half": "Trùm nửa", "inset": "Cánh lọt lòng"},
                     "help": "Quyết định kích thước cánh và loại đế bản lề.", "source": "Hettich/Blum (theo mã bản lề)."},
    "door_thickness": {"label": "Độ dày cánh", "type": "number", "default": 17, "unit": "mm", "min": 4, "max": 50,
                       "help": "", "source": "Theo ván thùng."},
    "door_gap": {"label": "Khe cánh", "type": "number", "default": 3, "unit": "mm", "min": 0, "max": 10,
                 "help": "Khe giữa hai cánh / cánh và ngăn kéo.", "source": "Phổ biến 2–3 mm [nguồn phụ]."},
    "shelf_setback": {"label": "Đợt lùi so mặt trước", "type": "number", "default": 20, "unit": "mm", "min": 0, "max": 100,
                      "help": "", "source": "Thực hành phổ biến [chưa xác minh]."},
    "edge_band": {"label": "Dày dán cạnh", "type": "number", "default": 1.0, "unit": "mm", "min": 0, "max": 3,
                  "help": "Cạnh lộ ra ngoài được dán; cạnh áp tường/vào rãnh không dán.", "source": "Phổ biến 0,4–2 mm."},
    "board_density": {"label": "Khối lượng riêng ván", "type": "number", "default": 720, "unit": "kg/m³", "min": 300, "max": 1200,
                      "help": "Để tính khối lượng cánh → số bản lề.", "source": "MDF/MFC ~650–750 [kiến thức nghề, cần xác nhận theo nhà cung cấp]."},
    "partition_auto": {"label": "Tự thêm vách ngăn", "type": "choice", "default": "auto",
                       "options": {"auto": "Tự thêm khi cần (bản lề, ngăn kéo, nhịp đợt)", "off": "Không tự thêm (chỉ theo bản vẽ)"},
                       "help": "Cánh bản lề và ray ngăn kéo phải bắt vào hồi hoặc vách; đợt dài cần vách đỡ.",
                       "source": "Nguyên tắc tủ không khung (hệ 32 mm): bản lề/ray bắt vào tấm đứng."},
    "shelf_max_span": {"label": "Nhịp đợt tối đa", "type": "number", "default": 700, "unit": "mm", "min": 300, "max": 1200,
                       "help": "Khoang có đợt rộng hơn: thêm vách hoặc đợt dày hơn.",
                       "source": "Ván 17–18 mm: khuyến nghị chung 600–700 mm (Woodweb, bảng võng Sagulator); kiểm theo bảng CPA/ANSI A208.1 hoặc thử tải của xưởng."},
    "door_max_width": {"label": "Cánh rộng tối đa", "type": "number", "default": 600, "unit": "mm", "min": 300, "max": 1200,
                       "help": "Rộng hơn: cảnh báo chia 2 cánh hoặc thêm bản lề.", "source": "Blum: bảng số bản lề áp cho cánh rộng tới 600 mm; cánh nên cao hơn rộng."},
    "base_top": {"label": "Nóc tủ dưới (có mặt đá)", "type": "choice", "default": "rails",
                 "options": {"rails": "2 thanh giằng trước/sau", "full": "Nóc liền"},
                 "help": "Tủ bếp dưới đỡ mặt đá thường dùng thanh giằng thay nóc liền.", "source": "Thực hành phổ biến tủ bếp; mỗi xưởng một kiểu."},
    "rail_width": {"label": "Bề rộng thanh giằng", "type": "number", "default": 100, "unit": "mm", "min": 40, "max": 300,
                   "help": "", "source": "Phổ biến 80–100 mm [chưa xác minh]."},
    "hinge_brand": {"label": "Hãng bản lề", "type": "text", "default": "Blum CLIP top", "help": "", "source": ""},
    "hinge_2_max_kg": {"label": "2 bản lề tới (kg)", "type": "number", "default": 6, "unit": "kg", "min": 1, "max": 30,
                       "help": "", "source": "Blum: 4–6 kg dùng 2 bản lề."},
    "hinge_3_max_kg": {"label": "3 bản lề tới (kg)", "type": "number", "default": 12, "unit": "kg", "min": 1, "max": 40,
                       "help": "Nặng hơn: 4 bản lề.", "source": "Blum: 6–12 kg dùng 3 bản lề."},
    "hinge_wide_door": {"label": "Cánh rộng hơn (thêm 1 bản lề)", "type": "number", "default": 600, "unit": "mm", "min": 300, "max": 1200,
                        "help": "", "source": "Blum: bảng áp cho cánh rộng tới 600 mm."},
}


def defaults() -> dict:
    return {k: f["default"] for k, f in FIELDS.items()}


def _clean(values: dict) -> tuple[dict, list[str]]:
    out, errs = {}, []
    for k, v in (values or {}).items():
        f = FIELDS.get(k)
        if f is None:
            continue
        if f["type"] == "number":
            try:
                x = float(str(v).replace(",", "."))
            except ValueError:
                errs.append(f"{f['label']}: phải là số.")
                continue
            if not f["min"] <= x <= f["max"]:
                errs.append(f"{f['label']}: ngoài khoảng {f['min']}–{f['max']} {f['unit']}.")
                continue
            out[k] = int(x) if x == int(x) else x
        elif f["type"] == "choice":
            if v not in f["options"]:
                errs.append(f"{f['label']}: lựa chọn không hợp lệ.")
                continue
            out[k] = v
        else:
            out[k] = str(v)[:80]
    return out, errs


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    vals, _ = _clean(data.get("values") or {}) if isinstance(data, dict) else ({}, [])
    return vals


def paths(project_root: Path | None) -> dict[str, Path]:
    from .app.settings import config_dir

    out = {"machine": config_dir() / FILE}
    if project_root is not None:
        out["project"] = Path(project_root) / ".cadguard" / FILE
    return out


def effective(project_root: Path | None = None) -> dict:
    """{values, origin{key: default|machine|project}, confirmed: đã có ai lưu hồ sơ chưa}."""
    p = paths(project_root)
    vals, origin = defaults(), {k: "default" for k in FIELDS}
    for scope in ("machine", "project"):
        if scope in p:
            for k, v in _read(p[scope]).items():
                vals[k], origin[k] = v, scope
    confirmed = any(scope in p and p[scope].is_file() for scope in ("machine", "project"))
    return {"schema": SCHEMA, "values": vals, "origin": origin, "confirmed": confirmed}


def save(project_root: Path | None, scope: str, values: dict) -> dict:
    if scope not in ("machine", "project") or (scope == "project" and project_root is None):
        raise ValueError("Phạm vi lưu phải là 'machine' (cả máy) hoặc 'project' (dự án đang mở).")
    clean, errs = _clean(values)
    if errs:
        raise ValueError(" ".join(errs))
    path = paths(project_root)[scope]
    path.parent.mkdir(parents=True, exist_ok=True)
    old = _read(path)
    path.write_text(yaml.safe_dump({"schema": SCHEMA, "values": clean}, allow_unicode=True, sort_keys=True), encoding="utf-8")
    with (path.parent / "construction-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "scope": scope,
                             "changed": {k: [old.get(k), v] for k, v in clean.items() if old.get(k) != v}},
                            ensure_ascii=False) + "\n")
    return effective(project_root)


def reset(project_root: Path | None, scope: str) -> dict:
    p = paths(project_root).get(scope)
    if p is not None and p.is_file():
        p.unlink()
    return effective(project_root)


def describe() -> list[dict]:
    """Định nghĩa các ô cho giao diện."""
    return [{"key": k, **{x: y for x, y in f.items()}} for k, f in FIELDS.items()]


__all__ = ["FIELDS", "SCHEMA", "defaults", "describe", "effective", "reset", "save"]
