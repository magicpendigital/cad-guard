"""Ẩn danh tên trong một phiên."""
import hashlib
import secrets


class Anonymizer:
    def __init__(self, enabled: bool = True, salt: str | None = None):
        self.enabled = enabled
        self.salt = salt if salt is not None else secrets.token_hex(32)

    def token(self, kind: str, name: str) -> str:
        """Đổi tên thành mã ổn định trong phiên."""
        if not self.enabled or name in ("0", "Model"):
            return name
        prefix = {"layer": "L", "block": "B", "style": "S", "file": "F", "layout": "Y"}[kind]
        return prefix + "_" + hashlib.sha256((self.salt + kind + name).encode()).hexdigest()[:10]

    def scrub_text(self, msg: str, names) -> str:
        """Thay tên đã biết trong thông điệp bằng mã phiên."""
        if not self.enabled:
            return msg
        import re
        pairs = sorted(((name, self.token(kind, name)) for kind, name in names if name and name not in ("0", "Model")), key=lambda x: -len(x[0]))
        if not pairs:
            return msg
        lookup = dict(reversed(pairs))
        return re.sub("|".join(re.escape(name) for name, _ in pairs), lambda m: lookup[m.group()], msg)
