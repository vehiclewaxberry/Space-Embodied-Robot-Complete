"""Read-only source collection for the pre-mode-switch audit. No project code imported."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path('F:/China Graduate Future Flight Vehicle Innovation Competition')
OUT = ROOT / '01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905'
BASE = '20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2'
ODR = BASE + '/_work/odr'
MODE = BASE + '/_work/mode_a_native_design_r1'
F4 = '20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1'
SIM = '30_simulation/sim_13_physics_gated_embodied_grasping'
AD = BASE + '/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json'
sources = [
 'PROJECT_MAP.md',
 '10_research/knowledge_base/spacecraft_mechanical_design/README.md',
 '.codex/agents/spacecraft-mechanical-design-agent.md',
 '01_project/current/PROJECT_CURRENT_AUTHORITY_V1.yaml',
 '01_project/competition/CURRENT_R2_AUTHORITY_INDEX.json',
 '01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json',
 '01_project/competition/CURRENT_R2_GAP_AND_CRITICAL_PATH_V7.md',
 BASE + '/00_RELEASE_GATE.json',
 BASE + '/17_MECH_TO_EMBODIED_HANDOFF_GATE.json',
 BASE + '/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml',
 MODE + '/00_authority/A3_00_INPUT_AUTHORITY.json',
 MODE + '/04_a3_2d/A3_2D_FINAL_GATE.json',
 F4 + '/00_charter/CHARTER.md',
 F4 + '/00_charter/ODR_F4R1_01_SIGNED.md',
 F4 + '/00_charter/ODR_F4R1_02_SIGNED.md',
 '20_engineering/F5R2_TERMINAL_CLOSURE_V1/00_frontier/CURRENT_FRONTIER_FABLE5_V1.json',
 ODR + '/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json',
 ODR + '/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_BINDING_READINESS_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/results/M01_SYSTEM_PAIR_ORACLE_BACKEND_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json',
 ODR + '/ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json',
 BASE + '/_work/current_r2_mechanical_dynamics_control_increment_v3/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V3.json',
 SIM + '/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json',
 AD,
 '30_simulation/sim_13_viability_extension_r1/00_authority/SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json',
 '30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json',
 SIM + '/v4_synthetic_contact_capture_diagnostic/phase_b4g_post_freeze_synthetic_jaw_retraction_execution/results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json',
 SIM + '/v4_synthetic_contact_capture_diagnostic/phase_b4g_post_freeze_synthetic_jaw_retraction_execution/results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json',
 'C:/Users/stude/.codex/attachments/0cd497c9-fcae-4714-997d-859171b88dc2/pasted-text.txt',
]
for rel in ['30_simulation/r2_dynamics_engineering_closure', '30_simulation/r2_control_engineering_closure']:
    sources.extend(str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / rel).rglob('*GATE*.json'))
paths = sorted(set((ROOT / p).resolve() for p in sources), key=lambda p: str(p).lower())
records = []
key_re = re.compile(r'verdict|scope|authority|generated|reissue|supersed|score|next_stage|release_credit|operational|path_search|pair_queries|signoff_evidence|owner_decision', re.I)
for p in paths:
    raw = p.read_bytes()
    content = raw.decode('utf-8-sig')
    record = {
        'path': p.as_posix(), 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest().upper(),
        'file_mtime_note': 'Filesystem timestamps are not used as authorization or chronology proof.',
        'line_extracts': [{'line': i, 'text': line} for i, line in enumerate(content.splitlines(), 1)
                          if key_re.search(line) and len(line) < 2500],
    }
    if p.suffix.lower() == '.json':
        data = json.loads(content)
        record['top_level_scalar_fields'] = {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    records.append(record)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'authority_sources.txt').write_text(''.join(p.as_posix() + '\n' for p in paths), encoding='utf-8')
(OUT / 'authority_source_extract.json').write_text(json.dumps({
    'scope': 'READ_ONLY_SOURCE_HASH_AND_TEXT_EXTRACTION__NO_GATE_REEVALUATION',
    'audit_date': '2026-09-05', 'source_count': len(records), 'sources': records,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'source_count': len(records), 'missing_sources': 0, 'output': str(OUT)}, ensure_ascii=False))
