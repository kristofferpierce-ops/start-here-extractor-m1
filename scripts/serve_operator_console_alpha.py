from __future__ import annotations

import argparse
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class OperatorConsoleHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", ""}:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/operator_console_alpha.html")
            self.end_headers()
            return
        super().do_GET()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the operator console alpha locally")
    parser.add_argument(
        "--console-dir",
        required=True,
        help="Directory containing operator_console_alpha.html",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser tab")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    console_dir = Path(args.console_dir).resolve()
    target = console_dir / "operator_console_alpha.html"
    if not target.exists():
        raise SystemExit(f"operator console file not found: {target}")

    handler = partial(OperatorConsoleHandler, directory=str(console_dir))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{server.server_port}/operator_console_alpha.html"
    print(url)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
