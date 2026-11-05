"""Xem trước bản vẽ chính xác bằng bộ vẽ của ezdxf (`ezdxf.addons.drawing`, giấy phép MIT, có sẵn trong ezdxf).

- Dựng SVG không gian mô hình: khối bung đúng, chữ đúng cỡ/góc/căn lề (vẽ thành đường bao glyph theo phông có sẵn trên
  máy, thiếu phông thì phông thay thế của ezdxf), MTEXT nhiều dòng, kích thước, hatch, cung, ellipse, spline, polyline.
- Màu: mọi nét dùng `currentColor` (giao diện đặt màu theo theme sáng/tối, như in đơn sắc); hatch nhạt hơn để không
  che chữ. Nền trong suốt (nền của khung xem trong app).
- Chạy một lần cho mỗi NỘI DUNG tệp (băm SHA-256), cache ở `<dự án>/.cadguard/cache/preview-<băm>.svg` + `.json`.
  Tệp quá lớn / dựng quá lâu / lỗi → trả `fallback` để giao diện dùng hình đơn giản hoá (`geometry.py`).
- Định vị phát hiện: khung bao theo handle (`ezdxf.bbox`) đổi sang toạ độ SVG bằng ĐÚNG ma trận bộ vẽ dùng.
- SVG gửi ra trình duyệt luôn qua `sanitize_svg` (danh sách trắng phần tử/thuộc tính, không script, không URL ngoài).
"""
from __future__ import annotations

import hashlib
import math
import os
import subprocess
import sys
import io
import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

PREVIEW_VERSION = 2  # đổi khi đổi cách dựng: cache cũ tự bỏ
PREVIEW_MAX_MB = 20.0  # tệp lớn hơn: dùng hình đơn giản hoá
PREVIEW_MAX_SECONDS = 60.0  # dựng quá lâu: dừng, dùng hình đơn giản hoá
MAX_BOXES = 60000  # trần số khung bao theo handle gửi về trình duyệt
MAX_PATH_CHARS = 200_000  # gộp nét liên tiếp cùng kiểu thành một <path> tối đa ngần này ký tự
MAX_CACHE_FILES = 60  # số bản xem trước giữ lại trong cache (cũ nhất bị xoá trước)
OUTPUT_SPACE = 1_000_000  # toạ độ SVG nguyên trong [0, OUTPUT_SPACE] (độ phân giải 1e-6 cạnh lớn)
CACHE_DIR = Path(".cadguard") / "cache"
SVG_NS = "http://www.w3.org/2000/svg"

INK = "#000000"  # màu đánh dấu nét thường (đổi thành currentColor)
HATCH_INK = "#808080"  # màu đánh dấu hatch (đổi thành currentColor + độ mờ)
FAINT_TYPES = frozenset({"HATCH", "MPOLYGON"})
HIDDEN_TYPES = frozenset({"WIPEOUT", "IMAGE", "OLE2FRAME", "POINT"})  # nền che/ảnh/điểm: không vẽ trong xem trước

# ---------- bộ lọc SVG (danh sách trắng) ----------
_D_RE = re.compile(r"^[MLQCZmlqcz0-9 .\-]*$")
_NUM_RE = re.compile(r"^-?\d{1,9}(\.\d{1,6})?$")
_PAINT_RE = re.compile(r"^(none|currentColor)$")
_OPACITY_RE = re.compile(r"^(0(\.\d{1,3})?|1(\.0{1,3})?)$")
_CLASS_RE = re.compile(r"^(dxf-s|dxf-f|dxf-hs|dxf-hf)$")
_ALLOWED: dict[str, dict[str, re.Pattern]] = {
    "svg": {"viewBox": re.compile(r"^0 0 \d{1,9} \d{1,9}$")},
    "g": {"class": re.compile(r"^dxf-g$"), "fill-rule": re.compile(r"^evenodd$"),
          "stroke-linecap": re.compile(r"^round$"), "stroke-linejoin": re.compile(r"^round$")},
    "path": {"d": _D_RE, "class": _CLASS_RE, "stroke": _PAINT_RE, "fill": _PAINT_RE,
             "stroke-opacity": _OPACITY_RE, "fill-opacity": _OPACITY_RE},
}
MAX_SVG_BYTES = 10 * 1024 * 1024
_PROCESS_LOCK = threading.Lock()


