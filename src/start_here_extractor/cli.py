from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .batch import BatchConfig, run_batch
from .jsonl import append_jsonl
from .locator import discover_zip_paths
from .processor import process_zip
from .reporter import build_inventory_record, write_inventory
from .types import ExtractSettings, Limits, MatchPolicy
from .utils import ensure_dir, safe_slug


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Secure inspect-first START HERE ZIP extractor")
    parser.add_argument("paths", nargs="*", help="Explicit ZIP paths to process")
    parser.add_argument("--root", action="append", default=[], help="Root directory to recursively search for ZIPs")
    parser.add_argument("--output-dir", required=True, help="Directory for flattened extracted files")
    parser.add_argument("--report-dir", required=True, help="Directory for JSON inventory outputs")
    parser.add_argument("--all", action="store_true", help="Process all discovered ZIPs in one batch run")
    parser.add_argument("--jsonl-out", default=None, help="Append batch JSONL inventory records to this path")
    parser.add_argument("--fail-fast", action="store_true", help="Stop batch mode after the first ZIP with errors")
    parser.add_argument("--durable-jsonl", action="store_true", help="fsync JSONL output after each line in batch mode")
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
    parser.add_argument(
        "--strict-zip-validation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable additive strict ZIP structure validation and policy reporting",
    )
    parser.add_argument(
        "--sandbox-platform",
        choices=["windows-sandbox"],
        default=None,
        help="Optional sandbox backend used when policy escalates to sandbox",
    )
    parser.add_argument(
        "--sandbox-dry-run",
        action="store_true",
        help="Emit sandbox config and command artifacts without launching the sandbox",
    )
    parser.add_argument(
        "--sandbox-timeout-seconds",
        type=int,
        default=120,
        help="Maximum seconds to wait for sandbox completion signaling",
    )
    parser.add_argument(
        "--sandbox-root",
        default=None,
        help="Host directory used for sandbox staging/results artifacts",
    )
    parser.add_argument(
        "--sandbox-command",
        default=None,
        help="Optional command line executed inside the sandbox job script",
    )
    parser.add_argument(
        "--sandbox-enable-network",
        action="store_true",
        help="Enable networking in the sandbox config (default off)",
    )
    parser.add_argument(
        "--sandbox-enable-clipboard",
        action="store_true",
        help="Enable clipboard redirection in the sandbox config (default off)",
    )
    parser.add_argument(
        "--sandbox-enable-vgpu",
        action="store_true",
        help="Enable vGPU in the sandbox config (default off)",
    )
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
        strict_zip_validation=bool(args.strict_zip_validation),
        sandbox_platform=args.sandbox_platform,
        sandbox_dry_run=bool(args.sandbox_dry_run),
        sandbox_timeout_seconds=args.sandbox_timeout_seconds,
        sandbox_root=args.sandbox_root,
        sandbox_command=args.sandbox_command,
        sandbox_network_enabled=bool(args.sandbox_enable_network),
        sandbox_clipboard_enabled=bool(args.sandbox_enable_clipboard),
        sandbox_vgpu_enabled=bool(args.sandbox_enable_vgpu),
    )

    if not args.all and args.fail_fast:
        parser.error("--fail-fast is only valid with --all")
    if not args.all and args.jsonl_out:
        parser.error("--jsonl-out is only valid with --all")
    if not args.all and args.durable_jsonl:
        parser.error("--durable-jsonl is only valid with --all")
    if args.sandbox_dry_run and not args.sandbox_platform:
        parser.error("--sandbox-dry-run requires --sandbox-platform")

    zip_paths = discover_zip_paths(args.paths, args.root, allow_symlink_traversal=args.allow_symlink_traversal)
    if not zip_paths:
        parser.error("No ZIP files found from the provided paths/roots")

    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    ensure_dir(output_dir)
    ensure_dir(report_dir)

    if args.all:
        jsonl_out = Path(args.jsonl_out) if args.jsonl_out else report_dir / "inventories.jsonl"
        batch_config = BatchConfig(targets=zip_paths, fail_fast=bool(args.fail_fast), sort_paths=True, max_attempts=1)
        state = {"had_error": False}

        def records_iter():
            for result in run_batch(
                batch_config,
                limits=limits,
                policy=policy,
                settings=settings,
                output_root=output_dir,
                process_one=process_zip,
            ):
                record = build_inventory_record(result.to_dict())
                print(f"[{result.outcome}] {result.zip_file.path} -> {jsonl_out}")
                if result.errors:
                    state["had_error"] = True
                yield record

        append_jsonl(jsonl_out, records_iter(), flush_each=True, durable=bool(args.durable_jsonl))
        return 1 if state["had_error"] else 0

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
