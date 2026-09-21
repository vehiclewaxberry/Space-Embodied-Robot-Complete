"""Candidate runtime aggregator integrated by pose_screen.classify_self_surface.

Aggregates run/configuration/hash-bound records; synthetic controls test protocol only.
A valid runtime result covers only the declared nonadjacent surface pair set,
with the finger pair explicitly unknown.
It cannot establish containment, adjacent-link clearance or whole-spacecraft safety.
"""
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pair_id(links):
    if not isinstance(links, list) or len(links) != 2 or any(not isinstance(x, str) for x in links) or links[0] == links[1]:
        raise ValueError('MALFORMED_PAIR_ID')
    return tuple(sorted(links))


def aggregate(contract, evidence):
    """Contract/evidence are runtime-bound records supplied by the candidate pose entry."""
    result = {'evidence_type': 'RUNTIME_BOUND_SCOPED_SURFACE_PROTOCOL',
              'geometry_executed': evidence.get('geometry_executed') is True, 'status': 'INCOMPLETE_OR_INVALID_EVIDENCE',
              'reasons': [], 'surface_hits': [],
              'unknown': ['finger/finger', 'all adjacent-link pairs', 'volume containment',
                          'continuous paths', 'arm/spacecraft and all other spacecraft pairs'],
              'full_geometry_pass': None}
    reasons = result['reasons']
    def finite(v):
        if isinstance(v,float): return math.isfinite(v)
        if isinstance(v,dict): return all(finite(x) for x in v.values())
        if isinstance(v,(list,tuple)): return all(finite(x) for x in v)
        return True
    if not finite(contract) or not finite(evidence): reasons.append('NONFINITE_PROTOCOL_VALUE')
    try:
        expected_list = [pair_id(p) for p in contract['expected_nonadjacent_pairs']]
        expected = set(expected_list)
        deferred = {pair_id(p) for p in contract['explicit_unknown_pairs']}
        if len(expected) != len(expected_list) or not expected or not deferred <= expected:
            reasons.append('INVALID_EXPECTED_PAIR_CONTRACT')
        if not contract['input_sha256']:
            reasons.append('MISSING_CONTRACT_HASHES')
        if evidence.get('run_id') != contract['run_id']:
            reasons.append('WRONG_RUN_ID')
        if evidence.get('configuration') != contract['configuration']:
            reasons.append('CONFIGURATION_MISMATCH')
        if evidence.get('input_sha256_before') != contract['input_sha256']:
            reasons.append('OLD_OR_WRONG_INPUT_HASH')
        if evidence.get('input_sha256_after') != contract['input_sha256']:
            reasons.append('INPUT_CHANGED_OR_END_HASH_MISSING')
        if evidence.get('worker_returncode') != 0 or type(evidence.get('worker_returncode')) is not int:
            reasons.append('WORKER_RETURN_CODE_NOT_ZERO')
        if evidence.get('worker_error') is not None:
            reasons.append('WORKER_ERROR')
        if evidence.get('timed_out') is not False:
            reasons.append('TIMEOUT_OR_TIMEOUT_STATE_UNKNOWN')
        completion = evidence.get('completion')
        if not isinstance(completion, dict) or completion.get('completed') is not True:
            reasons.append('NO_COMPLETION_EVENT')
        elif (completion.get('run_id') != contract['run_id']
              or completion.get('pose_id') != contract['configuration']['pose_id']
              or completion.get('snapshot_digest') != digest(contract['input_sha256'])
              or completion.get('expected_pair_count') != len(expected)):
            reasons.append('COMPLETION_IDENTITY_MISMATCH')
        rows = evidence['records']
        ids = [pair_id(r['links']) for r in rows]
        if len(ids) != len(set(ids)):
            reasons.append('DUPLICATE_PAIR_ID')
        if set(ids) != expected:
            reasons.append('MISSING_OR_UNEXPECTED_PAIR_ID')
        for row, identity in zip(rows, ids):
            if (row.get('run_id') != contract['run_id']
                    or row.get('pose_id') != contract['configuration']['pose_id']
                    or row.get('snapshot_digest') != digest(contract['input_sha256'])):
                reasons.append('ROW_IDENTITY_OR_SNAPSHOT_MISMATCH')
            value = row.get('surface_intersection')
            if identity in deferred:
                if value is not None or not row.get('unknown_reason'):
                    reasons.append('EXPLICIT_UNKNOWN_SCOPE_CHANGED')
            elif type(value) is not bool:
                reasons.append('INVALID_OR_MISSING_BOOLEAN_RESULT')
            elif value:
                result['surface_hits'].append(list(identity))
        result['expected_pair_count'] = len(expected)
        result['required_surface_pair_count'] = len(expected - deferred)
        result['record_count'] = len(rows)
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append('MALFORMED_EVIDENCE: ' + str(exc))
    result['reasons'] = sorted(set(reasons))
    if not result['reasons']:
        result['status'] = ('SCOPED_SURFACE_INTERSECTION_RECORDED' if result['surface_hits']
                            else 'DECLARED_NONADJACENT_BODY_PAIR_SURFACES_DISJOINT_ONLY')
    return result


def require_physical_view(receipt):
    """Physical-view guard used by this candidate entry."""
    if receipt.get('view') != 'complete' or receipt.get('state') not in ('parking', 'released', 'service'):
        raise ValueError('DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED')
    return 'DECLARED_COMPLETE_VIEW_ONLY_NOT_GEOMETRY_VALIDATION'
