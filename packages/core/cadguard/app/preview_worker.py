"""Worker render DXF; stdin là nội dung DXF, stdout chỉ là JSON đã lọc."""
import contextlib
import io
import json
import sys
from .preview import PreviewError, render_preview


def main():
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            svg, meta = render_preview(sys.stdin.buffer.read(), float(sys.argv[2]), sys.argv[1])
        result = {"svg": svg, "meta": meta}
    except PreviewError as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "Bộ vẽ gặp lỗi; dùng hình đơn giản hoá."}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
