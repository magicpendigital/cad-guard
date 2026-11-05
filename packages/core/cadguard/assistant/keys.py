"""Khoá API của khách: đọc từ biến môi trường hoặc kho khoá hệ điều hành (gói `keyring`, import lười).

- KHÔNG BAO GIỜ ghi khoá ra tệp; `keyring` không có thì báo tiếng Việt (không có phương án ghi tệp).
- Không in, không log khoá. `status` chỉ nói có/không và nguồn.
- `keyring` KHÔNG phải phụ thuộc của cad-guard; người dùng tự cài nếu muốn lưu khoá trong kho khoá hệ điều hành.
"""
from __future__ import annotations

import os

SERVICE = "cad-guard"
KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
NO_KEYRING = ("Không có gói `keyring` nên không dùng được kho khoá hệ điều hành. Cài bằng `pip install keyring`, "
              "hoặc đặt khoá trong biến môi trường {env} của phiên terminal. cad-guard không ghi khoá ra tệp.")


class KeyStoreError(RuntimeError):
    """Lỗi kho khoá; thông điệp tiếng Việt, không chứa khoá."""


def _keyring():
    try:
        import keyring  # noqa: PLC0415 — import lười, không phải phụ thuộc bắt buộc
    except ImportError:
        return None
    return keyring


def check_provider(provider: str) -> str:
    if provider not in KEY_ENV:
        raise KeyStoreError(f"Nhà cung cấp '{provider}' không dùng khoá (hoặc không có). Chọn một trong: {', '.join(KEY_ENV)}.")
    return KEY_ENV[provider]


def get_key(provider: str) -> str | None:
    """Biến môi trường trước, rồi kho khoá hệ điều hành. Không có -> None."""
    env = KEY_ENV.get(provider)
    if env and os.environ.get(env):
        return os.environ[env]
    kr = _keyring()
    if kr is None or env is None:
        return None
    try:
        return kr.get_password(SERVICE, provider) or None
    except Exception:  # noqa: BLE001 — backend hỏng: coi như không có
        return None


def set_key(provider: str, value: str) -> None:
    env = check_provider(provider)
    if not value or not value.strip():
        raise KeyStoreError("Khoá rỗng; không lưu.")
    kr = _keyring()
    if kr is None:
        raise KeyStoreError(NO_KEYRING.format(env=env))
    try:
        kr.set_password(SERVICE, provider, value.strip())
    except Exception:  # noqa: BLE001
        raise KeyStoreError("Kho khoá hệ điều hành từ chối lưu khoá (backend không khả dụng).") from None


def delete_key(provider: str) -> bool:
    env = check_provider(provider)
    kr = _keyring()
    if kr is None:
        raise KeyStoreError(NO_KEYRING.format(env=env))
    try:
        kr.delete_password(SERVICE, provider)
        return True
    except Exception:  # noqa: BLE001 — không có khoá để xoá
        return False


def key_status(provider: str) -> dict:
    """{"provider", "env": bool, "keyring": bool|None (None = không có gói keyring)}. Không trả khoá."""
    env = check_provider(provider)
    kr = _keyring()
    in_kr = None
    if kr is not None:
        try:
            in_kr = bool(kr.get_password(SERVICE, provider))
        except Exception:  # noqa: BLE001
            in_kr = False
    return {"provider": provider, "env_var": env, "env": bool(os.environ.get(env)), "keyring": in_kr}


# Bí mật vận hành cục bộ, tách khỏi danh sách nhà cung cấp LLM.
LOCAL_SECRET_ENV = {
    "web-password-hash": "CADGUARD_WEB_PASSWORD_HASH",
    "web-app-token": "CADGUARD_WEB_APP_TOKEN",
}


def get_local_secret(name: str) -> str | None:
    if name not in LOCAL_SECRET_ENV:
        raise KeyStoreError("Tên bí mật cục bộ không hợp lệ.")
    value = os.environ.get(LOCAL_SECRET_ENV[name])
    if value:
        return value
    kr = _keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(SERVICE, name) or None
    except Exception:
        return None


def set_local_secret(name: str, value: str) -> None:
    if name not in LOCAL_SECRET_ENV or not isinstance(value, str) or not value:
        raise KeyStoreError("Bí mật cục bộ không hợp lệ.")
    kr = _keyring()
    if kr is None:
        raise KeyStoreError("Cần keyring và kho khóa hệ điều hành; không có phương án ghi bí mật ra tệp.")
    try:
        kr.set_password(SERVICE, name, value)
    except Exception:
        raise KeyStoreError("Không lưu được bí mật trong kho khóa hệ điều hành.") from None
