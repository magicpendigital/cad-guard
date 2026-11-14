"""Hợp đồng dữ liệu trung tâm (Central Schema Contract) cho toàn bộ không gian làm việc CAD Guard."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from .model import DrawingModel


class AuditFindingSpec(BaseModel):
    id: str = ""
    rule_id: str
    severity: Literal["E", "W", "I"] = "W"
    title: str = ""
    message: str
    layer: str | None = None
    layout: str | None = None
    handles: list[str] = Field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    state: Literal["open", "accepted", "fixed", "dismissed", "false_positive"] = "open"


class AuditReportSpec(BaseModel):
    schema_version: str = "cg.audit/1"
    file_path: str
    standard: str
    standard_version: str = "0.1"
    department: str = "ky-thuat"
    counts: dict[str, int] = Field(default_factory=lambda: {"E": 0, "W": 0, "I": 0})
    rules_run: int = 0
    findings: list[AuditFindingSpec] = Field(default_factory=list)
    fixable_rules: list[str] = Field(default_factory=list)
    records_capped: bool = False


class ChangesetSpec(BaseModel):
    schema_version: str = "cg.changeset/1"
    changeset_id: str
    source_path: str
    standard: str
    created_by: Literal["user", "agent"] = "user"
    ops: list[dict[str, Any]] = Field(default_factory=list)
    preview: dict[str, Any] | None = None
    applied: dict[str, Any] | None = None
    ok: bool = True
    summary_vi: str = ""


class ReviewNoteSpec(BaseModel):
    id: str
    file_path: str
    department: str = "ky-thuat"
    author: str = "Kỹ thuật"
    severity: Literal["E", "W", "I"] = "I"
    message: str
    rule_id: str | None = None
    handle: str | None = None
    pos: tuple[float, float] | None = None
    resolved: bool = False
    created_at: str = ""


class WorkspaceState(BaseModel):
    """Hợp đồng phiên làm việc hợp nhất (Unified Session Contract) cho 4 chế độ Studio."""

    schema_version: str = "cg.workspace/1"
    workspace_name: str = ""
    active_file: str | None = None
    active_mode: Literal["audit", "diff", "scene", "review"] = "audit"
    department: str = "ky-thuat"
    standard: str = "furniture-v0"
    anonymize: bool = True
    drawing: DrawingModel | None = None
    audit_report: AuditReportSpec | None = None
    changeset: ChangesetSpec | None = None
    scene_3d: dict[str, Any] | None = None
    review_notes: list[ReviewNoteSpec] = Field(default_factory=list)


DrawingSessionSpec = WorkspaceState
