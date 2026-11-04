"""Người trả lời THAM CHIẾU cho bộ chấm: gọi thẳng các hàm công cụ trong `cadguard.agent.tools`, tất định.

Đây là "trợ lý hoàn hảo" dùng chính 5 công cụ chỉ đọc mà máy chủ MCP đưa cho trợ lý thật, nên:
- bộ chấm phải đạt 100% với người trả lời này (nếu không: tác vụ hoặc đáp án sai, hoặc công cụ đã đổi hành vi);
- mỗi hàm `_dang_*` là bản mẫu "trợ lý nên gọi công cụ nào, đọc trường nào" cho skill trong `knowledge/skills/`.

Hồ sơ công ty: tác vụ có `moi_truong.ho_so` thì ngữ cảnh mang `profile` (như máy chủ khởi động với
`python -m cadguard mcp --profile <tệp>`); công cụ `audit`/`explain_rule` tự áp hồ sơ khi gọi đúng chuẩn của hồ sơ
và ghi `profile: {name, version}` vào kết quả. Không gọi LLM, không gọi mạng.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

from cadguard.agent import tools
from cadguard.agent.anonymize import Anonymizer
from cadguard.agent.workspace import Workspace
from cadguard.dxf_stream import DEFAULT_MAX_ENTITY_RECORDS
from cadguard.reader_select import DEFAULT_STREAM_THRESHOLD_MB
from cadguard.standard import find_standards_dir, load_profile

PROFILE_FILE = "ho-so.yaml"


def make_context(task: dict, workspace: Path) -> tools.ToolContext:
    """Dựng ngữ cảnh công cụ giống `python -m cadguard mcp` với các cờ trong `moi_truong` của tác vụ."""
    env = task.get("moi_truong") or {}
    workspace = Path(workspace)
    return tools.ToolContext(
        Workspace(workspace),
        Anonymizer(enabled=env.get("an_danh", True)),  # mặc định ẩn danh Bậc 1, như máy chủ MCP
        find_standards_dir(Path(__file__).resolve()),
        stream_threshold_mb=env.get("stream_threshold_mb", DEFAULT_STREAM_THRESHOLD_MB),
        max_entity_records=env.get("max_entity_records", DEFAULT_MAX_ENTITY_RECORDS),
        profile=load_profile(workspace / PROFILE_FILE) if env.get("ho_so") else None,  # như cờ --profile
    )


def _only_file(ctx: tools.ToolContext) -> str:
    drawings = tools.list_drawings(ctx)["drawings"]
    if len(drawings) != 1:
        raise ValueError("tác vụ cần đúng một bản vẽ trong thư mục làm việc")
    return drawings[0]["id"]


def _rule_ids(findings: list[dict], severity: str | None = None) -> list[str]:
    return sorted({f["rule_id"] for f in findings if severity is None or f["severity"] == severity})


def _standard(task: dict) -> str:
    return (task.get("tham_so") or {}).get("chuan", "furniture-v0")


# ---------- mỗi dạng tác vụ ----------


def _dang_dem_loi(task, ctx):
    res = tools.audit(ctx, _only_file(ctx), _standard(task))
    return {"so_loi_e": res["counts"]["E"], "ma_luat_e": _rule_ids(res["findings"], "E"),
            "records_capped": res["records_capped"]}


def _dang_tap_ma_luat(task, ctx):
    res = tools.audit(ctx, _only_file(ctx), _standard(task))
    return {"ma_luat": _rule_ids(res["findings"]), "so_luat_da_chay": res["rules_run"]}


def _dang_layer_du_xref(task, ctx):
    res = tools.audit(ctx, _only_file(ctx), "design-hygiene-v0")
    hits = [f for f in res["findings"] if f["rule_id"] == "VS-01"]
    return {"so_layer_du_xref": sum(f["count"] for f in hits), "ma_luat": "VS-01",
            "thong_diep": [f["message"] for f in hits]}


def _dang_kich_thuoc_ghi_de(task, ctx):
    file = _only_file(ctx)
    items, cursor = [], None
    while True:  # đi hết các trang của query_model
        page = tools.query_model(ctx, file, {"type": "DIMENSION"}, 500, cursor)
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    return {"tong_kich_thuoc": len(items), "so_ghi_de": sum(i["dim_text_overridden"] for i in items),
            "records_capped": page["records_capped"]}


def _dang_xac_nhan_sach(task, ctx):
    res = tools.audit(ctx, _only_file(ctx), _standard(task))
    clean = not res["findings"] and not res["skipped"] and not res["records_capped"]
    return {"sach": clean, "so_phat_hien": len(res["findings"]), "so_luat_da_chay": res["rules_run"],
            "so_luat_bo_qua": len(res["skipped"])}


def _dang_ho_so(task, ctx):
    file = _only_file(ctx)
    name = _standard(task)
    # "Trước" = máy chủ không có --profile; "sau" = máy chủ của phiên (có --profile). Cả hai đều qua công cụ audit.
    plain = tools.audit(dataclasses.replace(ctx, profile=None), file, name)
    with_profile = tools.audit(ctx, file, name)
    before, after = _rule_ids(plain["findings"]), _rule_ids(with_profile["findings"])
    return {"truoc": before, "sau": after, "mat_di": sorted(set(before) - set(after)),
            "them_moi": sorted(set(after) - set(before)), "ho_so": with_profile["profile"],
            "ho_so_truoc": plain["profile"]}


def _dang_records_capped(task, ctx):
    file = _only_file(ctx)
    res = tools.audit(ctx, file, _standard(task))
    summary = tools.get_model_summary(ctx, file)
    capped = res["records_capped"] or summary["records_capped"]
    note = ("Bản vẽ rất lớn: danh sách đối tượng đã bị cắt ở trần bộ nhớ, số đối tượng và phát hiện có thể thiếu."
            if capped else "")
    return {"records_capped": capped, "canh_bao_du_lieu": note}


def _dang_ban_giao(task, ctx):
    params = task.get("tham_so") or {}
    file = _only_file(ctx)
    res = tools.audit(ctx, file, _standard(task))
    summary = tools.get_model_summary(ctx, file)
    accepted = set(params.get("chap_nhan", []))
    errors = Counter(f["rule_id"] for f in res["findings"] if f["severity"] == "E")
    warns = _rule_ids(res["findings"], "W")
    remaining = [r for r in warns if r not in accepted]
    capped = res["records_capped"] or summary["records_capped"]
    ready = not errors and not remaining and not capped
    todo = [f"Sửa {rule} ({n} phát hiện) trước khi chuyển" for rule, n in sorted(errors.items())]
    todo += [f"Xử lý hoặc xin {params.get('den_phong', 'phòng nhận')} chấp nhận cảnh báo {rule}" for rule in remaining]
    return {
        "tu_phong": params.get("tu_phong"),
        "den_phong": params.get("den_phong"),
        "nguoi_nhan": f"Phòng {params.get('den_phong')}",
        "ban_ve": file,
        "chuan": res["standard"],
        "phien_ban_chuan": res["version"],
        "so_loi_e": res["counts"]["E"],
        "ma_loi_e": sorted(errors),
        "canh_bao_chap_nhan": sorted(accepted & set(warns)),
        "canh_bao_con_lai": remaining,
        "luat_bo_qua": [s["rule_id"] for s in res["skipped"]],
        "records_capped": capped,
        "san_sang_ban_giao": ready,
        "viec_can_lam": todo,
    }


def _dang_luat_bo_qua(task, ctx):
    res = tools.audit(ctx, _only_file(ctx), _standard(task))
    return {"luat_bo_qua": [s["rule_id"] for s in res["skipped"]], "ly_do": [s["reason"] for s in res["skipped"]],
            "so_luat_da_chay": res["rules_run"]}


def _dang_giai_thich_luat(task, ctx):
    params = task.get("tham_so") or {}
    info = tools.explain_rule(ctx, params["ma_luat"], _standard(task))
    return {"ma_luat": info["id"], "muc_do": info["severity"], "loai": info["kind"], "tieu_de": info["title"],
            "nguon": info["source"], "da_cai": info["implemented"]}


def _dang_tom_tat(task, ctx):
    s = tools.get_model_summary(ctx, _only_file(ctx))
    return {"so_layer": s["layer_count"], "so_doi_tuong": sum(s["entities_by_space"].values()),
            "so_layout": len(s["layouts"]), "insunits": s["insunits"], "phien_ban_dxf": s["dxf_version"],
            "loai_nhieu_nhat": next(iter(s["entities_by_type"]), None), "records_capped": s["records_capped"]}


HANDLERS = {
    "dem_loi": _dang_dem_loi,
    "tap_ma_luat": _dang_tap_ma_luat,
    "layer_du_xref": _dang_layer_du_xref,
    "kich_thuoc_ghi_de": _dang_kich_thuoc_ghi_de,
    "xac_nhan_sach": _dang_xac_nhan_sach,
    "ho_so_cong_ty": _dang_ho_so,
    "records_capped": _dang_records_capped,
    "ghi_chu_ban_giao": _dang_ban_giao,
    "luat_bo_qua": _dang_luat_bo_qua,
    "giai_thich_luat": _dang_giai_thich_luat,
    "tom_tat_mo_hinh": _dang_tom_tat,
}


def answer(task: dict, workspace: Path) -> dict:
    """Điểm vào cho `scripts/bench.py`. Chi phí của tham chiếu luôn bằng 0."""
    handler = HANDLERS.get(task["dang"])
    if handler is None:
        raise ValueError(f"tham chiếu chưa biết dạng tác vụ '{task['dang']}'")
    result = handler(task, make_context(task, Path(workspace)))
    result["_chi_phi"] = {"tokens": 0, "usd": 0.0}
    return result
