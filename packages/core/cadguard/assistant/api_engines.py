"""Engine API (cách C): gọi thẳng nhà cung cấp bằng khoá của khách, vòng gọi công cụ tối thiểu, CHỈ công cụ cad-guard.

- Chỉ thư viện chuẩn (`urllib.request`, `json`); không thêm phụ thuộc.
- Công cụ: gọi thẳng `cadguard.agent.tools` qua `ToolBox` (ẩn danh Bậc 1 mặc định; propose chỉ khi allow_propose;
  KHÔNG có apply). Bản vẽ không bao giờ được gửi thô; chỉ kết quả công cụ đã ẩn danh.
- Khoá: biến môi trường hoặc kho khoá hệ điều hành (`keys.py`). Không đưa khoá vào log/lỗi/telemetry/báo cáo.
- Giới hạn: số vòng công cụ, trần token và chi phí mỗi phiên, thời hạn mạng.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator

from . import events as ev
from .base import (CancelToken, Engine, EngineError, EngineInfo, check_server_options, load_system_prompt,
                   normalize_messages, resolve_session)
from .events import Event, Usage
from .keys import get_key
from .toolspec import ToolBox

ANTHROPIC_VERSION = "2026-10-21"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"

# Giá tham khảo USD / 1 triệu token (input, output, đọc cache, ghi cache) — bảng Anthropic 10/2026. Ước tính, không phải hoá đơn.
ANTHROPIC_PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5),
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}


@dataclass(frozen=True)
class Provider:
    name: str
    title: str
    kind: str  # "anthropic" | "openai"
    base_url: str
    key_env: str | None
    default_model: str | None
    terms: str
    default_off: bool = False
    local: bool = False


PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        "anthropic", "Anthropic API (khoá của bạn)", "anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY",
        DEFAULT_ANTHROPIC_MODEL,
        "Khoá API của khách, tính cước trực tiếp cho khách (Commercial Terms). Đường thương mại sạch nhất với Anthropic."),
    "openai": Provider(
        "openai", "OpenAI API (khoá của bạn)", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY", None,
        "Khoá API của tổ chức khách, theo cài đặt dữ liệu của tổ chức API. Đường mặc định cho thương mại với OpenAI."),
    "gemini": Provider(
        "gemini", "Google Gemini API (khoá AI Studio/Enterprise)", "openai",
        "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", None,
        "Google khuyên dùng khoá Gemini Enterprise/AI Studio cho agent bên thứ ba (FAQ Antigravity)."),
    "openrouter": Provider(
        "openrouter", "OpenRouter (bên trung gian thứ ba)", "openai", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
        None,
        "Bên trung gian thứ ba: thêm một chặng chuyển dữ liệu. MẶC ĐỊNH TẮT; chỉ bật rõ (--allow-openrouter) khi khách đồng ý.",
        default_off=True),
    "ollama": Provider(
        "ollama", "Ollama (mô hình cục bộ)", "openai", "http://localhost:11434/v1", None, None,
        "Chạy trên máy: dữ liệu không rời máy. Không cần khoá. Chất lượng gọi công cụ/tiếng Việt tuỳ mô hình (chưa đo).",
        local=True),
}


def provider_model(p: Provider, model: str | None) -> str | None:
    """Mô hình: tham số > biến môi trường CADGUARD_<P>_MODEL > mặc định của nhà cung cấp (nếu có)."""
    return model or os.environ.get(f"CADGUARD_{p.name.upper()}_MODEL") or p.default_model


def provider_base_url(p: Provider, base_url: str | None) -> str:
    return (base_url or os.environ.get(f"CADGUARD_{p.name.upper()}_BASE_URL") or p.base_url).rstrip("/")


_KEYLIKE = re.compile(r"(sk|key|pk|AIza)[-_A-Za-z0-9]{12,}")


def redact(text: str, key: str | None) -> str:
    if key:
        text = text.replace(key, "…")
    return _KEYLIKE.sub("…", text)


class HttpError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def post_json(url: str, body: dict, headers: dict, timeout: float, key: str | None) -> dict:
    """POST JSON; lỗi -> HttpError tiếng Việt không chứa khoá."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URL do cad-guard/người dùng cấu hình
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
            err = payload.get("error") if isinstance(payload, dict) else None
            detail = err.get("message", "") if isinstance(err, dict) else (err if isinstance(err, str) else "")
        except Exception:  # noqa: BLE001
            pass
        detail = redact(str(detail), key)[:300]
        s = exc.code
        if s in (401, 403):
            msg, code = "Khoá API không hợp lệ hoặc không đủ quyền (HTTP %d). Kiểm khoá bằng `cadguard keys status`." % s, "auth"
        elif s == 429:
            msg, code = "Nhà cung cấp báo vượt hạn mức hoặc tốc độ (HTTP 429). Đợi một lát rồi thử lại.", "rate_limit"
        elif s >= 500:
            msg, code = "Máy chủ nhà cung cấp lỗi (HTTP %d). Thử lại sau." % s, "server"
        else:
            msg, code = "Nhà cung cấp từ chối yêu cầu (HTTP %d)." % s, "http"
        if detail and s not in (401, 403):
            msg += f" Chi tiết: {detail}"
        raise HttpError(msg, code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise HttpError(f"Hết thời hạn mạng ({timeout:g} giây) khi gọi nhà cung cấp.", "timeout") from None
        raise HttpError("Không kết nối được tới nhà cung cấp (mạng hoặc địa chỉ sai).", "network") from None
    except json.JSONDecodeError:
        raise HttpError("Nhà cung cấp trả dữ liệu không phải JSON.", "bad_response") from None


class ApiEngine(Engine):
    """Vòng gọi công cụ chung; lớp con lo định dạng yêu cầu/đáp của từng API."""

    def __init__(self, provider: str, *, model: str | None = None, api_key: str | None = None, base_url: str | None = None,
                 max_tool_rounds: int = 12, max_session_tokens: int = 300_000, max_cost_usd: float | None = 2.0,
                 network_timeout: float = 120.0, max_output_tokens: int = 16000, allow_third_party: bool = False):
        if provider not in PROVIDERS:
            raise EngineError(f"Không biết nhà cung cấp '{provider}'.", "provider")
        self.provider = PROVIDERS[provider]
        self.info = EngineInfo(self.provider.name, "api", self.provider.title, self.provider.terms,
                               default_off=self.provider.default_off)
        self.model = provider_model(self.provider, model)
        self._api_key = api_key
        self.base_url = provider_base_url(self.provider, base_url)
        self.max_tool_rounds = int(max_tool_rounds)
        self.max_session_tokens = int(max_session_tokens)
        self.max_cost_usd = max_cost_usd
        self.network_timeout = float(network_timeout)
        self.max_output_tokens = int(max_output_tokens)
        self.allow_third_party = allow_third_party or os.environ.get("CADGUARD_ALLOW_OPENROUTER") == "1"
        self.session_usage = Usage(cost_usd=None)  # cộng dồn qua mọi lượt của phiên (trần token/chi phí)

    def __repr__(self) -> str:  # không bao giờ in khoá
        return f"<{type(self).__name__} provider={self.provider.name} model={self.model}>"

    def _key(self) -> str | None:
        if self.provider.key_env is None:
            return None
        key = self._api_key or get_key(self.provider.name)
        if not key:
            raise EngineError(f"Chưa có khoá API cho '{self.provider.name}'. Đặt biến {self.provider.key_env} hoặc chạy "
                              f"`cadguard keys set {self.provider.name}` (lưu trong kho khoá hệ điều hành).", "no_key")
        return key

    def _check(self) -> None:
        if self.provider.default_off and not self.allow_third_party:
            raise EngineError("OpenRouter là bên trung gian thứ ba (thêm một chặng chuyển dữ liệu) nên mặc định TẮT. Chỉ bật "
                              "khi khách đồng ý: thêm --allow-openrouter (hoặc CADGUARD_ALLOW_OPENROUTER=1).", "disabled")
        if not self.model:
            raise EngineError(f"Chưa chọn mô hình cho '{self.provider.name}': dùng --model hoặc đặt biến "
                              f"CADGUARD_{self.provider.name.upper()}_MODEL.", "no_model")

    def _over_limits(self) -> str | None:
        u = self.session_usage
        if u.total_tokens >= self.max_session_tokens:
            return f"Đã chạm trần {self.max_session_tokens} token của phiên; dừng để tránh tốn thêm."
        if self.max_cost_usd is not None and u.cost_usd is not None and u.cost_usd >= self.max_cost_usd:
            return f"Đã chạm trần chi phí {self.max_cost_usd:g} USD của phiên (ước tính); dừng."
        return None

    def run(self, messages, *, workspace, standard=None, profile=None, allow_propose=False,
            compare_without_profile=False, server_options=None, cancel: CancelToken | None = None) -> Iterator[Event]:
        final = ""
        try:
            self._check()
            msgs = normalize_messages(messages)
            ws, prof = resolve_session(workspace, profile)
            box = ToolBox(ws, standard=standard, profile=prof, allow_propose=allow_propose,
                          compare_without_profile=compare_without_profile, **check_server_options(server_options))
            key = self._key()
        except EngineError as exc:
            yield ev.error(str(exc), exc.code)
            yield ev.done("")
            return
        system = load_system_prompt(include_skills=True)
        if box.compare:
            system += ("\n\nCông cụ `audit` áp hồ sơ công ty; `audit_khong_ho_so` chạy cùng luật KHÔNG áp hồ sơ "
                       "(để so trước/sau hồ sơ).")
        if standard:
            system += f"\n\nChuẩn người dùng chọn cho phiên: {standard}."
        convo = self.start(msgs)
        rounds = 0
        try:
            while True:
                if cancel is not None and cancel.cancelled:
                    yield ev.error("Đã huỷ theo yêu cầu.", "cancelled")
                    break
                limit = self._over_limits()
                if limit:
                    yield ev.error(limit, "budget")
                    break
                resp = self.request(system, convo, box, key)
                u = self.usage_of(resp)
                self.session_usage.add(u)
                yield ev.usage(u)
                texts, calls, stop = self.read(resp)
                for t in texts:
                    yield ev.text(t)
                final = "\n".join(texts) if texts else final
                self.append_assistant(convo, resp)
                if stop == "refusal":
                    yield ev.error("Mô hình từ chối trả lời yêu cầu này.", "refusal")
                    break
                if not calls:
                    if stop == "max_tokens":
                        yield ev.error("Câu trả lời bị cắt vì chạm trần token đầu ra.", "max_tokens")
                    break
                rounds += 1
                if rounds > self.max_tool_rounds:
                    yield ev.error(f"Đã quá {self.max_tool_rounds} vòng gọi công cụ; dừng.", "tool_rounds")
                    break
                results = []
                for call in calls:
                    yield Event("tool_call", {"id": call["id"], "name": call["name"], "arguments": call["arguments"]})
                    content, is_error = box.call(call["name"], call["arguments"])
                    yield Event("tool_result", {"id": call["id"], "name": call["name"], "content": content, "is_error": is_error})
                    results.append((call, content, is_error))
                self.append_results(convo, results)
        except HttpError as exc:
            yield ev.error(str(exc), exc.code)
        yield ev.done(final)

    # ---------- định dạng từng API ----------

    def start(self, msgs: list[dict]) -> list[dict]:
        raise NotImplementedError

    def request(self, system: str, convo: list[dict], box: ToolBox, key: str | None) -> dict:
        raise NotImplementedError

    def usage_of(self, resp: dict) -> Usage:
        raise NotImplementedError

    def read(self, resp: dict) -> tuple[list[str], list[dict], str]:
        raise NotImplementedError

    def append_assistant(self, convo: list[dict], resp: dict) -> None:
        raise NotImplementedError

    def append_results(self, convo: list[dict], results: list) -> None:
        raise NotImplementedError


class AnthropicEngine(ApiEngine):
    """Messages API (`POST /v1/messages`, `x-api-key`, `anthropic-version`) với công cụ do cad-guard định nghĩa."""

    def __init__(self, **kwargs):
        super().__init__("anthropic", **kwargs)

    def start(self, msgs):
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    def request(self, system, convo, box, key):
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": s["name"], "description": s["description"], "input_schema": s["schema"]} for s in box.specs()],
            "messages": convo,
        }
        headers = {"x-api-key": key or "", "anthropic-version": ANTHROPIC_VERSION}
        return post_json(f"{self.base_url}/v1/messages", body, headers, self.network_timeout, key)

    def usage_of(self, resp):
        u = resp.get("usage") or {}
        usage = Usage(int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0),
                      int(u.get("cache_read_input_tokens") or 0), int(u.get("cache_creation_input_tokens") or 0), None, True)
        price = ANTHROPIC_PRICES.get(self.model or "")
        if price:
            pin, pout, pread, pwrite = price
            usage.cost_usd = (usage.input_tokens * pin + usage.output_tokens * pout + usage.cache_read_tokens * pread
                              + usage.cache_write_tokens * pwrite) / 1e6
        return usage

    def read(self, resp):
        texts, calls = [], []
        for block in resp.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
            elif block.get("type") == "tool_use":
                calls.append({"id": block.get("id"), "name": block.get("name"), "arguments": block.get("input") or {}})
        return texts, calls, resp.get("stop_reason") or ""

    def append_assistant(self, convo, resp):
        convo.append({"role": "assistant", "content": resp.get("content") or []})  # giữ nguyên khối (kể cả thinking)

    def append_results(self, convo, results):
        convo.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call["id"], "content": content, "is_error": is_error}
            for call, content, is_error in results]})


