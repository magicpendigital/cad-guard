"""Đọc DXF ASCII theo dòng -> Drawing Model `cg.drawing/1`, cùng mô hình như `dxf_reader.read_dxf` (đường ezdxf).

Dùng cho tệp rất lớn (hàng trăm MB, xem docs/real-sample-profile.md): không nạp trọn tệp, không dựng cây
đối tượng ezdxf. Mỗi lúc chỉ giữ các cặp (mã nhóm, giá trị) của MỘT bản ghi; bảng, khối và layout được
tóm thành số đếm. Bộ nhớ có trần qua `max_entity_records`: quá trần thì ngừng ghi `entities` chi tiết, vẫn
đếm đủ thống kê, và đặt `stats.entity_records_truncated = True`.

Bám theo cách ezdxf nạp tệp để hai đường đọc cho cùng mô hình:
- thứ tự khối theo bảng BLOCK_RECORD; thứ tự layout theo từ điển ACAD_LAYOUT;
- đối tượng ở mục ENTITIES vào không gian mô hình/giấy theo mã chủ (330), dự phòng mã 67;
- ATTRIB/VERTEX/SEQEND là bản ghi con (gắn vào INSERT/POLYLINE), không phải đối tượng độc lập;
- tự thêm layer "0", "Defpoints" (luôn không in), kiểu chữ và kiểu kích thước "Standard" nếu thiếu.

Mã hoá: DXF R2007+ (AC1021 trở lên) là UTF-8; bản cũ theo `$DWGCODEPAGE` (ví dụ ANSI_1258 -> cp1258).
Lỗi giải mã được thay bằng ký tự thay thế, không ném lỗi. Chỉ hỗ trợ DXF ASCII; DXF nhị phân báo lỗi rõ ràng.

Giới hạn đã biết (đường ezdxf làm thêm mà đường này không làm): nâng cấp R13/R14 (ezdxf thêm khối mũi tên),
đổi tên khối `$MODEL_SPACE` của DXF R12, và đường khôi phục `ezdxf.recover` cho tệp hỏng cấu trúc.
"""

from __future__ import annotations

import codecs
import hashlib
import math
import re
from pathlib import Path

from .dxf_reader import _block_depth, _font_kind
from .model import BlockRec, DrawingModel, EntityRec, LayerRec, LayoutRec, ModelStats, SpaceStats, StyleRec, ViewportRec

DEFAULT_MAX_ENTITY_RECORDS = 300_000  # ~1,2 KB/bản ghi -> khoảng 350 MB ở trần
HASH_CHUNK = 1 << 20
HEADER_SCAN_MAX_LINES = 200_000
BINARY_SENTINEL = b"AutoCAD Binary DXF"

Z_TOL = 1e-6
PROXY_TYPES = {"ACAD_PROXY_ENTITY", "PROXY", "ACAD_PROXY_OBJECT"}
LINKED_TYPES = {"ATTRIB", "VERTEX", "SEQEND"}
WANTED_TABLES = {"LAYER", "STYLE", "DIMSTYLE", "BLOCK_RECORD"}
# Mã Z của các điểm mà ezdxf kiểm (start, end, center, insert, location), theo loại đối tượng.
_Z30 = (30,)
Z_CODES: dict[str, tuple[int, ...]] = {
    "LINE": (30, 31),
    **{t: _Z30 for t in ("CIRCLE", "ARC", "ELLIPSE", "TEXT", "ATTDEF", "ATTRIB", "MTEXT", "INSERT", "IMAGE",
                         "WIPEOUT", "POINT", "XLINE", "RAY", "SHAPE", "TOLERANCE", "LIGHT", "ACAD_TABLE",
                         "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY")},
    **{t: (32,) for t in ("DIMENSION", "ARC_DIMENSION", "LARGE_RADIAL_DIMENSION")},
}
# Mã nhóm riêng của đối tượng mà mô hình cần (ngoài phần chung AcDbEntity).
SPEC_CODES = frozenset({1, 2, 7, 10, 11, 20, 21, 30, 31, 32, 38, 40, 41, 45, 50, 51, 66, 69, 70})


