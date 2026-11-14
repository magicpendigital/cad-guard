"""Ẩn danh tên trong một phiên."""
import hashlib
import re
import secrets

PREFIX = {"layer": "L", "block": "B", "style": "S", "file": "F", "layout": "Y", "dimstyle": "D"}
TOKEN_RE = re.compile(r"^[" + "".join(PREFIX.values()) + r"]_[0-9a-f]{10}$")


class TokenError(ValueError):
    """Mã ẩn danh không khớp tên nào đã biết."""


class Anonymizer:
    def __init__(self, enabled: bool = True, salt: str | None = None):
        self.enabled = enabled
        self.salt = salt if salt is not None else secrets.token_hex(32)

    def token(self, kind: str, name: str) -> str:
        """Đổi tên thành mã ổn định trong phiên."""
        if not self.enabled or name in ("0", "Model"):
            return name
        prefix = PREFIX[kind]
        return prefix + "_" + hashlib.sha256((self.salt + kind + name).encode()).hexdigest()[:10]

    def decoder(self, names):
        """Hàm giải mã `(kind, value) -> tên thật` cho các tên đã biết `[(kind, name), ...]`.

        - `value` là mã của một tên đã biết cùng loại (kind "any" = mọi loại) -> trả tên thật;
        - `value` trông như mã (L_…, S_…) nhưng không khớp -> TokenError;
        - còn lại (tên thường, ví dụ tên layer mới, "0", "Model") -> giữ nguyên.
        """
        table: dict[tuple[str, str], str] = {}
        for kind, name in names:
            if name:
                table[(kind, self.token(kind, name))] = name
                table[("any", self.token(kind, name))] = name

        def decode(kind: str, value: str) -> str:
            if not self.enabled:
                return value
            real = table.get((kind, value))
            if real is not None:
                return real
            if TOKEN_RE.fullmatch(value or ""):
                raise TokenError(f"Mã '{value}' không khớp tên nào trong bản vẽ (mã chỉ dùng được trong phiên đã cấp).")
            return value

        return decode

    def scrub_text(self, msg: str, names) -> str:
        """Thay tên đã biết trong thông điệp bằng mã phiên."""
        if not self.enabled:
            return msg
        pairs = sorted(((name, self.token(kind, name)) for kind, name in names if name and name not in ("0", "Model")), key=lambda x: -len(x[0]))
        if not pairs:
            return msg
        lookup = dict(reversed(pairs))
        return re.sub("|".join(re.escape(name) for name, _ in pairs), lambda m: lookup[m.group()], msg)
