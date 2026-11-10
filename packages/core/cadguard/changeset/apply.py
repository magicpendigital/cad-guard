"""Changeset `cg.changeset/1`: đề xuất (chạy khô) → người xác nhận → áp dụng ra TỆP MỚI → kiểm → hoàn tác.

- `propose`: đọc bản sao trong bộ nhớ, kiểm schema, chạy thao tác, dự báo luật hết/xuất hiện, lưu changeset JSON
  vào `<thư mục làm việc>/.cadguard/changesets/<id>.json`. KHÔNG ghi DXF.
- `apply`: cần `confirm=True`; kiểm mã băm nguồn, áp lại thao tác lên bản sao, ghi tạm, `validate_output`,
  đạt mới tạo `<tên>.cg-<id ngắn>.dxf` (tạo độc quyền: tên đã có thì từ chối, không ghi đè), ghi nhật ký JSON.
- `undo`: xoá đúng tệp mới mà nhật ký ghi (mã băm phải khớp). Tệp gốc không bao giờ bị ghi.
Changeset và nhật ký chỉ chứa đường dẫn TƯƠNG ĐỐI trong thư mục làm việc.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..agent.workspace import PathDenied, Workspace
from ..standard import CompanyProfile, Standard, load_standard
from .diff import sha256_file
from .engine import Protection, read_doc, run_ops
from .ops import OpError, dump_ops, parse_ops
from .validate import evaluate, validate_output

SCHEMA = "cg.changeset/1"
LOG_SCHEMA = "cg.changeset-apply/1"
STORE_DIR = ".cadguard/changesets"
ID_RE = re.compile(r"^cs-[0-9a-f]{12}$")
DEFAULT_STANDARD = "design-hygiene-v0"


class ChangesetError(ValueError):
    """Lỗi quy trình changeset (tiếng Việt, không đường dẫn tuyệt đối)."""


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str  # tương đối trong thư mục làm việc, dạng posix
    sha256: str


class ProtectionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layers: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)


class Changeset(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_id: str = Field(default=SCHEMA, alias="schema")
    id: str
    source: SourceRef
    standard: str
    standard_version: str
    profile: dict[str, str] | None = None
    protection: ProtectionRef = Field(default_factory=ProtectionRef)
    ops: list[dict[str, Any]]
    created_by: Literal["agent", "user"]
    created_at: str
    preview: dict[str, Any] | None = None

    def dump(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def short_id(cid: str) -> str:
    return cid[3:11]


def store_dir(ws: Workspace) -> Path:
    return ws.root / STORE_DIR


def _write_json_new(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _rel(ws: Workspace, path: Path) -> str:
    return path.resolve().relative_to(ws.root).as_posix()


def load_std(standard: str, standards_dir: Path | None, profile: CompanyProfile | None,
             workspace: Path | None = None) -> Standard:
    if not isinstance(standard, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.\-]*", standard):
        raise ChangesetError("Tên chuẩn không hợp lệ.")
    use = profile if profile is not None and profile.standard == standard else None
    try:
        if workspace is not None:  # cài đặt luật + template của dự án (rule_config): cùng số với App/CLI/MCP
            from ..rule_config import effective_standard

            return effective_standard(standard, standards_dir, profile=use, workspace=workspace)
        return load_standard(standard, standards_dir, profile=use)
    except FileNotFoundError:
        raise ChangesetError(f"Không có chuẩn '{standard}'.") from None


def protection_for(protected_layers: list[str] | None, profile: CompanyProfile | None) -> Protection:
    layers = [str(x) for x in (protected_layers or []) if str(x)]
    patterns = list(getattr(profile.layer_patterns, "protected", None) or []) if profile is not None else []
    return Protection(layers=layers, patterns=patterns)


def preview_of(cs: Changeset, reports: list[dict], ev: dict) -> dict:
    return {
        "changeset_id": cs.id,
        "source": cs.source.model_dump(),
        "standard": ev["standard"],
        "standard_version": ev["standard_version"],
        "profile": ev["profile"],
        "protection": cs.protection.model_dump(),
        "ops": reports,
        "diff": ev["diff"]["summary"],
        "definitions": ev["diff"]["definitions"],
        "diff_summary_vi": ev["diff_summary_vi"],
        "rules": ev["rules"],
        "rules_regressed": ev["rules_regressed"],
        "findings_after": ev["findings_after"],
        "checks": ev["checks"],
        "ok": ev["ok"],
        "summary_vi": ev["summary_vi"],
    }


def propose(ws: Workspace, file: str, ops_data: Any, *, standard: str = DEFAULT_STANDARD,
            standards_dir: Path | None = None, profile: CompanyProfile | None = None,
            protected_layers: list[str] | None = None, created_by: str = "user", ops: list | None = None) -> tuple[Changeset, dict]:
    """Chạy khô và lưu changeset. `ops` (đã kiểm) dùng thay `ops_data` khi người gọi đã tự kiểm/giải mã."""
    path = ws.resolve(file)
    ops = ops if ops is not None else parse_ops(ops_data)
    std = load_std(standard, standards_dir, profile, ws.root)
    prot = protection_for(protected_layers, profile)
    sha = sha256_file(path)
    before, after = read_doc(path), read_doc(path)
    reports = run_ops(after, ops, prot)
    ev = evaluate(before, after, ops, prot, std)
    cid = "cs-" + secrets.token_hex(6)
    cs = Changeset(id=cid, source=SourceRef(path=_rel(ws, path), sha256=sha), standard=std.name,
                   standard_version=std.version, profile=std.profile,
                   protection=ProtectionRef(**prot.to_dict()), ops=dump_ops(ops), created_by=created_by,
                   created_at=_now())
    preview = preview_of(cs, reports, ev)
    cs.preview = preview
    _write_json_new(store_dir(ws) / f"{cid}.json", cs.dump())
    return cs, preview


def resolve_changeset_path(ws: Workspace, ref: str) -> Path:
    """Nhận mã `cs-…` (tìm trong kho của thư mục làm việc) hoặc đường dẫn tệp JSON nằm trong kho đó."""
    if ID_RE.fullmatch(ref or ""):
        path = store_dir(ws) / f"{ref}.json"
    else:
        path = Path(ref)
        if not path.is_absolute():
            path = Path.cwd() / path
    try:
        path = path.resolve(strict=True)
    except OSError:
        raise ChangesetError("Không tìm thấy changeset.") from None
    if not path.is_relative_to(store_dir(ws).resolve()) or not ID_RE.fullmatch(path.stem):
        raise ChangesetError(f"Changeset phải nằm trong thư mục {STORE_DIR} của thư mục làm việc.")
    return path


def load_changeset(path: Path) -> Changeset:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cs = Changeset.model_validate(data)
    except (OSError, ValueError, ValidationError):
        raise ChangesetError("Tệp changeset hỏng hoặc sai định dạng.") from None
    if cs.schema_id != SCHEMA or not ID_RE.fullmatch(cs.id) or cs.id != path.stem:
        raise ChangesetError(f"Changeset sai định dạng (cần schema {SCHEMA}, mã khớp tên tệp).")
    return cs


def workspace_of(changeset_path: str | Path) -> Workspace:
    """Thư mục làm việc suy ra từ đường dẫn `<ws>/.cadguard/changesets/<id>.json`."""
    p = Path(changeset_path).resolve()
    if p.parent.name != "changesets" or p.parent.parent.name != ".cadguard":
        raise ChangesetError(f"Không suy ra được thư mục làm việc: changeset phải nằm trong {STORE_DIR}.")
    return Workspace(p.parents[2])


def output_path(ws: Workspace, cs: Changeset, src: Path, out_dir: str | None) -> Path:
    base = src.parent
    if out_dir:
        try:
            base = ws._resolve(out_dir)
        except PathDenied:
            raise ChangesetError("Thư mục đầu ra phải là thư mục tương đối, đã tồn tại, trong thư mục làm việc.") from None
        if not base.is_dir():
            raise ChangesetError("Thư mục đầu ra phải là thư mục.")
    return base / f"{src.stem}.cg-{short_id(cs.id)}.dxf"


def check_profile(cs: Changeset, profile: CompanyProfile | None) -> None:
    if cs.profile is None or "name" not in cs.profile:  # chỉ cài đặt luật của dự án/máy, không hồ sơ công ty
        return
    if profile is None or {"name": profile.name, "version": profile.version} != {
            "name": cs.profile.get("name"), "version": cs.profile.get("version")}:
        raise ChangesetError(f"Changeset được đề xuất với hồ sơ công ty '{cs.profile.get('name')}' "
                             f"{cs.profile.get('version')}; hãy áp dụng với đúng hồ sơ đó (--profile).")


def load_for_apply(ws: Workspace, ref: str, profile: CompanyProfile | None, standards_dir: Path | None):
    """Nạp changeset + kiểm mọi điều kiện trước khi áp. Trả (changeset, ops, chuẩn, bảo vệ, tệp nguồn)."""
    cs = load_changeset(resolve_changeset_path(ws, ref))
    check_profile(cs, profile)
    try:
        src = ws.resolve(cs.source.path)
    except PathDenied:
        raise ChangesetError("Không tìm thấy tệp gốc của changeset trong thư mục làm việc.") from None
    if sha256_file(src) != cs.source.sha256:
        raise ChangesetError("Tệp gốc đã thay đổi sau khi đề xuất (mã băm không khớp): từ chối áp dụng. "
                             "Hãy đề xuất lại changeset trên tệp hiện tại.")
    ops = parse_ops(cs.ops)
    std = load_std(cs.standard, standards_dir, profile, ws.root)
    if std.version != cs.standard_version:
        raise ChangesetError(f"Changeset viết cho {cs.standard} {cs.standard_version}, chuẩn hiện có là {std.version}.")
    prot = Protection(**cs.protection.model_dump())
    return cs, ops, std, prot, src


def apply(ws: Workspace, ref: str, *, confirm: bool = False, out_dir: str | None = None,
          profile: CompanyProfile | None = None, standards_dir: Path | None = None) -> dict:
    """Áp changeset ra TỆP MỚI. Không xác nhận, nguồn đổi, tên ra đã có, hoặc kiểm không đạt -> ChangesetError."""
    if not confirm:
        raise ChangesetError("Cần người dùng xác nhận trước khi áp dụng changeset.")
    cs, ops, std, prot, src = load_for_apply(ws, ref, profile, standards_dir)
    out = output_path(ws, cs, src, out_dir)
    log_path = store_dir(ws) / f"{cs.id}.apply.json"
    if out.exists() or log_path.exists():
        raise ChangesetError(f"Tệp ra '{out.name}' hoặc nhật ký áp dụng của changeset này đã có: không ghi đè. "
                             "Mỗi changeset chỉ áp một lần; muốn làm lại thì đề xuất changeset mới.")
    doc = read_doc(src)
    reports = run_ops(doc, ops, prot)
    tmp = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    try:
        doc.saveas(tmp)
        res = validate_output(src, tmp, ops, prot, std, cs.source.sha256)
        if not res["ok"]:
            raise ChangesetError("Kiểm tệp ra KHÔNG ĐẠT, không tạo tệp mới: " + "; ".join(
                c["message"] for c in res["checks"] if not c["ok"]))
        data = tmp.read_bytes()
        try:
            with open(out, "xb") as f:  # tạo độc quyền: không bao giờ ghi đè
                f.write(data)
        except FileExistsError:
            raise ChangesetError(f"Tệp ra '{out.name}' đã có: không ghi đè.") from None
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    if sha256_file(src) != cs.source.sha256:  # phòng thủ: gốc không bao giờ được đổi
        raise ChangesetError("Tệp gốc thay đổi trong lúc áp dụng; hãy kiểm tra lại.")
    out_sha = sha256_file(out)
    log = {
        "schema": LOG_SCHEMA,
        "changeset_id": cs.id,
        "applied_at": _now(),
        "applied_by": "user",
        "source": {"path": cs.source.path, "sha256": cs.source.sha256},
        "output": {"path": _rel(ws, out), "sha256": out_sha},
        "ops": reports,
        "validation": {"ok": res["ok"], "checks": res["checks"], "rules": res["rules"],
                       "rules_regressed": res["rules_regressed"], "summary_vi": res["summary_vi"]},
        "undone_at": None,
    }
    _write_json_new(log_path, log)
    return {**log, "log": _rel(ws, log_path), "diff_summary_vi": res["diff_summary_vi"]}


def undo(ws: Workspace, ref: str, *, confirm: bool = False) -> dict:
    """Hoàn tác = xoá tệp mới mà nhật ký ghi; chỉ khi mã băm còn khớp (tệp ra chưa bị ai sửa)."""
    if not confirm:
        raise ChangesetError("Cần người dùng xác nhận trước khi hoàn tác.")
    cs = load_changeset(resolve_changeset_path(ws, ref))
    log_path = store_dir(ws) / f"{cs.id}.apply.json"
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ChangesetError("Changeset chưa được áp dụng (không có nhật ký).") from None
    if log.get("undone_at"):
        raise ChangesetError("Changeset này đã được hoàn tác.")
    try:
        out = ws.resolve(log["output"]["path"])
    except (PathDenied, KeyError, TypeError):
        raise ChangesetError("Không tìm thấy tệp ra trong thư mục làm việc.") from None
    if sha256_file(out) != log["output"]["sha256"]:
        raise ChangesetError("Tệp ra đã bị sửa sau khi áp dụng (mã băm khác): không xoá. Hãy tự xử lý tệp này.")
    os.remove(out)
    log["undone_at"] = _now()
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, log_path)
    return {"changeset_id": cs.id, "removed": log["output"]["path"], "undone_at": log["undone_at"]}


__all__ = ["Changeset", "ChangesetError", "OpError", "apply", "load_changeset", "propose", "undo", "workspace_of"]
