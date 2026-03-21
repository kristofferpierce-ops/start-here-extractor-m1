from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_packages import (
    build_target_group_adapter_package_artifacts,
    load_canonical_raw_payload_contracts,
    load_family_interface_templates,
    load_target_group_catalog,
    render_target_group_adapter_package_review_queue_markdown,
    render_target_group_adapter_package_rollup_markdown,
    render_target_group_adapter_packages_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build target-group adapter package scaffolds from family interface templates")
    parser.add_argument("--family-interface-templates-path", required=True, help="Path to family_interface_templates.json")
    parser.add_argument("--raw-payload-contracts-path", required=True, help="Path to canonical_raw_payload_contracts.json")
    parser.add_argument("--target-group-catalog-path", required=True, help="Path to target group catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for target-group adapter package artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    templates_doc = load_family_interface_templates(args.family_interface_templates_path)
    contracts_doc = load_canonical_raw_payload_contracts(args.raw_payload_contracts_path)
    catalog = load_target_group_catalog(args.target_group_catalog_path)
    packages_doc, review_queue, rollup = build_target_group_adapter_package_artifacts(templates_doc, contracts_doc, catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_group_adapter_packages.json").write_text(json.dumps(packages_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_packages.md").write_text(render_target_group_adapter_packages_markdown(packages_doc), encoding="utf-8")
    (out_dir / "target_group_adapter_package_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_package_review_queue.md").write_text(render_target_group_adapter_package_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_group_adapter_package_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_package_rollup.md").write_text(render_target_group_adapter_package_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
