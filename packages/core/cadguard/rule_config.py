"""Cài đặt luật sửa trên giao diện, không tài khoản (`cg.rule-settings/1`, kế hoạch sheets-presentation mục 6).

Hai phạm vi, áp theo thứ tự (sau hồ sơ công ty nếu có):

1. **máy**: `<thư mục cấu hình cad-guard>/rules.yaml`: áp cho mọi dự án trên máy;
2. **dự án**: `<thư mục dự án>/.cadguard/rules.yaml`: ghi đè phạm vi máy.

Mỗi luật có thể đặt `enabled` (bật/tắt), `severity` (E/W/I) và `params` (ghi đè tham số; kiểu phải khớp mặc định).
Tệp chuẩn gốc trong `standards/` không đổi, nên luôn "về mặc định" được. Mỗi lần sửa thêm một dòng vào nhật ký cục
bộ `rules-log.jsonl` cạnh tệp cài đặt (thời điểm, chuẩn, luật, giá trị cũ → mới).

CLI (`cadguard audit`), App và MCP đều nạp chuẩn qua `effective_standard`, nên cùng một bản vẽ ra cùng số.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .standard import CompanyProfile, ProfileError, Standard, _coerce_param, load_standard

SCHEMA = "cg.rule-settings/1"
FILE_NAME = "rules.yaml"
LOG_NAME = "rules-log.jsonl"
SEVERITIES = ("E", "W", "I")
SCOPES = ("project", "machine")


class RuleSettingsError(ValueError):
    """Cài đặt luật sai (thông điệp tiếng Việt)."""


def machine_dir() -> Path:
    from .app.settings import config_dir  # nạp lười: tránh vòng nhập

    return config_dir()


def settings_path(scope: str, workspace: Path | None) -> Path:
    if scope == "machine":
        return machine_dir() / FILE_NAME
    if scope == "project":
        if workspace is None:
            raise RuleSettingsError("Cần thư mục dự án để lưu cài đặt luật theo dự án.")
        return Path(workspace) / ".cadguard" / FILE_NAME
    raise RuleSettingsError("Phạm vi phải là 'project' (dự án này) hoặc 'machine' (mọi dự án trên máy).")


def find_workspace(start: Path) -> Path | None:
    """Thư mục dự án gần nhất (có `.cadguard/rules.yaml`) đi lên từ `start`; không thấy thì None."""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    for d in [p, *p.parents]:
        if (d / ".cadguard" / FILE_NAME).is_file():
            return d
    return None


def _read(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema": SCHEMA, "standards": {}}
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise RuleSettingsError(f"Tệp cài đặt luật '{path.name}' hỏng ({type(exc).__name__}).") from None
    if not isinstance(data, dict):
        return {"schema": SCHEMA, "standards": {}}
    std = data.get("standards")
    data["standards"] = std if isinstance(std, dict) else {}
    data["schema"] = SCHEMA
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
    fd, tmp = tempfile.mkstemp(prefix=".rules-", suffix=".yaml", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _log(path: Path, entry: dict) -> None:
    log = path.with_name(LOG_NAME)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_log(scope: str, workspace: Path | None, limit: int = 100) -> list[dict]:
    log = settings_path(scope, workspace).with_name(LOG_NAME)
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def layers_for(workspace: Path | None) -> list[tuple[str, dict]]:
    """[(phạm vi, dữ liệu)] theo thứ tự áp: máy rồi dự án."""
    out = [("machine", _read(settings_path("machine", None)))]
    if workspace is not None:
        out.append(("project", _read(settings_path("project", workspace))))
    return out


def apply_settings(std: Standard, data: dict, where: str = "cài đặt luật") -> Standard:
    """Áp cài đặt của MỘT phạm vi lên chuẩn (sửa tại chỗ trên bản sao của người gọi). Luật lạ thì bỏ qua."""
    rules = (data.get("standards") or {}).get(std.name) or {}
    if not isinstance(rules, dict):
        return std
    for rule_id, cfg in rules.items():
        spec = std.rule(rule_id)
        if spec is None or not isinstance(cfg, dict):
            continue
        if isinstance(cfg.get("enabled"), bool):
            spec.enabled = cfg["enabled"]
        if cfg.get("severity") in SEVERITIES:
            spec.severity = cfg["severity"]
        params = cfg.get("params")
        if isinstance(params, dict):
            for name, value in params.items():
                if name in spec.params:
                    try:
                        spec.params[name] = _coerce_param(f"{where}.{rule_id}", name, spec.params[name], value)
                    except ProfileError:
                        continue  # giá trị hỏng trong tệp: giữ mặc định, giao diện vẫn mở được
    return std


def effective_standard(name: str, standards_dir: Path | None = None, profile: CompanyProfile | None = None,
                       workspace: Path | None = None, use_settings: bool = True) -> Standard:
    """Chuẩn đã áp hồ sơ công ty + cài đặt luật máy + dự án. Hồ sơ viết cho chuẩn khác -> ProfileError (như trước)."""
    std = load_standard(name, standards_dir, profile=profile)
    if not use_settings:
        return std
    std = std.model_copy(deep=True)
    applied = []
    for scope, data in layers_for(workspace):
        if (data.get("standards") or {}).get(name):
            apply_settings(std, data, scope)
            applied.append(scope)
    if applied:
        base = dict(std.profile or {})
        base["rule_settings"] = "+".join(applied)
        std.profile = base
    return std


def _check_value(std: Standard, rule_id: str, key: str, value: Any) -> Any:
    spec = std.rule(rule_id)
    if spec is None:
        raise RuleSettingsError(f"Chuẩn '{std.name}' không có luật '{rule_id}'.")
    if key == "enabled":
        if not isinstance(value, bool):
            raise RuleSettingsError("Bật/tắt phải là true/false.")
        return value
    if key == "severity":
        if value not in SEVERITIES:
            raise RuleSettingsError("Mức độ phải là E (lỗi), W (cảnh báo) hoặc I (thông tin).")
        return value
    if key.startswith("params."):
        pname = key[len("params."):]
        if pname not in spec.params:
            raise RuleSettingsError(f"Luật {rule_id} không có tham số '{pname}'.")
        try:
            return _coerce_param(f"luật {rule_id}", pname, spec.params[pname], value)
        except ProfileError as exc:
            raise RuleSettingsError(str(exc)) from None
    raise RuleSettingsError(f"Không sửa được '{key}'.")


def update_rule(standard: str, rule_id: str, changes: dict[str, Any], *, scope: str = "project",
                workspace: Path | None = None, standards_dir: Path | None = None) -> dict:
    """Ghi thay đổi cho một luật. `changes`: {"enabled": bool, "severity": "E|W|I", "params": {tên: giá trị}}.
    Giá trị `None` = về mặc định cho khoá đó. Trả {"rule": cấu hình mới của luật trong phạm vi, "log": dòng nhật ký}."""
    if not isinstance(changes, dict) or not changes:
        raise RuleSettingsError("Không có thay đổi.")
    base = load_standard(standard, standards_dir)
    if base.rule(rule_id) is None:
        raise RuleSettingsError(f"Chuẩn '{standard}' không có luật '{rule_id}'.")
    path = settings_path(scope, workspace)
    data = _read(path)
    rules = data["standards"].setdefault(standard, {})
    cur = dict(rules.get(rule_id) or {})
    old = json.loads(json.dumps(cur))
    for key in ("enabled", "severity"):
        if key in changes:
            if changes[key] is None:
                cur.pop(key, None)
            else:
                cur[key] = _check_value(base, rule_id, key, changes[key])
    if "params" in changes:
        params = changes["params"]
        if not isinstance(params, dict):
            raise RuleSettingsError("params phải là bảng {tên tham số: giá trị}.")
        cp = dict(cur.get("params") or {})
        for pname, value in params.items():
            if value is None:
                cp.pop(pname, None)
            else:
                cp[pname] = _check_value(base, rule_id, "params." + pname, value)
        if cp:
            cur["params"] = cp
        else:
            cur.pop("params", None)
    unknown = set(changes) - {"enabled", "severity", "params"}
    if unknown:
        raise RuleSettingsError("Khoá lạ: " + ", ".join(sorted(unknown)) + ".")
    if cur:
        rules[rule_id] = cur
    else:
        rules.pop(rule_id, None)
    if not rules:
        data["standards"].pop(standard, None)
    _write(path, data)
    entry = {"at": datetime.now().astimezone().isoformat(timespec="seconds"), "scope": scope,
             "standard": standard, "rule": rule_id, "old": old, "new": cur}
    _log(path, entry)
    return {"rule": cur, "log": entry}


def reset_rule(standard: str, rule_id: str, *, scope: str = "project", workspace: Path | None = None,
               standards_dir: Path | None = None) -> dict:
    """Về mặc định: xoá mọi cài đặt của luật trong phạm vi."""
    return update_rule(standard, rule_id, {"enabled": None, "severity": None,
                                           "params": {k: None for k in _params_set(standard, rule_id, scope, workspace)}}
                       , scope=scope, workspace=workspace, standards_dir=standards_dir)


def _params_set(standard: str, rule_id: str, scope: str, workspace: Path | None) -> list[str]:
    data = _read(settings_path(scope, workspace))
    cfg = ((data.get("standards") or {}).get(standard) or {}).get(rule_id) or {}
    return list((cfg.get("params") or {}).keys())


def scope_settings(standard: str, scope: str, workspace: Path | None) -> dict:
    data = _read(settings_path(scope, workspace))
    return dict((data.get("standards") or {}).get(standard) or {})


__all__ = ["SCHEMA", "RuleSettingsError", "effective_standard", "find_workspace", "read_log", "reset_rule",
           "scope_settings", "update_rule"]
