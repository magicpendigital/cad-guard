"""Máy chủ HTTP cục bộ của `cadguard app` (chỉ thư viện chuẩn).

An toàn:
- chỉ nghe 127.0.0.1, cổng ngẫu nhiên mặc định;
- mã phiên ngẫu nhiên: mọi `/api/*` cần header `X-CadGuard-Token` khớp (so sánh hằng thời gian);
- `Host` phải là `127.0.0.1:<cổng>` hoặc `localhost:<cổng>` (chống DNS rebinding); `Origin` (nếu có) phải cùng nguồn;
- không CORS; CSP chặt (chỉ tài nguyên của chính máy chủ), `X-Content-Type-Options`, `Referrer-Policy: no-referrer`;
- tệp tĩnh theo danh sách cố định (không nhận đường dẫn tệp từ URL);
- dự án đổi được lúc chạy: mọi rào đường dẫn (`Workspace`) dựng lại cho thư mục mới;
- khoá API chỉ đi MỘT CHIỀU (POST JSON -> kho khoá hệ điều hành); không API nào trả lại khoá.
"""
from __future__ import annotations

import dataclasses
import hmac
import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from ..privacy import effective as privacy_effective, label as privacy_label, set_project_anonymize as privacy_set
from .. import __version__
from ..review.types import ReviewError, LOCAL
from ..standard import ProfileError, find_standards_dir, load_profile
from . import api, bulkfix, connect, history
from .api import DEPARTMENTS_FILE, NAME_RE, ApiError, AppConfig, AppData, load_departments
from .chat import Assistant
from .project import DialogBusy, check_profile_file, check_project_dir, dialog_available, run_dialog
from .settings import Settings, SettingsError

STATIC_DIR = Path(__file__).with_name("static")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
MAX_BODY = 1_000_000
SMALL_BODY = {"/api/ai/key": 4096, "/api/ai/key/delete": 1024, "/api/ai/key/test": 1024}
TOKEN_HEADER = "X-CadGuard-Token"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; font-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}
NO_PROJECT = "Chưa mở dự án: chọn thư mục dự án (nút “Mở thư mục…” hoặc dự án gần đây)."


