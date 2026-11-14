"""Offline review probes. Run with Draff/packages/core on PYTHONPATH."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys

from cadguard import fixtures
from cadguard.app import api
from cadguard.scene.build import Scene
from cadguard.scene.gltf import build_glb

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / ".review-runtime" / "python-probes"
WORK.mkdir(parents=True, exist_ok=True)
fixtures.make_hygiene_ok(WORK / "clean.dxf")
fixtures.make_room_missing_height(WORK / "missing.dxf")
app = api.AppData(api.AppConfig(workspace=WORK, standards_dir=ROOT / "Draff/standards"))
api.add_review_note(app, "clean.dxf", "Synthetic unresolved review blocker", severity="E")
handover = api.handover_package(app, "clean.dxf", "design-hygiene-v0")
initial = api.scene_3d(app, "missing.dxf")
supplement = {f["key"]: 900 for g in initial["scene"]["gaps"] for f in g["fields"]}
completed = api.scene_3d(app, "missing.dxf", supplement)
blob = api.scene_glb(app, "missing.dxf")
preview_blob = build_glb(Scene.model_validate(completed["scene"]))
chunk_len = struct.unpack_from("<I", blob, 12)[0]
glb = json.loads(blob[20:20 + chunk_len].decode("utf-8"))
snapshot = api.workspace_state(app, "missing.dxf", "furniture-v0", mode="scene")
report = {
    "handover_unresolved_E_note": {
        "ready": handover["ready"], "counts": handover["counts"],
        "unresolved_notes": handover["unresolved_notes"],
    },
    "scene_export_state": {
        "initial_modules": len(initial["scene"]["modules"]),
        "supplemented_preview_modules": len(completed["scene"]["modules"]),
        "glb_mesh_count": len(glb.get("meshes", [])),
        "initial_boxes": len(initial["boxes"]),
        "supplemented_boxes": len(completed["boxes"]),
        "workspace_snapshot_modules": len(snapshot["scene_3d"]["modules"]),
        "glb_sha256": hashlib.sha256(blob).hexdigest(),
        "supplemented_preview_glb_sha256": hashlib.sha256(preview_blob).hexdigest(),
        "export_matches_supplemented_preview": blob == preview_blob,
    },
}
sys.stdout.reconfigure(encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