class PreviewError(Exception):
    """Lỗi khi dựng xem trước (thông điệp tiếng Việt, không đường dẫn)."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sanitize_svg(text: str) -> str:
    """Giữ lại đúng các phần tử `svg/g/path` và thuộc tính trong danh sách trắng với giá trị khớp mẫu.

    Mọi thứ khác (script, foreignObject, style, image, use, href, on*, url(...), thực thể XML) bị bỏ. Trả về chuỗi SVG
    mới dựng lại từ đầu (không giữ nguyên văn đầu vào).
    """
    if len(text) > MAX_SVG_BYTES:
        raise PreviewError("Hình xem trước quá lớn.")
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise PreviewError("Hình xem trước không hợp lệ.")
    try:
        src = ET.fromstring(text)
    except ET.ParseError:
        raise PreviewError("Hình xem trước không đọc được.") from None
    if _local(src.tag) != "svg":
        raise PreviewError("Hình xem trước không hợp lệ.")

    def copy(node: ET.Element, depth: int) -> ET.Element | None:
        name = _local(node.tag)
        rules = _ALLOWED.get(name)
        if rules is None or depth > 4:
            return None
        out = ET.Element(name)
        for k, v in node.attrib.items():
            pat = rules.get(_local(k))
            if pat is not None and pat.fullmatch(v):
                out.set(_local(k), v)
        if name != "path":
            for ch in node:
                c = copy(ch, depth + 1)
                if c is not None:
                    out.append(c)
        return out

    root = copy(src, 0)
    assert root is not None
    root.set("xmlns", SVG_NS)
    return ET.tostring(root, encoding="unicode")


# ---------- dựng ----------

def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Deadline(Exception):
    pass


def _style_key(attrs: dict[str, str]) -> tuple[str, str]:
    """Phân loại một <path> của ezdxf theo màu đánh dấu: nét/vùng tô thường hay của hatch."""
    stroke = attrs.get("stroke", "none")
    fill = attrs.get("fill", "none")
    if fill != "none":
        return ("dxf-hf" if fill.lower() == HATCH_INK else "dxf-f"), "fill"
    return ("dxf-hs" if stroke.lower() == HATCH_INK else "dxf-s"), "stroke"


def _rebuild(svg_root: ET.Element) -> tuple[ET.Element, tuple[int, int], int]:
    """Dựng lại SVG gọn: bỏ nền/kích thước mm/<style>, đổi lớp Cn của ezdxf sang thuộc tính trình bày cho phép,
    gộp các <path> liên tiếp cùng kiểu (giảm số nút DOM)."""
    styles: dict[str, dict[str, str]] = {}
    for st in svg_root.iter():
        if _local(st.tag) != "style" or not st.text:
            continue
        m = re.match(r"\s*\.(\w+)\s*\{(.*)\}\s*$", st.text, re.S)
        if not m:
            continue
        props = {}
        for part in m.group(2).split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                props[k.strip()] = v.strip()
        styles[m.group(1)] = props
    vb = (svg_root.get("viewBox") or "0 0 1 1").split()
    w, h = int(float(vb[2])), int(float(vb[3]))
    out = ET.Element("svg", {"xmlns": SVG_NS, "viewBox": f"0 0 {w} {h}"})
    g = ET.SubElement(out, "g", {"class": "dxf-g", "fill-rule": "evenodd", "stroke-linecap": "round",
                                 "stroke-linejoin": "round"})
    cur_cls, cur_parts, cur_len, n = None, [], 0, 0

    def flush() -> None:
        nonlocal cur_parts, cur_len, n
        if cur_cls and cur_parts:
            attrs = {"class": cur_cls, "d": " ".join(cur_parts)}
            if cur_cls in ("dxf-s", "dxf-hs"):
                attrs.update(stroke="currentColor", fill="none")
            else:
                attrs.update(stroke="none", fill="currentColor")
            if cur_cls == "dxf-hs":
                attrs["stroke-opacity"] = "0.45"
            if cur_cls == "dxf-hf":
                attrs["fill-opacity"] = "0.16"
            ET.SubElement(g, "path", attrs)
            n += 1
        cur_parts, cur_len = [], 0

    for el in svg_root.iter():
        if _local(el.tag) != "path":
            continue
        d = el.get("d") or ""
        if not d or not _D_RE.fullmatch(d):
            continue
        cls, _ = _style_key(styles.get(el.get("class") or "", {}))
        # vùng tô hatch không gộp (gộp với evenodd làm thủng chỗ chồng nhau)
        if cls != cur_cls or cur_len + len(d) > MAX_PATH_CHARS or cls == "dxf-hf":
            flush()
            cur_cls = cls
        cur_parts.append(d)
        cur_len += len(d) + 1
    flush()
    return out, (w, h), n


def render_preview(data: bytes, max_seconds: float = PREVIEW_MAX_SECONDS, layout_name: str = "Model") -> tuple[str, dict]:
    """Dựng SVG không gian mô hình từ nội dung DXF. Trả (svg đã lọc, meta). Ném PreviewError nếu không dựng được."""
    import ezdxf
    from ezdxf import bbox as ezbbox
    from ezdxf import recover

    from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
    from ezdxf.addons.drawing.config import (BackgroundPolicy, ColorPolicy, Configuration, HatchPolicy,
                                             LineweightPolicy, ProxyGraphicPolicy)

    t0 = time.monotonic()
    deadline = t0 + max_seconds
    try:
        doc, _auditor = recover.read(io.BytesIO(data))
    except (ezdxf.DXFStructureError, ValueError, UnicodeError, EOFError) as exc:
        raise PreviewError("Không đọc được tệp DXF để dựng hình.") from exc
    if layout_name not in doc.layout_names():
        raise PreviewError("Layout không tồn tại trong bản vẽ.")
    msp = doc.layouts.get(layout_name)
    ctx = RenderContext(doc)
    ctx.set_current_layout(msp)
    backend = svg.SVGBackend()
    cfg = Configuration(background_policy=BackgroundPolicy.OFF, color_policy=ColorPolicy.COLOR,
                        lineweight_policy=LineweightPolicy.ABSOLUTE, hatch_policy=HatchPolicy.NORMAL,
                        proxy_graphic_policy=ProxyGraphicPolicy.SHOW)
    fe = Frontend(ctx, backend, config=cfg)
    count = [0]

    def override(entity, props) -> None:
        count[0] += 1
        if count[0] % 200 == 0 and time.monotonic() > deadline:
            raise _Deadline()
        t = entity.dxftype()
        if t in HIDDEN_TYPES:
            props.is_visible = False
        props.color = HATCH_INK if t in FAINT_TYPES else INK

    fe.push_property_override_function(override)
    try:
        fe.draw_layout(msp, finalize=True)
    except _Deadline:
        raise PreviewError(f"Dựng hình quá {max_seconds:.0f} giây.") from None
    except Exception as exc:  # noqa: BLE001 — đối tượng lạ không được làm hỏng app: chuyển sang hình đơn giản hoá
        raise PreviewError("Bộ vẽ ezdxf không dựng được bản vẽ này.") from exc
    page = layout.Page(0, 0, layout.Units.mm, margins=layout.Margins.all(0))
    settings = layout.Settings(output_coordinate_space=OUTPUT_SPACE, fit_page=True)
    try:
        root = backend.get_xml_root_element(page, settings=settings)
    except Exception as exc:  # noqa: BLE001
        raise PreviewError("Bộ vẽ ezdxf không xuất được hình.") from exc
    m = backend.transformation_matrix
    if m is None or root.get("viewBox") is None:
        raise PreviewError("Không gian mô hình không có hình để vẽ.")
    clean, (w, h), n_paths = _rebuild(root)
    t_render = time.monotonic() - t0

    # khung bao theo handle (đối tượng cấp trên của không gian mô hình), cùng ma trận với bộ vẽ
    boxes: dict[str, list[int]] = {}
    cache = ezbbox.Cache()
    boxes_capped = False
    for i, e in enumerate(msp):
        if len(boxes) >= MAX_BOXES or (i % 200 == 0 and time.monotonic() > deadline):
            boxes_capped = True
            break
        try:
            ext = ezbbox.extents([e], cache=cache, fast=True)
        except Exception:  # noqa: BLE001
            continue
        if not ext.has_data:
            continue
        b = svg_box(m, (ext.extmin.x, ext.extmin.y), (ext.extmax.x, ext.extmax.y))
        if b is not None:
            boxes[e.dxf.handle] = b
    omitted = {}
    for entity in msp:
        kind = entity.dxftype()
        if kind in HIDDEN_TYPES or kind in ("3DSOLID", "BODY", "REGION"):
            omitted[kind] = omitted.get(kind, 0) + 1
    limitations = "Phông có thể được thay thế; MTEXT/proxy có thể khác CAD. Đối chiếu trong CAD trước khi chốt."
    if omitted:
        limitations += " Không hiển thị: " + ", ".join(f"{kind} ({count})" for kind, count in sorted(omitted.items())) + "."
    meta = {
        "v": PREVIEW_VERSION, "layout": layout_name, "layouts": list(doc.layout_names()),
        "limitations": limitations, "omitted_types": omitted, "viewbox": [0, 0, w, h], "boxes": boxes, "boxes_capped": boxes_capped,
        "paths": n_paths, "model_entities": len(msp), "insunits": int(doc.header.get("$INSUNITS", 0) or 0),
        "dxf_version": str(doc.dxfversion), "render_seconds": round(t_render, 2),
        "total_seconds": round(time.monotonic() - t0, 2),
        # ma trận model → SVG (đồng dạng, lật trục y): x' = sx*x + tx, y' = sy*y + ty
        "transform": [m[0, 0], m[1, 1], m[3, 0], m[3, 1]],
    }
    text = ET.tostring(clean, encoding="unicode")
    if len(text.encode("utf-8")) > MAX_SVG_BYTES:
        raise PreviewError("Hình xem trước vượt 10 MiB.")
    return sanitize_svg(text), meta


def svg_box(m, p0: tuple[float, float], p1: tuple[float, float]) -> list[int] | None:
    from ezdxf.math import Vec3

    pts = [m.transform(Vec3(x, y, 0)) for x in (p0[0], p1[0]) for y in (p0[1], p1[1])]
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    vals = [min(xs), min(ys), max(xs), max(ys)]
    if any(v != v or abs(v) > 1e12 for v in vals):  # NaN / vô hạn
        return None
    return [round(v) for v in vals]


def font_signature() -> str:
    """Cache thay khi thư viện/phông đổi; chỉ băm metadata phông cục bộ."""
    import ezdxf
    roots = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", Path(ezdxf.__file__).parent / "fonts"]
    parts = [ezdxf.__version__, str(PREVIEW_VERSION)]
    for root in roots:
        if root.is_dir():
            for p in sorted(root.iterdir()):
                if p.suffix.lower() in (".ttf", ".otf", ".shx", ".ttc"):
                    try:
                        st = p.stat()
                        parts.append(f"{p.name}:{st.st_size}:{st.st_mtime_ns}")
                    except OSError:
                        pass
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def isolated_render(data: bytes, seconds: float, layout_name: str) -> tuple[str, dict]:
    """Tiến trình bị kết thúc khi hết hạn, kể cả đọc DXF/xuất SVG/tính bbox."""
    with _PROCESS_LOCK:
        return _isolated_render(data, seconds, layout_name)


def _isolated_render(data: bytes, seconds: float, layout_name: str) -> tuple[str, dict]:
    try:
        proc = subprocess.run([sys.executable, "-m", "cadguard.app.preview_worker", layout_name, str(seconds)],
                              input=data, capture_output=True, timeout=max(.05, seconds),
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                              env=dict(os.environ, PYTHONUTF8="1"))
    except subprocess.TimeoutExpired:
        raise PreviewError("Dựng hình quá thời gian cho phép; dùng hình đơn giản hoá.") from None
    if proc.returncode or len(proc.stdout) > MAX_SVG_BYTES * 3:
        raise PreviewError("Không dựng được hình đầy đủ; kiểm tra phông và phụ thuộc Pillow.")
    result = json.loads(proc.stdout)
    if "error" in result:
        raise PreviewError(result["error"])
    return sanitize_svg(result["svg"]), result["meta"]


# ---------- cache + chạy nền ----------

class PreviewManager:
    """Dựng xem trước trong luồng nền (một bản dựng một lúc), cache theo băm nội dung trong `<dự án>/.cadguard/cache`."""

    def __init__(self, root: Path, max_mb: float = PREVIEW_MAX_MB, max_seconds: float = PREVIEW_MAX_SECONDS):
        self.root = Path(root)
        self.max_mb = max_mb
        self.max_seconds = max_seconds
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self.font_signature = font_signature()
        self._jobs: dict[str, dict] = {}  # băm -> {"status": pending|failed, "reason"}

    @property
    def cache_dir(self) -> Path:
        return self.root / CACHE_DIR

    def _paths(self, sha: str) -> tuple[Path, Path]:
        return self.cache_dir / f"preview-{sha}.svg", self.cache_dir / f"preview-{sha}.json"

    def _load_cached(self, sha: str) -> dict | None:
        svg_p, meta_p = self._paths(sha)
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if meta.get("v") != PREVIEW_VERSION:
                return None
            text = sanitize_svg(svg_p.read_text(encoding="utf-8"))  # lọc lại: tệp cache có thể bị sửa tay
        except (OSError, ValueError, PreviewError):
            return None
        boxes = meta.get("boxes") if isinstance(meta.get("boxes"), dict) else {}
        meta["boxes"] = {str(k): [int(x) for x in v][:4] for k, v in boxes.items()
                         if isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)}
        return {"status": "ready", "svg": text, **meta}

    def _store(self, sha: str, text: str, meta: dict) -> None:
        d = self.cache_dir
        d.mkdir(parents=True, exist_ok=True)
        svg_p, meta_p = self._paths(sha)
        tmp = svg_p.with_suffix(".svg.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(svg_p)
        tmp = meta_p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        tmp.replace(meta_p)
        self._prune()

    def _prune(self) -> None:
        try:
            files = sorted(self.cache_dir.glob("preview-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return
        for p in files[MAX_CACHE_FILES:]:
            for q in (p, p.with_suffix(".svg")):
                try:
                    q.unlink()
                except OSError:
                    pass

    def status(self, path: Path, wait: float = 0.0, layout_name: str = "Model") -> dict:
        """Trạng thái xem trước của tệp: `ready` (kèm svg + meta), `pending` (đang dựng), `fallback` (kèm lý do)."""
        try:
            size = path.stat().st_size
        except OSError:
            return {"status": "fallback", "reason": "Không đọc được tệp."}
        if size > self.max_mb * 1024 * 1024:
            return {"status": "fallback", "reason": f"Tệp lớn hơn {self.max_mb:g} MB nên dùng hình đơn giản hoá."}
        try:
            data = path.read_bytes()
        except OSError:
            return {"status": "fallback", "reason": "Không đọc được tệp."}
        sha = hashlib.sha256((file_sha256(data) + "|" + layout_name + "|" + self.font_signature + "|" + str(PREVIEW_VERSION)).encode()).hexdigest()
        cached = self._load_cached(sha)
        if cached is not None:
            cached["cached"] = True
            return cached
        with self._lock:
            job = self._jobs.get(sha)
            if job is None:
                if len(self._jobs) >= 8:
                    return {"status": "fallback", "reason": "Hàng đợi dựng hình đang đầy; thử lại sau."}
                job = {"status": "pending", "done": threading.Event()}
                self._jobs[sha] = job
                threading.Thread(target=self._run, args=(sha, data, job, layout_name), daemon=True,
                                 name="cadguard-preview").start()
        if wait > 0:
            job["done"].wait(wait)
        if job["status"] == "failed":
            return {"status": "fallback", "reason": job["reason"]}
        if job["status"] == "ready":
            res = self._load_cached(sha)
            if res is not None:
                res["cached"] = False
                return res
            if "result" in job:  # không ghi được cache (thư mục chỉ đọc): trả kết quả trong bộ nhớ
                return dict(job["result"], cached=False)
            return {"status": "fallback", "reason": "Không lưu được hình xem trước."}
        return {"status": "pending"}

    def _run(self, sha: str, data: bytes, job: dict, layout_name: str) -> None:
        with self._run_lock:  # một bản dựng một lúc: không giành hết CPU của máy
            try:
                text, meta = isolated_render(data, self.max_seconds, layout_name)
                meta["sha256"] = file_sha256(data)
                meta["font_signature"] = self.font_signature
                try:
                    self._store(sha, text, meta)
                except OSError:
                    job["result"] = {"status": "ready", "svg": text, **meta}
                job["status"] = "ready"
            except PreviewError as exc:
                job.update(status="failed", reason=str(exc))
            except Exception:  # noqa: BLE001
                job.update(status="failed", reason="Bộ vẽ gặp lỗi không lường trước.")
            finally:
                job["done"].set()
                with self._lock:
                    for key in list(self._jobs):
                        if len(self._jobs) > 6 and key != sha and self._jobs[key]["status"] == "failed":
                            self._jobs.pop(key)
                if job["status"] == "ready" and "result" not in job:
                    with self._lock:  # đã có trong cache: bỏ khỏi bảng việc
                        self._jobs.pop(sha, None)


__all__ = ["PREVIEW_MAX_MB", "PREVIEW_MAX_SECONDS", "PreviewError", "PreviewManager", "file_sha256",
           "render_preview", "sanitize_svg", "svg_box"]
