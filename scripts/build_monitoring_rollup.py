from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.metrics import build_monitoring_rollup


def main() -> int:
    parser = argparse.ArgumentParser(description='Build a monitoring rollup JSON file from monitoring JSONL streams')
    parser.add_argument('monitoring_dir')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    monitoring_dir = Path(args.monitoring_dir)
    data = build_monitoring_rollup(monitoring_dir)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding='utf-8')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
