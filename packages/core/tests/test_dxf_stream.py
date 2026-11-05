"""Bộ đọc DXF theo dòng (`cadguard.dxf_stream`): khớp đường ezdxf, trần bộ nhớ, mã hoá, CLI, hiệu năng.

Chỉ dùng DXF tổng hợp (fixtures.py, ezdxf, hoặc `fixtures.make_large` sinh vào tmp_path).
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import ezdxf
import pytest

from cadguard import fixtures
from cadguard.cli import main
from cadguard.dxf_reader import read_dxf
from cadguard.dxf_stream import DXFStreamError, detect_header, read_dxf_stream
from cadguard.runner import audit_model

STANDARDS = Path(__file__).resolve().parents[3] / "standards"
# Trường số thực tính bằng phép toán (không đọc thẳng từ tệp): LINE.length dùng math.sqrt ở đường stream còn
# ezdxf dùng Vec3.magnitude (phần mở rộng C), LWPOLYLINE.length/area cộng dồn số thực; có thể lệch ở chữ số
# cuối nên so theo dung sai tương đối. Hiện tại trên mọi fixture chúng vẫn khớp tuyệt đối.
FLOAT_FIELDS = {"length", "area"}
REL_TOL = 1e-9


# Mọi fixture do `fixtures.make_all` sinh: bộ chính ở thư mục gốc, bộ dựng 3D (scene/studio) ở thư mục con scene/.
ALL_FIXTURES = sorted(fixtures.ALL) + [f"scene/{n}" for n in sorted(fixtures.SCENE_FIXTURES)]


def _diff(a, b, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = [] if set(a) == set(b) else [f"{path}: khoá khác {sorted(set(a) ^ set(b))}"]
        for k in set(a) & set(b):
            out += _diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = [] if len(a) == len(b) else [f"{path}: độ dài {len(a)} != {len(b)}"]
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff(x, y, f"{path}[{i}]")
        return out
    if path.rsplit(".", 1)[-1] in FLOAT_FIELDS and isinstance(a, float) and isinstance(b, float):
        return [] if math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-12) else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def assert_same_model(path: Path) -> None:
    a = read_dxf(path).model_dump()
    b = read_dxf_stream(path).model_dump()
    assert a["stats"]["source"] == "ezdxf" and b["stats"]["source"] == "stream"
    a["stats"]["source"] = b["stats"]["source"] = "?"
    problems = _diff(a, b)
    assert not problems, f"{path.name}: mô hình stream khác ezdxf:\n" + "\n".join(problems[:30])


def _findings(model, standard) -> Counter:
    res = audit_model(model, standard)
    return Counter((f.rule_id, f.count, f.layer, f.layout) for f in res.findings)


# ---- khớp với đường ezdxf


def test_synthetic_set_is_complete(synthetic):
    assert {p.name for p in synthetic.glob("*.dxf")} == set(fixtures.ALL)
    assert {p.name for p in (synthetic / "scene").glob("*.dxf")} == set(fixtures.SCENE_FIXTURES)
    assert "model_features.dxf" in fixtures.ALL


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_stream_model_matches_ezdxf(synthetic, name):
    assert_same_model(synthetic / name)


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_stream_audit_matches_ezdxf(synthetic, standard, name):
    path = synthetic / name
    assert _findings(read_dxf_stream(path), standard) == _findings(read_dxf(path), standard)


@pytest.fixture(scope="module")
def small_large(tmp_path_factory):
    path = tmp_path_factory.mktemp("large") / "large_small.dxf"
    info = fixtures.make_large(path, target_mb=1.5, seed=7)
    return path, info


def test_make_large_small_matches_ezdxf(small_large, standard):
    path, info = small_large
    assert info["bytes"] >= 1.5 * 1024 * 1024 and info["model_entities"] > 0 and info["block_entities"] > 0
    assert_same_model(path)
    model = read_dxf_stream(path)
    assert model.stats.blocks.entities > model.stats.modelspace.entities  # phần lớn nội dung trong khối
    values = [v for e in model.entities if e.attribs for v in e.attribs.values()]
    assert any(re.search(r"[^\x00-\x7f]", v) for v in values), "thiếu chữ tiếng Việt tổng hợp trong thuộc tính"
    assert all(la.name.startswith("SYN-") for la in model.layers if la.name not in ("0", "Defpoints"))
    assert _findings(model, standard) == _findings(read_dxf(path), standard)


def _edge_cases_doc(version: str):
    doc = ezdxf.new(version, setup=False)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("SYN-ĐƯƠNG")
    off = doc.layers.add("SYN-OFF")
    off.off()
    doc.layers.add("SYN-FROZEN").freeze()
    doc.layers.add("SYN-XR|NHA")
    doc.styles.add("SYN-SHAPE", font="syn.shx").dxf.flags = 1
    doc.styles.add("SYN-VN", font="syn_vn.shx")
    doc.dimstyles.add("SYN-DIM")
    blk = doc.blocks.new("SYN-THE")
    blk.add_attdef("SYN_MA", (0, 0), dxfattribs={"height": 2.5})
    blk.add_circle((0, 0), 5, dxfattribs={"layer": "SYN-ĐƯƠNG", "color": 0})
    msp = doc.modelspace()
    msp.add_line((0, 0, 0), (3, 4, 0), dxfattribs={"layer": "SYN-ĐƯƠNG", "lineweight": 25})
    msp.add_line((1, 1, 2), (5, 5, 2), dxfattribs={"layer": "SYN-OFF"})
    msp.add_circle((1, 2), 3, dxfattribs={"layer": "SYN-FROZEN"})
    msp.add_arc((1, 2), 3, 10, 200, dxfattribs={"layer": "SYN-FROZEN"})
    msp.add_point((1, 1, 7), dxfattribs={"layer": "SYN-XR|NHA"})
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 10)], close=False, dxfattribs={"layer": "SYN-ĐƯƠNG"})
    msp.add_polyline2d([(0, 0), (1, 1), (2, 0)], dxfattribs={"layer": "SYN-ĐƯƠNG"})
    msp.add_text("Ghi chú SYN Đường", dxfattribs={"style": "SYN-VN", "height": 2.5})
    msp.add_mtext("Ghi chú SYN dài", dxfattribs={"style": "SYN-VN"})
    msp.add_blockref("SYN-THE", (5, 5)).add_auto_attribs({"SYN_MA": "Mã SYN Đ-01"})
    lo = doc.layouts.new("SYN-GIAY")
    lo.page_setup(size=(11, 8.5), margins=(0, 0, 0, 0), units="inch")
    lo.add_viewport(center=(5, 4), size=(8, 6), view_center_point=(0, 0), view_height=60)
    lo.add_blockref("SYN-THE", (1, 1)).add_auto_attribs({"SYN_MA": "Giấy SYN"})
    return doc


def test_edge_cases_r2018_match_ezdxf(tmp_path):
    path = tmp_path / "edge_r2018.dxf"
    _edge_cases_doc("R2018").saveas(path)
    assert detect_header(path) == ("AC1032", "utf-8")
    assert_same_model(path)
    m = read_dxf_stream(path)
    names = {la.name: la for la in m.layers}
    assert names["SYN-OFF"].off and names["SYN-FROZEN"].frozen and names["SYN-XR|NHA"].xref_dependent
    assert not names["Defpoints"].plot
    assert m.stats.shape_styles == 1 and "SYN-GIAY" in {lo.name for lo in m.layouts}
    assert m.stats.modelspace.lineweight_override == 1 and m.stats.blocks.color_override == 1
    paper = [e for e in m.entities if e.space == "SYN-GIAY"]
    assert paper and paper[0].attribs == {"SYN_MA": "Giấy SYN"}


def test_cp1258_r2000_match_ezdxf(tmp_path):
    """DXF cũ (trước R2007) theo $DWGCODEPAGE: ANSI_1258 -> cp1258 cho tiếng Việt."""
    path = tmp_path / "edge_cp1258.dxf"
    doc = _edge_cases_doc("R2000")
    doc.encoding = "cp1258"  # ezdxf ghi $DWGCODEPAGE = ANSI_1258 và mã hoá tệp theo cp1258
    doc.saveas(path)
    assert "SYN-ĐƯƠNG".encode("cp1258") in path.read_bytes()  # tệp thật sự là cp1258, không phải UTF-8
    assert detect_header(path) == ("AC1015", "cp1258")
    assert_same_model(path)
    assert "SYN-ĐƯƠNG" in {la.name for la in read_dxf_stream(path).layers}


def test_geometry_and_content_fields_match_ezdxf(tmp_path):
    """Trường hình học/nội dung (pts, insert, rotation, xscale, yscale, text, pos, dim_value, radius) khớp ezdxf
    trên đủ loại DIMENSION, MTEXT nhiều khúc có mã định dạng, INSERT xoay/co giãn."""
    doc = ezdxf.new("R2018", setup=True)
    blk = doc.blocks.new("SYN-B")
    blk.add_line((0, 0), (1, 1))
    msp = doc.modelspace()
    msp.add_blockref("SYN-B", (12.34567, -8.5), dxfattribs={"rotation": 33.3, "xscale": 2.5, "yscale": -1.25})
    msp.add_mtext("{\\fArial|b1;Đậm} dòng 1\\Pdòng 2 " +"chữ dài SYN " * 40, dxfattribs={"insert": (3, 4)})
    msp.add_text("Chữ SYN", dxfattribs={"insert": (7.123456, 8.5)})
    msp.add_circle((1.5, 2.25), 3.125)
    msp.add_lwpolyline([(0, 0), (1.23456789, 0), (1, 1)])
    msp.add_linear_dim(base=(0, 5), p1=(0, 0), p2=(10, 3), angle=30).render()
    msp.add_aligned_dim(p1=(0, 0), p2=(7, 7), distance=2).render()
    msp.add_radius_dim(center=(20, 20), radius=4.5, angle=45).render()
    msp.add_diameter_dim(center=(30, 20), radius=2.75, angle=10).render()
    msp.add_angular_dim_2l(base=(5, 5), line1=((0, 0), (10, 0)), line2=((0, 0), (10, 10))).render()
    msp.add_angular_dim_3p(base=(5, 5), center=(0, 0), p1=(10, 0), p2=(0, 10)).render()
    msp.add_ordinate_x_dim(feature_location=(3, 4), offset=(2, 2)).render()
    path = tmp_path / "fields.dxf"
    doc.saveas(path)
    assert_same_model(path)
    ents = read_dxf_stream(path).entities
    dims = [e.dim_value for e in ents if e.type == "DIMENSION"]
    assert len(dims) == 7 and sum(v is not None for v in dims) == 6  # kích thước toạ độ: không có số đo vô hướng
    mtext = next(e for e in ents if e.type == "MTEXT")
    assert mtext.text.startswith("Đậm dòng 1\ndòng 2") and len(mtext.text) == 300
    ins = next(e for e in ents if e.type == "INSERT")
    assert (ins.insert, ins.rotation, ins.xscale, ins.yscale) == ((12.3457, -8.5), 33.3, 2.5, -1.25)


def test_bad_bytes_are_replaced_not_raised(tmp_path, synthetic):
    data = (synthetic / "ok_sheet.dxf").read_bytes()
    path = tmp_path / "bad_utf8.dxf"
    bad, n = re.subn(rb"(\r?\n)FN-ANNO-TEXT(\r?\n)", lambda mt: mt[1] + b"FN-ANNO-\xff\xfeTEXT" + mt[2], data, count=1)
    assert n == 1
    path.write_bytes(bad)  # byte không hợp lệ UTF-8 trong tên layer của tệp R2018
    m = read_dxf_stream(path)
    assert any(chr(0xFFFD) in la.name for la in m.layers)  # ký tự thay thế U+FFFD


def test_binary_dxf_is_rejected_in_vietnamese(tmp_path):
    path = tmp_path / "binary.dxf"
    ezdxf.new("R2018").saveas(path, fmt="bin")
    with pytest.raises(DXFStreamError, match="DXF nhị phân"):
        read_dxf_stream(path)


def test_broken_group_code_is_reported(tmp_path):
    path = tmp_path / "broken.dxf"
    path.write_text("  0\nSECTION\n  2\nENTITIES\nxx\nLINE\n  0\nENDSEC\n  0\nEOF\n", encoding="utf-8")
    with pytest.raises(DXFStreamError, match="mã nhóm không hợp lệ"):
        read_dxf_stream(path)


# ---- trần bộ nhớ


def test_max_entity_records_truncates_but_keeps_stats(small_large):
    path, _info = small_large
    full = read_dxf_stream(path)
    assert not full.stats.entity_records_truncated and len(full.entities) > 50
    capped = read_dxf_stream(path, max_entity_records=50)
    assert len(capped.entities) == 50 and capped.stats.entity_records_truncated
    assert capped.stats.modelspace == full.stats.modelspace and capped.stats.blocks == full.stats.blocks
    assert capped.blocks == full.blocks and capped.layers == full.layers
    assert [e.handle for e in capped.entities] == [e.handle for e in full.entities[:50]]
    none = read_dxf_stream(path, max_entity_records=0)
    assert none.entities == [] and none.stats.entity_records_truncated


def test_no_truncation_flag_when_under_cap(synthetic):
    m = read_dxf_stream(synthetic / "ok_sheet.dxf", max_entity_records=10_000)
    assert not m.stats.entity_records_truncated


# ---- không nạp trọn tệp


def test_source_never_loads_whole_file():
    src = (Path(__file__).resolve().parents[1] / "cadguard" / "dxf_stream.py").read_text(encoding="utf-8")
    assert "read_bytes(" not in src
    assert "readlines(" not in src
    assert not re.search(r"\.read\(\s*\)", src), "cấm .read() không giới hạn"
    assert "read_text(" not in src


# ---- CLI


def _cli_json(capsys, *args: str) -> tuple[int, dict, str]:
    code = main(["audit", *args, "--json", "--standards-dir", str(STANDARDS)])
    cap = capsys.readouterr()
    return code, json.loads(cap.out), cap.err


def _strip(rep: dict) -> list:
    return [(f["file"], f["file_hash"], f["counts"], f["findings"]) for f in rep["files"]]


def test_cli_reader_stream_on_fixture_dir(synthetic, capsys):
    code_s, rep_s, _ = _cli_json(capsys, str(synthetic), "--reader", "stream")
    code_e, rep_e, _ = _cli_json(capsys, str(synthetic), "--reader", "ezdxf")
    assert code_s == code_e == 1
    assert len(rep_s["files"]) == len(ALL_FIXTURES)  # thư mục được quét đệ quy, gồm cả scene/
    assert _strip(rep_s) == _strip(rep_e)


def test_cli_auto_switches_by_threshold(synthetic, capsys):
    ok = str(synthetic / "ok_sheet.dxf")
    _code, rep_small, err_small = _cli_json(capsys, ok, "--reader", "auto")
    assert "theo dòng" not in err_small  # tệp nhỏ: giữ đường ezdxf
    code, rep_stream, err = _cli_json(capsys, ok, "--reader", "auto", "--stream-threshold-mb", "0")
    assert code == 0 and "dùng bộ đọc theo dòng" in err
    assert _strip(rep_stream) == _strip(rep_small)


def test_cli_stream_reports_binary_in_vietnamese(tmp_path, capsys):
    path = tmp_path / "binary.dxf"
    ezdxf.new("R2018").saveas(path, fmt="bin")
    assert main(["audit", str(path), "--reader", "stream", "--standards-dir", str(STANDARDS)]) == 2
    assert "DXF nhị phân" in capsys.readouterr().err


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_choose_reader_rejects_non_finite_threshold(tmp_path, bad):
    from cadguard.reader_select import choose_reader

    path = tmp_path / "a.dxf"
    ezdxf.new().saveas(path)
    with pytest.raises(ValueError, match="hữu hạn"):
        choose_reader(path, "auto", bad)
    assert choose_reader(path, "auto", None).reason == "disabled"
    assert choose_reader(path, "auto", 0).reader == "stream"


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_cli_rejects_non_finite_threshold(tmp_path, capsys, bad):
    path = tmp_path / "a.dxf"
    ezdxf.new().saveas(path)
    code = main(["audit", str(path), f"--stream-threshold-mb={bad}", "--standards-dir", str(STANDARDS)])
    err = capsys.readouterr().err
    assert code == 2
    assert "--stream-threshold-mb" in err and "hữu hạn" in err


# ---- hiệu năng tệp rất lớn (chỉ chạy với -m slow)

MEASURE = r"""
import json, os, sys, time

