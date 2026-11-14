"""Phiên làm việc của studio: giữ bản vẽ, giá trị bổ sung, ánh xạ hình chiếu, đề xuất, hội thoại.

Chỉnh sửa DXF (set_attrib, change_layer) chỉ áp dụng lên bản sao trong bộ nhớ và chỉ được xuất ra tệp MỚI;
tệp nguồn được lưu nguyên trong thư mục làm việc và không bao giờ bị ghi đè. Hoàn tác = nạp lại nguồn rồi chạy lại các thao tác còn lại.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import ezdxf

from ..dxf_reader import build_model
from ..scene import boxes, build_scene
from ..scene.gltf import build_glb, color_for
from .clusters import clusters_of, digest
from .llm import ANALYZE_PROMPT, SYSTEM_PROMPT, Backend, LlmError
from .protocol import Observation, Proposal, parse_reply, validate_proposals


def _load_doc(path: Path):
    try:
        return ezdxf.readfile(path)
    except ezdxf.DXFError:
        from ezdxf import recover

        doc, _ = recover.readfile(str(path))
        return doc


def apply_edit(doc, op: dict) -> None:
    """Thao tác cố định. Đã được `validate_proposals` kiểm; ở đây chỉ thực thi."""
    if op["kind"] == "set_attrib":
        ins = doc.entitydb.get(op["handle"])
        for a in ins.attribs:
            if str(a.dxf.tag) == op["tag"]:
                a.dxf.text = op["value"]
                return
        ins.add_attrib(op["tag"], op["value"], insert=ins.dxf.insert, dxfattribs={"height": 20})
    elif op["kind"] == "change_layer":
        if op["layer"] not in doc.layers:
            doc.layers.add(op["layer"])
        for h in op["handles"]:
            e = doc.entitydb.get(h)
            if e is not None:
                e.dxf.layer = op["layer"]


class Session:
    def __init__(self, data: bytes, workdir: Path, backend: Backend | None) -> None:
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.source = self.workdir / "source.dxf"
        self.source.write_bytes(data)
        self.hash = hashlib.sha256(data).hexdigest()[:16]
        self.backend = backend
        self.consent = False
        self.supplement: dict[str, str] = {}
        self.view_handles: dict[str, list[str]] = {}
        self.edits: list[dict] = []
        self.history: list[dict] = []
        self.proposals: list[Proposal] = []
        self.observations: list[Observation] = []
        self.notes: list[str] = []
        self.chat: list[dict] = []
        self._pid = 0
        self.doc = _load_doc(self.source)
        self.rebuild()

    # ---- dựng lại -----------------------------------------------------
    def rebuild(self) -> None:
        self.model = build_model(self.doc, file_hash=self.hash)
        self.clusters = clusters_of(self.model)
        by_h = {e.handle: e for e in self.model.entities}
        views = {v: [by_h[h] for h in hs if h in by_h] for v, hs in self.view_handles.items()} or None
        self.scene = build_scene(self.model, self.supplement, views)

    def _snapshot(self, pid: str, edit: dict | None) -> None:
        self.history.append({"pid": pid, "supplement": dict(self.supplement), "views": {k: list(v) for k, v in self.view_handles.items()}, "edit": edit})

    # ---- người dùng nhập tay (form) -------------------------------------
    def set_values(self, values: dict) -> None:
        valid = {f.key for g in self.scene.gaps for f in g.fields}
        self._snapshot("form", None)
        for k, v in values.items():
            if k in valid and str(v).strip() != "":
                self.supplement[k] = str(v).strip()
        self.rebuild()

    # ---- đề xuất ---------------------------------------------------------
    def _find(self, pid: str) -> Proposal | None:
        return next((p for p in self.proposals if p.id == pid and p.status == "pending"), None)

    def accept(self, pid: str) -> bool:
        p = self._find(pid)
        if p is None:
            return False
        edit = None
        if p.kind == "set_views":
            cl = {c.id: c for c in self.clusters}
            self._snapshot(pid, None)
            self.view_handles = {v: [e.handle for e in cl[cid].entities] for v, cid in (p.views or {}).items()}
        elif p.kind == "set_value":
            self._snapshot(pid, None)
            self.supplement[p.key] = p.value
        else:
            edit = {"kind": p.kind, "handle": p.handle, "tag": p.tag, "value": p.value, "handles": p.handles, "layer": p.layer}
            self._snapshot(pid, edit)
            apply_edit(self.doc, edit)
            self.edits.append(edit)
        p.status = "accepted"
        self.rebuild()
        return True

    def reject(self, pid: str) -> bool:
        p = self._find(pid)
        if p is None:
            return False
        p.status = "rejected"
        return True

    def undo(self) -> bool:
        if not self.history:
            return False
        h = self.history.pop()
        self.supplement, self.view_handles = h["supplement"], h["views"]
        if h["edit"] is not None:
            self.edits.pop()
            self.doc = _load_doc(self.source)
            for op in self.edits:
                apply_edit(self.doc, op)
        for p in self.proposals:
            if p.id == h["pid"] and p.status == "accepted":
                p.status = "pending"
        self.rebuild()
        return True

    # ---- LLM --------------------------------------------------------------
    def ask(self, message: str | None) -> None:
        """`message=None`: phân tích lần đầu. Không bao giờ ném lỗi LLM ra ngoài; ghi vào `notes`."""
        if self.backend is None:
            self.notes.append("Chưa có LLM (không có ANTHROPIC_API_KEY và không thấy lệnh claude).")
            return
        if not self.consent:
            self.notes.append("Chưa đồng ý gửi dữ liệu bản vẽ cho LLM trong phiên này.")
            return
        user_text = message if message is not None else ANALYZE_PROMPT
        self.chat.append({"role": "user", "text": user_text})
        d = digest(self.model, self.scene, self.clusters)
        history = [{"role": m["role"], "content": m["text"]} for m in self.chat[:-1][-10:]]
        content = "BẢN TÓM TẮT BẢN VẼ (JSON):\n" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n\nNGƯỜI DÙNG: " + user_text
        msgs = history + [{"role": "user", "content": content}]
        try:
            raw = self.backend.complete(SYSTEM_PROMPT, msgs)
        except (LlmError, OSError, Exception) as exc:  # noqa: BLE001 - lỗi mạng/khoá/CLI không được làm sập phiên
            self.notes.append(f"LLM lỗi: {str(exc)[:300]}")
            self.chat.pop()
            return
        reply, err = parse_reply(raw)
        if err:
            self.notes.append(err)
        handles = {e.handle: e.type for e in self.model.entities}
        keys = {f.key for g in self.scene.gaps for f in g.fields}
        ok, dropped = validate_proposals(reply.proposals, cluster_ids={c.id for c in self.clusters}, handles=handles, valid_keys=keys, start_id=self._pid)
        self._pid += len(ok)
        self.notes.extend(dropped)
        self.proposals.extend(ok)
        self.observations.extend(reply.observations)
        text = reply.reply
        if reply.questions:
            text += "\n\nCâu hỏi:\n" + "\n".join(f"- {q}" for q in reply.questions)
        self.chat.append({"role": "assistant", "text": text})

    # ---- đầu ra --------------------------------------------------------------
    def export_dxf(self) -> Path:
        """Ghi bản chuẩn hoá ra tệp MỚI (không ghi đè nguồn)."""
        out = self.workdir / f"{self.hash}-chuan-hoa.dxf"
        self.doc.saveas(out)
        return out

    def glb(self) -> bytes:
        return build_glb(self.scene)

    def state(self) -> dict:
        sc = self.scene
        return {
            "hash": self.hash,
            "backend": self.backend.name if self.backend else None,
            "consent": self.consent,
            "scene": {
                "boxes": [{"b": [list(p) for p in b.base], "z0": b.z0, "z1": b.z1, "c": list(color_for(b.material)), "k": b.kind, "n": b.name} for b in boxes(sc)],
                "walls": len(sc.walls),
                "modules": len(sc.modules),
                "panels": [p.model_dump() for p in sc.panels],
                "gaps": [g.model_dump() for g in sc.gaps],
                "skipped": [s.model_dump() for s in sc.skipped],
                "notes": sc.notes,
            },
            "clusters": [{"id": c.id, "size": [round(c.bbox[2] - c.bbox[0], 1), round(c.bbox[3] - c.bbox[1], 1)], "entities": len(c.entities), "layers": sorted({e.layer for e in c.entities})} for c in self.clusters],
            "proposals": [p.model_dump(exclude_none=True) for p in self.proposals],
            "observations": [o.model_dump() for o in self.observations],
            "chat": self.chat,
            "notes": self.notes[-10:],
            "can_undo": bool(self.history),
            "edits": len(self.edits),
        }
