from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.live_smoke_matrix import (
    build_live_smoke_matrix_plan,
    build_live_smoke_matrix_summary,
    render_live_smoke_matrix_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and gate hosted live smoke provider matrices")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Normalize the provider matrix selection")
    plan_parser.add_argument("--providers", required=True, help="Comma-separated provider list or 'all'")
    plan_parser.add_argument(
        "--required-providers",
        default="",
        help="Comma-separated providers that must pass the release gate (defaults to the selected providers)",
    )
    plan_parser.add_argument("--out-dir", required=True, help="Output directory for matrix plan artifacts")

    gate_parser = subparsers.add_parser("gate", help="Aggregate provider smoke artifacts and enforce a release gate")
    gate_parser.add_argument("--providers", required=True, help="Comma-separated provider list or 'all'")
    gate_parser.add_argument(
        "--required-providers",
        default="",
        help="Comma-separated providers that must pass the release gate (defaults to the selected providers)",
    )
    gate_parser.add_argument("--artifacts-root", required=True, help="Directory containing downloaded live-smoke artifacts")
    gate_parser.add_argument("--out-dir", required=True, help="Output directory for matrix summary artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = build_live_smoke_matrix_plan(args.providers, getattr(args, "required_providers", ""))

    if args.command == "plan":
        json_path = out_dir / "live_smoke_matrix_plan.json"
        markdown_path = out_dir / "live_smoke_matrix_plan.md"
        payload = plan.to_dict()
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        markdown = "\n".join(
            [
                "# Live smoke matrix plan",
                "",
                f"- Version: `{payload['version']}`",
                f"- Providers: `{', '.join(payload['providers'])}`",
                f"- Required providers: `{', '.join(payload['required_providers'])}`",
                "",
            ]
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        print(json_path)
        print(markdown_path)
        return 0

    summary = build_live_smoke_matrix_summary(
        artifacts_root=args.artifacts_root,
        providers=plan.providers,
        required_providers=plan.required_providers,
    )
    summary_json_path = out_dir / "live_smoke_matrix_summary.json"
    summary_markdown_path = out_dir / "live_smoke_matrix_summary.md"
    summary_json_path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_markdown_path.write_text(render_live_smoke_matrix_markdown(summary), encoding="utf-8")
    print(summary_json_path)
    print(summary_markdown_path)
    return 0 if summary.gate_passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
