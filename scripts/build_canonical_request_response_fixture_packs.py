from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_packages import (
    build_canonical_request_response_fixture_pack_artifacts,
    render_canonical_request_response_fixture_packs_markdown,
    render_canonical_request_response_fixture_review_queue_markdown,
    render_canonical_request_response_fixture_rollup_markdown,
)


def load_target_group_adapter_packages(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError("Target-group adapter packages payload must be a JSON object")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build canonical request/response fixture packs from target-group adapter packages")
    parser.add_argument("--target-group-packages-path", required=True, help="Path to target_group_adapter_packages.json")
    parser.add_argument("--out-dir", required=True, help="Directory for request/response fixture pack artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    packages_doc = load_target_group_adapter_packages(args.target_group_packages_path)
    packs_doc, review_queue, rollup = build_canonical_request_response_fixture_pack_artifacts(packages_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "canonical_request_response_fixture_packs.json").write_text(json.dumps(packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_request_response_fixture_packs.md").write_text(render_canonical_request_response_fixture_packs_markdown(packs_doc), encoding="utf-8")
    (out_dir / "canonical_request_response_fixture_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_request_response_fixture_review_queue.md").write_text(render_canonical_request_response_fixture_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "canonical_request_response_fixture_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_request_response_fixture_rollup.md").write_text(render_canonical_request_response_fixture_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
