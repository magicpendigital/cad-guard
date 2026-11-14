#!/usr/bin/env python3
"""Kiểm vệ sinh repo cad-guard: quét các tệp ĐÃ ĐƯỢC GIT THEO DÕI (`git ls-files`).

Luật kiểm:
- không có tệp .dwg; không có .dxf ngoài fixtures/synthetic/;
- không có từ cấm: tên thư mục dữ liệu thật cũ, cộng danh sách đọc từ biến môi trường
  CADGUARD_FORBIDDEN_TERMS (phân tách bằng ';' hoặc xuống dòng) và tệp cục bộ .cadguard-forbidden.txt
  ở gốc repo (mỗi dòng một từ, '#' là chú thích; tệp này đã được .gitignore) — để tên khách
  không bao giờ phải ghi vào repo. Từ cấm khớp không phân biệt hoa thường và KHÔNG được in ra;
- không có chuỗi giống khoá (sk-…, AKIA…, ghp_…, khối PRIVATE KEY);
- không có BOM UTF-8 ở đầu tệp văn bản.
Tệp nhị phân (có byte NUL trong 8 KB đầu) được bỏ qua. Ngoại lệ có lý do khai trong EXCEPTIONS.

Dùng: python scripts/check_repo_hygiene.py [--root THƯ_MỤC] [--forbidden-file TỆP]
Mã thoát: 0 = sạch; 1 = có vi phạm; 2 = không chạy được (thiếu git, không phải repo git).
Chỉ dùng thư viện chuẩn.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = "fixtures/synthetic/"
FORBIDDEN_ENV = "CADGUARD_FORBIDDEN_TERMS"
FORBIDDEN_FILE = ".cadguard-forbidden.txt"
# Ghép chuỗi để chính tệp này không chứa nguyên văn từ cấm.
BUILTIN_FORBIDDEN = ["Data" + " sample"]
BOM = b"\xef\xbb\xbf"
BINARY_SNIFF = 8192

# (mã, mô tả, biểu thức). Mẫu được ghép để mã nguồn của script không tự khớp.
SECRET_PATTERNS = [
    ("sk", "khoá dạng sk-…", re.compile(r"sk-" + r"[A-Za-z0-9]{20,}")),
    ("akia", "khoá truy cập AWS (AKIA…)", re.compile(r"AKIA" + r"[0-9A-Z]{16}")),
    ("ghp", "token GitHub (ghp_…)", re.compile(r"ghp_" + r"[A-Za-z0-9]{20,}")),
    ("private-key", "khối khoá riêng (PRIVATE KEY)", re.compile(r"-----" + r"BEGIN .*PRIVATE KEY-----")),
]

# Ngoại lệ: đường dẫn (posix, tương đối gốc repo) -> {mã kiểm: lý do}. Mã kiểm: dwg, dxf, forbidden, secret, bom.
EXCEPTIONS: dict[str, dict[str, str]] = {
    "scripts/check_repo_hygiene.py": {
        "forbidden": "Chứa định nghĩa mẫu dò từ cấm.",
        "secret": "Chứa định nghĩa mẫu dò chuỗi giống khoá.",
    },
    "scripts/bootstrap.ps1": {
        "bom": "Windows PowerShell 5.1 đọc tệp .ps1 không BOM theo bảng mã ANSI, làm hỏng chuỗi tiếng Việt; cần giữ BOM.",
    },
}


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def tracked_files(root: Path) -> list[str]:
    """Danh sách tệp git theo dõi (đường dẫn posix tương đối gốc). Ném RuntimeError nếu git không chạy được."""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False)
    except FileNotFoundError:
        raise RuntimeError("Không tìm thấy lệnh git.") from None
    if proc.returncode != 0:
        raise RuntimeError("Thư mục không phải repo git (git ls-files thất bại).")
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def forbidden_terms(root: Path, extra_file: Path | None = None) -> list[str]:
    terms = list(BUILTIN_FORBIDDEN)
    env = os.environ.get(FORBIDDEN_ENV, "")
    terms += re.split(r"[;\n]", env)
    for f in (root / FORBIDDEN_FILE, extra_file):
        if f is not None and f.is_file():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip().startswith("#"):
                    terms.append(line)
    seen: list[str] = []
    for t in (x.strip() for x in terms):
        if t and t.casefold() not in (s.casefold() for s in seen):
            seen.append(t)
    return seen


def _excepted(rel: str, check: str) -> bool:
    return check in EXCEPTIONS.get(rel, {})


def check(root: Path, terms: list[str]) -> list[str]:
    """Trả danh sách vi phạm (câu tiếng Việt, có mã kiểm trong ngoặc vuông)."""
    out: list[str] = []
    folded = [t.casefold() for t in terms]
    for rel in tracked_files(root):
        low = rel.lower()
        if low.endswith(".dwg") and not _excepted(rel, "dwg"):
            out.append(f"{rel}: [dwg] tệp DWG không được nằm trong repo.")
        if low.endswith(".dxf") and not rel.startswith(SYNTHETIC_DIR) and not _excepted(rel, "dxf"):
            out.append(f"{rel}: [dxf] tệp DXF chỉ được nằm trong {SYNTHETIC_DIR}.")
        path = root / rel
        if not path.is_file():
            continue  # đã xoá khỏi thư mục làm việc nhưng còn trong chỉ mục
        try:
            data = path.read_bytes()
        except OSError:
            out.append(f"{rel}: [doc] không đọc được tệp.")
            continue
        if b"\0" in data[:BINARY_SNIFF]:
            continue  # nhị phân
        if data.startswith(BOM) and not _excepted(rel, "bom"):
            out.append(f"{rel}: [bom] có BOM UTF-8 ở đầu tệp; hãy lưu UTF-8 không BOM.")
        text = data.decode("utf-8", "replace")
        if not _excepted(rel, "forbidden"):
            lines = text.casefold().splitlines()
            for i, term in enumerate(folded, 1):
                for n, line in enumerate(lines, 1):
                    if term in line:
                        # Không in nguyên văn từ cấm (có thể là tên khách); chỉ in số thứ tự.
                        out.append(f"{rel}:{n}: [forbidden] chứa từ cấm số {i}.")
                        break
        if not _excepted(rel, "secret"):
            for n, line in enumerate(text.splitlines(), 1):
                for code, label, pat in SECRET_PATTERNS:
                    if pat.search(line):
                        out.append(f"{rel}:{n}: [secret:{code}] có chuỗi giống {label}.")
    return out


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    p = argparse.ArgumentParser(description="Kiểm vệ sinh các tệp git theo dõi trong repo cad-guard.")
    p.add_argument("--root", default=str(ROOT), help="gốc repo git cần quét (mặc định: repo chứa script này)")
    p.add_argument("--forbidden-file", default=None, help=f"tệp từ cấm bổ sung (ngoài {FORBIDDEN_FILE} và {FORBIDDEN_ENV})")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    terms = forbidden_terms(root, Path(args.forbidden_file) if args.forbidden_file else None)
    try:
        violations = check(root, terms)
    except RuntimeError as exc:
        print(f"Không kiểm được repo: {exc}", file=sys.stderr)
        return 2
    if violations:
        print(f"Phát hiện {len(violations)} vi phạm vệ sinh repo:")
        for v in violations:
            print(f"- {v}")
        return 1
    print(f"Repo sạch: không có vi phạm ({len(terms)} từ cấm được kiểm).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
