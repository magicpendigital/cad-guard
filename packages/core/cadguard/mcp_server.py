"""Máy chủ MCP stdio CHỈ ĐỌC: bọc 5 hàm trong `cadguard.agent.tools` cho trợ lý AI ở máy khách.

Chạy: `python -m cadguard mcp --workspace <thư mục>`.

- SDK `mcp` chỉ được import khi chạy lệnh này (extras `[agent]`); thiếu SDK thì báo ra stderr, thoát mã 2.
- stdout chỉ dành cho JSON-RPC: trước khi phục vụ, fd 1 và `sys.stdout` được chuyển sang stderr;
  luồng giao thức ghi vào bản sao riêng của stdout gốc.
- Mặc định ẩn danh Bậc 1 (mã phiên thay tên tệp/layer/khối/kiểu chữ); `--no-anonymize` tắt và cảnh báo ra stderr.
- Lỗi công cụ trả về là câu tiếng Việt chung, không chứa đường dẫn tuyệt đối hay nội dung ngoại lệ nội bộ.
"""

import argparse
import json
import os
import sys
from io import TextIOWrapper
from pathlib import Path

from .agent import tools
from .agent.anonymize import Anonymizer
from .agent.workspace import PathDenied, Workspace
from .standard import find_standards_dir

SERVER_NAME = "cad-guard"
TOOL_NAMES = ("list_drawings", "audit", "explain_rule", "get_model_summary", "query_model")

INSTALL_HINT = (
    "Thiếu SDK MCP cho Python (gói `mcp`), nên chưa chạy được máy chủ MCP của cad-guard.\n"
    "Cài một trong hai cách:\n"
    "  pip install cadguard[agent]\n"
    "  python scripts/test.py --extras agent      (trong repo cad-guard, venv dùng chung)\n"
)
PATH_DENIED_MSG = "Đường dẫn không được phép: chỉ nhận tệp .dxf nằm trong thư mục làm việc, viết dạng tương đối."
GENERIC_ERROR_MSG = "Không thể thực hiện yêu cầu; hãy kiểm tra dữ liệu và đường dẫn."

INSTRUCTIONS = (
    "Công cụ CHỈ ĐỌC của cad-guard để kiểm tra bản vẽ nội thất DXF theo luật tất định. "
    "Đường dẫn luôn tương đối với thư mục làm việc của máy chủ; có thể dùng mã tệp do list_drawings trả về. "
    "Khi bật ẩn danh, tên tệp/layer/khối/kiểu chữ là mã phiên (L_…, B_…, F_…), dùng lại được trong cùng phiên. "
    "Kết luận đúng/sai lấy từ kết quả luật, không tự suy đoán."
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
        default="furniture-v0",
        metavar="TÊN",
        help="chuẩn mặc định cho audit/explain_rule (mặc định: furniture-v0); công cụ vẫn nhận tham số standard riêng.",
    )


def _err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _import_sdk():
    """Import SDK lười. Trả None nếu thiếu."""
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        from mcp.server.stdio import stdio_server  # noqa: F401
        from mcp.types import CallToolResult, TextContent, ToolAnnotations  # noqa: F401
    except ImportError:
        return None
    import mcp

    return mcp


