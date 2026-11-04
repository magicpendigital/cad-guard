"""Nạp chuẩn trình bày (standards/<tên>.yaml): tham số chung + danh mục luật có phiên bản.

Hồ sơ công ty (`cg.company-profile/1`, ví dụ `standards/company-profile.example.yaml`) ghi đè tham số luật,
mẫu tên layer và tắt luật cho một công ty, KHÔNG sửa tệp chuẩn: `load_standard(..., profile=...)`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    reads: str = ""
    kind: str  # deterministic | heuristic
    severity: str  # E | W | I
    false_positive_risk: str  # low | medium | high
    source: str = ""
    implemented: bool = False
    enabled: bool = True
    realtime_ok: bool = False
    params: dict[str, Any] = Field(default_factory=dict)  # tham số của luật (giá trị mặc định); hồ sơ công ty ghi đè được


class Standard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    description: str = ""
    globals: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleSpec]
    profile: dict[str, str] | None = None  # hồ sơ công ty đã áp (tên, phiên bản); None = mặc định của chuẩn

    def rule(self, rule_id: str) -> RuleSpec | None:
        return next((r for r in self.rules if r.id == rule_id), None)


def find_standards_dir(start: Path | None = None) -> Path:
    env = os.environ.get("CADGUARD_STANDARDS")
    if env:
        return Path(env)
    for base in [start or Path.cwd(), Path(__file__).resolve()]:
        for d in [base, *base.parents]:
            cand = d / "standards"
            if cand.is_dir() and any(cand.glob("*.yaml")):
                return cand
    raise FileNotFoundError("Không tìm thấy thư mục standards/ (đặt CADGUARD_STANDARDS hoặc chạy trong repo cad-guard).")


def load_standard(name: str, standards_dir: Path | None = None,
                  profile: CompanyProfile | str | Path | None = None) -> Standard:
    """Nạp chuẩn; nếu có `profile` (đối tượng hoặc đường dẫn tệp) thì áp hồ sơ công ty lên một bản sao."""
    d = standards_dir or find_standards_dir()
    path = d / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Không có chuẩn '{name}' ({path}).")
    std = Standard.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if profile is not None:
        prof = profile if isinstance(profile, CompanyProfile) else load_profile(profile)
        std = apply_profile(std, prof)
    return std


# ---- Hồ sơ công ty

PROFILE_SCHEMA = "cg.company-profile/1"
# Khoá trong `layer_patterns` của hồ sơ -> khoá `globals` của chuẩn mà nó thay thế.
LAYER_PATTERN_GLOBALS = {"allowed": "allowed_layer_patterns", "exempt": "exempt_layer_patterns"}


class ProfileError(ValueError):
    """Hồ sơ công ty sai. Thông điệp tiếng Việt, chỉ nêu tên tệp (không đường dẫn đầy đủ)."""


class LayerPatterns(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: list[str] | None = None
    exempt: list[str] | None = None


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_id: str = Field(alias="schema")
    name: str
    version: str
    standard: str
    standard_version: str | None = None
    description: str = ""
    layer_patterns: LayerPatterns = Field(default_factory=LayerPatterns)
    overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    disabled: list[str] = Field(default_factory=list)


def _pydantic_msg(exc: Exception) -> str:
    errs = getattr(exc, "errors", None)
    if not callable(errs):
        return str(exc)
    out = []
    for e in errs():
        loc = ".".join(str(x) for x in e.get("loc", ())) or "(gốc)"
        kind = e.get("type", "")
        if kind == "extra_forbidden":
            out.append(f"trường lạ '{loc}'")
        elif kind == "missing":
            out.append(f"thiếu trường bắt buộc '{loc}'")
        else:
            out.append(f"trường '{loc}' sai kiểu")
    return "; ".join(out)


def load_profile(path: str | Path) -> CompanyProfile:
    p = Path(path)
    if not p.is_file():
        raise ProfileError(f"Không thấy tệp hồ sơ công ty '{p.name}'.")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ProfileError(f"Hồ sơ công ty '{p.name}' không phải YAML hợp lệ ({type(exc).__name__}).") from None
    if not isinstance(data, dict):
        raise ProfileError(f"Hồ sơ công ty '{p.name}' phải là một bảng khoá–giá trị YAML.")
    try:
        prof = CompanyProfile.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - ValidationError của pydantic
        raise ProfileError(f"Hồ sơ công ty '{p.name}' sai: {_pydantic_msg(exc)}.") from None
    if prof.schema_id != PROFILE_SCHEMA:
        raise ProfileError(f"Hồ sơ công ty '{p.name}': schema phải là '{PROFILE_SCHEMA}', đang là '{prof.schema_id}'.")
    return prof


def _type_name(v: Any) -> str:
    if isinstance(v, bool):
        return "đúng/sai (true/false)"
    if isinstance(v, int):
        return "số nguyên"
    if isinstance(v, float):
        return "số"
    if isinstance(v, list):
        return "danh sách"
    if isinstance(v, dict):
        return "bảng"
    return "chuỗi" if isinstance(v, str) else type(v).__name__


def _check_patterns(where: str, value: Any) -> None:
    if not isinstance(value, list):
        raise ProfileError(f"{where}: phải là danh sách mẫu (chuỗi biểu thức chính quy).")
    for pat in value:
        if not isinstance(pat, str):
            raise ProfileError(f"{where}: mỗi mẫu phải là chuỗi, gặp {_type_name(pat)}.")
        try:
            re.compile(pat)
        except re.error as exc:
            raise ProfileError(f"{where}: mẫu '{pat}' không phải biểu thức chính quy hợp lệ ({exc}).") from None


def _coerce_param(where: str, name: str, default: Any, value: Any) -> Any:
    """Kiểu của giá trị ghi đè phải khớp kiểu của giá trị mặc định trong chuẩn."""
    bad = ProfileError(f"{where}: tham số '{name}' phải là {_type_name(default)}, gặp {_type_name(value)} ({value!r}).")
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise bad
        return value
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise bad
        if isinstance(default, int) and not isinstance(value, int):
            raise bad
        if value < 0:
            raise ProfileError(f"{where}: tham số '{name}' không được âm ({value}).")
        if name.endswith("_ratio") and value > 1:
            raise ProfileError(f"{where}: tham số '{name}' là tỉ lệ, phải nằm trong khoảng 0–1 ({value}).")
        return float(value) if isinstance(default, float) else value
    if isinstance(default, list):
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ProfileError(f"{where}: tham số '{name}' phải là danh sách chuỗi.")
        if name.endswith("_patterns"):
            _check_patterns(f"{where}: '{name}'", value)
        return list(value)
    if isinstance(default, str):
        if not isinstance(value, str):
            raise bad
        return value
    raise bad


def apply_profile(std: Standard, prof: CompanyProfile) -> Standard:
    """Trả về BẢN SAO của chuẩn đã áp hồ sơ (chuẩn gốc không đổi). Mọi sai sót -> ProfileError tiếng Việt."""
    if prof.standard != std.name:
        raise ProfileError(f"Hồ sơ '{prof.name}' viết cho chuẩn '{prof.standard}', không dùng được với chuẩn '{std.name}'.")
    if prof.standard_version is not None and prof.standard_version != std.version:
        raise ProfileError(f"Hồ sơ '{prof.name}' viết cho {prof.standard} phiên bản {prof.standard_version}, "
                           f"chuẩn đang nạp là phiên bản {std.version}.")
    out = std.model_copy(deep=True)
    for key, gkey in LAYER_PATTERN_GLOBALS.items():
        value = getattr(prof.layer_patterns, key)
        if value is None:
            continue
        if gkey not in out.globals:
            raise ProfileError(f"layer_patterns.{key}: chuẩn '{std.name}' không dùng mẫu layer này.")
        _check_patterns(f"layer_patterns.{key}", value)
        out.globals[gkey] = list(value)
    for rule_id, params in prof.overrides.items():
        spec = out.rule(rule_id)
        if spec is None:
            raise ProfileError(f"overrides: chuẩn '{std.name}' không có luật '{rule_id}'.")
        if not params:
            raise ProfileError(f"overrides.{rule_id}: phải là bảng {{tham_số: giá_trị}} không rỗng.")
        for name, value in params.items():
            if name not in spec.params:
                known = ", ".join(sorted(spec.params)) or "(luật này không có tham số)"
                raise ProfileError(f"overrides.{rule_id}: luật không có tham số '{name}'. Tham số hợp lệ: {known}.")
            spec.params[name] = _coerce_param(f"overrides.{rule_id}", name, spec.params[name], value)
    for rule_id in prof.disabled:
        spec = out.rule(rule_id)
        if spec is None:
            raise ProfileError(f"disabled: chuẩn '{std.name}' không có luật '{rule_id}'.")
        spec.enabled = False
    out.profile = {"name": prof.name, "version": prof.version}
    return out
