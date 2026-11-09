"""Đưa người dùng tới đối tượng lỗi trong AutoCAD (M2 + M3, duyệt 09/11/2026). CHỈ điều hướng, không sửa bản vẽ.

Hai đường, dùng chung một tệp yêu cầu `<thư mục làm việc>/.cadguard/goto.txt` (UTF-8, không BOM):

    F <tên bản vẽ không đuôi>
    H <handle>          (nhiều dòng)
    L <tên layer>       (nhiều dòng)

- **M2 (theo tệp, chạy cả AutoCAD LT):** giao diện ghi tệp; người dùng gõ `CGDEN` trong AutoCAD; `cadguard.lsp` đọc tệp,
  phóng tới và chọn đối tượng.
- **M3 (COM, chỉ Windows + AutoCAD bản đầy đủ, cần pywin32):** sau khi ghi tệp, cad-guard tìm bản vẽ đang mở trong
  AutoCAD, đưa cửa sổ lên trước và gửi đúng MỘT biểu thức cố định `(cg:den "<tệp yêu cầu>")`. Không gửi lệnh nào khác,
  không đọc/ghi đối tượng qua COM, không lưu. Không có AutoCAD/pywin32 hoặc AutoCAD đang bận thì trả lý do và người dùng
  gõ `CGDEN` như M2.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

GOTO_REL = ".cadguard/goto.txt"
LSP_PATH = Path(__file__).with_name("cadguard.lsp")
HANDLE_RE = re.compile(r"^[0-9A-F]{1,16}$")
MAX_HANDLES = 200
MAX_LAYERS = 100
MAX_LAYER_LEN = 255
PROGID = "AutoCAD.Application"


class BridgeError(ValueError):
    """Lỗi trả cho người dùng/trợ lý: câu tiếng Việt, không tên bản vẽ/layer, không đường dẫn."""


@dataclass
class GotoRequest:
    drawing: str  # tên bản vẽ không đuôi (khớp với DWGNAME trong AutoCAD)
    handles: list[str] = field(default_factory=list)
    layers: list[str] = field(default_factory=list)
    truncated: bool = False

    def text(self) -> str:
        lines = [f"F {self.drawing}"] + [f"H {h}" for h in self.handles] + [f"L {n}" for n in self.layers]
        return "\n".join(lines) + "\n"

    def toi_command(self) -> str | None:
        """Lệnh CGTOI tương đương (để chép tay khi không dùng CGDEN); None nếu chỉ có layer."""
        return "CGTOI " + ",".join(self.handles) if self.handles else None


def make_request(rel: str, handles: Any = None, layers: Any = None) -> GotoRequest:
    """Kiểm và chuẩn hoá yêu cầu. Handle: số hex (tối đa 16 ký tự); layer: không xuống dòng, ≤ 255 ký tự.

    Quá trần thì cắt (truncated = True) thay vì báo lỗi: nhóm lỗi lớn vẫn nhảy được tới phần đầu.
    """
    stem = Path(str(rel)).stem
    if not stem or "\n" in stem or "\r" in stem:
        raise BridgeError("Tên bản vẽ không hợp lệ.")
    hs: list[str] = []
    for h in _as_list(handles, "handles"):
        h = h.strip().upper()
        if not HANDLE_RE.fullmatch(h):
            raise BridgeError("Handle không hợp lệ: chỉ nhận số hex như 2A3F.")
        if h not in hs:
            hs.append(h)
    ls: list[str] = []
    for n in _as_list(layers, "layers"):
        if not n or len(n) > MAX_LAYER_LEN or any(c in n for c in "\r\n\x00"):
            raise BridgeError("Tên layer không hợp lệ.")
        if n not in ls:
            ls.append(n)
    if not hs and not ls:
        raise BridgeError("Phát hiện này không có handle hay layer để tìm trong AutoCAD.")
    truncated = len(hs) > MAX_HANDLES or len(ls) > MAX_LAYERS
    return GotoRequest(stem, hs[:MAX_HANDLES], ls[:MAX_LAYERS], truncated)


def _as_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not all(isinstance(x, str) for x in value):
        raise BridgeError(f"'{name}' phải là danh sách chuỗi.")
    return list(value)


def goto_path(ws_root: Path) -> Path:
    return Path(ws_root).resolve() / GOTO_REL


def write_goto(ws_root: Path, req: GotoRequest) -> Path:
    """Ghi tệp yêu cầu (ghi tệp tạm rồi thay, để AutoCAD không đọc nửa chừng)."""
    p = goto_path(ws_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(req.text().encode("utf-8"))
    tmp.replace(p)
    return p


def lisp_call(path: Path) -> str:
    """Biểu thức DUY NHẤT gửi sang AutoCAD. Đường dẫn đổi sang dấu / (AutoLISP nhận được) và không chứa dấu nháy kép."""
    s = Path(path).resolve().as_posix()
    if '"' in s or "\n" in s:
        raise BridgeError("Đường dẫn thư mục làm việc có ký tự không hợp lệ.")
    lsp = LSP_PATH.resolve().as_posix()
    # Chưa nạp cadguard.lsp thì nạp tệp đi kèm gói (AutoCAD có thể hỏi bảo mật một lần).
    return f'(progn (if (not cg:den) (load "{lsp}" "")) (if cg:den (cg:den "{s}") (princ "\\n[cad-guard] Chưa nạp cadguard.lsp: chạy APPLOAD.")) (princ))\n'


# ---------- M3: COM ----------

def _connect_default() -> Any:
    if sys.platform != "win32":
        raise BridgeError("Mở thẳng AutoCAD chỉ có trên Windows. Gõ CGDEN trong AutoCAD.")
    try:
        import pythoncom  # noqa: F401
        import win32com.client
    except ImportError:
        raise BridgeError("Chưa cài pywin32 (extras [autocad]). Gõ CGDEN trong AutoCAD.") from None
    try:
        return win32com.client.GetActiveObject(PROGID)
    except Exception:  # noqa: BLE001 — pywintypes.com_error: không có AutoCAD đang chạy
        raise BridgeError("Không thấy AutoCAD đang chạy (hoặc là AutoCAD LT, không hỗ trợ). Gõ CGDEN trong AutoCAD.") from None


def _foreground_default(hwnd: int) -> None:
    """Đưa cửa sổ AutoCAD lên trước. Windows có thể chặn khi tiến trình khác đang ở trước; khi đó bỏ qua."""
    try:
        import win32api
        import win32con
        import win32gui

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Nhấn-nhả phím Alt: Windows cho phép tiến trình nền đổi cửa sổ trước (không gửi phím nào tới AutoCAD).
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:  # noqa: BLE001
        pass


def send_via_com(drawing: str, path: Path, *, connect: Callable[[], Any] | None = None,
                 foreground: Callable[[int], None] | None = None) -> None:
    """Tìm bản vẽ `drawing` đang mở trong AutoCAD, kích hoạt, gửi `lisp_call(path)`. Lỗi -> BridgeError."""
    com_init = connect is None and sys.platform == "win32"
    if com_init:
        try:
            import pythoncom

            pythoncom.CoInitialize()  # gọi từ luồng của máy chủ HTTP
        except ImportError:
            com_init = False
    try:
        acad = (connect or _connect_default)()
        try:
            doc = None
            for d in acad.Documents:
                if Path(str(d.Name)).stem.lower() == drawing.lower():
                    doc = d
                    break
            if doc is None:
                raise BridgeError("Bản vẽ này chưa mở trong AutoCAD. Mở bản vẽ rồi bấm lại.")
            if str(acad.ActiveDocument.Name) != str(doc.Name):
                doc.Activate()
            if int(doc.GetVariable("CMDACTIVE") or 0):
                raise BridgeError("AutoCAD đang chạy một lệnh. Nhấn Esc trong AutoCAD rồi bấm lại.")
            try:
                (foreground or _foreground_default)(int(acad.HWND))
            except Exception:  # noqa: BLE001
                pass
            doc.SendCommand(lisp_call(path))
        except BridgeError:
            raise
        except Exception:  # noqa: BLE001 — com_error: AutoCAD bận (hộp thoại mở) hoặc vừa đóng
            raise BridgeError("AutoCAD không nhận lệnh (có thể đang mở hộp thoại). Đóng hộp thoại rồi bấm lại, "
                              "hoặc gõ CGDEN trong AutoCAD.") from None
    finally:
        if com_init:
            import pythoncom

            pythoncom.CoUninitialize()


def show(ws_root: Path, rel: str, handles: Any = None, layers: Any = None, *, com: bool = True,
         connect: Callable[[], Any] | None = None, foreground: Callable[[int], None] | None = None) -> dict:
    """Ghi yêu cầu; nếu `com` thì thử gửi thẳng sang AutoCAD (M3). Không bao giờ ném lỗi vì AutoCAD vắng mặt."""
    req = make_request(rel, handles, layers)
    p = write_goto(ws_root, req)
    out = {"written": True, "command": "CGDEN", "toi_command": req.toi_command(), "handles": len(req.handles),
           "layers": len(req.layers), "truncated": req.truncated, "sent": False, "message": ""}
    if com:
        try:
            send_via_com(req.drawing, p, connect=connect, foreground=foreground)
            out["sent"] = True
            out["message"] = "Đã chuyển sang AutoCAD và chọn đối tượng."
        except BridgeError as exc:
            out["message"] = str(exc)
    else:
        out["message"] = "Đã ghi yêu cầu. Chuyển sang AutoCAD và gõ CGDEN."
    return out


__all__ = ["GOTO_REL", "MAX_HANDLES", "MAX_LAYERS", "BridgeError", "GotoRequest", "goto_path", "lisp_call",
           "make_request", "send_via_com", "show", "write_goto"]
