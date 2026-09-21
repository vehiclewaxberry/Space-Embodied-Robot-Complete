"""Strict aggregation of the real pose_screen worker chain (integrated edition).

Consumes results/POSE_SCREEN.json produced by pose_screen.py (V2 schema with
self_screen_contract and worker identity events). The isolated prototype at
runs/loop0_20260905/a4/strict_surface_aggregator.py is untouched; this module is
the deployed integration. Fail-closed: stale/missing input hashes, wrong script,
worker non-zero/timeout/error, missing or mismatched completion events,
duplicate/missing/unexpected pair IDs, non-boolean or NaN results, deferred-scope
changes all prevent PASS. Protocol acceptance and mechanical collision acceptance
are reported separately; a protocol PASS is not a mechanical clearance claim.
"""
from pathlib import Path
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
POSE_JSON = HERE / 'results' / 'POSE_SCREEN.json'
SCHEMA = 'WP03_BOUNDED_EXISTING_POSE_SCREEN_V2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair_id(links):
    if not isinstance(links, list) or len(links) != 2 or any(not isinstance(x, str) for x in links) or links[0] == links[1]:
        raise ValueError('MALFORMED_PAIR_ID')
    return tuple(sorted(links))


def require_physical_view(receipt):
    """输入视图守卫：爆炸/剖切/地面等展示视图不得充当物理检查输入。"""
    if receipt.get('view') != 'complete' or receipt.get('state') not in ('parking', 'released', 'service'):
        raise ValueError('DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED')
    return 'DECLARED_COMPLETE_VIEW_ONLY_NOT_GEOMETRY_VALIDATION'


