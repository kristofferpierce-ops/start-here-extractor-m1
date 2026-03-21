from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.family_interface_templates import (
    build_family_interface_template_artifacts,
    load_family_interface_template_catalog,
    render_family_interface_template_review_queue_markdown,
    render_family_interface_template_rollup_markdown,
    render_family_interface_templates_markdown,
)
from start_here_extractor.target_runner_families import load_target_family_runner_stubs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build family-specific adapter interface templates from target-family runner stubs")
    parser.add_argument("--target-runner-stubs-path", required=True, help="Path to target_family_runner_stubs.json")
    parser.add_argument("--family-interface-catalog-path", required=True, help="Path to family interface template catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for family interface template artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    stubs_doc = load_target_family_runner_stubs(args.target_runner_stubs_path)
    catalog = load_family_interface_template_catalog(args.family_interface_catalog_path)
    templates_doc, review_queue, rollup = build_family_interface_template_artifacts(stubs_doc, catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "family_interface_templates.json").write_text(json.dumps(templates_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "family_interface_templates.md").write_text(render_family_interface_templates_markdown(templates_doc), encoding="utf-8")
    (out_dir / "family_interface_template_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "family_interface_template_review_queue.md").write_text(render_family_interface_template_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "family_interface_template_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "family_interface_template_rollup.md").write_text(render_family_interface_template_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"template_count": templates_doc.get("template_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
