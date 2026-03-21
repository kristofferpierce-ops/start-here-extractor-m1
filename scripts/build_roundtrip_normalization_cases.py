from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_skeletons import (
    build_roundtrip_normalization_case_artifacts,
    load_canonical_request_response_fixture_packs,
    render_roundtrip_normalization_cases_markdown,
    render_roundtrip_normalization_review_queue_markdown,
    render_roundtrip_normalization_rollup_markdown,
)


def load_target_group_adapter_skeletons(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError("Target-group adapter skeletons payload must be a JSON object")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build round-trip normalization cases from target-group adapter skeletons")
    parser.add_argument("--target-group-adapter-skeletons-path", required=True, help="Path to target_group_adapter_skeletons.json")
    parser.add_argument("--request-response-fixture-packs-path", required=True, help="Path to canonical_request_response_fixture_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for round-trip normalization case artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    skeletons_doc = load_target_group_adapter_skeletons(args.target_group_adapter_skeletons_path)
    fixture_packs_doc = load_canonical_request_response_fixture_packs(args.request_response_fixture_packs_path)
    cases_doc, review_queue, rollup = build_roundtrip_normalization_case_artifacts(skeletons_doc, fixture_packs_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "roundtrip_normalization_cases.json").write_text(json.dumps(cases_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "roundtrip_normalization_cases.md").write_text(render_roundtrip_normalization_cases_markdown(cases_doc), encoding="utf-8")
    (out_dir / "roundtrip_normalization_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "roundtrip_normalization_review_queue.md").write_text(render_roundtrip_normalization_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "roundtrip_normalization_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "roundtrip_normalization_rollup.md").write_text(render_roundtrip_normalization_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