class DXFStreamError(ValueError):
    """Tệp không đọc được bằng bộ đọc theo dòng. Thông điệp bằng tiếng Việt, không chứa đường dẫn."""


def _r(v: float) -> float:
    return round(float(v), 4)


def _int(v: str) -> int | None:
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except ValueError:
            return None


def _float(spec: dict, code: int, default: float = 0.0) -> float:
    v = spec.get(code)
    return default if v is None else float(v)


def file_hash(path: str | Path) -> str:
    """sha256 rút gọn (16 ký tự hex) của nội dung tệp, đọc theo khối 1 MB: giống `read_dxf`."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(HASH_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:16]


def is_binary_dxf(path: str | Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(len(BINARY_SENTINEL)) == BINARY_SENTINEL


def detect_header(path: str | Path) -> tuple[str, str]:
    """Đọc phần HEADER (chỉ phần đầu tệp) để lấy ($ACADVER, mã hoá văn bản Python).

    Giống ezdxf: R2007+ luôn UTF-8; bản cũ theo $DWGCODEPAGE, mặc định cp1252; mã hoá lạ -> cp1252.
    """
    version, codepage = "AC1009", "ANSI_1252"
    want = None
    with open(path, "rb") as fh:
        n = 0
        code = None
        for raw in fh:
            n += 1
            if n > HEADER_SCAN_MAX_LINES:
                break
            line = raw.decode("latin-1").strip()
            if code is None:
                code = line
                continue
            value, c, code = line, code, None
            if c == "0" and value == "ENDSEC":
                break
            if c == "9":
                want = value
            elif want == "$ACADVER" and c == "1":
                version, want = value.upper(), None
            elif want == "$DWGCODEPAGE" and c == "3":
                codepage, want = value, None
    if version >= "AC1021":
        return version, "utf-8"
    try:
        from ezdxf.tools.codepage import toencoding

        enc = toencoding(codepage)
    except Exception:  # noqa: BLE001
        enc = "cp1252"
    try:
        codecs.lookup(enc)
    except LookupError:
        enc = "cp1252"
    return version, enc


class _Space:
    """Bộ đếm nhẹ cho một SpaceStats (tránh gán thuộc tính pydantic cho mỗi đối tượng)."""

    __slots__ = ("entities", "by_type", "by_layer", "color_override", "lineweight_override", "true_color",
                 "dim_total", "dim_text_override", "wipeout", "image", "ole", "proxy")

    def __init__(self) -> None:
        self.entities = self.color_override = self.lineweight_override = self.true_color = 0
        self.dim_total = self.dim_text_override = self.wipeout = self.image = self.ole = self.proxy = 0
        self.by_type: dict[str, int] = {}
        self.by_layer: dict[str, int] = {}

    def add(self, t: str, layer: str, color, lw, tc, dim_text) -> None:
        # Giống dxf_reader._count_entity: không tính bản ghi con.
        if t in LINKED_TYPES:
            return
        self.entities += 1
        self.by_type[t] = self.by_type.get(t, 0) + 1
        self.by_layer[layer] = self.by_layer.get(layer, 0) + 1
        if color is not None and color != 256:
            self.color_override += 1
        if lw is not None and lw not in (-1, -2, -3):
            self.lineweight_override += 1
        if tc is not None:
            self.true_color += 1
        if t == "DIMENSION":
            self.dim_total += 1
            if (dim_text or "") not in ("", "<>"):
                self.dim_text_override += 1
        elif t == "WIPEOUT":
            self.wipeout += 1
        elif t == "IMAGE":
            self.image += 1
        elif t in ("OLE2FRAME", "OLEFRAME"):
            self.ole += 1
        elif t == "ACAD_PROXY_ENTITY":
            self.proxy += 1

    def merge(self, other: "_Space") -> None:
        for name in self.__slots__:
            if name in ("by_type", "by_layer"):
                mine = getattr(self, name)
                for k, v in getattr(other, name).items():
                    mine[k] = mine.get(k, 0) + v
            else:
                setattr(self, name, getattr(self, name) + getattr(other, name))

    def to_model(self) -> SpaceStats:
        return SpaceStats(**{name: getattr(self, name) for name in self.__slots__})


class _Block:
    __slots__ = ("name", "flags", "count", "types", "layers", "children")

    def __init__(self, name: str, flags: int) -> None:
        self.name, self.flags, self.count = name, flags, 0
        self.types: dict[str, int] = {}
        self.layers: dict[str, int] = {}
        self.children: dict[str, int] = {}


def _is_layout_block(key: str) -> bool:
    return key.startswith(("*model_space", "*paper_space"))


def _scan(tags: list, geometry: bool):
    """Tách phần chung (AcDbEntity) và các mã riêng cần dùng của một bản ghi đối tượng.

    Bỏ nhóm 102 {...}, dừng ở dữ liệu mở rộng (mã >= 1000) và đối tượng nhúng (101).
    """
    handle, layer = "", "0"
    color = lw = tc = owner = pspace = None
    spec: dict[int, str] = {}
    xs: list[float] = []
    ys: list[float] = []
    n100 = 0
    in102 = False
    for code, val in tags:
        if code >= 1000 or code == 101:
            break
        if code == 102:
            in102 = val.startswith("{")
            continue
        if in102:
            continue
        if code == 100:
            n100 += 1
            continue
        if n100 <= 1:  # trước/trong AcDbEntity (DXF R12 không có mốc 100: mọi mã ở đây)
            if code == 8:
                layer = val
                continue
            if code == 5:
                handle = val
                continue
            if code == 62:
                color = _int(val)
                continue
            if code == 370:
                lw = _int(val)
                continue
            if code == 420:
                tc = _int(val)
                continue
            if code == 330:
                if owner is None:
                    owner = val
                continue
            if code == 67:
                pspace = _int(val)
                continue
        if n100 != 1 and code in SPEC_CODES:
            if geometry and code == 10:
                xs.append(float(val))
            elif geometry and code == 20:
                ys.append(float(val))
            spec[code] = val
    return handle, layer, color, lw, tc, owner, pspace, spec, xs, ys


def _polyline_metrics(pts: list[tuple[float, float]], closed: bool) -> tuple[float, float | None, bool]:
    # Cùng công thức với dxf_reader._polyline_metrics.
    length = 0.0
    for a, b in zip(pts, pts[1:]):
        length += ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    area = None
    if closed and len(pts) >= 3:
        length += ((pts[0][0] - pts[-1][0]) ** 2 + (pts[0][1] - pts[-1][1]) ** 2) ** 0.5
        s = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
        area = abs(s) / 2.0
    return length, area, closed


def _entity_rec(t: str, handle: str, layer: str, color, lw, tc, spec: dict, xs: list, ys: list) -> EntityRec:
    f: dict = {"handle": handle, "type": t, "layer": layer, "space": "Model", "length": None, "area": None,
               "closed": None, "has_nonzero_z": False, "dup_key": None, "text_style": None, "dim_text": None,
               "block": None, "attribs": None, "is_proxy": t in PROXY_TYPES, "color": color, "lineweight": lw,
               "true_color": tc}
    try:
        if t == "LWPOLYLINE":
            f["has_nonzero_z"] = abs(_float(spec, 38) or 0.0) > Z_TOL
        else:
            f["has_nonzero_z"] = any(abs(float(spec[c])) > Z_TOL for c in Z_CODES.get(t, ()) if c in spec)
    except ValueError:
        pass
    try:
        if t == "LINE":
            sx, sy, sz = _float(spec, 10), _float(spec, 20), _float(spec, 30)
            ex, ey, ez = _float(spec, 11), _float(spec, 21), _float(spec, 31)
            dx, dy, dz = ex - sx, ey - sy, ez - sz
            f["length"] = math.sqrt(dx * dx + dy * dy + dz * dz)
            f["dup_key"] = f"LINE|{layer}|{sorted([(_r(sx), _r(sy)), (_r(ex), _r(ey))])}"
        elif t == "LWPOLYLINE":
            flags = _int(spec.get(70, "0")) or 0
            f["length"], f["area"], f["closed"] = _polyline_metrics(list(zip(xs, ys)), bool(flags & 1))
        elif t == "CIRCLE":
            f["dup_key"] = f"CIRCLE|{layer}|{(_r(_float(spec, 10)), _r(_float(spec, 20)))}|{_r(_float(spec, 40, 1.0))}"
        elif t == "ARC":
            f["dup_key"] = (f"ARC|{layer}|{(_r(_float(spec, 10)), _r(_float(spec, 20)))}|{_r(_float(spec, 40, 1.0))}"
                            f"|{_r(_float(spec, 50))}|{_r(_float(spec, 51, 360.0))}")
        elif t in ("TEXT", "MTEXT"):
            f["text_style"] = spec.get(7, "Standard")
        elif t == "DIMENSION":
            f["dim_text"] = spec.get(1, "") or ""
        elif t == "INSERT":
            f["block"] = spec.get(2, "")
            f["attribs"] = {}
    except ValueError:  # số hỏng trong tệp: giữ phần đã đọc được, như đường ezdxf
        pass
    return EntityRec.model_construct(**f)


class _Parser:
    def __init__(self, max_entity_records: int) -> None:
        self.max_records = max(0, int(max_entity_records))
        self.n_records = 0
        self.truncated = False
        self.section: str | None = None
        self.table: str | None = None
        self.insunits = 0
        # bảng: khoá chữ thường -> bản ghi (giữ vị trí đầu, giá trị cuối như ezdxf)
        self.layers: dict[str, LayerRec] = {}
        self.styles: dict[str, tuple[str, int, str, str]] = {}
        self.dimstyles: dict[str, str] = {}
        self.block_records: dict[str, str] = {}  # khoá -> tên
        self.br_handles: dict[str, str] = {}  # handle -> khoá
        self.msp_handle: str | None = None  # handle BLOCK_RECORD của *Model_Space / *Paper_Space
        self.psp_handle: str | None = None
        # khối
        self.block_defs: dict[str, _Block] = {}
        self.cur_block: str | None = None  # khoá khối đang đọc
        self.block_layers: set[str] = set()
        self.blocks_space = _Space()
        # layout: khoá khối layout -> dữ liệu
        self.spaces: dict[str, _Space] = {}
        self.records: dict[str, list[EntityRec]] = {}
        self.viewports: dict[str, list[tuple[int, float | None]]] = {}
        # liên kết bản ghi con
        self.linking = False
        self.attribs: dict | None = None
        # OBJECTS
        self.root_seen = False
        self.layout_dict_handle: str | None = None
        self.layout_entries: list[tuple[str, str]] = []
        self.layout_objs: dict[str, tuple[str, str | None, float, float, int]] = {}

    # ---- vòng đọc

    def wants(self, rtype: str) -> bool:
        s = self.section
        if s in ("BLOCKS", "ENTITIES"):
            return True
        if s == "TABLES":
            return rtype == "TABLE" or self.table in WANTED_TABLES
        if s == "OBJECTS":
            return rtype in ("DICTIONARY", "LAYOUT")
        return False

    def dispatch(self, rtype: str, tags: list | None) -> None:
        if rtype == "SECTION":
            self.section = next((v for c, v in tags if c == 2), None) if tags else None
            if self.section == "HEADER":
                self._header(tags)
            return
        s = self.section
        if s in ("BLOCKS", "ENTITIES"):
            self._entity(rtype, tags)
        elif s == "TABLES":
            if rtype == "TABLE":
                self.table = next((v for c, v in tags if c == 2), None) if tags else None
            elif rtype == "ENDTAB":
                self.table = None
            elif tags is not None:
                self._table_entry(rtype, tags)
        elif s == "OBJECTS" and tags is not None:
            if rtype == "DICTIONARY":
                self._dictionary(tags)
            elif rtype == "LAYOUT":
                self._layout(tags)

    def _header(self, tags: list) -> None:
        var = None
        for code, val in tags:
            if code == 9:
                var = val
            elif var == "$INSUNITS" and code == 70:
                self.insunits = _int(val) or 0
                var = None

    # ---- TABLES

    def _table_entry(self, rtype: str, tags: list) -> None:
        if rtype != self.table:
            return
        d: dict[int, str] = {}
        handle = None
        in102 = False
        for code, val in tags:
            if code >= 1000:
                break
            if code == 102:
                in102 = val.startswith("{")
                continue
            if in102:
                continue
            if code in (5, 105) and handle is None:
                handle = val
            elif code not in d:
                d[code] = val
        name = d.get(2, "")
        key = name.lower()
        if rtype == "LAYER":
            parts = re.split(r"\||\$0\$", name, maxsplit=1)
            flags = _int(d.get(70, "0")) or 0
            color = _int(d.get(62, "7"))
            color = 7 if color is None else color
            lw = _int(d.get(370, "-3"))
            plot = _int(d.get(290, "1"))
            self.layers[key] = LayerRec(
                name=name,
                xref_dependent=bool(flags & 16 or len(parts) > 1),
                xref_name=parts[0] if len(parts) > 1 else None,
                color=color,
                linetype=d.get(6, "Continuous"),
                lineweight=-3 if lw is None else lw,
                frozen=bool(flags & 1),
                off=color < 0,
                plot=bool(1 if plot is None else plot),
            )
        elif rtype == "STYLE":
            flags = _int(d.get(70, "0")) or 0
            if name == "" and flags & 1:  # tệp hình SHX không tên: ezdxf không liệt kê
                return
            self.styles[key] = (name, flags, d.get(3, "") or "", d.get(4, "") or "")
        elif rtype == "DIMSTYLE":
            self.dimstyles[key] = name
        elif rtype == "BLOCK_RECORD":
            self.block_records[key] = name
            if handle is not None:
                self.br_handles[handle] = key
                if key == "*model_space":
                    self.msp_handle = handle
                elif key == "*paper_space":
                    self.psp_handle = handle

    # ---- BLOCKS / ENTITIES

    def _entity(self, t: str, tags: list | None) -> None:
        tags = tags or []
        in_blocks = self.section == "BLOCKS"
        if in_blocks and t == "BLOCK":
            _h, _l, _c, _w, _t, _o, _p, spec, _x, _y = _scan(tags, False)
            name = spec.get(2, "")
            key = name.lower()
            self.cur_block = key
            if key not in self.block_defs:
                self.block_defs[key] = _Block(name, _int(spec.get(70, "0")) or 0)
            self.linking, self.attribs = False, None
            return
        if in_blocks and t == "ENDBLK":
            self.cur_block = None
            self.linking, self.attribs = False, None
            return
        if in_blocks and self.cur_block is None:
            return  # đối tượng nằm ngoài BLOCK...ENDBLK: ezdxf cũng không gán vào đâu
        # Bản ghi con của INSERT/POLYLINE đang mở.
        if self.linking:
            if t == "SEQEND":
                self.linking, self.attribs = False, None
                return
            if t == "ATTRIB" and self.attribs is not None:
                _h, _l, _c, _w, _t, _o, _p, spec, _x, _y = _scan(tags, False)
                self.attribs[spec.get(2, "")] = spec.get(1, "")
            return
        container = self.cur_block if in_blocks else None
        layout_ctx = container is None or _is_layout_block(container)
        geometry = layout_ctx and self.n_records < self.max_records
        handle, layer, color, lw, tc, owner, pspace, spec, xs, ys = _scan(tags, geometry)
        if container is None:  # mục ENTITIES: chọn không gian như ezdxf (mã chủ trước, mã 67 sau)
            if owner is not None and owner == self.msp_handle:
                container = "*model_space"
            elif owner is not None and owner == self.psp_handle:
                container = "*paper_space"
            else:
                container = "*paper_space" if pspace else "*model_space"
        attribs_follow = t == "INSERT" and bool(_int(spec.get(66, "0")) or 0)
        if t == "POLYLINE" or attribs_follow:
            self.linking = True
        self.attribs = None
        if not layout_ctx:
            self._block_entity(container, t, layer, color, lw, tc, spec)
            return
        sp = self.spaces.get(container)
        if sp is None:
            sp = self.spaces[container] = _Space()
        sp.add(t, layer, color, lw, tc, spec.get(1) if t == "DIMENSION" else None)
        if t == "VIEWPORT":
            vid = _int(spec.get(69, "0")) or 0
            scale = None
            try:
                vh, ph = _float(spec, 45, 1.0), _float(spec, 41, 1.0)
                scale = ph / vh if vh > 0 and ph > 0 else None
            except ValueError:
                pass
            self.viewports.setdefault(container, []).append((vid, scale))
            return
        if self.n_records >= self.max_records:
            self.truncated = True
            return
        rec = _entity_rec(t, handle, layer, color, lw, tc, spec, xs, ys)
        self.n_records += 1
        self.records.setdefault(container, []).append(rec)
        if attribs_follow:
            self.attribs = rec.attribs

    def _block_entity(self, key: str, t: str, layer: str, color, lw, tc, spec: dict) -> None:
        b = self.block_defs[key]
        if not key.startswith("*"):
            self.block_layers.add(layer)
        if t in LINKED_TYPES:
            return
        b.count += 1
        b.types[t] = b.types.get(t, 0) + 1
        b.layers[layer] = b.layers.get(layer, 0) + 1
        if t == "INSERT":
            child = spec.get(2, "")
            b.children[child] = b.children.get(child, 0) + 1
        self.blocks_space.add(t, layer, color, lw, tc, spec.get(1) if t == "DIMENSION" else None)

    # ---- OBJECTS

    def _dictionary(self, tags: list) -> None:
        handle = None
        entries: list[tuple[str, str]] = []
        pending = None
        in102 = False
        for code, val in tags:
            if code >= 1000:
                break
            if code == 102:
                in102 = val.startswith("{")
                continue
            if in102:
                continue
            if code == 5 and handle is None:
                handle = val
            elif code == 3:
                pending = val
            elif code in (350, 360) and pending is not None:
                entries.append((pending, val))
                pending = None
        if not self.root_seen:  # từ điển gốc là đối tượng đầu tiên của OBJECTS
            self.root_seen = True
            self.layout_dict_handle = next((h for n, h in entries if n == "ACAD_LAYOUT"), None)
        elif handle is not None and handle == self.layout_dict_handle:
            self.layout_entries = entries

    def _layout(self, tags: list) -> None:
        handle = None
        sub = ""
        name, br, w, h, units = "Layoutname", None, "420", "297", "1"
        in102 = False
        for code, val in tags:
            if code >= 1000:
                break
            if code == 102:
                in102 = val.startswith("{")
                continue
            if in102:
                continue
            if code == 100:
                sub = val
            elif code == 5 and handle is None:
                handle = val
            elif sub == "AcDbPlotSettings":
                if code == 44:
                    w = val
                elif code == 45:
                    h = val
                elif code == 72:
                    units = val
            elif sub == "AcDbLayout":
                if code == 1:
                    name = val
                elif code == 330:
                    br = val
        if handle is None:
            return
        try:
            wf, hf = float(w), float(h)
        except ValueError:
            wf = hf = 0.0
        self.layout_objs[handle] = (name, br, wf, hf, _int(units) if _int(units) is not None else 1)

    # ---- ráp mô hình

    def build(self, file_hash_: str, dxf_version: str) -> DrawingModel:
        m = DrawingModel(file_hash=file_hash_, dxf_version=dxf_version, insunits=self.insunits)
        stats = ModelStats(source="stream", modelspace=SpaceStats(), paperspace=SpaceStats(), blocks=SpaceStats())

        # Bảng bắt buộc mà ezdxf tự thêm khi nạp tệp.
        layers = dict(self.layers)
        if "0" not in layers:
            layers["0"] = LayerRec(name="0", color=7, linetype="Continuous", lineweight=-3)
        if "defpoints" not in layers:
            layers["defpoints"] = LayerRec(name="Defpoints", color=7, linetype="Continuous", lineweight=-3, plot=False)
        else:
            layers["defpoints"] = layers["defpoints"].model_copy(update={"plot": False})
        m.layers = list(layers.values())
        stats.layers_xref_dependent = sum(la.xref_dependent for la in m.layers)

        styles = dict(self.styles)
        if "standard" not in styles:
            styles["standard"] = ("Standard", 0, "", "")
        for name, flags, font, bigfont in styles.values():
            if flags & 1:
                stats.shape_styles += 1
                continue
            m.styles.append(StyleRec(name=name, font=font, bigfont=bigfont, font_kind=_font_kind(font)))
        dimstyles = dict(self.dimstyles)
        if "standard" not in dimstyles:
            dimstyles["standard"] = "Standard"
        m.dim_styles = list(dimstyles.values())

        # Khối theo thứ tự BLOCK_RECORD; thêm bản ghi thiếu như ezdxf.
        order = dict(self.block_records)
        for key, name in (("*model_space", "*Model_Space"), ("*paper_space", "*Paper_Space")):
            order.setdefault(key, name)
        for key, b in self.block_defs.items():
            order.setdefault(key, b.name)
        for key, name in order.items():
            b = self.block_defs.get(key)
            is_layout = name.lower().startswith(("*model_space", "*paper_space"))
            kind = "named" if not name.startswith("*") else "anon_" + (name[1:2].upper() if name[1:2].upper() in "UDXA" else "other")
            try:
                rec = BlockRec(name=name, kind=kind, is_layout=is_layout, is_xref=bool((b.flags if b else 0) & 4))
            except Exception:  # noqa: BLE001 - tên khối lạ: bỏ qua như đường ezdxf
                continue
            m.blocks.append(rec)
            if is_layout or b is None:
                continue
            rec.entity_count, rec.types, rec.layers, rec.child_blocks = b.count, b.types, b.layers, b.children
        m.block_layers = sorted(self.block_layers)
        lookup = {b.name.casefold(): b for b in m.blocks if not b.is_layout}
        graph = {k: b.model_copy(update={"child_blocks": {n.casefold(): v for n, v in b.child_blocks.items()}}) for k, b in lookup.items()}
        for k, b in lookup.items():
            b.depth = _block_depth(k, graph, set())
        stats.blocks = self.blocks_space.to_model()
        stats.blocks_named = sum(b.kind == "named" for b in lookup.values())
        stats.blocks_anonymous = sum(b.kind != "named" for b in lookup.values())
        stats.blocks_xref = sum(b.is_xref for b in lookup.values())
        stats.max_block_depth = max((b.depth for b in lookup.values()), default=0)

        # Layout theo thứ tự từ điển ACAD_LAYOUT.
        layouts: dict[str, tuple[str, str | None, float, float, int]] = {}
        for name, handle in self.layout_entries:
            obj = self.layout_objs.get(handle)
            if obj is not None:
                layouts[name.lower()] = obj
        if len(layouts) < 2:  # DXF R12: ezdxf dựng lại Model và Layout1 từ khối
            layouts.setdefault("model", ("Model", "@*model_space", 420.0, 297.0, 1))
            layouts.setdefault("layout1", ("Layout1", "@*paper_space", 420.0, 297.0, 1))
        model_space, paper_space = _Space(), _Space()
        for name, br, w, h, units in layouts.values():
            key = br[1:] if br and br.startswith("@") else self.br_handles.get(br or "")
            if key is None:
                continue
            is_model = name.lower() == "model"
            space = self.spaces.get(key)
            if space is not None:
                (model_space if is_model else paper_space).merge(space)
            recs = self.records.get(key, [])
            if is_model:
                m.entities.extend(recs)
                continue
            if units == 0:  # 0 = inch
                w, h = w * 25.4, h * 25.4
            pw, ph = (round(w, 2), round(h, 2)) if w > 0 and h > 0 else (None, None)
            lrec = LayoutRec(name=name, paper_w_mm=pw, paper_h_mm=ph)
            lrec.viewports = [ViewportRec(layout=name, id=vid, scale=sc) for vid, sc in self.viewports.get(key, []) if vid != 1]
            m.layouts.append(lrec)
            for rec in recs:
                rec.space = name
            m.entities.extend(recs)
        stats.modelspace = model_space.to_model()
        stats.paperspace = paper_space.to_model()
        stats.entity_records_truncated = self.truncated
        m.stats = stats
        return m


def _normalize_version(version: str) -> str:
    # ezdxf nâng R13/R14 lên R2000 và bản trước R12 lên R12 khi nạp.
    if version < "AC1009":
        return "AC1009"
    if version in ("AC1012", "AC1014"):
        return "AC1015"
    return version


def read_dxf_stream(path: str | Path, max_entity_records: int = DEFAULT_MAX_ENTITY_RECORDS) -> DrawingModel:
    """Đọc DXF ASCII theo dòng, trả về Drawing Model như `read_dxf`, với `stats.source == "stream"`.

    `max_entity_records`: số bản ghi `entities` tối đa giữ trong bộ nhớ; quá trần thì cắt và đặt
    `stats.entity_records_truncated`. Ném `DXFStreamError` (tiếng Việt) nếu là DXF nhị phân hoặc sai cấu trúc.
    """
    p = Path(path)
    if is_binary_dxf(p):
        raise DXFStreamError("Tệp là DXF nhị phân; bộ đọc theo dòng chỉ hỗ trợ DXF ASCII. "
                             "Hãy xuất lại dạng DXF ASCII hoặc dùng --reader ezdxf.")
    version, encoding = detect_header(p)
    parser = _Parser(max_entity_records)
    rtype: str | None = None
    tags: list | None = None
    wants, dispatch = parser.wants, parser.dispatch
    line = 0
    with open(p, encoding=encoding, errors="replace") as fh:
        readline = fh.readline
        while True:
            c = readline()
            if not c:
                break
            v = readline()
            if not v:
                break
            line += 2
            try:
                code = int(c)
            except ValueError:
                raise DXFStreamError(f"Cấu trúc DXF hỏng: mã nhóm không hợp lệ ở dòng {line - 1}.") from None
            if code == 0:
                v = v.rstrip("\n")
                if rtype is not None:
                    dispatch(rtype, tags)
                if v == "EOF":
                    rtype = tags = None
                    break
                if v == "ENDSEC":
                    parser.section = parser.table = None
                    rtype = tags = None
                    continue
                rtype = v
                tags = [] if (v == "SECTION" or wants(v)) else None
                continue
            if tags is not None and code != 999:
                tags.append((code, v.rstrip("\n")))
        if rtype is not None:
            dispatch(rtype, tags)
    return parser.build(file_hash(p), _normalize_version(version))
