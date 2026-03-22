from __future__ import annotations

import argparse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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

    handler = partial(SimpleHTTPRequestHandler, directory=str(console_dir))
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
