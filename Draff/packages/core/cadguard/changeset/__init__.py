"""Công cụ ghi an toàn (A2): changeset `cg.changeset/1`, diff theo handle, validate_output.

Quy trình: trợ lý/người dùng ĐỀ XUẤT (chạy khô, xem trước) → NGƯỜI xác nhận và ÁP DỤNG ra tệp mới → kiểm → hoàn tác
bằng cách xoá tệp mới. Tệp gốc không bao giờ bị ghi. Xem docs/changeset.md.
"""

from .apply import Changeset, ChangesetError, apply, load_changeset, propose, undo, workspace_of
from .diff import diff_files
from .engine import Protection
from .ops import OP_HELP, OpError, parse_ops
from .validate import validate_output

__all__ = ["OP_HELP", "Changeset", "ChangesetError", "OpError", "Protection", "apply", "diff_files", "load_changeset",
           "parse_ops", "propose", "undo", "validate_output", "workspace_of"]
