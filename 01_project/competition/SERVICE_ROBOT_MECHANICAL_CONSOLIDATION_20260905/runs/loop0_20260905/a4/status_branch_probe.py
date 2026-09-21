"""Probe only the status expression extracted from pose_screen.py.

Does NOT import or execute pose_screen.py, CAD code, VTK, numpy, or local project
modules. All pair rows are synthetic. This is NOT a geometry/collision test.
Usage: python status_branch_probe.py --source PATH --output PATH
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


def extract_status_expression(source: str) -> tuple[Any, int]:
    tree = ast.parse(source)
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'status' for t in node.targets
        ):
            text = ast.get_source_segment(source, node) or ''
            if '35_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN' in text:
                candidates.append(node)
    if len(candidates) != 1:
        raise ValueError('Expected exactly one source status assignment; review changed source manually.')
    node = candidates[0]
    allowed = (ast.IfExp, ast.Name, ast.Load, ast.Constant, ast.Compare, ast.Eq)
    for part in ast.walk(node.value):
        if not isinstance(part, allowed):
            raise ValueError(f'Refusing unrecognized expression node: {type(part).__name__}')
        if isinstance(part, ast.Name) and part.id not in {'hits', 'checked'}:
            raise ValueError('Unexpected expression variable')
    return compile(ast.Expression(node.value), '<isolated_status_expression>', 'eval'), node.lineno


def expected_pair(index: int) -> tuple[str, str]:
    return (f'synthetic_part_A_{index:02d}', f'synthetic_part_B_{index:02d}')


def make_row(index: int, hit: bool | None = False) -> dict[str, Any]:
    return {'links': list(expected_pair(index)), 'surface_intersection': hit}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error('Source is not a file')
    if args.source.resolve() == args.output.resolve():
        parser.error('Output must not overwrite source')
    raw = args.source.read_bytes()
    if len(raw) > 5_000_000:
        parser.error('Source too large for this bounded probe')
    source = raw.decode('utf-8-sig')
    compiled, lineno = extract_status_expression(source)
    expected = {expected_pair(i) for i in range(35)}
    normal = [make_row(i) for i in range(35)]
    cases = [
        ('35_distinct_rows_completed', normal, True),
        ('34_distinct_plus_duplicate_row', [make_row(i) for i in range(34)] + [make_row(0)], True),
        ('35_unexpected_pair_ids', [make_row(i + 100) for i in range(35)], True),
        ('35_distinct_rows_no_completion_event', normal, False),
        ('34_rows_only', [make_row(i) for i in range(34)], False),
        ('one_surface_hit', [make_row(i, i == 5) for i in range(35)], True),
    ]
    records = []
    for name, rows, completed in cases:
        hits = [row for row in rows if row['surface_intersection']]
        checked = sum(row['surface_intersection'] is not None for row in rows)
        observed = eval(compiled, {'__builtins__': {}}, {'hits': hits, 'checked': checked})
        ids = [tuple(row['links']) for row in rows]
        identities_match = set(ids) == expected and len(ids) == len(set(ids))
        records.append({
            'case': name,
            'synthetic': True,
            'evaluated_row_count': checked,
            'unique_pair_count': len(set(ids)),
            'identity_set_matches_fixture': identities_match,
            'worker_completed_fixture': completed,
            'production_status_expression_result': observed,
            'review_policy_result': ('INTERSECTION' if hits else 'BOUNDED_SURFACE_EVIDENCE'
                                     if identities_match and completed else 'INCOMPLETE_OR_INVALID_EVIDENCE'),
        })
    data = {
        'scope': 'ISOLATED_STATUS_EXPRESSION_WITH_SYNTHETIC_ROWS_ONLY',
        'executed_project_script': False,
        'executed_geometry_tests': False,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_status_line': lineno,
        'conclusion': ('The extracted expression depends on hit presence and count==35 only. '
                       'Malformed/duplicated/unexpected pair evidence can receive the same surface label. '
                       'This demonstrates a robustness gap, not that any historical geometry report is false.'),
        'cases': records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error('Output already exists; choose a new path to preserve previous evidence')
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(records), 'output': str(args.output), 'geometry_executed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
