#!/usr/bin/env python3
"""Bộ chấm (bench) của cad-guard: chấm trợ lý trả lời câu hỏi về bản vẽ DXF TỔNG HỢP bằng kiểm tra tất định.

  python scripts/bench.py                                  # người trả lời tham chiếu (bench/reference.py), phải đạt 100%
  python scripts/bench.py --answerer goi.mo_dun:ham        # cắm người trả lời khác (CLI agent, LLM...)
  python scripts/bench.py --task B02-vs-hygiene-bad --json # chạy một tác vụ, in JSON
  python scripts/bench.py --threshold 80                   # ngưỡng % đúng để thoát mã 0
  python scripts/bench.py --engine claude-cli --out kq.json # trợ lý THẬT qua engine cad-guard (tốn token), ghi JSON
  python scripts/bench.py --engine anthropic --model claude-sonnet-5-5 --threshold 0

Tác vụ: `bench/tasks/*.yaml`. Mỗi tác vụ chạy trong một thư mục làm việc tạm, rỗng, chỉ chứa DXF tổng hợp do
`cadguard.fixtures` sinh (và hồ sơ công ty nếu tác vụ cần). Không đọc bản vẽ thật, không gọi mạng hay LLM ở chế độ mặc định.

Giao diện người trả lời: `ham(task: dict, workspace: Path) -> dict`.
- `task` là bản CÔNG KHAI của tác vụ (không có `kiem_tra`): id, mo_ta, dang, fixture, cau_hoi, moi_truong, tham_so, tra_loi.
- Kết quả là một dict JSON theo `tra_loi`. Có thể kèm khoá `_chi_phi` = {"tokens": int, "usd": float}; khoá này
  được tách ra để ghi vào cột chi phí, không đem chấm.
- Ném ngoại lệ = tác vụ trượt (ghi lý do), không làm dừng cả lượt chấm.

Không có venv có ezdxf thì script tự chạy lại trong venv dùng chung của `scripts/test.py` (biến CADGUARD_VENV).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "packages" / "core"
TASKS_DIR = ROOT / "bench" / "tasks"
DEFAULT_ANSWERER = "bench.reference:answer"
ENGINE_ANSWERER = "bench.engine_answerer:answer"
DEFAULT_THRESHOLD = 100.0

REQUIRED_KEYS = ("id", "mo_ta", "dang", "fixture", "cau_hoi", "tra_loi", "kiem_tra")
OPTIONAL_KEYS = ("moi_truong", "tham_so")
ENV_KEYS = {"an_danh", "stream_threshold_mb", "max_entity_records", "ho_so"}
CHECK_TYPES = {
    "bang": ("truong", "gia_tri"),  # trường bằng đúng giá trị (đúng kiểu: số, chuỗi, đúng/sai)
    "tap": ("truong", "gia_tri"),  # trường là danh sách, so như tập hợp
    "co_truong": ("truong",),  # các trường có mặt và khác null
    "khong_chua": ("chuoi",),  # câu trả lời (dạng JSON) không chứa chuỗi nào trong danh sách
}
ANSWER_TYPES = {"so_nguyen", "chuoi", "dung_sai", "danh_sach", "doi_tuong"}
PRIVATE_COST_KEY = "_chi_phi"

Answerer = Callable[[dict, Path], dict]


@dataclass
class TaskResult:
    id: str
    ok: bool
    seconds: float
    tokens: int = 0
    usd: float = 0.0
    reasons: list[str] = field(default_factory=list)


# ---------- nạp và kiểm tác vụ ----------


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[dict]:
    import yaml

    tasks = []
    for path in sorted(Path(tasks_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: tác vụ phải là một ánh xạ YAML")
        data["_tep"] = path.name
        tasks.append(data)
    return tasks


def validate_task(task: dict) -> list[str]:
    """Trả danh sách lỗi schema (rỗng = hợp lệ)."""
    from cadguard import fixtures

    errs: list[str] = []
    tid = task.get("id", "?")
    missing = [k for k in REQUIRED_KEYS if k not in task]
    if missing:
        return [f"{tid}: thiếu khoá {missing}"]
    extra = set(task) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS) - {"_tep"}
    if extra:
        errs.append(f"{tid}: khoá lạ {sorted(extra)}")
    for key in ("id", "mo_ta", "dang", "cau_hoi"):
        if not isinstance(task[key], str) or not task[key].strip():
            errs.append(f"{tid}: '{key}' phải là chuỗi khác rỗng")
    if task.get("_tep") and task["_tep"] != f"{tid}.yaml":
        errs.append(f"{tid}: tên tệp phải là '<id>.yaml'")
    names = task["fixture"] if isinstance(task["fixture"], list) else [task["fixture"]]
    for name in names:
        if name not in fixtures.ALL:
            errs.append(f"{tid}: fixture '{name}' không có trong cadguard.fixtures.ALL")
    env = task.get("moi_truong") or {}
    if not isinstance(env, dict) or set(env) - ENV_KEYS:
        errs.append(f"{tid}: 'moi_truong' chỉ nhận {sorted(ENV_KEYS)}")
    elif env.get("ho_so") and not (ROOT / env["ho_so"]).is_file():
        errs.append(f"{tid}: không thấy hồ sơ {env['ho_so']}")
    if not isinstance(task.get("tham_so") or {}, dict):
        errs.append(f"{tid}: 'tham_so' phải là ánh xạ")
    schema = task["tra_loi"]
    if not isinstance(schema, dict) or not schema:
        errs.append(f"{tid}: 'tra_loi' phải là ánh xạ trường -> kiểu")
        schema = {}
    for fname, ftype in schema.items():
        if ftype not in ANSWER_TYPES:
            errs.append(f"{tid}: kiểu '{ftype}' của trường '{fname}' không thuộc {sorted(ANSWER_TYPES)}")
    checks = task["kiem_tra"]
    if not isinstance(checks, list) or not checks:
        errs.append(f"{tid}: 'kiem_tra' phải là danh sách khác rỗng")
        checks = []
    for i, chk in enumerate(checks):
        kind = chk.get("loai") if isinstance(chk, dict) else None
        if kind not in CHECK_TYPES:
            errs.append(f"{tid}: kiểm tra #{i} có 'loai' không hợp lệ")
            continue
        need = CHECK_TYPES[kind]
        if set(chk) != {"loai", *need}:
            errs.append(f"{tid}: kiểm tra #{i} ({kind}) cần đúng các khoá {list(need)}")
            continue
        fields = chk.get("truong")
        for f in (fields if isinstance(fields, list) else [fields] if fields else []):
            if f.split(".")[0] not in schema:
                errs.append(f"{tid}: kiểm tra #{i} dùng trường '{f}' không khai trong 'tra_loi'")
    return errs


def public_view(task: dict) -> dict:
    """Bản tác vụ đưa cho người trả lời: bỏ `kiem_tra` (đáp án) và khoá nội bộ."""
    return {k: v for k, v in task.items() if k != "kiem_tra" and not k.startswith("_")}


def build_workspace(task: dict, dest: Path) -> Path:
    """Tạo thư mục làm việc rỗng chỉ chứa DXF tổng hợp của tác vụ (+ `ho-so.yaml` nếu có)."""
    from cadguard import fixtures

    dest.mkdir(parents=True, exist_ok=True)
    names = task["fixture"] if isinstance(task["fixture"], list) else [task["fixture"]]
    for name in names:
        fixtures.ALL[name](dest / name)
    prof = (task.get("moi_truong") or {}).get("ho_so")
    if prof:
        shutil.copyfile(ROOT / prof, dest / "ho-so.yaml")
    return dest


# ---------- chấm ----------


def _get(answer: Any, dotted: str) -> tuple[bool, Any]:
    cur = answer
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _same(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(actual) is bool and actual is expected
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and actual == expected
    return actual == expected


def grade(task: dict, answer: Any) -> list[str]:
    """Chấm tất định. Trả danh sách lý do trượt (rỗng = đúng)."""
    if not isinstance(answer, dict):
        return ["câu trả lời không phải đối tượng JSON"]
    reasons = []
    for chk in task["kiem_tra"]:
        kind = chk["loai"]
        if kind == "bang":
            found, val = _get(answer, chk["truong"])
            if not found or not _same(val, chk["gia_tri"]):
                reasons.append(f"{chk['truong']}: cần {chk['gia_tri']!r}, nhận {val!r}")
        elif kind == "tap":
            found, val = _get(answer, chk["truong"])
            if not found or not isinstance(val, list) or set(map(str, val)) != set(map(str, chk["gia_tri"])):
                reasons.append(f"{chk['truong']}: cần tập {sorted(chk['gia_tri'])}, nhận {val!r}")
        elif kind == "co_truong":
            for f in chk["truong"]:
                found, val = _get(answer, f)
                if not found or val is None:
                    reasons.append(f"thiếu trường bắt buộc '{f}'")
        elif kind == "khong_chua":
            text = json.dumps(answer, ensure_ascii=False)
            leaked = [s for s in chk["chuoi"] if s in text]
            if leaked:
                reasons.append(f"câu trả lời lộ chuỗi cấm: {leaked}")
    return reasons


# ---------- chạy ----------


def _prepare_sys_path() -> None:
    """Gốc repo và packages/core lên đầu; bỏ thư mục scripts/ để `bench` là gói bench/, không phải tệp này."""
    here = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != here]
    for p in (str(CORE), str(ROOT)):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def resolve_answerer(spec: str) -> Answerer:
    """`goi.mo_dun:ham` -> hàm. Đường dẫn tìm gồm gốc repo và packages/core."""
    if ":" not in spec:
        raise ValueError("--answerer phải có dạng 'mo_dun:ham'")
    mod_name, func_name = spec.split(":", 1)
    _prepare_sys_path()
    fn = getattr(importlib.import_module(mod_name), func_name)
    if not callable(fn):
        raise ValueError(f"{spec} không gọi được")
    return fn


def run_task(task: dict, answerer: Answerer) -> TaskResult:
    with tempfile.TemporaryDirectory(prefix="cadguard-bench-") as tmp:
        ws = build_workspace(task, Path(tmp) / "phien")
        start = time.perf_counter()
        try:
            answer = answerer(public_view(task), ws)
            error = None
        except Exception as exc:  # noqa: BLE001 — người trả lời hỏng thì tác vụ trượt
            answer, error = None, f"người trả lời lỗi: {type(exc).__name__}: {exc}"
        seconds = time.perf_counter() - start
    tokens, usd = 0, 0.0
    if isinstance(answer, dict) and PRIVATE_COST_KEY in answer:
        cost = answer.pop(PRIVATE_COST_KEY) or {}
        tokens, usd = int(cost.get("tokens", 0)), float(cost.get("usd", 0.0))
    reasons = [error] if error else grade(task, answer)
    return TaskResult(task["id"], not reasons, seconds, tokens, usd, reasons)


def run_bench(answerer: Answerer, tasks: list[dict]) -> list[TaskResult]:
    return [run_task(t, answerer) for t in tasks]


def score(results: list[TaskResult]) -> float:
    return 100.0 * sum(r.ok for r in results) / len(results) if results else 0.0


def format_table(results: list[TaskResult], answerer: str) -> str:
    head = ("Tác vụ", "Kết quả", "Thời gian (s)", "Token", "Chi phí (USD)")
    rows = [(r.id, "ĐÚNG" if r.ok else "SAI", f"{r.seconds:.3f}", str(r.tokens), f"{r.usd:.4f}") for r in results]
    total = ("TỔNG", f"{sum(r.ok for r in results)}/{len(results)}", f"{sum(r.seconds for r in results):.3f}",
             str(sum(r.tokens for r in results)), f"{sum(r.usd for r in results):.4f}")
    widths = [max(len(x[i]) for x in [head, *rows, total]) for i in range(len(head))]
    line = "-+-".join("-" * w for w in widths)
    fmt = lambda row: " | ".join(c.ljust(w) for c, w in zip(row, widths))  # noqa: E731
    out = [f"Người trả lời: {answerer}", fmt(head), line, *map(fmt, rows), line, fmt(total)]
    for r in results:
        for why in r.reasons:
            out.append(f"  - {r.id}: {why}")
    out.append(f"Tỉ lệ đúng: {score(results):.1f}%")
    return "\n".join(out)


def write_summary(path: Path, results: list[TaskResult], args, pct: float) -> None:
    """Kết quả tổng hợp: mã tác vụ, đúng/sai, thời gian, token, USD, lý do trượt. Không đường dẫn, không tên tệp khách."""
    data = {
        "answerer": args.answerer,
        "engine": args.engine,
        "model": args.model,
        "score_pct": pct,
        "threshold_pct": args.threshold,
        "totals": {"tasks": len(results), "ok": sum(r.ok for r in results),
                   "seconds": round(sum(r.seconds for r in results), 3), "tokens": sum(r.tokens for r in results),
                   "usd": round(sum(r.usd for r in results), 6)},
        "results": [asdict(r) for r in results],
        "date": time.strftime("%Y-%m-%d"),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã ghi kết quả: {path.name}", file=sys.stderr)


def _ensure_deps(argv: list[str]) -> int | None:
    """Thiếu ezdxf/yaml thì chạy lại script trong venv dùng chung của scripts/test.py."""
    try:
        import ezdxf  # noqa: F401
        import yaml  # noqa: F401
        return None
    except ImportError:
        if os.environ.get("CADGUARD_BENCH_CHILD"):
            print("Thiếu ezdxf/pyyaml trong venv; chạy `python scripts/test.py` một lần để cài.", file=sys.stderr)
            return 2
    spec = importlib.util.spec_from_file_location("cadguard_test_runner", ROOT / "scripts" / "test.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    py = runner.ensure_venv([])
    env = dict(os.environ, PYTHONPATH=str(CORE) + os.pathsep + os.environ.get("PYTHONPATH", ""),
               PYTHONUTF8="1", CADGUARD_BENCH_CHILD="1")
    return subprocess.run([str(py), str(Path(__file__).resolve()), *argv], env=env).returncode


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(description="Bộ chấm cad-guard trên DXF tổng hợp (tất định).")
    p.add_argument("--answerer", default=DEFAULT_ANSWERER, metavar="MO_DUN:HAM",
                   help=f"người trả lời (mặc định {DEFAULT_ANSWERER}: tham chiếu, không gọi LLM/mạng)")
    p.add_argument("--threshold", "--nguong", type=float, default=DEFAULT_THRESHOLD, metavar="PHAN_TRAM",
                   help="tỉ lệ đúng tối thiểu để thoát mã 0 (mặc định 100)")
    p.add_argument("--task", action="append", default=[], metavar="ID", help="chỉ chạy tác vụ này (lặp được)")
    p.add_argument("--tasks-dir", default=str(TASKS_DIR), metavar="THU_MUC", help="thư mục tác vụ YAML")
    p.add_argument("--json", action="store_true", help="in kết quả dạng JSON thay cho bảng")
    p.add_argument("--engine", default=None, metavar="TÊN",
                   help="chấm trợ lý THẬT qua engine cad-guard (claude-cli, codex-cli, agy-cli, anthropic, openai, gemini, "
                   "openrouter, ollama); thay cho --answerer. GỌI MÔ HÌNH, TỐN TOKEN")
    p.add_argument("--model", default=None, help="mô hình cho --engine")
    p.add_argument("--account", default=None, choices=["business", "api-key"], help="agy-cli: loại tài khoản (bắt buộc)")
    p.add_argument("--experimental", action="store_true", help="cho phép engine thử nghiệm (codex-cli)")
    p.add_argument("--allow-openrouter", action="store_true", help="cho phép OpenRouter (bên trung gian thứ ba)")
    p.add_argument("--task-timeout", type=float, default=None, metavar="GIÂY", help="thời hạn mỗi tác vụ cho --engine")
    p.add_argument("--out", default=None, metavar="TỆP", help="ghi kết quả tổng hợp JSON (không tên tệp khách)")
    args = p.parse_args(argv)
    if args.engine:
        # Truyền cấu hình cho bench/engine_answerer.py qua biến môi trường (cả khi script chạy lại trong venv).
        os.environ["CADGUARD_BENCH_ENGINE"] = args.engine
        for key, val in (("CADGUARD_BENCH_MODEL", args.model), ("CADGUARD_BENCH_ACCOUNT", args.account),
                         ("CADGUARD_BENCH_TIMEOUT", None if args.task_timeout is None else str(args.task_timeout))):
            if val:
                os.environ[key] = val
        if args.experimental:
            os.environ["CADGUARD_BENCH_EXPERIMENTAL"] = "1"
        if args.allow_openrouter:
            os.environ["CADGUARD_ALLOW_OPENROUTER"] = "1"
        args.answerer = ENGINE_ANSWERER

    rerun = _ensure_deps(argv)
    if rerun is not None:
        return rerun
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _prepare_sys_path()

    tasks = load_tasks(Path(args.tasks_dir))
    errors = [e for t in tasks for e in validate_task(t)]
    if errors:
        print("Tác vụ sai schema:\n" + "\n".join(errors), file=sys.stderr)
        return 2
    if args.task:
        unknown = set(args.task) - {t["id"] for t in tasks}
        if unknown:
            print(f"Không có tác vụ: {sorted(unknown)}", file=sys.stderr)
            return 2
        tasks = [t for t in tasks if t["id"] in args.task]
    if not tasks:
        print("Không có tác vụ nào.", file=sys.stderr)
        return 2
    answerer = resolve_answerer(args.answerer)
    results = run_bench(answerer, tasks)
    pct = score(results)
    label = f"{args.answerer} (engine {args.engine}, mô hình {args.model or 'mặc định'})" if args.engine else args.answerer
    if args.out:
        write_summary(Path(args.out), results, args, pct)
    if args.json:
        print(json.dumps({"answerer": args.answerer, "score_pct": pct, "threshold_pct": args.threshold,
                          "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2))
    else:
        print(format_table(results, label))
    return 0 if pct >= args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