def build_server(ctx: tools.ToolContext, default_standard: str = "furniture-v0"):
    """Tạo FastMCP với đúng 5 công cụ chỉ đọc. Cần SDK đã cài."""
    from typing import Annotated

    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult, TextContent, ToolAnnotations
    from pydantic import BaseModel, ConfigDict, Field

    server = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

    def call(fn, *args, **kwargs) -> CallToolResult:
        try:
            data = fn(ctx, *args, **kwargs)
        except tools.ToolError as exc:  # thông điệp đã an toàn (tiếng Việt, không đường dẫn)
            return CallToolResult(content=[TextContent(type="text", text=str(exc))], isError=True)
        except PathDenied:
            return CallToolResult(content=[TextContent(type="text", text=PATH_DENIED_MSG)], isError=True)
        except Exception:  # noqa: BLE001 — không lộ chi tiết nội bộ
            return CallToolResult(content=[TextContent(type="text", text=GENERIC_ERROR_MSG)], isError=True)
        text = json.dumps(data, ensure_ascii=False)
        return CallToolResult(content=[TextContent(type="text", text=text)], structuredContent=data)

    FileArg = Annotated[
        str,
        Field(description="Tệp .dxf: đường dẫn tương đối trong thư mục làm việc (vd. 'a/b.dxf') hoặc mã tệp từ list_drawings."),
    ]
    StandardArg = Annotated[
        str,
        Field(description=f"Tên chuẩn (mặc định {default_standard}).", pattern=r"^[a-z0-9][a-z0-9.\-]*$"),
    ]
    StrOrList = str | list[str] | None

    class QueryFilter(BaseModel):
        """Bộ lọc đối tượng; các khoá kết hợp theo AND, danh sách trong một khoá theo OR."""

        model_config = ConfigDict(extra="forbid")
        layer: StrOrList = Field(None, description="Tên layer hoặc mã layer (L_…); một giá trị hoặc danh sách.")
        type: StrOrList = Field(None, description="Loại đối tượng DXF, vd. LINE, LWPOLYLINE, TEXT, INSERT, DIMENSION.")
        space: StrOrList = Field(None, description="Không gian: 'Model' hoặc tên/mã layout (Y_…).")

    @server.tool(
        name="list_drawings",
        description=f"Liệt kê tệp DXF trong thư mục làm việc (tối đa {ctx.max_drawings} mục; 'truncated' báo bị cắt). "
        "Trả mã tệp (id) dùng cho các công cụ khác, và kích thước.",
        annotations=read_only,
        structured_output=False,
    )
    def list_drawings(
        dir: Annotated[str, Field(description="Thư mục con tương đối trong thư mục làm việc; '.' là gốc.")] = ".",
    ) -> CallToolResult:
        return call(tools.list_drawings, dir)

    @server.tool(
        name="audit",
        description="Kiểm tra một bản vẽ theo chuẩn bằng luật tất định. Trả số lỗi theo mức (E/W/I), "
        f"luật đã chạy/bỏ qua và tối đa {ctx.max_findings} phát hiện.",
        annotations=read_only,
        structured_output=False,
    )
    def audit(file: FileArg, standard: StandardArg = default_standard) -> CallToolResult:
        return call(tools.audit, file, standard)

    @server.tool(
        name="explain_rule",
        description="Giải thích một mã luật (vd. LY-01): tiêu đề, mức độ, loại, nguồn, tham số chung và đoạn mô tả trong chuẩn.",
        annotations=read_only,
        structured_output=False,
    )
    def explain_rule(
        rule_id: Annotated[str, Field(description="Mã luật, vd. 'LY-01'.", min_length=1, max_length=32)],
        standard: StandardArg = default_standard,
    ) -> CallToolResult:
        return call(tools.explain_rule, rule_id, standard)

    @server.tool(
        name="get_model_summary",
        description="Tóm tắt Drawing Model của một bản vẽ: số layer/khối, đối tượng theo loại và không gian, "
        "layout, kiểu chữ, đơn vị, phiên bản DXF (JSON tối đa 16 KB).",
        annotations=read_only,
        structured_output=False,
    )
    def get_model_summary(file: FileArg) -> CallToolResult:
        return call(tools.get_model_summary, file)

    @server.tool(
        name="query_model",
        description=f"Lọc đối tượng trong bản vẽ theo layer/loại/không gian, có phân trang: mỗi trang tối đa "
        f"{tools.MAX_QUERY_RECORDS} mục và {tools.MAX_QUERY_BYTES // 1024} KB; còn nữa thì 'next_cursor' khác null, "
        "gửi lại nguyên bộ lọc cùng cursor để lấy trang sau.",
        annotations=read_only,
        structured_output=False,
    )
    def query_model(
        file: FileArg,
        filter: Annotated[QueryFilter | None, Field(description="Bộ lọc; bỏ trống = mọi đối tượng.")] = None,
        limit: Annotated[
            int, Field(ge=1, le=tools.MAX_QUERY_RECORDS, description=f"Số mục tối đa mỗi trang (1–{tools.MAX_QUERY_RECORDS}).")
        ] = 100,
        cursor: Annotated[str | None, Field(description="Giá trị 'next_cursor' của trang trước; bỏ trống ở trang đầu.")] = None,
    ) -> CallToolResult:
        flt = filter.model_dump(exclude_none=True) if filter is not None else {}
        return call(tools.query_model, file, flt, limit, cursor)

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
            low = server._mcp_server  # SDK 1.x: máy chủ cấp thấp của FastMCP
            await low.run(read, write, low.create_initialization_options())

    anyio.run(run)


def run_from_args(args: argparse.Namespace) -> int:
    """Điểm vào của `python -m cadguard mcp`."""
    if _import_sdk() is None:
        _err(INSTALL_HINT)
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
    anonymize = not args.no_anonymize
    ctx = tools.ToolContext(workspace, Anonymizer(enabled=anonymize), standards_dir)
    try:
        tools._standard(ctx, args.standard)
    except tools.ToolError:
        _err(f"Không dùng được chuẩn '{args.standard}'.")
        return 2
    if not anonymize:
        _err(
            "CẢNH BÁO: đã TẮT ẩn danh (--no-anonymize). Trợ lý AI sẽ thấy tên tệp, layer, khối và kiểu chữ thật "
            "(ngoài Bậc 1). Chỉ dùng khi khách đã đồng ý bằng văn bản."
        )
    server = build_server(ctx, args.standard)
    _err("cad-guard MCP: đang phục vụ qua stdio (chỉ đọc). Dừng bằng cách đóng stdin hoặc Ctrl+C.")
    try:
        serve(server)
    except KeyboardInterrupt:
        pass
    return 0


__all__ = ["TOOL_NAMES", "add_arguments", "build_server", "run_from_args"]
