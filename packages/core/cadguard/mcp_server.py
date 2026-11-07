"""Máy chủ MCP stdio cho trợ lý AI ở máy khách: bọc các hàm trong `cadguard.agent.tools`.

Chạy: `python -m cadguard mcp --workspace <thư mục>`.

- Mặc định CHỈ ĐỌC: 6 công cụ (list_drawings, audit, explain_rule, get_model_summary, query_model, diff).
- `--allow-propose` (mặc định TẮT) thêm `propose_changeset`: chạy khô và ghi changeset JSON vào
  `<thư mục làm việc>/.cadguard/changesets/`; không bao giờ ghi DXF.
- KHÔNG có `apply_changeset` qua MCP: áp dụng (ghi tệp mới) chỉ do người dùng qua `cadguard apply`, sau khi xem trước
  và xác nhận. Lý do: trợ lý không được tự quyết sửa bản vẽ sản xuất (docs/changeset.md mục 5).

- SDK `mcp` chỉ được import khi chạy lệnh này (extras `[agent]`); thiếu SDK thì báo ra stderr, thoát mã 2.
- stdout chỉ dành cho JSON-RPC: trước khi phục vụ, fd 1 và `sys.stdout` được chuyển sang stderr;
  luồng giao thức ghi vào bản sao riêng của stdout gốc.
- Mặc định ẩn danh Bậc 1 (mã phiên thay tên tệp/layer/khối/kiểu chữ); `--no-anonymize` tắt và cảnh báo ra stderr.
- `--profile <tệp>`: hồ sơ công ty áp cho audit/explain_rule khi gọi đúng chuẩn của hồ sơ; kết quả ghi tên/phiên bản
  hồ sơ (không đường dẫn). Hồ sơ sai, hoặc ngưỡng --stream-threshold-mb là NaN/vô cực: báo stderr, thoát mã 2.
- Lỗi công cụ trả về là câu tiếng Việt chung, không chứa đường dẫn tuyệt đối hay nội dung ngoại lệ nội bộ.
"""

import argparse
import os
import sys
from io import TextIOWrapper
from pathlib import Path

from .agent import registry, tools
from .agent.anonymize import Anonymizer
from .agent.workspace import PathDenied, Workspace
from .limits import DEFAULT_MAX_ENTITY_RECORDS, DEFAULT_STREAM_THRESHOLD_MB, check_threshold
from .standard import ProfileError, find_standards_dir, load_profile

SERVER_NAME = "cad-guard"
DEFAULT_STANDARD = "furniture-v0"
TOOL_NAMES = registry.READ_TOOLS
PROPOSE_TOOL = registry.PROPOSE_TOOL  # chỉ có khi --allow-propose

INSTALL_HINT = (
    "Thiếu SDK MCP cho Python (gói `mcp`), nên chưa chạy được máy chủ MCP của cad-guard.\n"
    "Cài một trong hai cách:\n"
    "  pip install cadguard[agent]\n"
    "  python scripts/test.py --extras agent      (trong repo cad-guard, venv dùng chung)\n"
)
PATH_DENIED_MSG = registry.PATH_DENIED_MSG
GENERIC_ERROR_MSG = registry.GENERIC_ERROR_MSG

INSTRUCTIONS = (
    "Công cụ CHỈ ĐỌC của cad-guard để kiểm tra bản vẽ nội thất DXF theo luật tất định: list_drawings, audit, "
    "explain_rule, get_model_summary, query_model, diff (so hai bản vẽ, vd. bản gốc và tệp mới sau khi người dùng áp dụng). "
    "Đường dẫn luôn tương đối với thư mục làm việc của máy chủ; có thể dùng mã tệp do list_drawings trả về. "
    "Khi bật ẩn danh, tên tệp/layer/khối/kiểu chữ là mã phiên (L_…, B_…, F_…), dùng lại được trong cùng phiên. "
    "Kết luận đúng/sai lấy từ kết quả luật, không tự suy đoán. "
    "Nếu kết quả có records_capped = true: bản vẽ rất lớn, danh sách đối tượng đã bị cắt ở trần bộ nhớ, "
    "nên số đối tượng/phát hiện có thể thiếu; hãy nói rõ điều này với người dùng. "
    "Không có công cụ áp dụng sửa: nếu máy chủ bật propose_changeset, trợ lý chỉ ĐỀ XUẤT changeset (xem trước); "
    "người dùng tự áp dụng bằng `cadguard apply`, kết quả ghi ra tệp mới."
)


