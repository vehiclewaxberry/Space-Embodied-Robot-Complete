"""File-only delivery audit. Existing files and failed attempts are not PASS.

--audit-only leaves BUILD_STATUS/BOM untouched. No CAD/COM imports or calls.
"""
from pathlib import Path
import argparse
import collections
import csv
import datetime
import hashlib
import importlib.util
import json
import math

OUT = Path(__file__).resolve().parents[1]


def norm(p):
    return str(Path(p).resolve()).casefold()


def positive(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def close(a, b, rel=1e-6, absolute=1e-8):
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a) and math.isfinite(b) and abs(a-b) <= max(absolute, abs(b)*rel)


def sw16(T):
    return [T[i][j] for j in range(3) for i in range(3)] + [T[i][3]/1000 for i in range(3)] + [1., 0., 0., 0.]


class Audit:
    def __init__(self):
        self.cache, self.rejected, self.errors = {}, [], []

    def sha(self, path):
        if not path:
            return None
        p = Path(path)
        try:
            a = p.stat(); stamp = (a.st_size, a.st_mtime_ns); key = norm(p)
            if key in self.cache and self.cache[key][0] == stamp:
                return self.cache[key][1]
            with p.open('rb') as f:
                value = hashlib.file_digest(f, 'sha256').hexdigest()
            b = p.stat()
            if (b.st_size, b.st_mtime_ns) != stamp:
                return None
            self.cache[key] = (stamp, value)
            return value
        except OSError:
            return None

    def matches(self, path, digest):
        return bool(digest) and self.sha(path) == digest

    def read(self, path, required=False):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
            return data
        except (OSError, ValueError) as ex:
            if required:
                raise ValueError(f'Required input unavailable: {path}: {ex}') from ex
            self.reject(path, ['UNREADABLE_OR_IN_PROGRESS_JSON'], detail=str(ex))
            return {}

    def reject(self, path, reasons, target=None, **extra):
        self.rejected.append(dict(receipt=str(path), target=target, reasons=reasons, **extra))

    def ref(self, path):
        return dict(path=str(path), sha256=self.sha(path))


def material_errors(row, candidate):
    errors = []
    assigned = candidate.get('assignment_action') == 'ASSIGN_NATIVE_BULK_MATERIAL'
    if row.get('assigned') is not assigned:
        errors.append('MATERIAL_ACTION_MISMATCH')
    if row.get('open_errors') != 0:
        errors.append('MATERIAL_COLD_OPEN_NOT_SUCCESSFUL')
    if candidate.get('conflict'):
        errors.append('MATERIAL_PLAN_CONFLICT')
    if assigned:
        actual = row.get('cold_material') or []
        if not actual or actual[0] != candidate.get('sw_material_name'):
            errors.append('NATIVE_MATERIAL_NAME_MISMATCH')
        rho, volume, mass = [row.get(k) for k in ('density_kg_m3', 'volume_m3', 'candidate_geometry_mass_kg')]
        expected = candidate.get('density_kg_m3')
        if not positive(expected) or not positive(rho) or not close(rho, expected):
            errors.append('NATIVE_DENSITY_NOT_EXPLICIT_DESIGN_CANDIDATE')
        if not positive(volume) or not positive(mass) or not close(mass/volume, expected):
            errors.append('NATIVE_MASS_VOLUME_DENSITY_INCONSISTENT')
    elif any(row.get(k) is not None for k in ('density_kg_m3', 'volume_m3', 'candidate_geometry_mass_kg')):
        errors.append('UNKNOWN_OR_COMPOSITE_HAS_ARTIFICIAL_BULK_MASS')
    return errors


def geometry_errors(facts, job):
    errors = []
    if facts.get('solid_count') != job.get('expected_solids') or facts.get('sheet_count') != 0:
        errors.append('NATIVE_BODY_COUNT_MISMATCH')
    actual, expected = facts.get('volume_mm3'), job.get('expected_volume_mm3')
    if not positive(actual) or not positive(expected) or not close(actual, expected, 1e-5, 1e-4):
        errors.append('NATIVE_VOLUME_SCREEN_FAILED')
    try:
        actual, expected = facts['bounds_mm'], job['expected_local_bbox_mm']
        if isinstance(actual, dict): actual = [actual['min_mm'], actual['max_mm']]
        if isinstance(expected, dict): expected = [expected['min_mm'], expected['max_mm']]
        if any(not close(actual[i][j], expected[i][j], 0, 1e-4) for i in range(2) for j in range(3)):
            errors.append('NATIVE_BOUNDS_SCREEN_FAILED')
    except (KeyError, TypeError, IndexError):
        errors.append('NATIVE_BOUNDS_SCREEN_MISSING')
    return errors


