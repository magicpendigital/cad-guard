"""`validate_output`: mở lại tệp ra và kiểm nó chỉ khác tệp gốc đúng như changeset cho phép.

Kiểm (mỗi mục có `id`, `ok`, `message` tiếng Việt):
1. `source_hash`  — tệp gốc còn đúng mã băm ghi trong changeset;
2. `entity_count` — tổng đối tượng hình học không đổi (không thêm, không xoá; chỉ nội dung khối bị purge được mất);
3. `allowed_attrs` — chỉ những thuộc tính mà các thao tác cho phép bị đổi;
4. `protected_layers` — đối tượng trên layer bảo vệ và định nghĩa layer bảo vệ không đổi;
5. `definitions` — định nghĩa chỉ thêm/xoá theo thao tác (đổi tên, gộp, purge);
6. `rules` — chạy lại luật (chuẩn + hồ sơ): `rules_regressed` = số luật mới xuất hiện hoặc tăng, phải = 0.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..dxf_reader import build_model
from ..runner import audit_model
from ..standard import Standard
from .diff import changed_attrs, diff_snapshots, sha256_file, snapshot, summary_vi
from .engine import Protection, read_doc
from .ops import PURGE_KINDS, allowed_attrs, allowed_data_types

MAX_LISTED = 20


def rule_counts(model, std: Standard) -> tuple[dict[str, int], list]:
    res = audit_model(model, std)
    counts: Counter = Counter()
    for f in res.findings:
        counts[f.rule_id] += max(1, int(f.count or 1))
    return dict(sorted(counts.items())), res.findings


def compare_rules(before: dict[str, int], after: dict[str, int]) -> dict:
    ids = sorted(set(before) | set(after))
    regressed = [r for r in ids if after.get(r, 0) > before.get(r, 0)]
    resolved = [r for r in ids if before.get(r, 0) > 0 and after.get(r, 0) == 0]
    improved = [r for r in ids if 0 < after.get(r, 0) < before.get(r, 0)]
    return {"before": before, "after": after, "resolved": resolved, "improved": improved,
            "regressed": regressed, "rules_regressed": len(regressed)}


def _allowed_defs(ops: list[Any]) -> dict[str, dict[str, set[str] | bool]]:
    """Định nghĩa được phép thêm/xoá theo thao tác: tên cụ thể, hoặc True = mọi tên (purge không giới hạn tên)."""
    allow: dict[str, dict[str, Any]] = {k: {"added": set(), "removed": set(), "changed": set()} for k in PURGE_KINDS}
    for o in ops:
        if o.op == "rename_layer":
            allow["layers"]["removed"].add(o.from_.casefold())
            allow["layers"]["added"].add(o.to.casefold())
        elif o.op == "merge_layers":
            allow["layers"]["removed"].update(x.casefold() for x in o.sources)
        elif o.op == "convert_unicode":
            # kiểu chữ phông cũ được trỏ sang phông Unicode (đổi) hoặc thêm kiểu "<tên>-UNICODE" khi chuyển một phần
            allow["text_styles"]["changed"] = True
            allow["text_styles"]["added"] = True
        elif o.op == "purge_unused":
            for kind in o.kinds:
                if o.names is None:
                    allow[kind]["removed"] = True
                elif allow[kind]["removed"] is not True:
                    allow[kind]["removed"].update(x.casefold() for x in o.names)
    return allow


def tolerated_rules(ops: list[Any]) -> set[str]:
    """Luật được phép tăng vì là tác dụng phụ đã biết, ghi rõ trong xem trước."""
    out: set[str] = set()
    for o in ops:
        if o.op == "convert_unicode" and o.handles:
            out.add("VS-02")  # chuyển một phần: thêm kiểu chữ "<tên>-UNICODE"
    return out


def _check(cid: str, ok: bool, msg_ok: str, msg_bad: str) -> dict:
    return {"id": cid, "ok": bool(ok), "message": msg_ok if ok else msg_bad}


def _names(xs: list[str]) -> str:
    shown = ", ".join(f"'{x}'" for x in xs[:MAX_LISTED])
    return shown + (f" và {len(xs) - MAX_LISTED} mục khác" if len(xs) > MAX_LISTED else "")


def evaluate(doc_a, doc_b, ops: list[Any], prot: Protection, std: Standard, source_hash_ok: bool | None = None,
             max_items: int = 50) -> dict:
    """So `doc_a` (gốc) với `doc_b` (kết quả) theo changeset; dùng cho cả chạy khô (propose) và validate_output."""
    sa, sb = snapshot(doc_a), snapshot(doc_b)
    d = diff_snapshots(sa, sb, max_items=None)
    checks = []
    if source_hash_ok is not None:
        checks.append(_check("source_hash", source_hash_ok, "Tệp gốc khớp mã băm trong changeset.",
                             "Tệp gốc KHÔNG khớp mã băm trong changeset (đã bị sửa sau khi đề xuất)."))

    purged_blocks = {x.casefold() for x in d["definitions"]["blocks"]["removed"]}
    removed = [e for e in d["entities"]["removed"] if not (e["space"].startswith("block:") and e["space"][6:].casefold() in purged_blocks)]
    added = d["entities"]["added"]
    by_type_a = Counter(s.type for s in sa["entities"].values() if not s.space.startswith("block:"))
    by_type_b = Counter(s.type for s in sb["entities"].values() if not s.space.startswith("block:"))
    count_ok = not removed and not added and by_type_a == by_type_b
    checks.append(_check(
        "entity_count", count_ok,
        f"Tổng đối tượng hình học không đổi ({sum(by_type_a.values())} trong không gian mô hình/giấy).",
        f"Số đối tượng thay đổi: {len(added)} thêm, {len(removed)} xoá "
        f"({sum(by_type_a.values())} → {sum(by_type_b.values())} trong không gian mô hình/giấy)."))

    allowed = allowed_attrs(ops)
    data_types = allowed_data_types(ops)
    bad_attrs: Counter = Counter()
    bad_handles: list[str] = []
    touched_protected: list[str] = []
    for item in d["entities"]["changed"]:
        attrs = set(item["attrs"])
        extra = attrs - allowed
        if extra == {"data"} and item["type"] in data_types:
            extra = set()
        if extra or item.get("type_after"):
            bad_attrs.update(extra or {"type"})
            bad_handles.append(item["handle"])
        layer_after = item["attrs"].get("layer", [None, item["layer"]])[1]
        if prot.is_protected(item["layer"]) or prot.is_protected(layer_after):
            touched_protected.append(item["handle"])
    checks.append(_check(
        "allowed_attrs", not bad_attrs,
        "Chỉ những thuộc tính thao tác cho phép bị đổi" + (f" ({', '.join(sorted(allowed))})." if allowed else "."),
        "Có thuộc tính bị đổi ngoài phạm vi thao tác: " + ", ".join(f"{k} ×{v}" for k, v in sorted(bad_attrs.items()))
        + f" (handle {', '.join(bad_handles[:MAX_LISTED])})."))

    prot_defs = [name for key, (name, _tags) in sa["defs"]["layers"].items() if prot.is_protected(name)]
    prot_def_bad = [name for name in prot_defs if sa["defs"]["layers"][name.casefold()] != sb["defs"]["layers"].get(name.casefold())]
    prot_removed = [e["handle"] for e in d["entities"]["removed"] if prot.is_protected(e["layer"])]
    prot_ok = not touched_protected and not prot_def_bad and not prot_removed
    checks.append(_check(
        "protected_layers", prot_ok,
        f"Layer bảo vệ không đổi ({len(prot_defs)} layer)." if prot_defs else "Không có layer bảo vệ trong bản vẽ.",
        "Layer bảo vệ bị chạm: " + "; ".join(x for x in (
            f"{len(touched_protected)} đối tượng đổi (handle {', '.join(touched_protected[:MAX_LISTED])})" if touched_protected else "",
            f"định nghĩa đổi/xoá {_names(prot_def_bad)}" if prot_def_bad else "",
            f"{len(prot_removed)} đối tượng mất" if prot_removed else "") if x) + "."))

    allow = _allowed_defs(ops)
    bad_defs = []
    for kind in PURGE_KINDS:
        for key in ("added", "removed"):
            rule = allow[kind][key]
            for name in d["definitions"][kind][key]:
                if rule is True or name.casefold() in rule:
                    continue
                bad_defs.append(f"{kind}.{key}:{name}")
        for name in d["definitions"][kind]["changed"]:
            rule = allow[kind]["changed"]
            if rule is True or name.casefold() in rule:
                continue
            bad_defs.append(f"{kind}.changed:{name}")
    checks.append(_check("definitions", not bad_defs, "Định nghĩa chỉ thêm/xoá đúng theo thao tác.",
                         "Định nghĩa đổi ngoài phạm vi thao tác: " + ", ".join(bad_defs[:MAX_LISTED]) + "."))

    before, findings_a = rule_counts(build_model(doc_a), std)
    after, findings_b = rule_counts(build_model(doc_b), std)
    rules = compare_rules(before, after)
    tolerated = sorted(set(rules["regressed"]) & tolerated_rules(ops))
    if tolerated:  # tác dụng phụ đã biết của thao tác (vd. thêm kiểu chữ "-UNICODE" làm VS-02 tăng): báo, không chặn
        rules["regressed"] = [r for r in rules["regressed"] if r not in tolerated]
        rules["rules_regressed"] = len(rules["regressed"])
        rules["tolerated"] = tolerated
    checks.append(_check(
        "rules", rules["rules_regressed"] == 0,
        f"Không luật nào xuất hiện mới hoặc tăng (chuẩn {std.name} {std.version}); hết: {', '.join(rules['resolved']) or 'không'}."
        + (f" Chấp nhận tăng theo thao tác: {', '.join(tolerated)}." if tolerated else ""),
        f"{rules['rules_regressed']} luật xuất hiện mới hoặc tăng: {', '.join(rules['regressed'])}."))

    ok = all(c["ok"] for c in checks)
    small = diff_snapshots(sa, sb, max_items=max_items)
    return {
        "ok": ok,
        "checks": checks,
        "rules": rules,
        "rules_regressed": rules["rules_regressed"],
        "findings_after": [{"rule_id": f.rule_id, "severity": f.severity, "message": f.message, "count": f.count}
                           for f in findings_b[:max_items]],
        "diff": small,
        "diff_summary_vi": summary_vi(small),
        "standard": std.name,
        "standard_version": std.version,
        "profile": std.profile,
        "summary_vi": summary_text(ok, rules, checks),
    }


def summary_text(ok: bool, rules: dict, checks: list[dict]) -> str:
    head = "ĐẠT: tệp ra chỉ đổi đúng phạm vi changeset" if ok else "KHÔNG ĐẠT: " + "; ".join(
        c["id"] for c in checks if not c["ok"])
    return (f"{head}. Luật hết: {len(rules['resolved'])} ({', '.join(rules['resolved']) or '—'}); "
            f"giảm: {len(rules['improved'])}; xuất hiện mới/tăng: {rules['rules_regressed']}.")


def validate_output(original, output, ops: list[Any], prot: Protection, std: Standard,
                    source_sha256: str | None = None, max_items: int = 50) -> dict:
    """Mở lại hai tệp và kiểm. `source_sha256` (từ changeset) để kiểm tệp gốc chưa bị sửa."""
    ok_hash = None if source_sha256 is None else sha256_file(original) == source_sha256
    res = evaluate(read_doc(original), read_doc(output), ops, prot, std, ok_hash, max_items)
    res["output_sha256"] = sha256_file(output)
    return res
