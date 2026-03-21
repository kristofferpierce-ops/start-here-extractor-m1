from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.live_smoke import build_live_smoke_summary, render_live_smoke_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a secret-safe live smoke summary from workflow artifacts")
    parser.add_argument("--provider", required=True, help="Cloud provider used for the smoke run")
    parser.add_argument("--query", required=True, help="Query used for remote ZIP discovery")
    parser.add_argument("--cli-exit-code", required=True, type=int, help="CLI exit code captured from the smoke run")
    parser.add_argument("--out-dir", required=True, help="Output directory for summary artifacts")
    parser.add_argument("--report-dir", required=True, help="Directory containing inventory JSONL artifacts")
    parser.add_argument("--monitoring-dir", default=None, help="Directory containing monitoring JSONL artifacts")
    parser.add_argument("--audit-dir", default=None, help="Directory containing audit JSONL artifacts")
    parser.add_argument("--stdout-log", default=None, help="Optional CLI stdout log path")
    parser.add_argument("--stderr-log", default=None, help="Optional CLI stderr log path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = build_live_smoke_summary(
        provider=args.provider,
        query=args.query,
        cli_exit_code=args.cli_exit_code,
        report_dir=args.report_dir,
        monitoring_dir=args.monitoring_dir,
        audit_dir=args.audit_dir,
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
    )
    json_path = out_dir / "live_smoke_summary.json"
    markdown_path = out_dir / "live_smoke_summary.md"
    json_path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_live_smoke_markdown(summary), encoding="utf-8")
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