def peak_rss_mb():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / 2**20
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024

from cadguard.dxf_stream import read_dxf_stream
t = time.perf_counter()
m = read_dxf_stream(sys.argv[1])
sec = time.perf_counter() - t
print(json.dumps({"seconds": round(sec, 2), "peak_rss_mb": round(peak_rss_mb(), 1),
                  "entity_records": len(m.entities), "modelspace": m.stats.modelspace.entities,
                  "blocks": m.stats.blocks.entities, "truncated": m.stats.entity_records_truncated}))
"""


@pytest.mark.slow
def test_large_100mb_stream_time_and_memory(tmp_path):
    path = tmp_path / "large_100.dxf"
    t = time.perf_counter()
    info = fixtures.make_large(path, target_mb=100)
    gen_s = time.perf_counter() - t
    assert info["bytes"] >= 100 * 1024 * 1024
    # Đo trong tiến trình con: RAM đỉnh (working set) không lẫn bộ nhớ của pytest và của bước sinh tệp.
    out = subprocess.run([sys.executable, "-c", MEASURE, str(path)], capture_output=True, text=True, check=True)
    r = json.loads(out.stdout.strip().splitlines()[-1])
    print(f"\n[large-dxf] MB={info['bytes'] / 2**20:.1f} sinh={gen_s:.1f}s doc={r['seconds']}s "
          f"ram_dinh={r['peak_rss_mb']}MB doi_tuong_mo_hinh={r['modelspace']} doi_tuong_khoi={r['blocks']} "
          f"ban_ghi={r['entity_records']} cat={r['truncated']}")
    assert r["modelspace"] == info["model_entities"] + 1  # +1 kích thước mẫu do ezdxf dựng trong khung tệp
    assert r["blocks"] >= info["block_entities"]
    assert r["peak_rss_mb"] < 1024, "RAM đỉnh phải < 1 GB"
    assert r["seconds"] < 120, "đọc 100 MB phải < 120 giây"
