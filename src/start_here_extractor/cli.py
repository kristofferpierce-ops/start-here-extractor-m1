from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .locator import discover_zip_paths
from .processor import process_zip
from .reporter import write_inventory
from .types import ExtractSettings, Limits, MatchPolicy
from .utils import ensure_dir, safe_slug


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Secure inspect-first START HERE ZIP extractor")
    parser.add_argument("paths", nargs="*", help="Explicit ZIP paths to process")
    parser.add_argument("--root", action="append", default=[], help="Root directory to recursively search for ZIPs")
    parser.add_argument("--output-dir", required=True, help="Directory for flattened extracted files")
    parser.add_argument("--report-dir", required=True, help="Directory for JSON inventory outputs")
    parser.add_argument("--basename", action="append", default=["start here"], help="Allowed target basename alias")
    parser.add_argument("--allowed-ext", action="append", default=[".txt", ".md"], help="Allowed candidate extension")
    parser.add_argument("--prefer-ext", action="append", default=[".txt", ".md"], help="Preferred extension order")
    parser.add_argument("--tie-policy", choices=["prefer", "error"], default="prefer")
    parser.add_argument("--max-entries", type=int, default=10_000)
    parser.add_argument("--max-member-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-ratio", type=float, default=100.0)
    parser.add_argument("--preview-bytes", type=int, default=4096)
    parser.add_argument("--preview-lines", type=int, default=40)
    parser.add_argument("--strict-verify", action="store_true")
    parser.add_argument("--av-command", default=None, help="Advisory command template containing {path}")
    parser.add_argument("--allow-symlink-traversal", action="store_true")
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    limits = Limits(
        max_entries=args.max_entries,
        max_member_bytes=args.max_member_bytes,
        max_ratio=args.max_ratio,
        preview_bytes=args.preview_bytes,
        preview_lines=args.preview_lines,
    )
    policy = MatchPolicy(
        allowed_basenames=args.basename,
        allowed_extensions=args.allowed_ext,
        tie_policy=args.tie_policy,
        preferred_extensions=args.prefer_ext,
    )
    settings = ExtractSettings(
        flatten_output=True,
        strict_verify=args.strict_verify,
        allow_symlink_traversal=args.allow_symlink_traversal,
        av_command=args.av_command,
    )

    zip_paths = discover_zip_paths(args.paths, args.root, allow_symlink_traversal=args.allow_symlink_traversal)
    if not zip_paths:
        parser.error("No ZIP files found from the provided paths/roots")

    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    ensure_dir(output_dir)
    ensure_dir(report_dir)

    had_error = False
    for zip_path in zip_paths:
        per_zip_output_dir = output_dir / safe_slug(zip_path.stem)
        ensure_dir(per_zip_output_dir)
        result = process_zip(zip_path, per_zip_output_dir, limits, policy, settings)
        inventory_path = write_inventory(report_dir, zip_path, result.to_dict())
        print(f"[{result.outcome}] {zip_path} -> {inventory_path}")
        if result.outcome == "error":
            had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