def add_arguments(p: argparse.ArgumentParser) -> None:
    """Khai báo cờ của lệnh `mcp` (dùng chung cho cli.py; parser tạo với add_help=False)."""
    p._optionals.title = "tuỳ chọn"
    p.add_argument("-h", "--help", action="help", help="in hướng dẫn này rồi thoát")
    p.add_argument(
        "--workspace",
        required=True,
        metavar="THƯ_MỤC",
        help="BẮT BUỘC. Thư mục làm việc chứa DXF; máy chủ chỉ đọc tệp .dxf nằm trong thư mục này "
        "(không mặc định thư mục hiện tại để tránh lộ nhầm thư mục khác).",
    )
    p.add_argument(
        "--no-anonymize",
        action="store_true",
        help="TẮT ẩn danh Bậc 1 (mặc định BẬT): trợ lý AI sẽ thấy tên tệp/layer/khối thật. Chỉ dùng khi khách đã đồng ý.",
    )
    p.add_argument(
        "--standard",
        default=None,
        metavar="TÊN",
        help=f"chuẩn mặc định cho audit/explain_rule (mặc định: chuẩn ghi trong --profile, nếu không có thì {DEFAULT_STANDARD}); "
        "công cụ vẫn nhận tham số standard riêng (vd. design-hygiene-v0).",
    )
    p.add_argument(
        "--profile",
        default=None,
        metavar="TỆP",
        help="hồ sơ công ty (YAML cg.company-profile/1) ghi đè ngưỡng/mẫu layer/tắt luật; áp cho audit/explain_rule "
        "khi gọi đúng chuẩn của hồ sơ. Hồ sơ sai thì không khởi động (mã 2).",
    )
    p.add_argument(
        "--stream-threshold-mb",
        type=float,
        default=DEFAULT_STREAM_THRESHOLD_MB,
        metavar="MB",
        help=f"ngưỡng MB để đọc DXF theo dòng (ít bộ nhớ) thay cho ezdxf (mặc định {DEFAULT_STREAM_THRESHOLD_MB:g}, "
        "như `cadguard audit --reader auto`); 0 = luôn đọc theo dòng, số âm = luôn dùng ezdxf. DXF nhị phân luôn dùng ezdxf.",
    )
    p.add_argument(
        "--allow-propose",
        action="store_true",
        help="BẬT công cụ propose_changeset (mặc định TẮT): trợ lý được chạy khô thao tác sửa và ghi changeset JSON "
        "vào <thư mục làm việc>/.cadguard/changesets/. Không bao giờ ghi DXF; áp dụng chỉ do người qua `cadguard apply`.",
    )
    p.add_argument(
        "--max-entity-records",
        type=_non_negative_int,
        default=DEFAULT_MAX_ENTITY_RECORDS,
        metavar="N",
        help=f"trần số đối tượng giữ trong bộ nhớ khi đọc theo dòng (mặc định {DEFAULT_MAX_ENTITY_RECORDS}); "
        "quá trần thì danh sách đối tượng bị cắt và kết quả công cụ có records_capped = true.",
    )


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("phải là số nguyên không âm") from None
    if value < 0:
        raise argparse.ArgumentTypeError("phải là số nguyên không âm")
    return value


def _err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _import_sdk():
    """Import SDK lười. Trả None nếu thiếu."""
    try:
        from mcp.server.lowlevel import Server  # noqa: F401
        from mcp.server.stdio import stdio_server  # noqa: F401
        from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations  # noqa: F401
    except ImportError:
        return None
    import mcp

    return mcp