class CadGuardApp:
    """Một phiên ứng dụng: dự án hiện tại (đổi được lúc chạy) + trợ lý + cấu hình người dùng + mã phiên."""

    def __init__(self, config: AppConfig, *, token: str | None = None, settings: Settings | None = None,
                 settings_path: Path | None = None, dialog: Callable[[str], dict] | None = None,
                 popen: Callable[..., Any] | None = None, which: Callable[[str], str | None] | None = None,
                 key_opener: Callable[..., Any] | None = None, translate_backend: Any = "auto", **assistant_kwargs):
        self.config = config
        self.settings = settings or Settings(settings_path)
        self.dialog = dialog or run_dialog
        self.dialog_ok = dialog is not None or dialog_available()
        self.popen, self.which, self.key_opener = popen, which, key_opener
        self.translate_backend = translate_backend  # "auto" | "none" | đối tượng có complete() (test)
        self.standards_dir = Path(config.standards_dir or find_standards_dir(Path(__file__).resolve())).resolve()
        self.departments = load_departments(config.departments_path or DEPARTMENTS_FILE, self.standard_names())
        self.data: AppData | None = None
        self.on_quit: Callable[[], None] | None = None  # `cadguard app` gán: dừng máy chủ (phiên cũ nhường phiên mới)
        self.profile_note: str | None = None
        self._switch = threading.Lock()
        self.assistant = Assistant(None, config=config, ai_settings=self.settings.ai, **assistant_kwargs)
        self.token = token or secrets.token_urlsafe(32)
        self.port = 0
        self._titles: dict[str, str] | None = None
        self._realtime: dict[str, bool] | None = None
        if config.workspace is not None:
            res = self.open_project(str(Path(config.workspace).resolve()), confirm=True, profile=config.profile_path,
                                    remember=True)
            if not res.get("opened"):
                raise ApiError("Không mở được thư mục làm việc.")

    # ---------- dự án ----------

    def standard_names(self) -> list[str]:
        return sorted(p.stem for p in self.standards_dir.glob("*.yaml")
                      if NAME_RE.fullmatch(p.stem) and not p.stem.startswith("company-profile"))

    def d(self) -> AppData:
        data = self.data
        if data is None:
            raise ApiError(NO_PROJECT, 409)
        return data

    def open_project(self, raw: Any, *, confirm: Any = False, profile: Path | None = None, remember: bool = True) -> dict:
        try:
            path, warning = check_project_dir(raw)
        except ValueError as exc:
            raise ApiError(str(exc)) from None
        if warning and confirm is not True:
            return {"opened": False, "needs_confirm": True, "warning": warning, "name": path.name or str(path)}
        note = None
        prof = profile
        if prof is None:
            saved = self.settings.project(path).get("profile_path")
            if saved:
                try:
                    prof = check_profile_file(saved)
                    load_profile(prof)
                except (ValueError, ProfileError, OSError):
                    prof, note = None, "Hồ sơ công ty đã chọn cho dự án này không còn đọc được; đang dùng mặc định của chuẩn."
        cfg = dataclasses.replace(self.config, workspace=path, profile_path=prof, standards_dir=self.standards_dir)
        try:
            data = AppData(cfg)
        except ProfileError as exc:
            raise ApiError(str(exc)) from None
        with self._switch:
            self.assistant.stop_all()
            self.data = data
            self.assistant.data = data
            self.profile_note = note
            self._titles = None
        if remember:
            try:
                self.settings.touch_recent(path)
            except OSError:
                pass
        return {"opened": True, "session": self.session(), "note": note}

    def set_profile(self, raw: Any) -> dict:
        data = self.d()
        prof = None
        if raw is not None:
            try:
                prof = check_profile_file(raw)
                load_profile(prof)
            except ValueError as exc:
                raise ApiError(str(exc)) from None
            except ProfileError as exc:
                raise ApiError(str(exc)) from None
        try:
            self.settings.set_project_profile(data.ws.root, prof)
        except OSError:
            raise ApiError("Không ghi được cấu hình người dùng.", 500) from None
        return self.open_project(str(data.ws.root), confirm=True, profile=prof)

    def pick(self, kind: str) -> dict:
        if not self.dialog_ok:
            return {"unavailable": True}
        try:
            res = self.dialog(kind)
        except DialogBusy as exc:
            raise ApiError(str(exc), 409) from None
        if res.get("unavailable"):
            return {"unavailable": True}
        return {"path": res.get("path"), "cancelled": not res.get("path")}

    # ---------- dữ liệu tổng hợp ----------

    def _rule_meta(self) -> tuple[dict[str, str], dict[str, bool]]:
        if self._titles is None:
            titles, realtime = {}, {}
            data = self.d()
            for name in data.standard_names():
                try:
                    std = data.load_std(name, with_profile=False)
                except ApiError:
                    continue
                for r in std.rules:
                    titles.setdefault(r.id, r.title)
                    realtime.setdefault(r.id, bool(r.realtime_ok))
            self._titles, self._realtime = titles, realtime
        return self._titles, self._realtime or {}

    def dept_standards(self, dept: Any) -> list[str]:
        """Chuẩn của phòng cho sửa hàng loạt; phòng chỉ xem (3D) hoặc không chọn phòng: dùng chuẩn vệ sinh bản vẽ."""
        data = self.d()
        dep = api.check_dept(data, dept)
        stds = list(dep["standards"]) if dep else []
        return stds or [s for s in ("design-hygiene-v0",) if s in self.standard_names()]

    def home(self, dept: Any) -> dict:
        data = self.d()
        dep = api.check_dept(data, dept) or next(x for x in data.departments["departments"]
                                                 if x["id"] == data.departments["default"])
        drawings = api.list_drawings(data)["drawings"]
        rels = [x["path"] for x in drawings]
        names = data.history.names(rels)
        titles, _rt = self._rule_meta()
        events = data.history.read()
        out = history.home(events, dep, data.departments["departments"], names.get, titles.get)
        cs = api.list_changesets(data)["changesets"]
        agent = [c for c in cs if c.get("created_by") == "agent"]
        out["assistant"] = {
            "agent_proposed": len(agent),
            "agent_applied": sum(1 for c in agent if c.get("applied") and not c["applied"].get("undone_at")),
            "user_applied": sum(1 for c in cs if c.get("created_by") != "agent" and c.get("applied")
                                and not c["applied"].get("undone_at")),
        }
        files = out.pop("files")
        rows = []
        for x in drawings:
            if x["is_output"]:
                continue
            st = files.get(x["path"])
            rows.append({"path": x["path"], "name": x["name"], **(st or {"scanned": False})})
        rows.sort(key=lambda r: r["path"])
        rows.sort(key=lambda r: r.get("last_ts") or "", reverse=True)  # mới quét trước; chưa quét theo tên
        out["drawings"] = rows[:12]
        out["drawings_total"] = len(rows)
        out["dept"] = dep["id"]
        out["has_history"] = bool(events)
        return out

    def overview(self) -> dict:
        data = self.d()
        titles, realtime = self._rule_meta()
        cs = api.list_changesets(data)["changesets"]
        return history.overview(data.history.read(), data.departments["departments"], titles.get, realtime.get, cs)

    def setup_status(self) -> dict:
        from .. import setup

        return {"steps": setup.status()}

    def setup_run(self, step: Any, remove: bool) -> dict:
        from .. import setup

        if not isinstance(step, str):
            raise ApiError("Chưa chọn bước cài đặt.")
        try:
            setup.run(step, remove=remove)
        except setup.SetupError as exc:
            raise ApiError(str(exc)) from None
        except OSError as exc:
            raise ApiError(f"Không ghi được tệp ({type(exc).__name__}).", 500) from None
        return {"steps": setup.status()}

    def _anon(self) -> bool:
        return self.data.anonymize if self.data is not None else privacy_effective(None, self.config.anonymize)

    def set_privacy(self, value: Any) -> dict:
        data = self.d()
        if not isinstance(value, bool):
            raise ApiError("anonymize phải là true/false.")
        if self.config.anonymize is not None:
            raise ApiError("Chế độ dữ liệu đang bị ép bằng cờ dòng lệnh (--anonymize/--no-anonymize).", 409)
        try:
            privacy_set(data.ws.root, value)
        except OSError:
            raise ApiError("Không ghi được cài đặt dự án.", 500) from None
        data.anonymize = value
        return {"anonymize": value, "session": self.session()}

    def quit(self) -> dict:
        """Tắt phiên (lối tắt gọi khi phiên đang chạy mã cũ). Chỉ khi chạy bằng `cadguard app`."""
        if self.on_quit is None:
            raise ApiError("Phiên này không tắt từ xa được.", 409)
        threading.Timer(0.3, self.on_quit).start()
        return {"quitting": True}

    def session(self) -> dict:
        data = self.data
        prof = data.profile if data else None
        eff = self.assistant.effective()
        return {
            "app": "cad-guard", "version": __version__,
            "project": None if data is None else {"name": data.ws.root.name or str(data.ws.root)},
            "workspace_name": None if data is None else (data.ws.root.name or str(data.ws.root)),
            "profile": None if prof is None else {"name": prof.name, "version": prof.version, "standard": prof.standard,
                                                  "description": prof.description},
            "profile_note": self.profile_note,
            "anonymize": self._anon(),
            "anonymize_forced": self.config.anonymize is not None,
            "data_mode": privacy_label(self._anon()),
            "flags": {"experimental": eff["experimental"], "allow_openrouter": eff["allow_openrouter"],
                      "account": eff["account"], "cli_experimental": self.config.experimental,
                      "cli_allow_openrouter": self.config.allow_openrouter, "cli_account": self.config.account},
            "standards": self.standard_names(),
            "dialog_available": self.dialog_ok,
            **self.departments,
        }

    # ---------- Kết nối AI ----------

    def ai_settings(self) -> dict:
        names = [i.name for i in self.assistant.engine_lister()]
        view = connect.ai_view(self.settings.ai(), names)
        view["cli_flags"] = {"experimental": self.config.experimental, "allow_openrouter": self.config.allow_openrouter,
                             "account": self.config.account}
        return view

    def update_ai(self, body: dict) -> dict:
        try:
            self.settings.update_ai(body)
        except SettingsError as exc:
            raise ApiError(str(exc)) from None
        except OSError:
            raise ApiError("Không ghi được cấu hình người dùng.", 500) from None
        return self.ai_settings()

    @staticmethod
    def _conn(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except connect.ConnectError as exc:
            raise ApiError(str(exc), exc.status) from None

    # ---------- định tuyến ----------

    def routes(self) -> dict[tuple[str, str], Callable[[dict, dict], Any]]:
        d = self.d
        a = self.assistant

        def q1(q: dict, key: str):
            v = q.get(key)
            return v[0] if v else None

        def login(b: dict) -> dict:
            kw = {"popen": self.popen} if self.popen else {}
            if self.which:
                kw["which"] = self.which
            return self._conn(lambda: connect.open_login(b.get("engine"), a.effective()["ai"] | {
                "agy_account": a.effective()["account"]}, **kw))

        return {
            ("GET", "/api/review/state"): lambda q, b: d().reviews().state(LOCAL),
            ("POST", "/api/review/action"): lambda q, b: d().reviews().call(LOCAL, b.get("action", ""), {k: v for k, v in b.items() if k != "action"}),
            ("GET", "/api/session"): lambda q, b: self.session(),
            ("POST", "/api/app/quit"): lambda q, b: self.quit(),
            ("GET", "/api/projects"): lambda q, b: {"current": self.session()["project"], "recent": self.settings.recent(),
                                                    "dialog_available": self.dialog_ok},
            ("POST", "/api/project/pick"): lambda q, b: self.pick("folder"),
            ("POST", "/api/project/open"): lambda q, b: self.open_project(b.get("path"), confirm=b.get("confirm")),
            ("POST", "/api/project/forget"): lambda q, b: {"removed": self.settings.forget_recent(b.get("path"))
                                                           if isinstance(b.get("path"), str) else False},
            ("POST", "/api/project/profile/pick"): lambda q, b: self.pick("profile"),
            ("POST", "/api/project/profile"): lambda q, b: self.set_profile(b.get("path")),
            ("POST", "/api/project/privacy"): lambda q, b: self.set_privacy(b.get("anonymize")),
            ("GET", "/api/drawings"): lambda q, b: api.list_drawings(d()),
            ("POST", "/api/audit"): lambda q, b: api.audit_file(d(), b.get("file"), b.get("standard"), b.get("dept")),
            ("POST", "/api/autocad/show"): lambda q, b: api.show_in_autocad(d(), b.get("file"), b.get("handles"),
                                                                            b.get("layers")),
            ("POST", "/api/sheets"): lambda q, b: api.sheets_info(d(), b.get("file")),
            ("POST", "/api/sheets/lock"): lambda q, b: api.lock_sheet(d(), b.get("file"), b.get("sheet"),
                                                                     b.get("standards"), b.get("confirm")),
            ("POST", "/api/sheets/unlock"): lambda q, b: api.unlock_sheet(d(), b.get("file"), b.get("sheet")),
            ("POST", "/api/findings/ack"): lambda q, b: api.ack_finding(d(), b.get("file"), b.get("standard"),
                                                                       b.get("rule_id"), b.get("sheet"), b.get("kind"),
                                                                       b.get("reason", ""), bool(b.get("undo"))),
            ("POST", "/api/audit_all"):lambda q, b: api.audit_all(d(), b.get("standard"), b.get("dept")),
            ("GET", "/api/explain"): lambda q, b: api.explain(d(), q1(q, "rule"), q1(q, "standard")),
            ("POST", "/api/summary"): lambda q, b: api.summary(d(), b.get("file")),
            ("POST", "/api/geometry"): lambda q, b: api.geometry(d(), b.get("file")),
            ("POST", "/api/preview"): lambda q, b: api.preview(d(), b.get("file"), b.get("wait"), b.get("layout", "Model")),
            ("POST", "/api/scene"): lambda q, b: api.scene3d(d(), b.get("file"), b.get("item")),
            ("POST", "/api/scene/set"): lambda q, b: api.scene_action(d(), b.get("file"), "set", b),
            ("POST", "/api/scene/propose"): lambda q, b: api.scene_action(d(), b.get("file"), "propose", b),
            ("POST", "/api/scene/prompt"): lambda q, b: api.scene_action(d(), b.get("file"), "prompt", b),
            ("POST", "/api/scene/glb"): lambda q, b: api.scene_action(d(), b.get("file"), "glb", b),
            ("POST", "/api/handover"): lambda q, b: api.handover(d(), b.get("file"), b.get("dept")),
            ("GET", "/api/home"): lambda q, b: self.home(q1(q, "dept")),
            ("GET", "/api/overview"): lambda q, b: self.overview(),
            ("GET", "/api/rules"): lambda q, b: api.rules_table(d(), q1(q, "standard")),
            ("POST", "/api/rules/update"): lambda q, b: api.update_rule(d(), b.get("standard"), b.get("rule_id"),
                                                                       b.get("changes"), b.get("scope", "project")),
            ("POST", "/api/rules/learn_layers"): lambda q, b: api.learn_layers(d(), b.get("file"), b.get("standard"),
                                                                              b.get("scope", "project")),
            ("GET", "/api/template"): lambda q, b: api.template_info(d()),
            ("GET", "/api/setup"): lambda q, b: self.setup_status(),
            ("POST", "/api/setup/run"): lambda q, b: self.setup_run(b.get("step"), b.get("remove") is True),
            ("POST", "/api/translate"): lambda q, b: api.translate_drawing(d(), b.get("file"), b.get("to"), b.get("sheet"),
                                                                          self.translate_backend, b.get("mode") or "copy"),
            ("POST", "/api/template/learn"): lambda q, b: api.template_learn(d(), b.get("file"), b.get("sheet"),
                                                                            b.get("logo"), b.get("name")),
            ("POST", "/api/rules/reset"): lambda q, b: api.reset_rule(d(), b.get("standard"), b.get("rule_id"),
                                                                     b.get("scope", "project")),
            ("POST", "/api/changeset/suggest"): lambda q, b: api.suggest_ops(d(), b.get("file"), b.get("standard")),
            ("POST", "/api/changeset/propose"): lambda q, b: api.propose_changeset(
                d(), b.get("file"), b.get("standard"), b.get("ops"), b.get("protected_layers")),
            ("GET", "/api/changeset"): lambda q, b: api.get_changeset(d(), q1(q, "id")),
            ("GET", "/api/changesets"): lambda q, b: api.list_changesets(d()),
            ("POST", "/api/changeset/apply"): lambda q, b: api.apply_changeset(d(), b.get("changeset_id"), b.get("confirm")),
            ("POST", "/api/fix/bulk/plan"): lambda q, b: bulkfix.plan(d(), b.get("file"), self.dept_standards(b.get("dept")),
                                                                      unicode=b.get("unicode") is not False),
            ("POST", "/api/fix/bulk/apply"): lambda q, b: bulkfix.apply(d(), b.get("changeset_id"), b.get("confirm"),
                                                                        b.get("backup")),
            ("POST", "/api/changeset/undo"): lambda q, b: api.undo_changeset(d(), b.get("changeset_id"), b.get("confirm")),
            ("GET", "/api/engines"): lambda q, b: a.engines(refresh=q1(q, "refresh") == "1"),
            ("POST", "/api/chat/stop"): lambda q, b: {"stopped": a.stop(b.get("run_id"))},
            ("GET", "/api/ai/settings"): lambda q, b: self.ai_settings(),
            ("POST", "/api/ai/settings"): lambda q, b: self.update_ai(b),
            ("POST", "/api/ai/key"): lambda q, b: self._conn(lambda: connect.save_key(b.get("provider"), b.get("key"))),
            ("POST", "/api/ai/key/delete"): lambda q, b: self._conn(lambda: connect.delete_key(b.get("provider"))),
            ("POST", "/api/ai/key/test"): lambda q, b: self._conn(lambda: connect.check_key(
                b.get("provider"), a.effective()["ai"] | {"allow_openrouter": a.effective()["allow_openrouter"]},
                opener=self.key_opener)),
            ("POST", "/api/ai/cli/login"): lambda q, b: login(b),
        }


def make_handler(app: CadGuardApp):
    routes = app.routes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "cadguard-app"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def log_message(self, format, *args):  # noqa: A002 — không ghi nhật ký truy cập (URL/thân có thể chứa mã, khoá)
            return

        # ----- tiện ích -----

        def _headers(self, status: int, ctype: str, length: int | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.send_header("Connection", "close")
            self.end_headers()

        def _json(self, status: int, obj: Any) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            if self.command != "HEAD":
                self.wfile.write(body)

        def _error(self, status: int, message: str, hint: dict | None = None) -> None:
            # Windows gửi RST nếu đóng socket còn thân POST chưa đọc: client mất cả phản hồi 4xx.
            if self.command == "POST" and not getattr(self, "_body_consumed", False):
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    if 0 < n <= MAX_BODY:
                        old_timeout = self.connection.gettimeout()
                        try:
                            self.connection.settimeout(.25)
                            self.rfile.read(n)
                        finally:
                            self.connection.settimeout(old_timeout)
                except (ValueError, OSError):
                    pass
                self._body_consumed = True
            from .guidance import hint_for

            self._json(status, {"error": message, "hint": hint or hint_for(message, status)})

        def _allowed_hosts(self) -> set[str]:
            port = self.server.server_address[1]
            return {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _host_ok(self) -> bool:
            return (self.headers.get("Host") or "").strip().lower() in self._allowed_hosts()

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return origin.strip().lower() in {f"http://{h}" for h in self._allowed_hosts()}

        def _token_ok(self) -> bool:
            got = self.headers.get(TOKEN_HEADER) or ""
            return hmac.compare_digest(got.encode("utf-8", "replace"), app.token.encode("utf-8"))

        def _body(self, path: str) -> dict:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError("Content-Length sai.") from None
            if n < 0 or n > SMALL_BODY.get(path, MAX_BODY):
                raise ApiError("Yêu cầu quá lớn.", 413)
            if n == 0:
                return {}
            self._body_consumed = True
            raw = self.rfile.read(n)
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                raise ApiError("Chỉ nhận JSON (Content-Type: application/json).", 415)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ApiError("JSON không hợp lệ.") from None
            if not isinstance(data, dict):
                raise ApiError("Thân yêu cầu phải là một đối tượng JSON.")
            return data

        # ----- xử lý -----

        def _handle(self, method: str) -> None:
            self._body_consumed = False
            if not self._host_ok():
                self._error(421, "Host không hợp lệ: chỉ nhận 127.0.0.1 hoặc localhost với đúng cổng của phiên.")
                return
            parts = urlsplit(self.path)
            path = parts.path
            if method in ("GET", "HEAD") and path in ("/review.html", "/review.js", "/review.css"):
                from ..review.server import STATIC
                filename, kind = {"/review.html": ("index.html", "text/html; charset=utf-8"), "/review.js": ("review.js", "text/javascript"), "/review.css": ("review.css", "text/css")}[path]
                content = (STATIC / filename).read_bytes()
                self._headers(200, kind, len(content))
                if method != "HEAD":
                    self.wfile.write(content)
                return
            if not path.startswith("/api/"):
                if method in ("GET", "HEAD") and path in STATIC_FILES:
                    name, ctype = STATIC_FILES[path]
                    body = (STATIC_DIR / name).read_bytes()
                    self._headers(200, ctype, len(body))
                    if method != "HEAD":
                        self.wfile.write(body)
                    return
                self._error(404, "Không có trang này.")
                return
            if not self._origin_ok():
                self._error(403, "Nguồn yêu cầu (Origin) không được phép.")
                return
            if not self._token_ok():
                self._error(401, "Thiếu hoặc sai mã phiên. Mở đúng địa chỉ in ra khi chạy `cadguard app`.")
                return
            try:
                body = self._body(path) if method == "POST" else {}
                if method == "POST" and path == "/api/chat":
                    self._chat(body)
                    return
                fn = routes.get((method, path))
                if fn is None:
                    self._error(404 if not any(p == path for _, p in routes) else 405, "Không có API này.")
                    return
                self._json(200, fn(parse_qs(parts.query), body))
            except (ApiError, ReviewError) as exc:
                self._error(exc.status, str(exc), getattr(exc, "hint", None))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ (đường dẫn, khoá) ra trình duyệt
                code = log_internal_error(path)
                try:
                    self._error(500, f"Lỗi nội bộ của CAD Guard (mã {code}). Chi tiết đã ghi vào nhật ký lỗi trên máy này.")
                except OSError:
                    pass

        def _chat(self, body: dict) -> None:
            run, meta = app.assistant.start(body)
            self._headers(200, "application/x-ndjson; charset=utf-8")

            def send(obj: dict) -> None:
                self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

            try:
                send(meta)
                while True:
                    alive, ev = app.assistant.next_event(run)
                    if ev is not None:
                        send(ev)
                    if not alive:
                        break
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                run.cancel.cancel()  # trình duyệt đóng: dừng engine
            finally:
                app.assistant.finish(run)

        def do_GET(self):  # noqa: N802
            self._handle("GET")

        def do_HEAD(self):  # noqa: N802
            self._handle("HEAD")

        def do_POST(self):  # noqa: N802
            self._handle("POST")

        def do_PUT(self):  # noqa: N802
            self._error(405, "Phương thức không được hỗ trợ.")

        do_DELETE = do_PATCH = do_OPTIONS = do_PUT  # không CORS: OPTIONS bị từ chối

    return Handler


def log_internal_error(api_path: str) -> str:
    """Ghi traceback vào `<thư mục cấu hình>/logs/app-errors.log` (chỉ trên máy; ứng dụng chạy ngầm không có cửa sổ
    dòng lệnh). Trả mã ngắn để người dùng đối chiếu khi báo lỗi; trình duyệt không thấy chi tiết."""
    import secrets
    import time
    import traceback

    code = "E-" + secrets.token_hex(3).upper()
    print(f"cadguard app: lỗi nội bộ {code} khi xử lý {api_path}.", file=sys.stderr)
    try:
        from .settings import config_dir

        d = config_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "app-errors.log"
        if f.is_file() and f.stat().st_size > 2_000_000:
            f.replace(d / "app-errors.old.log")
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {code} {api_path}" + chr(10) + traceback.format_exc() + chr(10))
    except OSError:
        pass
    return code


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def create_server(app: CadGuardApp, port: int = 0) -> AppServer:
    """Tạo máy chủ nghe 127.0.0.1 (chưa chạy). `port=0` = cổng ngẫu nhiên."""
    srv = AppServer(("127.0.0.1", int(port)), make_handler(app))
    app.port = srv.server_address[1]
    return srv


def url_of(app: CadGuardApp) -> str:
    return f"http://127.0.0.1:{app.port}/?t={app.token}"


def start_in_thread(app: CadGuardApp, port: int = 0) -> tuple[AppServer, threading.Thread]:
    srv = create_server(app, port)
    t = threading.Thread(target=srv.serve_forever, name="cadguard-app", daemon=True)
    t.start()
    return srv, t


__all__ = ["CSP", "CadGuardApp", "AppServer", "SECURITY_HEADERS", "TOKEN_HEADER", "create_server", "start_in_thread",
           "url_of"]
