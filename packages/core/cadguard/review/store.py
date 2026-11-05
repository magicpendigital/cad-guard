"""Dữ liệu vận hành cộng tác tại dự án; không ghi vào telemetry hay lịch sử tổng hợp.

SQLite BEGIN IMMEDIATE + row version + request id: không ghi đè bình luận đồng thời, chống gửi lặp.
Snapshot DXF/SVG bất biến và kiểm hash trước khi xem, duyệt hay xuất bàn giao.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import secrets
import sqlite3
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..agent.workspace import Workspace, PathDenied
from ..app.preview import PREVIEW_MAX_MB, PreviewError, isolated_render, file_sha256
from ..dxf_reader import read_dxf
from ..report import build_report, render_html
from ..runner import audit_model
from ..standard import Standard

from .types import LOCAL, ReviewError
ROLES = {"designer", "customer", "technical"}
ID = re.compile(r"^[0-9a-f]{32}$")



def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReviewError("Nội dung rỗng hoặc quá dài.")
    return value.strip()


def principal(value):
    value = text(value, 254).casefold()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ReviewError("Nhập email đăng nhập Tailscale hợp lệ.")
    return value


class ReviewStore:
    def __init__(self, root: Path):
        self.ws = Workspace(root)
        self.dir = self.ws.root / ".cadguard" / "reviews"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = self.dir / "review.sqlite3"
        with self.connection() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS members (login TEXT PRIMARY KEY, role TEXT NOT NULL, active INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS packages (id TEXT PRIMARY KEY, family TEXT NOT NULL, revision INTEGER NOT NULL,
                    version INTEGER NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (actor TEXT, request TEXT, payload TEXT, result TEXT,
                    PRIMARY KEY(actor,request));
                CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def role(self, actor, c=None):
        if actor == LOCAL:
            return "owner"
        if c is None:
            with self.connection() as conn:
                return self.role(actor, conn)
        row = c.execute("SELECT role FROM members WHERE login=? AND active=1", (actor,)).fetchone()
        if not row:
            raise ReviewError("Chưa được cấp quyền hoặc quyền đã bị thu hồi.", 403)
        return row[0]

    def member(self, actor, login, role, active):
        if actor != LOCAL:
            raise ReviewError("Chỉ quản trị cục bộ được đổi thành viên.", 403)
        login = principal(login)
        if role not in ROLES or not isinstance(active, bool):
            raise ReviewError("Vai trò không hợp lệ.")
        with self.connection() as c:
            c.execute("INSERT OR REPLACE INTO members VALUES (?,?,?)", (login, role, int(active)))
        return {"login": login, "role": role, "active": active}

    def members(self):
        with self.connection() as c:
            return [dict(r) for r in c.execute("SELECT * FROM members ORDER BY login")]

    def origin(self, value=None):
        if value is not None:
            from urllib.parse import urlsplit
            u = urlsplit(value)
            if u.scheme != "https" or not u.hostname or not u.hostname.endswith(".ts.net") or u.path not in ("", "/") or u.query or u.fragment or u.username or u.password:
                raise ReviewError("Cần địa chỉ HTTPS Tailscale .ts.net.")
            value = value.rstrip("/")
            with self.connection() as c:
                c.execute("INSERT OR REPLACE INTO config VALUES ('origin',?)", (value,))
        with self.connection() as c:
            r = c.execute("SELECT value FROM config WHERE key='origin'").fetchone()
            return r[0] if r else None

    def _load(self, c, pid):
        if not isinstance(pid, str) or not ID.fullmatch(pid):
            raise ReviewError("Không có bộ hồ sơ này.", 404)
        row = c.execute("SELECT body FROM packages WHERE id=?", (pid,)).fetchone()
        if not row:
            raise ReviewError("Không có bộ hồ sơ này.", 404)
        return json.loads(row[0])

    def _access(self, actor, p, c):
        role = self.role(actor, c)
        if role == "customer" and actor not in p["customers"]:
            raise ReviewError("Không có bộ hồ sơ này.", 404)
        return role

    def _current(self, c, p):
        return c.execute("SELECT MAX(revision) FROM packages WHERE family=?", (p["family"],)).fetchone()[0] == p["revision"]

    def _save(self, c, p):
        c.execute("INSERT OR REPLACE INTO packages VALUES (?,?,?,?,?)", (p["id"], p["family"], p["revision"], p["version"], json.dumps(p, ensure_ascii=False)))

    def get(self, actor, pid):
        with self.connection() as c:
            p = self._load(c, pid)
            role = self._access(actor, p, c)
            p["current"] = self._current(c, p)
            if p["status"] != "review" and not self._client_ok(p, c):
                p["status"] = "review"
        if role == "customer":
            p["notes"] = [n for n in p["notes"] if n["visibility"] == "shared"]
            p.pop("reports", None)
            p.pop("standards", None)
            p["approvals"] = [{k: v for k, v in a.items() if k != "warnings"} for a in p["approvals"]]
            p["history"] = [e for e in p["history"] if e.get("visibility", "shared") == "shared"]
        return p

    def state(self, actor):
        role = self.role(actor)
        with self.connection() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM packages ORDER BY revision DESC, rowid DESC")]
        packs = []
        for pid in ids:
            try:
                p = self.get(actor, pid)
            except ReviewError as exc:
                if exc.status == 404:
                    continue
                raise
            packs.append({k: p[k] for k in ("id", "name", "revision", "version", "current", "status")})
        return {"role": role, "actor": actor, "packages": packs, "origin": self.origin()}

    def asset(self, actor, pid, item, kind):
        with self.connection() as c:
            p = self._load(c, pid)
            role = self._access(actor, p, c)
        if kind == "dxf" and role == "customer":
            raise ReviewError("Khách không được tải DXF nguồn.", 403)
        if not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < len(p["items"]):
            raise ReviewError("Không có bản vẽ này.", 404)
        if kind not in ("dxf", "svg", "meta"):
            raise ReviewError("Không có tài nguyên này.", 404)
        info = p["items"][item]
        path = self.dir / pid / f"{item}.{ 'json' if kind == 'meta' else kind}"
        data = path.read_bytes()
        if file_sha256(data) != info["hashes"][kind]:
            raise ReviewError("Snapshot đã thay đổi: không được dùng để duyệt.", 409)
        return data

    def _integrity(self, p):
        for i, info in enumerate(p["items"]):
            for kind, ext in (("dxf", "dxf"), ("svg", "svg"), ("meta", "json")):
                path = self.dir / p["id"] / f"{i}.{ext}"
                if not path.is_file() or file_sha256(path.read_bytes()) != info["hashes"][kind]:
                    raise ReviewError("Snapshot đã thay đổi; cần công bố phiên bản mới.", 409)

    def publish(self, actor, body, standards: list[Standard]):
        if self.role(actor) not in ("owner", "designer"):
            raise ReviewError("Chỉ thiết kế được công bố hồ sơ.", 403)
        entries = body.get("items")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 25 or body.get("cad_checked") is not True:
            raise ReviewError("Chọn 1–25 bản vẽ/layout và xác nhận đã đối chiếu trong CAD.")
        if not standards or not any(any(r.enabled and r.implemented for r in s.rules) for s in standards):
            raise ReviewError("Chưa cấu hình chuẩn kiểm bắt buộc.")
        customers = body.get("customers")
        if not isinstance(customers, list) or not customers:
            raise ReviewError("Chọn người khách được quyền chốt bộ hồ sơ.")
        customers = sorted(set(principal(x) for x in customers))
        for login in customers:
            if self.role(login) != "customer":
                raise ReviewError("Người chốt cần có vai trò khách đang hoạt động.")
        name = text(body.get("name"), 120)
        pid = secrets.token_hex(16)
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            replay = self._replay(c, actor, body)
            if replay:
                return replay
            family, revision = pid, 1
            if body.get("previous"):
                prev = self._load(c, body["previous"])
                self._access(actor, prev, c)
                if not self._current(c, prev):
                    raise ReviewError("Hãy tạo từ phiên bản mới nhất.", 409)
                family, revision = prev["family"], prev["revision"] + 1
            items = []
            with tempfile.TemporaryDirectory(prefix="publishing-", dir=self.dir) as tmp:
                staging = Path(tmp)
                for i, ent in enumerate(entries):
                    try:
                        path = self.ws.resolve(ent["file"])
                        layout = text(ent.get("layout", "Model"), 255)
                    except (PathDenied, KeyError, TypeError):
                        raise ReviewError("Chỉ nhận DXF trong dự án.", 403) from None
                    if path.stat().st_size > PREVIEW_MAX_MB * 1024 * 1024:
                        raise ReviewError("Tệp quá lớn để công bố preview đầy đủ.", 422)
                    data = path.read_bytes()
                    try:
                        svg, meta = isolated_render(data, 60, layout)
                    except PreviewError as exc:
                        raise ReviewError(str(exc), 422) from None
                    raw = {"dxf": data, "svg": svg.encode("utf-8"), "meta": json.dumps(meta).encode("utf-8")}
                    for kind, content in raw.items():
                        (staging / f"{i}.{ 'json' if kind == 'meta' else kind}").write_bytes(content)
                    items.append({"name": path.name, "layout": layout, "sha256": file_sha256(data),
                                  "hashes": {k: file_sha256(v) for k, v in raw.items()},
                                  "viewbox": meta["viewbox"], "transform": meta["transform"],
                                  "limitations": meta["limitations"]})
                p = {"schema": "cg.review/1", "id": pid, "family": family, "revision": revision, "version": 1,
                     "epoch": 0, "name": name, "created_at": now(), "customers": customers, "items": items,
                     "standards": [s.model_dump() for s in standards], "notes": [], "reports": [],
                     "approvals": [], "history": [], "status": "review"}
                # Di chuyển chỉ thư mục staging vừa tạo trong vùng review của dự án.
                staging.rename(self.dir / pid)
            self._event(p, actor, "publish")
            self._save(c, p)
            result = {"id": pid, "version": 1}
            self._remember(c, actor, body, result)
            return result

    def _replay(self, c, actor, body):
        key = body.get("request_id")
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise ReviewError("Thiếu mã yêu cầu chống gửi lặp.")
        payload = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        row = c.execute("SELECT payload,result FROM requests WHERE actor=? AND request=?", (actor, key)).fetchone()
        if row:
            if row[0] != payload:
                raise ReviewError("Mã yêu cầu đã dùng cho nội dung khác.", 409)
            return json.loads(row[1])
        return None

    def _remember(self, c, actor, body, result):
        payload = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        c.execute("INSERT INTO requests VALUES (?,?,?,?)", (actor, body["request_id"], payload, json.dumps(result)))

    def _event(self, p, actor, action, visibility="shared"):
        p["history"].append({"actor": actor, "action": action, "at": now(), "epoch": p["epoch"], "visibility": visibility})

    def _invalidate(self, p):
        p["epoch"] += 1
        p["status"] = "review"

    def _anchor(self, p, anchor):
        if anchor is None:
            return None
        if not isinstance(anchor, dict) or anchor.get("kind") not in ("point", "rect"):
            raise ReviewError("Neo ghi chú không hợp lệ.")
        item = anchor.get("item")
        if not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < len(p["items"]):
            raise ReviewError("Bản vẽ của ghi chú không hợp lệ.")
        coords = anchor.get("coords")
        count = 2 if anchor["kind"] == "point" else 4
        if not isinstance(coords, list) or len(coords) != count or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and abs(x) < 1e12 for x in coords):
            raise ReviewError("Tọa độ ghi chú không hợp lệ.")
        handle = anchor.get("handle")
        if handle is not None and (not isinstance(handle, str) or not re.fullmatch(r"[0-9A-Fa-f]{1,32}", handle)):
            raise ReviewError("Handle không hợp lệ.")
        return {"kind": anchor["kind"], "item": item, "coords": coords, "handle": handle,
                "sha256": p["items"][item]["sha256"], "layout": p["items"][item]["layout"]}

    def mutate(self, actor, action, body):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            p = self._load(c, body.get("id"))
            role = self._access(actor, p, c)
            replay = self._replay(c, actor, dict(body, _action=action))
            if replay:
                return replay
            if not self._current(c, p):
                raise ReviewError("Phiên bản cũ: hãy mở bộ hồ sơ mới nhất.", 409)
            if type(body.get("version")) is not int or body["version"] != p["version"]:
                raise ReviewError("Có người vừa cập nhật; tải lại trước khi gửi.", 409)
            if action == "note":
                vis = body.get("visibility", "internal")
                if vis not in ("internal", "shared") or (role == "customer" and vis != "shared"):
                    raise ReviewError("Không có quyền tạo ghi chú này.", 403)
                assignee = body.get("assignee") or None
                if assignee is not None:
                    assignee = principal(assignee)
                    assignee_role = self.role(assignee, c)
                    if assignee_role == "customer" and (assignee not in p["customers"] or vis == "internal"):
                        raise ReviewError("Không phân công ghi chú này cho khách.", 403)
                    if role == "customer" and assignee not in p["customers"]:
                        raise ReviewError("Chỉ thiết kế được phân công nội bộ.", 403)
                p["notes"].append({"id": secrets.token_hex(16), "text": text(body.get("text")), "actor": actor,
                    "at": now(), "visibility": vis, "assignee": assignee, "status": "open",
                    "anchor": self._anchor(p, body.get("anchor")), "replies": []})
                self._invalidate(p)
                self._event(p, actor, action, vis)
            elif action in ("reply", "resolve", "reopen", "assign"):
                note = next((n for n in p["notes"] if n["id"] == body.get("note")), None)
                if note is None or (role == "customer" and note["visibility"] != "shared"):
                    raise ReviewError("Không có ghi chú này.", 404)
                if action != "reply" and role not in ("owner", "designer", "technical"):
                    raise ReviewError("Chỉ thiết kế/kỹ thuật được xử lý ghi chú.", 403)
                if action == "reply":
                    note["replies"].append({"actor": actor, "text": text(body.get("text")), "at": now()})
                    note["status"] = "open"
                    self._invalidate(p)
                elif action == "assign":
                    target = principal(body.get("assignee"))
                    target_role = self.role(target, c)
                    if target_role == "customer" and (target not in p["customers"] or note["visibility"] == "internal"):
                        raise ReviewError("Không phân công ghi chú này cho khách.", 403)
                    note["assignee"] = target
                else:
                    note["status"] = "resolved" if action == "resolve" else "open"
                    if action == "reopen":
                        self._invalidate(p)
                self._event(p, actor, action, note["visibility"])
            elif action == "audit":
                if role not in ("owner", "technical"):
                    raise ReviewError("Chỉ kỹ thuật được quét hồ sơ bàn giao.", 403)
                self._integrity(p)
                reports = []
                for i, item in enumerate(p["items"]):
                    model = read_dxf(self.dir / p["id"] / f"{i}.dxf")
                    for spec in p["standards"]:
                        std = Standard.model_validate(spec)
                        res = audit_model(model, std)
                        report = build_report(std, [(item["name"], item["sha256"], res)])
                        report["internal_errors"] = bool(res.internal_errors)
                        report["item"] = i
                        reports.append(report)
                p["reports"] = reports
                p["status"] = "review" if not self._client_ok(p, c) else "client-approved"
                self._event(p, actor, action, "internal")
            elif action == "approve":
                if role != "customer" or actor not in p["customers"]:
                    raise ReviewError("Chỉ khách được chỉ định mới được chốt thiết kế.", 403)
                self._integrity(p)
                if any(n["status"] == "open" and n["visibility"] == "shared" for n in p["notes"]):
                    raise ReviewError("Còn trao đổi với khách chưa xử lý.", 409)
                p["approvals"].append({"actor": actor, "kind": "client", "epoch": p["epoch"], "at": now()})
                p["status"] = "client-approved" if self._client_ok(p, c) else "review"
                self._event(p, actor, action)
            elif action == "release":
                if role not in ("owner", "technical"):
                    raise ReviewError("Chỉ kỹ thuật được duyệt bàn giao sản xuất.", 403)
                self._integrity(p)
                if not self._client_ok(p, c) or any(n["status"] == "open" for n in p["notes"]):
                    raise ReviewError("Cần khách chốt và xử lý hết ghi chú.", 409)
                if len(p["reports"]) != len(p["items"]) * len(p["standards"]):
                    raise ReviewError("Chưa quét đủ chuẩn trên snapshot này.", 409)
                if any(r["internal_errors"] or r["totals"]["E"] or not r["files"][0]["rules_run"] for r in p["reports"]):
                    raise ReviewError("Còn lỗi E hoặc bộ kiểm chưa chạy đầy đủ.", 409)
                warnings = self.warnings(p)
                decisions = body.get("warnings") or {}
                if not isinstance(decisions, dict) or any(not isinstance(decisions.get(w["id"]), str) or not decisions[w["id"]].strip() or len(decisions[w["id"]]) > 1000 for w in warnings):
                    raise ReviewError("Cần ghi quyết định xử lý từng cảnh báo W.", 409)
                p["approvals"].append({"actor": actor, "kind": "technical", "epoch": p["epoch"], "at": now(), "warnings": decisions})
                p["status"] = "production-ready"
                self._event(p, actor, action)
            else:
                raise ReviewError("Thao tác không được hỗ trợ.", 404)
            p["version"] += 1
            self._save(c, p)
            result = {"id": p["id"], "version": p["version"], "status": p["status"]}
            self._remember(c, actor, dict(body, _action=action), result)
            return result

    def _client_ok(self, p, c):
        for actor in p["customers"]:
            row = c.execute("SELECT active,role FROM members WHERE login=?", (actor,)).fetchone()
            if not row or not row[0] or row[1] != "customer" or not any(a["actor"] == actor and a["kind"] == "client" and a["epoch"] == p["epoch"] for a in p["approvals"]):
                return False
        return True

    @staticmethod
    def warnings(p):
        out = []
        for ri, report in enumerate(p.get("reports", [])):
            for fi, finding in enumerate(report["files"][0]["findings"]):
                if finding["severity"] == "W":
                    out.append({"id": f"{ri}:{fi}", "text": finding["rule_id"] + ": " + finding["message"]})
        return out

    def export(self, actor, pid):
        with self.connection() as c:
            p = self._load(c, pid)
            if self._access(actor, p, c) not in ("owner", "technical"):
                raise ReviewError("Chỉ kỹ thuật được xuất hồ sơ sản xuất.", 403)
            if not self._current(c, p) or p["status"] != "production-ready" or not self._client_ok(p, c):
                raise ReviewError("Hồ sơ chưa sẵn sàng hoặc xác nhận đã mất hiệu lực.", 409)
            self._integrity(p)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(p, ensure_ascii=False, indent=2))
            for i, item in enumerate(p["items"]):
                z.writestr(f"drawings/{i}.dxf", self.asset(actor, pid, i, "dxf"))
            for i, report in enumerate(p["reports"]):
                z.writestr(f"reports/{i}.json", json.dumps(report, ensure_ascii=False))
                z.writestr(f"reports/{i}.html", render_html(report))
        return out.getvalue()
