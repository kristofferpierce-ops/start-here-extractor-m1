from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from .batch import BatchConfig, run_batch
from .cloud.base import provenance_for_candidate
from .cloud.auth import build_access_token_provider
from .cloud.runtime import CloudRunConfig, build_locator, search_remote_candidates
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
    parser.add_argument("--audit-dir", default=None, help="Optional audit JSONL directory (defaults to <report-dir>/_audit)")
    parser.add_argument("--durable-audit", action="store_true", help="fsync audit JSONL writes")
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
    parser.add_argument("--av-command", default=None, help="Advisory AV command template containing {path}")
    parser.add_argument("--av-engine", choices=["generic", "clamav", "defender"], default="generic", help="AV engine hint for exit-code interpretation")
    parser.add_argument("--scan-timeout-seconds", type=int, default=60, help="Timeout applied to AV and YARA command execution")
    parser.add_argument("--yara-command", default=None, help="Optional YARA command template containing {path}, {rules}, and {compiled_flag}")
    parser.add_argument("--yara-rules", default=None, help="Optional YARA rules path")
    parser.add_argument("--yara-ruleset-id", default=None, help="Optional YARA ruleset identifier stored in inventory")
    parser.add_argument("--yara-compiled-rules", action="store_true", help="Mark the provided YARA rules path as compiled rules")
    parser.add_argument("--yara-allow-compiled-rules", action="store_true", help="Explicitly allow running compiled YARA rules")
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
    parser.add_argument("--cloud-provider", choices=["gdrive", "dropbox", "graph"], default=None, help="Search and download ZIPs from a cloud provider instead of local paths/roots")
    parser.add_argument("--cloud-access-token", default=None, help="Bearer token used for remote provider access")
    parser.add_argument("--cloud-access-token-command", default=None, help="Shell command that prints a bearer token on stdout")
    parser.add_argument("--cloud-token-expires-at", default=None, help="Optional ISO timestamp hint for cloud access-token expiry")
    parser.add_argument("--cloud-token-min-valid-seconds", type=int, default=300, help="Warn when the provided cloud token expires within this many seconds")
    parser.add_argument("--cloud-query", default="start here", help="Search text for remote ZIP discovery")
    parser.add_argument("--cloud-folder-id", default=None, help="Optional provider-specific folder or root identifier")
    parser.add_argument("--cloud-page-size", type=int, default=100, help="Remote search page size")
    parser.add_argument("--cloud-max-pages", type=int, default=10, help="Maximum remote search pages to fetch")
    parser.add_argument("--cloud-download-dir", default=None, help="Directory used to stage remote ZIP downloads")
    parser.add_argument("--cloud-drive-id", default=None, help="Optional Google Drive shared drive identifier")
    parser.add_argument("--cloud-acknowledge-abuse", action="store_true", help="Allow abusive-file acknowledgement for Google Drive downloads")
    parser.add_argument("--cloud-operator-approval-ref", default=None, help="Operator approval reference required for abuse-gated cloud downloads")
    parser.add_argument(
        "--cloud-require-operator-approval-for-abuse",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require an operator approval reference when acknowledgeAbuse is used",
    )
    parser.add_argument("--retention-days", type=int, default=30, help="Retention window in days for governance metadata")
    parser.add_argument("--legal-hold", action="store_true", help="Mark records as legal hold for retention governance")
    parser.add_argument("--audit-stream-name", default="audit-events", help="Audit JSONL stream name without extension")
    parser.add_argument("--monitoring-dir", default=None, help="Optional monitoring JSONL directory (defaults to <report-dir>/_monitoring)")
    parser.add_argument("--durable-monitoring", action="store_true", help="fsync monitoring JSONL writes")
    parser.add_argument("--monitoring-stream-name", default="monitoring-events", help="Monitoring JSONL stream name without extension")
    parser.add_argument("--graph-drive-scope", default="me/drive/root", help="Microsoft Graph drive scope, for example me/drive/root")
    return parser


def _collect_local_zip_paths(args: argparse.Namespace) -> list[Path]:
    return discover_zip_paths(args.paths, args.root, allow_symlink_traversal=args.allow_symlink_traversal)


