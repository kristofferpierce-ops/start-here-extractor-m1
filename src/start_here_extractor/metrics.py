from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                yield value


def build_monitoring_rollup(monitoring_dir: str | Path) -> dict[str, Any]:
    path = Path(monitoring_dir)
    totals = {
        'records': 0,
        'review_required': 0,
        'severity_high': 0,
        'severity_medium': 0,
        'severity_low': 0,
        'provider_source_counts': {},
    }
    for file in path.glob('*.jsonl'):
        for rec in _iter_jsonl(file):
            totals['records'] += 1
            if rec.get('review_required'):
                totals['review_required'] += 1
            sev = rec.get('severity')
            if sev == 'high':
                totals['severity_high'] += 1
            elif sev == 'medium':
                totals['severity_medium'] += 1
            else:
                totals['severity_low'] += 1
            source = rec.get('source_type') or 'unknown'
            counts = totals['provider_source_counts']
            counts[source] = counts.get(source, 0) + 1
    return totals
