"""Dựng cảnh 3D tất định từ Drawing Model (tầng A/A2 của plans/cad-guard-3d.md)."""

from .build import Gap, Module, Panel, Scene, Skipped, Wall, build_scene, load_supplement
from .form import render_form
from .geometry import Box, boxes
from .gltf import write_glb
from .viewer import render_html

__all__ = [
    "Box", "Gap", "Module", "Panel", "Scene", "Skipped", "Wall",
    "boxes", "build_scene", "load_supplement", "render_form", "render_html", "write_glb",
]