def _collect_remote_targets(args: argparse.Namespace, output_dir: Path) -> list[tuple[Path, dict[str, object], dict[str, object]]]:
    token_provider = build_access_token_provider(
        access_token=args.cloud_access_token,
        access_token_command=args.cloud_access_token_command,
        expires_at=args.cloud_token_expires_at,
        min_valid_seconds=args.cloud_token_min_valid_seconds,
    )
    token_provider.get_token()
    cloud_cfg = CloudRunConfig(
        provider=args.cloud_provider,
        access_token=None,
        access_token_provider=token_provider,
        query_text=args.cloud_query,
        folder_id=args.cloud_folder_id,
        page_size=args.cloud_page_size,
        max_pages=args.cloud_max_pages,
        drive_id=args.cloud_drive_id,
        graph_drive_scope=args.graph_drive_scope,
        acknowledge_abuse=bool(args.cloud_acknowledge_abuse),
        operator_approval_ref=args.cloud_operator_approval_ref,
        require_operator_approval_for_abuse=bool(args.cloud_require_operator_approval_for_abuse),
    )
    locator = build_locator(cloud_cfg)
    candidates = search_remote_candidates(locator, cloud_cfg)
    if not candidates:
        raise SystemExit("No remote ZIP files found from the provided cloud provider/query")
    selected = candidates if args.all else candidates[:1]
    download_root = Path(args.cloud_download_dir) if args.cloud_download_dir else output_dir / "_downloads" / args.cloud_provider
    ensure_dir(download_root)
    fetched_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    targets: list[tuple[Path, dict[str, object], dict[str, object]]] = []
    for candidate in selected:
        local_path = Path(locator.download(candidate, str(download_root)))
        provenance = provenance_for_candidate(candidate, local_path, fetched_at=fetched_at, source_path=None)
        runtime_cloud = {"token_health": token_provider.public_state()}
        targets.append((local_path, provenance, runtime_cloud))
    return targets


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
        av_engine=args.av_engine,
        scan_timeout_seconds=args.scan_timeout_seconds,
        yara_command=args.yara_command,
        yara_rules=args.yara_rules,
        yara_ruleset_id=args.yara_ruleset_id,
        yara_compiled_rules=bool(args.yara_compiled_rules),
        yara_allow_compiled_rules=bool(args.yara_allow_compiled_rules),
        strict_zip_validation=bool(args.strict_zip_validation),
        sandbox_platform=args.sandbox_platform,
        sandbox_dry_run=bool(args.sandbox_dry_run),
        sandbox_timeout_seconds=args.sandbox_timeout_seconds,
        sandbox_root=args.sandbox_root,
        sandbox_command=args.sandbox_command,
        sandbox_network_enabled=bool(args.sandbox_enable_network),
        sandbox_clipboard_enabled=bool(args.sandbox_enable_clipboard),
        sandbox_vgpu_enabled=bool(args.sandbox_enable_vgpu),
        retention_days=args.retention_days,
        legal_hold=bool(args.legal_hold),
        audit_stream_name=args.audit_stream_name,
        monitoring_stream_name=args.monitoring_stream_name,
        durable_monitoring=bool(args.durable_monitoring),
        cloud_acknowledge_abuse=bool(args.cloud_acknowledge_abuse),
        cloud_operator_approval_ref=args.cloud_operator_approval_ref,
        cloud_require_operator_approval_for_abuse=bool(args.cloud_require_operator_approval_for_abuse),
    )

    if not args.all and args.fail_fast:
        parser.error("--fail-fast is only valid with --all")
    if not args.all and args.jsonl_out:
        parser.error("--jsonl-out is only valid with --all")
    if not args.all and args.durable_jsonl:
        parser.error("--durable-jsonl is only valid with --all")
    if args.sandbox_dry_run and not args.sandbox_platform:
        parser.error("--sandbox-dry-run requires --sandbox-platform")
    if args.yara_command and not args.yara_rules:
        parser.error("--yara-command requires --yara-rules")
    if args.yara_compiled_rules and not args.yara_allow_compiled_rules:
        parser.error("--yara-compiled-rules requires --yara-allow-compiled-rules")
    if args.cloud_provider and (args.paths or args.root):
        parser.error("Use either local paths/roots or --cloud-provider, not both")
    if args.cloud_provider and not (args.cloud_access_token or args.cloud_access_token_command):
        parser.error("--cloud-access-token or --cloud-access-token-command is required when --cloud-provider is used")
    if not args.cloud_provider and not (args.paths or args.root):
        parser.error("Provide local ZIP paths/roots or use --cloud-provider")

    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    ensure_dir(output_dir)
    ensure_dir(report_dir)

    if args.cloud_provider:
        targets = _collect_remote_targets(args, output_dir)
        zip_paths = [path for path, _, _ in targets]
        provenance_by_path = {str(path): prov for path, prov, _ in targets}
        runtime_cloud_by_path = {str(path): runtime for path, _, runtime in targets}
    else:
        zip_paths = _collect_local_zip_paths(args)
        provenance_by_path = {}
        runtime_cloud_by_path = {}
    if not zip_paths:
        parser.error("No ZIP files found from the provided inputs")

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
                if str(Path(result.zip_file.path)) in provenance_by_path:
                    result.provenance = provenance_by_path[str(Path(result.zip_file.path))]
                audit_dir = Path(args.audit_dir) if args.audit_dir else report_dir / "_audit"
                payload = result.to_dict()
                if str(Path(result.zip_file.path)) in runtime_cloud_by_path:
                    payload["_runtime_cloud"] = runtime_cloud_by_path[str(Path(result.zip_file.path))]
                record = build_inventory_record(payload, audit_dir=audit_dir, durable_audit=bool(args.durable_audit or args.durable_jsonl), audit_stream_name=args.audit_stream_name, monitoring_dir=Path(args.monitoring_dir) if args.monitoring_dir else report_dir / "_monitoring", durable_monitoring=bool(args.durable_monitoring or args.durable_jsonl), monitoring_stream_name=args.monitoring_stream_name)
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
        payload = result.to_dict()
        if str(Path(result.zip_file.path)) in provenance_by_path:
            result.provenance = provenance_by_path[str(Path(result.zip_file.path))]
            payload["provenance"] = result.provenance
        if str(Path(result.zip_file.path)) in runtime_cloud_by_path:
            payload["_runtime_cloud"] = runtime_cloud_by_path[str(Path(result.zip_file.path))]
        inventory_path = write_inventory(report_dir, zip_path, payload, durable_audit=bool(args.durable_audit), audit_stream_name=args.audit_stream_name, monitoring_dir=Path(args.monitoring_dir) if args.monitoring_dir else report_dir / "_monitoring", durable_monitoring=bool(args.durable_monitoring), monitoring_stream_name=args.monitoring_stream_name)
        print(f"[{result.outcome}] {zip_path} -> {inventory_path}")
        if result.outcome == "error":
            had_error = True

    return 1 if had_error else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