def aggregate(data, script_path=None, snapshot_binding=None):
    """data: 真实 POSE_SCREEN.json 内容。snapshot_binding: {绝对路径: sha256} 输入快照绑定。"""
    script_path = Path(script_path) if script_path else HERE / 'pose_screen.py'
    reasons = []
    poses_out = []
    if data.get('schema') != SCHEMA:
        reasons.append(f'SCHEMA_MISMATCH:{data.get("schema")!r}')
    if data.get('script_sha256') != sha(script_path):
        reasons.append('SCRIPT_HASH_STALE（输出非现行脚本生成=过期来源）')
    src = data.get('source_hashes')
    if not isinstance(src, dict) or not src:
        reasons.append('SOURCE_HASH_RECORD_MISSING')
        src = {}
    for path, h in src.items():
        if not Path(path).is_file():
            reasons.append(f'INPUT_FILE_MISSING:{path}')
        elif sha(path) != h:
            reasons.append(f'INPUT_STALE:{path}（检查后输入已变化）')
    if snapshot_binding:
        for path, h in snapshot_binding.items():
            if src.get(path) != h:
                reasons.append(f'SNAPSHOT_BINDING_MISMATCH:{path}（实际检查输入≠本次输入快照）')
    contract = data.get('self_screen_contract')
    if not isinstance(contract, dict):
        reasons.append('SELF_SCREEN_CONTRACT_MISSING')
        contract = {}
    try:
        expected_list = [pair_id(p) for p in contract.get('expected_nonadjacent_pairs', [])]
        deferred = {pair_id(p) for p in contract.get('explicit_unknown_pairs', [])}
    except ValueError as exc:
        return {'protocol': {'verdict': 'FAIL', 'reasons': ['MALFORMED_CONTRACT: ' + str(exc)]},
                'mechanical_collision': {'verdict': 'UNKNOWN_PROTOCOL_FAILED'},
                'overall': 'FAIL'}
    expected = set(expected_list)
    if len(expected) != len(expected_list) or not expected or not deferred <= expected:
        reasons.append('INVALID_EXPECTED_PAIR_CONTRACT')
    if not contract.get('input_sha256'):
        reasons.append('MISSING_CONTRACT_HASHES')
    rid, sd = contract.get('run_id'), contract.get('snapshot_digest')
    conf = contract.get('configuration', {})
    if data.get('worker_returncode') != 0:
        reasons.append('WORKER_RETURN_CODE_NOT_ZERO')
    if data.get('worker_timed_out') is not False:
        reasons.append('TIMEOUT_OR_TIMEOUT_STATE_UNKNOWN')
    if data.get('self_worker_error') is not None:
        reasons.append('WORKER_ERROR')
    pose_index = {p.get('id'): p for p in data.get('poses', [])}
    for pose_id in conf.get('poses', []):
        p = pose_index.get(pose_id)
        if p is None:
            reasons.append(f'POSE_MISSING:{pose_id}')
            continue
        preasons = []
        ssc = p.get('self_surface_check', {})
        comp = ssc.get('completion_event')
        if not isinstance(comp, dict) or comp.get('completed') is not True:
            preasons.append('NO_COMPLETION_EVENT')
        elif (comp.get('run_id') != rid or comp.get('pose_id') != pose_id
              or comp.get('snapshot_digest') != sd
              or comp.get('expected_pair_count') != len(expected)):
            preasons.append('COMPLETION_IDENTITY_MISMATCH')
        if ssc.get('worker_completed') is not True:
            preasons.append('WORKER_COMPLETION_FLAG_FALSE')
        rows = ssc.get('records', [])
        try:
            ids = [pair_id(r['links']) for r in rows]
        except (KeyError, ValueError) as exc:
            preasons.append('MALFORMED_RECORD: ' + str(exc))
            ids = []
        if len(ids) != len(set(ids)):
            preasons.append('DUPLICATE_PAIR_ID')
        if set(ids) != expected:
            preasons.append('MISSING_OR_UNEXPECTED_PAIR_ID')
        hits = []
        for row, identity in zip(rows, ids):
            value = row.get('surface_intersection')
            if isinstance(value, float):
                preasons.append(f'NAN_OR_FLOAT_RESULT:{list(identity)}')
                continue
            if identity in deferred:
                if value is not None or not (row.get('unknown_reason') or row.get('method')):
                    preasons.append('EXPLICIT_UNKNOWN_SCOPE_CHANGED')
            elif type(value) is not bool:
                preasons.append('INVALID_OR_MISSING_BOOLEAN_RESULT')
            elif value:
                hits.append(list(identity))
        expected_status = ('EXPLICIT_SELF_SURFACE_INTERSECTION_REJECTED' if hits
                           else 'NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN')
        if not preasons and ssc.get('status') != expected_status:
            preasons.append(f'POSE_STATUS_INCONSISTENT:{ssc.get("status")!r}')
        if ssc.get('evaluated_pairs') != ssc.get('required_evaluated_pairs'):
            preasons.append('EVALUATED_PAIR_COUNT_MISMATCH')
        poses_out.append({'pose_id': pose_id, 'protocol_reasons': sorted(set(preasons)),
                          'surface_hits': hits, 'records': len(rows),
                          'mechanical_status': ssc.get('status'),
                          'deferred_pairs': [list(x) for x in sorted(deferred)]})
        reasons.extend(f'{pose_id}:{r}' for r in preasons)
    protocol_ok = not reasons
    mech = {'verdict': ('DISJOINT_WITHIN_DECLARED_SCOPE' if protocol_ok and not any(p['surface_hits'] for p in poses_out)
                        else 'SURFACE_INTERSECTION_RECORDED' if protocol_ok else 'UNKNOWN_PROTOCOL_FAILED'),
            'scope': 'accepted STL 非相邻 link 对（延期：指/指对）；相邻对、闭体包含、连续路径、臂/星体其余对 UNKNOWN',
            'unknown': ['finger/finger pair', 'adjacent-link pairs', 'volume containment', 'continuous paths'],
            'per_pose': [{'pose_id': p['pose_id'], 'surface_hits': p['surface_hits']} for p in poses_out]}
    return {'schema': 'WP03_STRICT_SURFACE_INTEGRATION_V1',
            'protocol': {'verdict': 'PASS' if protocol_ok else 'FAIL', 'reasons': sorted(set(reasons)),
                         'expected_pair_count': len(expected), 'deferred_pair_count': len(deferred),
                         'poses_checked': len(poses_out)},
            'mechanical_collision': mech,
            'poses': poses_out,
            'overall': 'PASS' if protocol_ok else 'FAIL',
            'scope_note': '协议 PASS 仅证明证据链完整同源；机械碰撞结论限声明范围，不构成整星安全或发射收拢证明'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=POSE_JSON)
    ap.add_argument('--snapshot-binding', type=Path, default=None,
                    help='JSON {绝对路径: sha256}：本次输入快照绑定（缺省不绑定）')
    ap.add_argument('--output', type=Path, default=HERE / 'results' / 'STRICT_SURFACE_INTEGRATION.json')
    args = ap.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    binding = json.loads(args.snapshot_binding.read_text(encoding='utf-8')) if args.snapshot_binding else None
    result = aggregate(data, snapshot_binding=binding)
    result['input_pose_screen'] = str(args.input)
    result['input_pose_screen_sha256'] = sha(args.input)
    result['snapshot_binding_file'] = str(args.snapshot_binding) if args.snapshot_binding else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'overall': result['overall'], 'protocol': result['protocol']['verdict'],
                      'mechanical': result['mechanical_collision']['verdict'],
                      'reasons': result['protocol']['reasons'][:10]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
