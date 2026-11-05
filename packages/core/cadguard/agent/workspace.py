"""Rào đường dẫn cho không gian làm việc."""
import os
from pathlib import Path, PureWindowsPath


class PathDenied(ValueError):
    """Đường dẫn không được phép."""


class Workspace:
    def __init__(self, root: Path):
        try:
            self.root = Path(root).resolve(strict=True)
            if not self.root.is_dir():
                raise ValueError
        except (OSError, ValueError, RuntimeError):
            raise PathDenied("Thư mục làm việc không hợp lệ") from None

    def _resolve(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel or "\0" in rel:
            raise PathDenied("Đường dẫn không hợp lệ")
        win = PureWindowsPath(rel)
        if win.drive or win.root or Path(rel).is_absolute() or ".." in rel.replace("\\", "/").split("/"):
            raise PathDenied("Đường dẫn không được phép")
        try:
            path = (self.root / rel.replace("\\", "/")).resolve(strict=True)
            if not path.is_relative_to(self.root):
                raise PathDenied("Đường dẫn nằm ngoài thư mục làm việc")
            return path
        except (OSError, ValueError, RuntimeError):
            raise PathDenied("Đường dẫn không hợp lệ hoặc không tồn tại") from None

    def resolve(self, rel: str) -> Path:
        """Kiểm tra và trả tệp DXF nằm trong thư mục làm việc."""
        path = self._resolve(rel)
        if path.suffix.lower() != ".dxf" or not path.is_file():
            raise PathDenied("Chỉ cho phép tệp DXF thông thường")
        return path

    def list_dxf(self, rel_dir: str = ".", *, limit: int | None = None, max_dirs: int | None = None) -> list[Path]:
        """Liệt kê tệp DXF an toàn trong thư mục con.

        `limit`: dừng khi đã thấy đủ số tệp; `max_dirs`: dừng sau số thư mục đã duyệt (trần cho thư mục rất lớn).
        """
        directory = self._resolve(rel_dir)
        if not directory.is_dir():
            raise PathDenied("Cần một thư mục hợp lệ")
        result = []
        walked = 0
        for base, dirs, files in os.walk(directory, followlinks=False):
            walked += 1
            if (limit is not None and len(result) >= limit) or (max_dirs is not None and walked > max_dirs):
                break
            base_path = Path(base)
            safe_dirs = []
            for name in dirs:
                child = base_path / name
                try:
                    if not child.is_symlink() and not getattr(child, "is_junction", lambda: False)() and child.resolve(strict=True).is_relative_to(self.root):
                        safe_dirs.append(name)
                except (OSError, RuntimeError):
                    continue
            dirs[:] = safe_dirs
            for name in sorted(files):
                if limit is not None and len(result) >= limit:
                    break
                p = base_path / name
                try:
                    if p.suffix.lower() == ".dxf":
                        resolved = p.resolve(strict=True)
                        if resolved.is_relative_to(self.root) and resolved.is_file():
                            result.append(resolved)
                except (OSError, RuntimeError):
                    continue
        return sorted(set(result))
