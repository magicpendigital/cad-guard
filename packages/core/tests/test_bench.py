"""Bộ chấm (bench/, scripts/bench.py) và gói tri thức (knowledge/). Chỉ dùng DXF tổng hợp."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
KNOWLEDGE = REPO / "knowledge"
MCP_DIR = KNOWLEDGE / "mcp"
SKILLS_DIR = KNOWLEDGE / "skills"
REQUIRED_SKILLS = {"khao-sat-ban-ve", "kiem-va-giai-thich-loi", "don-ban-ve", "ghi-chu-ban-giao"}


def _load_runner():
    spec = importlib.util.spec_from_file_location("cadguard_bench_runner", REPO / "scripts" / "bench.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass cần mô-đun có trong sys.modules
    spec.loader.exec_module(mod)
    return mod


bench = _load_runner()
bench._prepare_sys_path()  # để `import bench.reference` trỏ vào gói bench/ của repo
TASKS = bench.load_tasks()


# ---------- tác vụ ----------


def test_at_least_eight_tasks_with_unique_ids():
    ids = [t["id"] for t in TASKS]
    assert len(ids) >= 8 and len(set(ids)) == len(ids)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t["id"])
def test_task_schema(task):
    assert bench.validate_task(task) == []
    assert "kiem_tra" not in bench.public_view(task)


def test_validate_task_rejects_bad_schema():
    good = dict(TASKS[0])
    assert bench.validate_task({k: v for k, v in good.items() if k != "kiem_tra"})
    assert bench.validate_task({**good, "fixture": "khong_co.dxf"})
    assert bench.validate_task({**good, "kiem_tra": [{"loai": "doan", "truong": "x"}]})
    assert bench.validate_task({**good, "kiem_tra": [{"loai": "bang", "truong": "truong_la", "gia_tri": 1}]})
    assert bench.validate_task({**good, "moi_truong": {"khoa_la": 1}})


# ---------- người trả lời ----------


@pytest.fixture(scope="module")
def reference_results():
    return bench.run_bench(bench.resolve_answerer(bench.DEFAULT_ANSWERER), TASKS)


def test_reference_answerer_scores_100(reference_results):
    failed = {r.id: r.reasons for r in reference_results if not r.ok}
    assert not failed
    assert bench.score(reference_results) == 100.0
    assert all(r.tokens == 0 and r.usd == 0.0 for r in reference_results)


def test_table_has_cost_and_time_columns(reference_results):
    table = bench.format_table(reference_results, bench.DEFAULT_ANSWERER)
    for col in ("Tác vụ", "Kết quả", "Thời gian (s)", "Token", "Chi phí (USD)", "Tỉ lệ đúng: 100.0%"):
        assert col in table


def _wrong_answerer(task, workspace):
    """Cố ý sai: lấy đáp án tham chiếu rồi làm hỏng mọi trường."""
    from bench.reference import answer

    good = answer(task, workspace)
    good.pop("_chi_phi", None)
    bad = {}
    for key, value in good.items():
        if isinstance(value, bool):
            bad[key] = not value
        elif isinstance(value, int):
            bad[key] = value + 1
        elif isinstance(value, list):
            bad[key] = [*value, "XX-99"]
        else:
            bad[key] = None
    return bad


def test_wrong_answerer_fails_every_task():
    results = bench.run_bench(_wrong_answerer, TASKS)
    assert not any(r.ok for r in results)
    assert all(r.reasons for r in results)


def test_crashing_and_leaking_answers_are_failed():
    def crash(task, workspace):
        raise RuntimeError("hỏng")

    assert not bench.run_task(TASKS[0], crash).ok
    task = next(t for t in TASKS if any(c["loai"] == "khong_chua" for c in t["kiem_tra"]))
    leak = {"so_layer_du_xref": 2, "ma_luat": "VS-01", "thong_diep": ["layer SYNX1|SYN-TUONG"]}
    assert any("lộ" in r for r in bench.grade(task, leak))


def test_grade_is_type_strict():
    task = {"kiem_tra": [{"loai": "bang", "truong": "a", "gia_tri": True}, {"loai": "bang", "truong": "b", "gia_tri": 1}]}
    assert bench.grade(task, {"a": True, "b": 1}) == []
    assert len(bench.grade(task, {"a": 1, "b": True})) == 2
    assert bench.grade(task, "không phải JSON") != []


def test_main_exit_codes(capsys):
    assert bench.main(["--task", "B02-vs-hygiene-bad"]) == 0
    assert "ĐÚNG" in capsys.readouterr().out
    wrong = f"{__name__}:_wrong_answerer"
    assert bench.main(["--task", "B02-vs-hygiene-bad", "--answerer", wrong]) == 1
    assert "SAI" in capsys.readouterr().out
    assert bench.main(["--task", "B02-vs-hygiene-bad", "--answerer", wrong, "--threshold", "0", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["threshold_pct"] == 0 and out["score_pct"] == 0 and out["results"][0]["ok"] is False
    assert bench.main(["--task", "khong-co"]) == 2


# ---------- gói tri thức ----------

SECRET = re.compile(
    r"sk-[A-Za-z0-9_\-]{8,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_|xox[bap]-"
    r"|(?i:token|api[_-]?key|secret|password)\s*[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-./+]{8,}"
)


def _mcp_files():
    return sorted(p for p in MCP_DIR.rglob("*") if p.is_file())


def test_four_mcp_templates_exist_and_parse():
    files = {p.relative_to(MCP_DIR).as_posix() for p in _mcp_files()}
    assert {"claude-code/.mcp.json", "codex/config.toml", "opencode/opencode.json", "antigravity/mcp_config.json",
            "README.md"} <= files
    for path in _mcp_files():
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            json.loads(text)
        elif path.suffix == ".toml":
            tomllib = pytest.importorskip("tomllib")
            data = tomllib.loads(text)
            assert data["mcp_servers"]["cad-guard"]["args"][:3] == ["-m", "cadguard", "mcp"]
        if path.name != "README.md" and path.suffix != ".md":
            assert "<THU_MUC_LAM_VIEC>" in text or path.name == "settings.json"


@pytest.mark.parametrize("path", _mcp_files(), ids=lambda p: p.relative_to(MCP_DIR).as_posix())
def test_mcp_templates_have_no_secrets(path):
    text = path.read_text(encoding="utf-8")
    assert not SECRET.search(text), SECRET.search(text)
    assert "AKIA" not in text and "ghp_" not in text and "sk-" not in text


def test_secret_detector_catches_examples():
    for sample in ('"token": "abcd1234efgh5678"', "api_key = 'abcdefgh12345'", "sk-" + "a" * 20, "ghp_" + "b" * 30):
        assert SECRET.search(sample), sample
    assert not SECRET.search("Không đặt khoá API hay token vào tệp này.")


def test_knowledge_avoids_wrong_audience_phrase():
    phrase = "đơn vị thiết kế"
    for path in KNOWLEDGE.rglob("*"):
        if path.is_file():
            assert phrase not in path.read_text(encoding="utf-8").lower(), path


def test_knowledge_agents_md_covers_rules():
    text = (KNOWLEDGE / "AGENTS.md").read_text(encoding="utf-8")
    for needle in ("Thiết kế", "Kỹ thuật", "Lập trình sản xuất", "records_capped", "skipped", "ẩn danh", "WIPEOUT", "xref",
                   "list_drawings", "audit", "explain_rule", "get_model_summary", "query_model"):
        assert needle in text, needle


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    assert m, f"{path}: thiếu frontmatter"
    data = yaml.safe_load(m.group(1))
    assert isinstance(data, dict)
    return data


def test_required_skills_have_valid_frontmatter():
    skills = {p.parent.name: p for p in SKILLS_DIR.glob("*/SKILL.md")}
    assert REQUIRED_SKILLS <= set(skills)
    for name, path in skills.items():
        meta = _frontmatter(path)
        assert meta.get("name") == name
        assert isinstance(meta.get("description"), str) and len(meta["description"]) >= 60
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)


def test_skills_reference_only_cadguard_tools():
    tools = {"list_drawings", "audit", "explain_rule", "get_model_summary", "query_model"}
    for path in SKILLS_DIR.glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        assert any(t in text for t in tools), path
    cleanup = (SKILLS_DIR / "don-ban-ve" / "SKILL.md").read_text(encoding="utf-8")
    assert "chỉ đọc" in cleanup and "tệp mới" in cleanup
