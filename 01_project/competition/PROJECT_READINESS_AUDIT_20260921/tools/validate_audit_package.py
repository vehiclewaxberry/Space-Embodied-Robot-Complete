"""Verify this audit's references and provenance; never runs or rewrites scientific gates."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import json
import re
from urllib.parse import unquote

D = Path(__file__).resolve().parents[1]
ROOT = D.parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

errors = []
source_checks = []
for filename, key in [('ENGINEERING_EVIDENCE.json', 'source_records'),
                      ('RESEARCH_EVIDENCE.json', 'machine_evidence'),
                      ('LICENSE_SOURCE_IDENTIFICATION.json', 'sources')]:
    document = json.loads((D / filename).read_text(encoding='utf-8'))
    for record in document[key]:
        path = ROOT / record['path']
        actual = digest(path) if path.is_file() else None
        matches = actual == record['sha256'].lower()
        source_checks.append({'evidence_file': filename, 'path': record['path'],
                              'sha256': actual, 'matches_audit_snapshot': matches})
        if not matches:
            errors.append({'kind': 'AUDIT_SOURCE_CHANGED', 'path': record['path']})

link_checks = []
for path in sorted(D.glob('*.md')):
    for raw in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        target = raw.strip().strip('<>')
        if target.startswith(('https://', 'http://', '#', 'mailto:')):
            continue
        target = unquote(target.split('#')[0])
        resolved = path.parent / target
        exists = resolved.exists()
        link_checks.append({'document': path.name, 'target': target, 'exists': exists})
        if not exists:
            errors.append({'kind': 'BROKEN_LOCAL_LINK', 'document': path.name, 'target': target})

for path in D.rglob('*.json'):
    if path.name != 'AUDIT_STATUS.json':
        json.loads(path.read_text(encoding='utf-8-sig'))

with (D / 'NEXT_STAGE_AND_PUBLICATION_GAPS.csv').open(encoding='utf-8-sig', newline='') as handle:
    gaps = list(csv.DictReader(handle))
counts = dict(Counter(row['track'] for row in gaps))
if len(gaps) != 28 or len({row['id'] for row in gaps}) != 28:
    errors.append({'kind': 'GAP_REGISTER_COUNT_OR_DUPLICATE'})
for row in gaps:
    if not (D / row['source']).is_file():
        errors.append({'kind': 'MISSING_GAP_SOURCE', 'id': row['id'], 'source': row['source']})

status = {
    'schema': 'PROJECT_READINESS_AUDIT_DELIVERY_V1',
    'generated_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Audit delivery integrity only; not a scientific gate or public release clearance',
    'audit_complete': not errors,
    'publication_ready': False,
    'whole_spacecraft_design_complete': False,
    'ready_to_power': False,
    'flight_ready': False,
    'github_repository_created': False,
    'files_uploaded': False,
    'git_history_modified': False,
    'scientific_gates_modified': False,
    'new_simulations_executed': False,
    'credentials_rotated': False,
    'full_history_secret_scan_completed': False,
    'gap_count': len(gaps), 'gap_counts_by_track': counts,
    'recorded_sources_rechecked': len(source_checks),
    'local_document_links_checked': len(link_checks),
    'source_checks': source_checks, 'local_link_checks': link_checks,
    'cross_review': 'FINAL_CROSS_REVIEW.json',
    'post_review_clarification': 'E23 report now labels relative errors as dimensionless ratios with percentage equivalents; source gate unchanged',
    'known_source_binding_mismatches': {
        'sim10_frozen_inputs': 2,
        'wp10_handoff_evidence': 1,
        'meaning': 'Disclosed upstream reproducibility issues, distinct from integrity of this audit snapshot'},
    'errors': errors,
    'manifest_policy': 'AUDIT_SHA256.csv includes all audit files except itself; source datasets remain in their original locations'
}
(D / 'AUDIT_STATUS.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with (D / 'AUDIT_SHA256.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=['path', 'bytes', 'sha256'])
    writer.writeheader()
    for path in sorted(D.rglob('*')):
        if path.is_file() and path.name != 'AUDIT_SHA256.csv' and '__pycache__' not in path.parts:
            writer.writerow({'path': path.relative_to(D).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)})
print(json.dumps({k: status[k] for k in ['audit_complete', 'publication_ready', 'gap_count', 'gap_counts_by_track', 'recorded_sources_rechecked', 'local_document_links_checked', 'errors']}, ensure_ascii=False))
raise SystemExit(0 if not errors else 2)
