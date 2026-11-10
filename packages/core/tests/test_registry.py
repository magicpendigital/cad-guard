"""Sổ khai báo công cụ `cadguard.agent.registry`: bất biến, kiểm tham số, module nhẹ."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import cadguard
from cadguard.agent import registry
from cadguard.agent.registry import SpecOptions, check_args, specs, tool_defs

CORE = Path(cadguard.__file__).resolve().parents[1]


@pytest.mark.parametrize("propose", [False, True])
@pytest.mark.parametrize("compare", [False, True])
def test_never_any_apply_tool_and_fixed_order(propose, compare):
    o = SpecOptions(allow_propose=propose, compare_without_profile=compare)
    names = [d.name for d in tool_defs(o)]
    assert names[:6] == list(registry.READ_TOOLS)
    assert (registry.PROPOSE_TOOL in names) is propose and (registry.BASELINE_TOOL in names) is compare
    assert not registry.FORBIDDEN_TOOLS & set(names)
    for s in specs(o):
        assert s["schema"]["type"] == "object" and s["schema"]["additionalProperties"] is False
        assert s["read_only"] is (s["name"] not in (registry.PROPOSE_TOOL, registry.TRANSLATE_TOOL))
        json.dumps(s, ensure_ascii=False)  # tuần tự hoá được cho mọi giao thức


def test_check_args_messages_name_fields_not_values():
    schema = {d.name: d.schema(SpecOptions()) for d in tool_defs(SpecOptions(allow_propose=True))}
    assert check_args(schema["audit"], {"file": "a.dxf"}) is None
    assert check_args(schema["audit"], {"file": "a.dxf", "standard": "design-hygiene-v0"}) is None
    assert "Thiếu tham số bắt buộc: file" in check_args(schema["audit"], {})
    assert "Tham số lạ" in check_args(schema["audit"], {"file": "a", "x": 1})
    bad = check_args(schema["audit"], {"file": "a", "standard": "BI_MAT/.."})
    assert "sai định dạng" in bad and "BI_MAT" not in bad
    q = schema["query_model"]
    assert check_args(q, {"file": "a", "filter": None}) is None
    assert check_args(q, {"file": "a", "filter": {"type": ["LINE"], "layer": "L_1"}}) is None
    assert check_args(q, {"file": "a", "filter": {"bbox": [0, 0, 1, 1]}})  # bbox không mở cho trợ lý
    assert check_args(q, {"file": "a", "limit": registry.MAX_QUERY_RECORDS + 1})
    assert check_args(q, {"file": "a", "limit": True})  # bool không phải số nguyên
    p = schema[registry.PROPOSE_TOOL]
    assert check_args(p, {"file": "a", "ops": []})
    assert check_args(p, {"file": "a", "ops": [{"op": "purge_unused"}]}) is None
    assert check_args(p, {"file": "a", "ops": [1]})


def test_unknown_tool_and_non_object_args(tmp_path):
    from cadguard.agent.tools import ToolContext
    from cadguard.agent.workspace import Workspace

    ctx = ToolContext(Workspace(tmp_path))
    o = registry.options_for(ctx)
    r = registry.call(ctx, "apply_changeset", {}, o)
    assert not r.ok and "Không có công cụ" in r.error
    assert not registry.call(ctx, "list_drawings", None, o).ok
    ok = registry.call(ctx, "list_drawings", {}, o)
    assert ok.ok and ok.data["total"] == 0


def test_registry_import_is_light():
    """Liệt kê công cụ không được kéo ezdxf (khởi động MCP nhanh hơn; hàm thật nạp lười)."""
    code = ("import sys; from cadguard.agent import registry as r; r.specs(r.SpecOptions()); "
            "print('ezdxf' in sys.modules)")
    env = dict(os.environ, PYTHONPATH=str(CORE), PYTHONUTF8="1")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"
