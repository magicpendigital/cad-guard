"""Người trả lời bench qua engine (bước A1) với ENGINE GIẢ: không gọi mô hình."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from cadguard.assistant import Engine, EngineInfo, Event, Usage

REPO = Path(__file__).resolve().parents[3]


def _load_runner():
    spec = importlib.util.spec_from_file_location("cadguard_bench_runner_engine", REPO / "scripts" / "bench.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass cần mô-đun có trong sys.modules
    spec.loader.exec_module(mod)
    return mod


bench = _load_runner()
bench._prepare_sys_path()

from bench import engine_answerer  # noqa: E402
from bench.reference import answer as reference_answer  # noqa: E402

TASKS = bench.load_tasks()


class FakeEngine(Engine):
    """Đọc câu hỏi, tìm tác vụ tương ứng, trả lời bằng người trả lời tham chiếu (đúng) hoặc JSON sai."""

    info = EngineInfo("gia", "api", "Engine giả", "")
    seen: list = []

    def __init__(self, wrong=False):
        self.wrong = wrong

    def run(self, messages, *, workspace, standard=None, profile=None, allow_propose=False,
            compare_without_profile=False, server_options=None, cancel=None):
        prompt = messages[-1]["content"]
        task = next(t for t in TASKS if t["cau_hoi"].strip() in prompt)
        FakeEngine.seen.append({"id": task["id"], "profile": profile, "compare": compare_without_profile,
                                "options": server_options, "standard": standard})
        yield Event("usage", {"usage": Usage(100, 20, 0, 0, 0.001)})
        if self.wrong:
            text = 'Kết quả:\n```json\n{"sai": 1}\n```'
        else:
            ans = reference_answer(bench.public_view(task), Path(workspace))
            ans.pop("_chi_phi")
            text = "Tôi đã dùng công cụ cad-guard.\n```json\n" + json.dumps(ans, ensure_ascii=False) + "\n```"
        yield Event("text", {"text": text})
        yield Event("done", {"text": text})


def test_engine_answerer_scores_12_of_12_with_correct_engine():
    FakeEngine.seen = []
    results = bench.run_bench(engine_answerer.make_answerer(FakeEngine), TASKS)
    assert [r.id for r in results if not r.ok] == []
    assert len(results) == 12 and bench.score(results) == 100.0
    assert all(r.tokens == 120 and r.usd == pytest.approx(0.001) for r in results)
    seen = {s["id"]: s for s in FakeEngine.seen}
    b06 = seen["B06-ho-so-cong-ty"]
    assert b06["profile"] is not None and b06["profile"].name == "ho-so.yaml" and b06["compare"] is True
    assert seen["B07-records-capped"]["options"] == {"anonymize": True, "stream_threshold_mb": 0, "max_entity_records": 5}
    assert seen["B03-layer-du-xref"]["options"]["anonymize"] is False
    assert seen["B01-dem-loi-e-furniture"]["standard"] == "furniture-v0"


def test_engine_answerer_fails_with_wrong_engine():
    results = bench.run_bench(engine_answerer.make_answerer(lambda: FakeEngine(wrong=True)), TASKS)
    assert not any(r.ok for r in results)


def test_engine_errors_fail_task_with_reason():
    class Broken(FakeEngine):
        def run(self, messages, **kw):
            yield Event("error", {"message": "Claude Code chưa đăng nhập.", "code": "not_logged_in"})
            yield Event("done", {"text": ""})

    res = bench.run_task(TASKS[0], engine_answerer.make_answerer(Broken))
    assert not res.ok and "chưa đăng nhập" in res.reasons[0]


def test_prompt_lists_schema_fields():
    task = next(t for t in TASKS if t["id"] == "B01-dem-loi-e-furniture")
    prompt = engine_answerer.build_prompt(bench.public_view(task))
    assert task["cau_hoi"].strip() in prompt and '"so_loi_e": số nguyên' in prompt and "```json" in prompt
    assert "kiem_tra" not in prompt and "LY-08" not in prompt  # không lộ đáp án


def test_extract_json_variants():
    assert engine_answerer.extract_json('x ```json\n{"a": 1}\n``` y ```json\n{"a": 2, "b": 3}\n```', ["a", "b"]) == {"a": 2, "b": 3}
    assert engine_answerer.extract_json('Trả lời: {"so": 3, "ds": ["A"]} hết') == {"so": 3, "ds": ["A"]}
    with pytest.raises(ValueError):
        engine_answerer.extract_json("không có JSON")


def test_bench_out_writes_summary_without_paths(tmp_path, capsys):
    out = tmp_path / "kq.json"
    assert bench.main(["--task", "B02-vs-hygiene-bad", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["score_pct"] == 100.0 and data["totals"]["tasks"] == 1 and data["engine"] is None
    text = out.read_text(encoding="utf-8")
    assert "cadguard-bench-" not in text and str(tmp_path) not in text and "hygiene_bad" not in text
    capsys.readouterr()
