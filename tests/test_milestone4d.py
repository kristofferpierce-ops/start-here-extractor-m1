from __future__ import annotations

import json
from pathlib import Path

from start_here_extractor.metrics import build_monitoring_rollup
from start_here_extractor.reporter import build_inventory_record


def test_token_redacted_from_inventory_and_monitoring():
    payload = {
        'outcome': 'extracted',
        'zip_file': {'path': 'a.zip', 'size_bytes': 1, 'sha256': 'x', 'md5': 'y'},
        'inspection': {'entry_count': 1, 'risk_flags': [], 'entries': [], 'candidates': []},
        'selected_candidate': {'name': 'START HERE.TXT'},
        'extracted_file': {'path': 'out/start_here.txt', 'size_bytes': 10, 'md5': 'm', 'sha256': 's'},
        'preview': {'encoding': 'utf-8', 'text': 'hello', 'bytes_read': 5, 'lines': 1},
        'warnings': [],
        '_runtime_cloud': {'token_health': {'token': 'secret-token', 'source': 'command', 'expires_at': '2030-01-01T00:00:00+00:00', 'status': 'fresh', 'notes': []}},
        'provenance': {'source_type': 'gdrive', 'staging_path': 'stage.zip'},
    }
    rec = build_inventory_record(payload)
    assert 'token' not in rec['governance']['token_health']
    assert 'token' not in rec['monitoring']['token_health']
    raw = json.dumps(rec)
    assert 'secret-token' not in raw


def test_monitoring_rollup_counts(tmp_path: Path):
    mdir = tmp_path / '_monitoring'
    mdir.mkdir(parents=True)
    entries = [
        {'source_type': 'gdrive', 'review_required': False, 'severity': 'low'},
        {'source_type': 'gdrive', 'review_required': True, 'severity': 'medium'},
        {'source_type': 'local', 'review_required': True, 'severity': 'high'},
    ]
    path = mdir / 'monitoring-events.jsonl'
    with path.open('w', encoding='utf-8') as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + '\n')
    rollup = build_monitoring_rollup(mdir)
    assert rollup['records'] == 3
    assert rollup['review_required'] == 2
    assert rollup['severity_high'] == 1
    assert rollup['severity_medium'] == 1
    assert rollup['severity_low'] == 1
    assert rollup['provider_source_counts']['gdrive'] == 2
