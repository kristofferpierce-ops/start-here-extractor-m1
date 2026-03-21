from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.live_smoke_release_gate import (
    build_live_smoke_release_decision,
    render_live_smoke_release_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a release decision from hosted smoke matrix artifacts")
    parser.add_argument("--matrix-summary", required=True, help="Path to the live smoke matrix summary JSON artifact")
    parser.add_argument("--out-dir", required=True, help="Output directory for release decision artifacts")
    parser.add_argument(
        "--promotion-target",
        default="hosted-live-smoke-release",
        help="Human-readable promotion target label written into the release decision artifact",
    )
    parser.add_argument(
        "--runbook-path",
        default="LIVE_SMOKE_OPERATOR_RUNBOOK.md",
        help="Path to the checked-in operator runbook referenced by the release decision",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    decision = build_live_smoke_release_decision(
        matrix_summary_path=args.matrix_summary,
        promotion_target=args.promotion_target,
        runbook_path=args.runbook_path,
    )
    json_path = out_dir / "live_smoke_release_gate.json"
    markdown_path = out_dir / "live_smoke_release_gate.md"
    json_path.write_text(json.dumps(decision.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_live_smoke_release_markdown(decision), encoding="utf-8")
    print(json_path)
    print(markdown_path)
    return 0 if decision.promote else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