def hash_link(current, original, material):
    if current and current == original:
        return 'CURRENT_HASH_EQUALS_COLD_GEOMETRY_HASH'
    if material and material['row'].get('before_native_sha256') == original and material['row'].get('sha256') == current:
        return 'COLD_GEOMETRY_TO_MATERIAL_WRITE_HASH_CHAIN'
    return None


def derive(root=OUT):
    audit = Audit(); inputs = root/'inputs'; results = root/'results'
    smap_path = inputs/'NEUTRAL_SOURCE_MAP.json'; apath = inputs/'INTEGRATED_ASSEMBLY_PLAN.json'
    source = audit.read(smap_path, True); assembly = audit.read(apath, True)
    copies = audit.read(inputs/'NATIVE_COPY_PLAN.json', True); imports = audit.read(inputs/'ALL_IMPORT_PLAN.json', True)
    groups = {g['id']: g for g in source['groups']}; agroups = {g['id']: g for g in assembly['groups']}
    jobs = {norm(j['native_path']): j for j in imports['parts']}; copyjobs = {norm(j['target']): j for j in copies['parts']}
    for p in (apath, inputs/'NATIVE_COPY_PLAN.json', inputs/'ALL_IMPORT_PLAN.json'):
        pin = next((v for k, v in source.get('source_manifest_sha256', {}).items() if norm(k) == norm(p)), None)
        if not audit.matches(p, pin): audit.errors.append(dict(path=str(p), reason='SOURCE_MAP_INPUT_PIN_MISMATCH'))
    plans, materials = {}, {}
    for name in ('NATIVE_MATERIAL_PLAN.json', 'INCREMENT_MATERIAL_PLAN.json'):
        p = inputs/name; data = audit.read(p, True); rows = {norm(r['native_path']): r for r in data['parts']}
        plans[audit.sha(p)] = dict(path=str(p), parts=rows)
        for key, row in rows.items():
            if key in materials and materials[key] != row: audit.errors.append(dict(path=row['native_path'], reason='CONFLICTING_MATERIAL_PLANS'))
            materials[key] = row

    cold = {}
    for p in sorted(results.glob('MATERIAL_NATIVE_*.json')):
        d = audit.read(p)
        if not d.get('status', '').startswith('PASS_NATIVE_MATERIAL_WRITE_AND_COLD_READ'):
            audit.reject(p, ['NON_SUCCESS_HISTORY_NOT_USED']); continue
        plan = plans.get(d.get('plan_sha256'))
        if not plan or (d.get('plan_path') and norm(d['plan_path']) != norm(plan['path'])):
            audit.reject(p, ['MATERIAL_PLAN_HASH_OR_PATH_MISMATCH']); continue
        for row in d.get('parts', []):
            target = row.get('path'); key = norm(target) if target else None; candidate = plan['parts'].get(key)
            why = material_errors(row, candidate) if candidate else ['PART_NOT_IN_HASH_BOUND_MATERIAL_PLAN']
            if not audit.matches(target, row.get('sha256')): why.append('CURRENT_NATIVE_HASH_MISMATCH_OR_MISSING')
            if key in jobs and row.get('source_STEP_sha256') != jobs[key]['source_sha256']: why.append('MATERIAL_STEP_SOURCE_PIN_MISSING_OR_MISMATCH')
            if why: audit.reject(p, why, target); continue
            cold[key] = dict(row=row, receipt=audit.ref(p), database_current_hash_matches=audit.matches(d.get('database_path'), d.get('database_sha256')))

    imported = {}
    receipts = list(results.glob('IMPORT_*.json')); pilot = results/'FIRST_MCP_NATIVE_COLD_SEAL.json'
    if pilot.exists(): receipts.append(pilot)
    for p in sorted(receipts):
        d = audit.read(p); first = p.name == pilot.name
        required = 'PASS_FIRST_MCP_NATIVE_COLD_BODY_BOUNDS_VOLUME_AND_NO_EXTERNAL_LINKS' if first else 'PASS_SOURCE_INCREMENT_IMPORTED_AND_COLD_READ'
        recovered = d.get('status') == 'PASS_VERIFIED_SUBSET_OF_INTERRUPTED_IMPORT'
        reconciled = d.get('status') == 'PASS_SINGLE_PART_VOLUME_REFERENCE_RECONCILIATION_UNCHANGED_TOLERANCE'
        volume_reconciliation = None
        parent_rows = []
        if reconciled:
            # The helper has one pinned part/source allowlist, fixed thresholds,
            # and recomputes all source/native/diagnostic/reviewer hash bindings.
            # Merely setting a PASS or exception field never bypasses the screen.
            try:
                helper_path = Path(__file__).with_name('reconcile_volume.py')
                spec = importlib.util.spec_from_file_location('delivery_volume_reconciliation', helper_path)
                helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
                volume_reconciliation = helper.validate_existing_receipt(p, root)
            except (OSError, ValueError, KeyError, TypeError, IndexError) as ex:
                audit.reject(p, ['SINGLE_PART_VOLUME_RECONCILIATION_INVALID'], detail=str(ex)); continue
        elif recovered:
            parent = d.get('interrupted_receipt')
            if not audit.matches(parent, d.get('interrupted_receipt_sha256')) or d.get('import_plan_sha256') != audit.sha(inputs/'ALL_IMPORT_PLAN.json'):
                audit.reject(p, ['RECOVERED_SUBSET_PARENT_OR_PLAN_SHA_MISMATCH']); continue
            parent_data = audit.read(parent)
            if parent_data.get('status') != 'FAILED':
                audit.reject(p, ['RECOVERED_SUBSET_PARENT_NOT_AN_INTERRUPTED_FAILURE']); continue
            parent_rows = parent_data.get('parts', [])
        elif d.get('status') != required:
            audit.reject(p, ['NON_SUCCESS_HISTORY_NOT_USED']); continue
        for row in [d] if first else d.get('parts', []):
            target = row.get('native_path') if first else row.get('target'); key = norm(target) if target else None; job = jobs.get(key)
            if not job: audit.reject(p, ['PART_NOT_IN_CURRENT_IMPORT_PLAN'], target); continue
            why = []
            if recovered and row not in parent_rows: why.append('RECOVERED_ROW_DIFFERS_FROM_HASH_BOUND_PARENT')
            if d.get('import_plan_sha256') and d['import_plan_sha256'] != audit.sha(inputs/'ALL_IMPORT_PLAN.json'): why.append('IMPORT_PLAN_SHA_MISMATCH')
            if row.get('source_sha256') != job['source_sha256'] or not audit.matches(job['step_path'], job['source_sha256']): why.append('IMPORT_SOURCE_SHA_MISMATCH')
            if not first and not audit.matches(row.get('source'), row.get('source_sha256')): why.append('ACTUAL_IMPORT_STEP_SHA_MISMATCH')
            opened = row.get('part_cold_reopen', {}); facts = row.get('facts', {}) if first else opened.get('facts', {})
            measurement_job = job
            if volume_reconciliation:
                measurement_job = dict(job, expected_volume_mm3=volume_reconciliation['volume_reference_reconciliation']['corrected_reference_volume_mm3'])
            why.extend(geometry_errors(facts, measurement_job))
            if not first:
                if row.get('import_stage') != 'COMPLETED' or row.get('import_errors') != 0 or opened.get('errors') != 0: why.append('IMPORT_COLD_OPEN_NOT_COMPLETED')
                if not volume_reconciliation and row.get('volume_numeric_screen_pass') is not True: why.append('IMPORT_VOLUME_SCREEN_NOT_ACCEPTED')
                if row.get('external_reference_count') != 0 or row.get('auxiliary_reference_count') != 0: why.append('IMPORT_EXTERNAL_REFERENCE_NOT_ZERO')
            oldsha = row.get('native_sha256') if first else row.get('native_save', {}).get('sha256')
            link = hash_link(audit.sha(target), oldsha, cold.get(key))
            if not link: why.append('CURRENT_NATIVE_NOT_LINKED_TO_IMPORT_COLD_HASH')
            if why: audit.reject(p, why, target); continue
            imported[key] = dict(id=job['id'], native_path=target, receipt=audit.ref(p), hash_link=link, cold_geometry_sha256=oldsha, current_sha256=audit.sha(target), source_sha256=job['source_sha256'],
                                 volume_reference_reconciliation=volume_reconciliation['volume_reference_reconciliation'] if volume_reconciliation else None)

    groupcold = {}
    for p in sorted(results.glob('GROUPS_*.json')):
        d = audit.read(p)
        if d.get('status') != 'PASS_FIXED_GROUP_BUILD_AND_COLD_READ': audit.reject(p, ['NON_SUCCESS_HISTORY_NOT_USED']); continue
        for row in d.get('groups', []):
            ident = row.get('id'); g = agroups.get(ident); saved = row.get('save', {}); why = []
            if not g or norm(saved.get('path', '.')) != norm(g['path']): why.append('GROUP_NOT_IN_CURRENT_PLAN')
            if d.get('assembly_plan_sha256') != audit.sha(apath): why.append('GROUP_PLAN_SHA_MISSING_OR_MISMATCH')
            if not audit.matches(saved.get('path'), saved.get('sha256')): why.append('CURRENT_GROUP_SHA_MISMATCH')
            if row.get('cold_errors') != 0 or (g and row.get('leaves') != len(g['rows'])): why.append('GROUP_COLD_READ_OR_COUNT_MISMATCH')
            if why: audit.reject(p, why, ident)
            else: groupcold[ident] = dict(receipt=audit.ref(p), path=saved['path'], sha256=saved['sha256'])

    npath = results/'NEUTRAL_ASSEMBLY.json'; neutral = audit.read(npath) if npath.exists() else {}
    neutral_source_ok = audit.matches(smap_path, neutral.get('source_map', {}).get('sha256'))
    status = dict(schema='DIGITAL_PROTOTYPE_DELIVERY_STATE_V2', generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        whole_design_complete=False, ready_to_power=False, flight_ready=False, whole_mass_kg=None, whole_COM_mm=None, whole_inertia_kg_m2=None,
        whole_mass_status='UNKNOWN_COMPOSITE_AND_UNASSIGNED_ITEMS; SOFTWARE_DEFAULT_DENSITY_EXCLUDED', full_material_assignment=False,
        native_material_readback_part_files=len(cold), native_bulk_material_assigned_part_files=sum(p['row']['assigned'] for p in cold.values()),
        increment_native_parts=dict(planned=len(jobs), files_present=sum(Path(j['native_path']).is_file() for j in jobs.values()), current_source_bound_cold_verified=len(imported), pending_or_unverified=len(jobs)-len(imported)),
        fixed_groups=dict(planned=len(agroups), current_plan_and_file_cold_verified=len(groupcold)), states={}, input_errors=audit.errors,
        input_manifest_sha256={str(p): audit.sha(p) for p in (smap_path, apath, inputs/'ALL_IMPORT_PLAN.json', inputs/'NATIVE_COPY_PLAN.json')},
        material_plan_sha256={p['path']: h for h, p in plans.items()},
        unclosed=['V36_COMPLETE_PCBA_INSTALLATIONS', 'CF1_THERMAL_MODULE_RELAYOUT', 'R01_MERGED_BEARING_EDGE_RECHECK', 'OEM_PROPULSION_SELECTION_AND_INSTALLATION', 'HARNESS_PIN_TO_PIN_AND_MOTION', 'STAGED_GROUND_POWER_AND_THERMAL_TESTS', 'ORBITAL_THERMAL_AND_RADIATION_IF_FLIGHT_SCOPE'])
    if neutral: status['neutral_receipt'] = dict(**audit.ref(npath), status=neutral.get('status'), source_map_sha256_matches=neutral_source_ok)
    tables = {}
    for state, s in assembly['states'].items():
        expected = {r['id']: r for gid in s['groups'] for r in agroups[gid]['rows']}; rows = []; counts = collections.Counter(); issues = []
        if source['states'].get(state, {}).get('groups') != s['groups']: issues.append('SOURCE_AND_NATIVE_STATE_GROUPS_DIFFER')
        for gid in s['groups']:
            for q in groups.get(gid, {}).get('rows', []):
                key = norm(q['native_path']); mat = materials.get(key, {}); proof = cold.get(key); geom = imported.get(key)
                source_ok = q.get('status') == 'SOURCE_AND_TRANSFORM_PINNED' and audit.matches(q.get('step_path'), q.get('source_sha256'))
                sha = audit.sha(q['native_path']); actual_plan = expected.get(q['id'])
                if not actual_plan or norm(q['native_path']) != norm(actual_plan['native_path']) or q['T_S_local'] != actual_plan['T_S_local'] or q['expected_solids'] != actual_plan['expected_solids']:
                    source_ok = False; issues.append('SOURCE_MAP_NATIVE_OR_TRANSFORM_MISMATCH:'+q['id'])
                if not mat: issues.append('MATERIAL_PLAN_ROW_MISSING:'+q['id'])
                candidate = mat.get('assignment_action') == 'ASSIGN_NATIVE_BULK_MATERIAL' and positive(mat.get('density_kg_m3')) and not mat.get('conflict')
                rho = mat.get('density_kg_m3') if candidate else None
                physical = bool(source_ok and proof and proof['row']['assigned'])
                mass = proof['row']['candidate_geometry_mass_kg'] if physical else None
                estimate = jobs[key]['expected_volume_mm3']*rho*1e-9 if source_ok and candidate and key in jobs and positive(jobs[key].get('expected_volume_mm3')) else None
                gstatus = 'MISSING_OR_UNVERIFIED_NATIVE_FILE'; gcold = False; chain = False; greceipt = None
                if geom:
                    gstatus = geom['hash_link']; gcold = chain = True; greceipt = geom['receipt']['path']
                elif key in copyjobs and sha:
                    cp = copyjobs[key]
                    if audit.matches(cp['source'], cp['source_sha256']):
                        link = hash_link(sha, cp['source_sha256'], proof)
                        if link: gstatus = 'HISTORICAL_SOURCE_COPY_'+link; chain = True
                        elif proof: gstatus = 'SOURCE_COPY_AND_CURRENT_MATERIAL_COLD_READ; LEGACY_PREWRITE_HASH_NOT_RECORDED'
                        else: gstatus = 'NATIVE_COPY_HASH_CHANGED_WITHOUT_CURRENT_PROOF'
                elif sha: gstatus = 'NATIVE_EXISTS_COLD_SOURCE_PROOF_PENDING'
                for yes, no, value in [('source_verified', 'source_unverified', source_ok), ('native_present', 'native_missing', bool(sha)), ('material_candidate', 'material_unknown_or_composite', candidate), ('native_material_verified', 'native_material_not_verified', physical), ('native_geometry_hash_chain_verified', 'native_geometry_hash_chain_not_verified', chain)]: counts[yes if value else no] += 1
                rows.append(dict(state=state, instance_id=q['id'], parent_group=gid, quantity=1, expected_solid_count=q['expected_solids'], representation_role=q.get('representation_role'), integration_lineage=q.get('integration_lineage'),
                    source_status='HASH_AND_TRANSFORM_VERIFIED' if source_ok else 'UNVERIFIED', step_path=q['step_path'], step_sha256=q['source_sha256'], step_current_sha256=audit.sha(q['step_path']), T_S_local_mm_json=json.dumps(q['T_S_local'], separators=(',', ':')),
                    native_path=q['native_path'], native_file_exists=bool(sha), native_current_sha256=sha, native_geometry_status=gstatus, native_increment_geometry_cold_verified=gcold, native_geometry_hash_chain_verified=chain, native_geometry_receipt=greceipt,
                    candidate_material=mat.get('sw_material_name'), candidate_material_id=mat.get('material_id'), material_status=mat.get('status', 'MISSING_MATERIAL_PLAN_ROW'), candidate_density_kg_m3=rho,
                    native_material_cold_verified=physical, native_material_decision_cold_recorded=bool(proof), native_material_receipt=proof['receipt']['path'] if proof else None, native_material_receipt_sha256=proof['receipt']['sha256'] if proof else None,
                    candidate_uniform_geometry_mass_kg=mass, mass_basis='NATIVE_UNIFORM_CANDIDATE_COLD_READ_NOT_AS_BUILT' if physical else 'UNKNOWN_NO_SOFTWARE_DEFAULT_MASS_CREDIT', source_geometry_candidate_mass_kg=estimate,
                    source_geometry_mass_basis='SOURCE_VOLUME_X_EXPLICIT_UNIFORM_CANDIDATE_DENSITY_NOT_AS_BUILT' if estimate is not None else 'UNKNOWN', procurement_material_note=mat.get('procurement_material_note'), as_built_mass_kg=None, as_built_material_certified=False, whole_assembly_fit_verified=False))
        ids = [r['instance_id'] for r in rows]
        if len(rows) != s['leaf_count'] or len(set(ids)) != len(rows) or set(ids) != set(expected): issues.append('BOM_INSTANCE_SET_COUNT_OR_DUPLICATE_ERROR')
        tables[state] = rows; target = Path(s['path']); top_proof = None
        for p in sorted(results.glob(f'TOP_{state}*.json')):
            top = audit.read(p); why = []
            if top.get('status') != 'PASS_FIXED_POSE_NATIVE_MEMBERSHIP_TRANSFORMS_AND_LOCAL_REFERENCES': audit.reject(p, ['NON_SUCCESS_HISTORY_NOT_USED']); continue
            if not audit.matches(target, top.get('sha256')) or norm(top.get('path', '.')) != norm(target): why.append('CURRENT_TOP_SHA_OR_PATH_MISMATCH')
            if top.get('assembly_plan_sha256') != audit.sha(apath): why.append('TOP_PLAN_SHA_MISSING_OR_MISMATCH')
            if top.get('cold_open', {}).get('errors') != 0 or top.get('leaf_count') != len(expected) or top.get('external_geometry_dependencies') != 0: why.append('TOP_COLD_COUNT_OR_REFERENCES_NOT_VERIFIED')
            observed = top.get('components', []); observed_ids = [r.get('id') for r in observed]
            if len(observed_ids) != len(set(observed_ids)) or set(observed_ids) != set(expected): why.append('TOP_COMPONENT_SET_MISMATCH')
            else:
                for actual in observed:
                    q = expected[actual['id']]; values = actual.get('transform_sw16', [])
                    if norm(actual.get('native_path', '.')) != norm(q['native_path']) or len(values) != 16 or any(not close(a, b, 0, 1e-8) for a, b in zip(values, sw16(q['T_S_local']))): why.append('TOP_PATH_OR_TRANSFORM_MISMATCH:'+q['id'])
            if not all(gid in groupcold for gid in s['groups']): why.append('TOP_GROUP_COLD_PROOFS_INCOMPLETE')
            if why: audit.reject(p, why)
            else: top_proof = audit.ref(p)
        nstate = neutral.get('states', {}).get(state, {}); v = nstate.get('verify', {})
        neutral_ok = bool(neutral_source_ok and v.get('status') == 'NAMED_LEAF_COUNTS_AND_TRANSFORMS_REOPENED' and audit.matches(v.get('path'), v.get('sha256')) and v.get('leaf_instances') == len(expected) and v.get('solids') == s['expected_solids'] and v.get('names_exact_set_and_unique') is True and v.get('all_leaf_solid_counts_match_source_map') is True and close(v.get('max_absolute_T_entry_error'), 0, 0, 1e-7))
        status['states'][state] = dict(instances=len(rows), planned_instances=s['leaf_count'], expected_solids=s['expected_solids'], material_coverage=dict(counts),
            bom_status='SOURCE_BOUND_INSTANCE_BOM' if not issues and not audit.errors and counts['source_unverified'] == 0 else 'BOM_HAS_UNVERIFIED_INPUTS', issues=issues,
            native_assembly_path=str(target), native_assembly_exists=target.is_file(), native_assembly_current_sha256=audit.sha(target), native_assembly_receipt=top_proof,
            native_assembly_verification_status='CURRENT_FILE_PLAN_MEMBERSHIP_TRANSFORMS_AND_LOCAL_REFERENCES_COLD_VERIFIED' if top_proof else 'NOT_BUILT_OR_CURRENT_PROOF_INCOMPLETE',
            neutral_assembly=dict(current_file_named_leaf_counts_and_transforms_verified=neutral_ok, path=v.get('path') or nstate.get('build', {}).get('path'), sha256=v.get('sha256') or nstate.get('build', {}).get('sha256'), receipt_status=v.get('status', 'NOT_BUILT_OR_NOT_COLD_VERIFIED')),
            native_verified_uniform_candidate_subtotal_kg=sum(r['candidate_uniform_geometry_mass_kg'] for r in rows if r['candidate_uniform_geometry_mass_kg'] is not None), subtotal_scope='ONLY_EXPLICIT_UNIFORM_MATERIAL_COLD_VERIFIED_INSTANCES; NOT_WHOLE_SPACECRAFT_MASS', whole_mass_kg=None, whole_COM_mm=None, whole_inertia_kg_m2=None)
    used = {norm(q['native_path']) for g in source['groups'] for q in g['rows']}
    status['active_native_part_files'] = dict(planned_unique=len(used), present=sum(audit.sha(p) is not None for p in used), material_cold_read=sum(p in cold for p in used), bulk_material_assigned=sum(p in cold and cold[p]['row']['assigned'] for p in used))
    native_ok = all(s['native_assembly_receipt'] for s in status['states'].values()) and len(imported) == len(jobs)
    neutral_ok = all(s['neutral_assembly']['current_file_named_leaf_counts_and_transforms_verified'] for s in status['states'].values())
    material_scope_ok = all(p in cold for p in used)
    input_ok = not audit.errors and all(s['bom_status'] == 'SOURCE_BOUND_INSTANCE_BOM' for s in status['states'].values())
    status.update(artifact_build_status='SOURCE_BOUND_FIXED_POSE_ARTIFACTS_VERIFIED_ENGINEERING_OPEN' if native_ok and neutral_ok and input_ok and material_scope_ok else 'ARTIFACT_BUILD_OR_CURRENT_EVIDENCE_INCOMPLETE', native_fixed_pose_delivery_verified=bool(native_ok and input_ok), neutral_fixed_pose_delivery_verified=bool(neutral_ok and input_ok), all_active_material_decisions_cold_verified=material_scope_ok, history_policy='Failed/stale attempts are audit history; successful current-hash proofs determine active status.')
    report = dict(schema='INDEPENDENT_BOM_AUDIT_V1', generated_utc=status['generated_utc'], auditor_source=audit.ref(Path(__file__)), method='STDLIB_MANIFEST_HASH_AND_RECEIPT_AUDIT_NO_CAD_OR_COM',
        status='INPUT_AND_DERIVATION_CHECKS_PASS_BUILD_MAY_BE_INCOMPLETE' if input_ok else 'INPUT_OR_BOM_RECONCILIATION_HOLD', input_errors=audit.errors, state_issues={k: v['issues'] for k, v in status['states'].items()},
        accepted_increment_geometry_proofs=list(imported.values()), accepted_material_receipts=sorted({p['receipt']['path'] for p in cold.values()}), accepted_material_current_part_count=len(cold), accepted_group_count=len(groupcold), accepted_group_proofs=groupcold, rejected_or_historical_receipts=audit.rejected,
        rules=['Counts come from current plans and current-file proofs, never hard-coded completion.', 'Increment geometry hash advances only through explicit material before/after hashes.', 'Legacy material readback is credited; absent prewrite geometry hashes remain disclosed.', 'Unknown/composite and software-default mass never enter candidate physical mass.', 'Whole mass, COM and inertia remain UNKNOWN.', 'Fixed-pose membership does not grant fit, power, thermal, propulsion or flight release.'], snapshot_scope='Rerun after builders finish; in-progress receipts are not completion evidence.')
    return status, tables, report


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--audit-only', action='store_true'); args = parser.parse_args()
    status, tables, report = derive()
    if not args.audit_only:
        for state, rows in tables.items():
            dest = OUT/'docs'/f'BOM_{state.upper()}_{len(rows)}.csv'
            with dest.open('w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            status['states'][state].update(bom=str(dest), bom_sha256=Audit().sha(dest))
        write(OUT/'results/BUILD_STATUS.json', status)
    write(OUT/'results/INDEPENDENT_BOM_AUDIT.json', report)
    print(json.dumps(dict(artifact_build_status=status['artifact_build_status'], increment_native_parts=status['increment_native_parts'], material_readback_part_files=status['native_material_readback_part_files'], audit_status=report['status'], states={k: dict(instances=v['instances'], coverage=v['material_coverage'], native=v['native_assembly_verification_status'], neutral_verified=v['neutral_assembly']['current_file_named_leaf_counts_and_transforms_verified']) for k, v in status['states'].items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
