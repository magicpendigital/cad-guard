"""`cadguard watch`: thư mục theo dõi (P1b "adapter xuất DXF + thư mục theo dõi"). Khi có DXF mới hoặc vừa đổi (vd. do lệnh
CGXUAT trong AutoCAD), tự kiểm theo chuẩn và ghi báo cáo vào `<thư mục>/.cadguard/reports/<tên>.html|.json`.

- Chỉ thư viện chuẩn (quét định kỳ, không cần gói theo dõi tệp). Chỉ ĐỌC DXF; không bao giờ ghi bản vẽ.
- Tệp còn đang được ghi thì chưa kiểm: phải đứng yên (cùng kích thước + thời gian sửa) qua hai lần quét liên tiếp.
- Bỏ qua thư mục ẩn (`.cadguard`…) và tệp đầu ra của changeset (`*.cg-<mã>.dxf`).
- Báo cáo lấy từ hợp đồng `cg.audit/1` qua `report.build_report`, nên cùng số với CLI, App và trợ lý.
- Telemetry chỉ ghi mã băm nội dung (như `cadguard audit`); báo cáo cục bộ mới có tên tệp.
"""
from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import report, telemetry
from .standard import Standard

REPORT_DIR = Path(".cadguard") / "reports"
OUTPUT_RE = re.compile(r"\.cg-[0-9a-f]{8}\.dxf$", re.IGNORECASE)  # như app/api.py
MAX_FILES = 2000


@dataclass
class WatchEvent:
    rel: str
    ok: bool
    counts: dict | None = None
    rules_run: int = 0
    html: Path | None = None
    error: str | None = None
    seconds: float = 0.0


def report_paths(root: Path, rel: str) -> tuple[Path, Path]:
    """Tên báo cáo theo đường dẫn tương đối (thư mục con nối bằng '__'), trùng tên bản vẽ để CGBAOCAO tìm được."""
    stem = rel[:-4] if rel.lower().endswith(".dxf") else rel
    safe = stem.replace("\\", "/").replace("/", "__")
    base = root / REPORT_DIR
    return base / f"{safe}.html", base / f"{safe}.json"


def scan(root: Path) -> dict[str, tuple[int, int]]:
    """{đường dẫn tương đối: (mtime_ns, kích thước)} của các .dxf cần theo dõi."""
    out: dict[str, tuple[int, int]] = {}
    for p in sorted(root.rglob("*")):
        if len(out) >= MAX_FILES:
            break
        rel_parts = p.relative_to(root).parts
        if any(part.startswith(".") for part in rel_parts[:-1]) or p.suffix.lower() != ".dxf" or OUTPUT_RE.search(p.name):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        if p.is_file():
            out["/".join(rel_parts)] = (st.st_mtime_ns, st.st_size)
    return out


@dataclass
class Watcher:
    root: Path
    standard: Standard
    reader: str = "auto"
    threshold_mb: float = 50.0
    on_event: Callable[[WatchEvent], None] | None = None
    _seen: dict[str, tuple[int, int]] = field(default_factory=dict)  # lần quét trước
    _done: dict[str, tuple[int, int]] = field(default_factory=dict)  # chữ ký đã kiểm

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError("Thư mục theo dõi không tồn tại hoặc không phải thư mục.")

    def poll(self, *, settle: bool = True) -> list[WatchEvent]:
        """Một lượt quét. `settle=False`: kiểm ngay mọi tệp chưa kiểm (không chờ đứng yên) — dùng cho `--once`."""
        now = scan(self.root)
        events = []
        for rel, sig in now.items():
            if self._done.get(rel) == sig:
                continue
            if settle and self._seen.get(rel) != sig:
                continue  # còn đang ghi hoặc mới thấy lần đầu: chờ lượt sau
            events.append(self._audit(rel))
            self._done[rel] = sig
        self._seen = now
        for gone in set(self._done) - set(now):
            self._done.pop(gone, None)
        return events

    def _audit(self, rel: str) -> WatchEvent:
        from .reader_select import choose_reader, read_with
        from .runner import audit_model

        t0 = time.perf_counter()
        path = self.root / rel
        try:
            choice = choose_reader(path, self.reader, self.threshold_mb)
            model = read_with(path, choice.reader)
            res = audit_model(model, self.standard)
        except Exception as exc:  # noqa: BLE001 — tệp hỏng không làm dừng việc theo dõi
            ev = WatchEvent(rel, False, error=f"Không đọc được ({type(exc).__name__}).", seconds=time.perf_counter() - t0)
            self._emit(ev)
            return ev
        rep = report.build_report(self.standard, [(rel, model.file_hash, res)])
        html, js = report_paths(self.root, rel)
        html.parent.mkdir(parents=True, exist_ok=True)
        report.write_json(rep, js)
        report.write_html(rep, html)
        telemetry.record_audit(model.file_hash)
        f = rep["files"][0]
        ev = WatchEvent(rel, True, counts=f["counts"], rules_run=f["rules_run"], html=html,
                        seconds=time.perf_counter() - t0)
        self._emit(ev)
        return ev

    def _emit(self, ev: WatchEvent) -> None:
        if self.on_event:
            self.on_event(ev)


def describe(ev: WatchEvent) -> str:
    if not ev.ok:
        return f"{ev.rel}: {ev.error}"
    c = ev.counts or {}
    return (f"{ev.rel}: {c.get('E', 0)} lỗi, {c.get('W', 0)} cảnh báo, {c.get('I', 0)} thông tin "
            f"({ev.rules_run} luật, {ev.seconds:.1f} s) → {ev.html}")


def run(root: Path, standard: Standard, *, interval: float = 2.0, once: bool = False, reader: str = "auto",
        threshold_mb: float = 50.0, out=None) -> int:
    out = out or sys.stdout
    w = Watcher(root, standard, reader=reader, threshold_mb=threshold_mb,
                on_event=lambda ev: print(describe(ev), file=out, flush=True))
    if once:
        events = w.poll(settle=False)
        if not events:
            print("Không có tệp .dxf nào để kiểm.", file=out)
        return 0 if all(e.ok for e in events) else 1
    print(f"cad-guard watch: đang theo dõi {w.root} (chuẩn {standard.name} {standard.version}, quét mỗi {interval:g} s). "
          "Dừng bằng Ctrl+C.", file=out, flush=True)
    w.poll(settle=False)  # kiểm ngay những gì đã có
    try:
        while True:
            time.sleep(max(0.2, interval))
            w.poll()
    except KeyboardInterrupt:
        print("Đã dừng theo dõi.", file=out)
    return 0


__all__ = ["REPORT_DIR", "WatchEvent", "Watcher", "describe", "report_paths", "run", "scan"]