def build_server(ctx: tools.ToolContext, default_standard: str = "furniture-v0", allow_propose: bool = False):
    """Tạo máy chủ MCP cấp thấp từ sổ khai báo `agent.registry`: 6 công cụ chỉ đọc, thêm propose_changeset khi
    `allow_propose`. Không bao giờ có apply. Tham số kiểm bằng `registry.check_args` (thông điệp tiếng Việt, không lặp
    lại giá trị), giống hệt engine API. Công cụ chạy trong luồng phụ, tuần tự (khoá) vì bộ ẩn danh giữ trạng thái phiên."""
    import threading

    import anyio
    from mcp.server.lowlevel import Server
    from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

    from . import __version__

    opts = registry.options_for(ctx, default_standard, allow_propose=allow_propose)
    server = Server(SERVER_NAME, version=__version__, instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    propose = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
    listing = [Tool(name=s["name"], description=s["description"], inputSchema=s["schema"],
                    annotations=read_only if s["read_only"] else propose) for s in registry.specs(opts)]
    lock = threading.Lock()

    @server.list_tools()
    async def _list() -> list:
        return listing

    def _run(name: str, arguments: dict):
        with lock:
            return registry.call(ctx, name, arguments, opts)

    @server.call_tool(validate_input=False)  # kiểm bằng registry.check_args: thông điệp tiếng Việt, không lộ giá trị
    async def _call(name: str, arguments: dict) -> CallToolResult:
        res = await anyio.to_thread.run_sync(_run, name, arguments)
        if not res.ok:
            return CallToolResult(content=[TextContent(type="text", text=res.error)], isError=True)
        return CallToolResult(content=[TextContent(type="text", text=res.text())], structuredContent=res.data)

    return server


def _protocol_stdout() -> TextIOWrapper:
    """Giữ riêng stdout gốc cho JSON-RPC; mọi ghi khác vào stdout (Python hay mã C) đi sang stderr."""
    sys.stdout.flush()
    try:
        saved = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        raw = os.fdopen(saved, "wb")
    except (OSError, ValueError, AttributeError):  # stdout không có fd thật (vd. bị nhúng): dùng buffer hiện có
        raw = sys.stdout.buffer
    sys.stdout = sys.stderr
    return TextIOWrapper(raw, encoding="utf-8", newline="\n", write_through=True)


def serve(server) -> None:
    import anyio
    from mcp.server.stdio import stdio_server

    out = _protocol_stdout()
    stdin = TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

    async def run() -> None:
        async with stdio_server(stdin=anyio.wrap_file(stdin), stdout=anyio.wrap_file(out)) as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(run)


def run_from_args(args: argparse.Namespace) -> int:
    """Điểm vào của `python -m cadguard mcp`."""
    try:
        check_threshold(args.stream_threshold_mb)
    except ValueError as exc:
        _err(f"--stream-threshold-mb: {exc}")
        return 2
    try:
        workspace = Workspace(Path(args.workspace))
    except PathDenied:
        _err("Thư mục làm việc (--workspace) không tồn tại hoặc không phải thư mục.")
        return 2
    try:
        standards_dir = find_standards_dir(Path(__file__).resolve())
    except FileNotFoundError as exc:
        _err(str(exc))
        return 2
    profile = None
    if getattr(args, "profile", None):
        try:
            profile = load_profile(args.profile)
        except ProfileError as exc:  # thông điệp chỉ nêu tên tệp, không đường dẫn đầy đủ
            _err(f"Không khởi động máy chủ MCP: {exc}")
            return 2
    standard = args.standard or (profile.standard if profile else DEFAULT_STANDARD)
    if profile is not None and profile.standard != standard:
        _err(
            f"Không khởi động máy chủ MCP: hồ sơ '{profile.name}' viết cho chuẩn '{profile.standard}', "
            f"không dùng được với chuẩn '{standard}' (--standard)."
        )
        return 2
    anonymize = not args.no_anonymize
    ctx = tools.ToolContext(
        workspace,
        Anonymizer(enabled=anonymize),
        standards_dir,
        stream_threshold_mb=args.stream_threshold_mb,
        max_entity_records=args.max_entity_records,
        profile=profile,
    )
    try:
        tools._standard(ctx, standard)
    except tools.ToolError:
        _err(f"Không dùng được chuẩn '{standard}'.")
        return 2
    except ProfileError as exc:  # vd. hồ sơ ghi đè luật/tham số không có trong chuẩn
        _err(f"Không khởi động máy chủ MCP: hồ sơ công ty '{profile.name}' sai: {exc}")
        return 2
    except FileNotFoundError:
        _err(f"Không dùng được chuẩn '{standard}'.")
        return 2
    if _import_sdk() is None:
        _err(INSTALL_HINT)
        return 2
    if profile is not None:
        _err(f"cad-guard MCP: áp hồ sơ công ty '{profile.name}' phiên bản {profile.version} cho chuẩn {standard}.")
    if not anonymize:
        _err(
            "CẢNH BÁO: đã TẮT ẩn danh (--no-anonymize). Trợ lý AI sẽ thấy tên tệp, layer, khối và kiểu chữ thật "
            "(ngoài Bậc 1). Chỉ dùng khi khách đã đồng ý bằng văn bản."
        )
    allow_propose = bool(getattr(args, "allow_propose", False))
    server = build_server(ctx, standard, allow_propose=allow_propose)
    # Nạp bộ đọc DXF (ezdxf) TRƯỚC khi đọc stdin: trên Windows, import lần đầu trong luồng phụ khi một luồng khác đang
    # chặn đọc ống stdin có thể treo cả tiến trình (đã gặp khi để nạp lười tới lượt gọi công cụ đầu tiên).
    import cadguard.reader_select  # noqa: F401

    mode = "chỉ đọc + đề xuất changeset (không áp dụng)" if allow_propose else "chỉ đọc"
    _err(f"cad-guard MCP: đang phục vụ qua stdio ({mode}). Dừng bằng cách đóng stdin hoặc Ctrl+C.")
    try:
        serve(server)
    except KeyboardInterrupt:
        pass
    return 0


__all__ = ["PROPOSE_TOOL", "TOOL_NAMES", "add_arguments", "build_server", "run_from_args"]