class OpenAICompatEngine(ApiEngine):
    """Chat Completions có `tools`/`tool_calls`: openai, gemini (endpoint tương thích), openrouter, ollama."""

    def start(self, msgs):
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    def request(self, system, convo, box, key):
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *convo],
            "tools": [{"type": "function", "function": {"name": s["name"], "description": s["description"],
                                                         "parameters": s["schema"]}} for s in box.specs()],
        }
        if self.provider.name == "openrouter":
            body["usage"] = {"include": True}  # OpenRouter trả `usage.cost`
        headers = {"authorization": f"Bearer {key}"} if key else {}
        return post_json(f"{self.base_url}/chat/completions", body, headers, self.network_timeout, key)

    def usage_of(self, resp):
        u = resp.get("usage") or {}
        cached = int(((u.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0)
        cost = u.get("cost")
        cost = float(cost) if isinstance(cost, (int, float)) else (0.0 if self.provider.local else None)
        return Usage(max(0, int(u.get("prompt_tokens") or 0) - cached), int(u.get("completion_tokens") or 0), cached, 0,
                     cost, True)

    def _message(self, resp) -> dict:
        choices = resp.get("choices") or []
        return (choices[0].get("message") or {}) if choices else {}

    def read(self, resp):
        msg = self._message(resp)
        texts = [msg["content"]] if isinstance(msg.get("content"), str) and msg["content"].strip() else []
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                args = None  # ToolBox báo lỗi tham số cho mô hình
            calls.append({"id": tc.get("id") or f"call_{len(calls)}", "name": fn.get("name"), "arguments": args})
        choices = resp.get("choices") or [{}]
        finish = choices[0].get("finish_reason") or ""
        return texts, calls, {"length": "max_tokens", "content_filter": "refusal"}.get(finish, finish)

    def append_assistant(self, convo, resp):
        msg = self._message(resp)
        out = {"role": "assistant", "content": msg.get("content")}
        if msg.get("tool_calls"):
            out["tool_calls"] = msg["tool_calls"]
        convo.append(out)

    def append_results(self, convo, results):
        for call, content, _ in results:
            convo.append({"role": "tool", "tool_call_id": call["id"], "content": content})


__all__ = ["ANTHROPIC_PRICES", "AnthropicEngine", "ApiEngine", "HttpError", "OpenAICompatEngine", "PROVIDERS", "redact"]
