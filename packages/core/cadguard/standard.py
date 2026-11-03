"""Nạp chuẩn trình bày (standards/<tên>.yaml): tham số chung + danh mục luật có phiên bản."""

from __future__ import annotations

import os
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


class Standard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    description: str = ""
    globals: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleSpec]

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


def load_standard(name: str, standards_dir: Path | None = None) -> Standard:
    d = standards_dir or find_standards_dir()
    path = d / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Không có chuẩn '{name}' ({path}).")
    return Standard.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
