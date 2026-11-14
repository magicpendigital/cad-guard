"""Trợ lý AI dùng trực tiếp trong cad-guard.

Hai cách (ngoài cách A — dùng gói làm việc từ CLI của người dùng, xem `knowledge/`):
- (B) engine CLI: cad-guard khởi chạy CLI nguyên bản người dùng đã cài và tự đăng nhập (`claude-cli`, `codex-cli`, `agy-cli`).
- (C) engine API: gọi thẳng nhà cung cấp bằng khoá của khách (`anthropic`, `openai`, `gemini`, `openrouter`, `ollama`).

Mọi engine có cùng giao diện `Engine.run(messages, *, workspace, standard, profile, allow_propose) -> Iterator[Event]`.
"""
from __future__ import annotations

from .base import CancelToken, Engine, EngineError, EngineInfo
from .events import Event, Usage

CLI_ENGINES = ("claude-cli", "codex-cli", "agy-cli")
API_ENGINES = ("anthropic", "openai", "gemini", "openrouter", "ollama")
ENGINE_NAMES = CLI_ENGINES + API_ENGINES


def create_engine(name: str, *, model: str | None = None, experimental: bool = False, account: str | None = None,
                  executable=None, timeout: float | None = None, allow_openrouter: bool = False, **api_kwargs) -> Engine:
    """Tạo engine theo tên. Tham số không dùng cho loại engine đó thì bỏ qua."""
    if name in CLI_ENGINES:
        from .cli_engines import AgyCliEngine, ClaudeCliEngine, CodexCliEngine

        kw = {"model": model, "experimental": experimental}
        if timeout:
            kw["timeout"] = timeout
        if name == "claude-cli":
            return ClaudeCliEngine(executable, **kw)
        if name == "codex-cli":
            return CodexCliEngine(executable, **kw)
        return AgyCliEngine(executable, account=account, **kw)
    if name in API_ENGINES:
        from .api_engines import AnthropicEngine, OpenAICompatEngine

        if timeout:
            api_kwargs.setdefault("network_timeout", timeout)
        if name == "anthropic":
            return AnthropicEngine(model=model, **api_kwargs)
        return OpenAICompatEngine(name, model=model, allow_third_party=allow_openrouter, **api_kwargs)
    raise EngineError(f"Không có engine '{name}'. Có: {', '.join(ENGINE_NAMES)}.", "unknown_engine")


def engine_infos() -> list[EngineInfo]:
    from .api_engines import PROVIDERS
    from .cli_engines import AgyCliEngine, ClaudeCliEngine, CodexCliEngine

    out = [ClaudeCliEngine.info, CodexCliEngine.info, AgyCliEngine.info]
    out += [EngineInfo(p.name, "api", p.title, p.terms, default_off=p.default_off) for p in PROVIDERS.values()]
    return out


__all__ = ["API_ENGINES", "CLI_ENGINES", "ENGINE_NAMES", "CancelToken", "Engine", "EngineError", "EngineInfo", "Event",
           "Usage", "create_engine", "engine_infos"]
