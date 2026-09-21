"""Bind the returned independent review to the bytes actually reviewed."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
files={
 'tools/cap_harness_heat_v19.py':'976772f8d00d69390a40711d9189f21f5fa112189e4d54b047bb646acd4c4744',
 'power/CAP_HARNESS_ELECTROTHERMAL_V19.json':'881cf56469fe0337febee4db1e27ad028c7d8112af5d86eb8fb1892a9da1e698',
 'thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv':'3d3b23cddb71834be33eb66641cbd94be7dd2ef3dabdd5a621d19b25b9333993',
 'thermal/ACTIVE_HEAT_LOADS_V19.json':'112904048cfc0bfbfd66377e5b2410c3c29e9523c773fee9443ce8142811e142'}
assert all(hashlib.sha256((A/p).read_bytes()).hexdigest()==h for p,h in files.items())
result=dict(status='PASS_SCOPED_FIXED_LEAKAGE_REALLOCATION',reviewer='/root/cap_terminal_review',reviewed_files=files,
 actual_scope='Read-only source, 384 reproduced scalar states, 1152 correlated R scenarios and fault injection; no CAD or temperature qualification.',
 source_faults_rejected=10,independent_extra_faults_rejected=['mm_to_m_error_with_conserved_total_heat','transfer_between_unrelated_nodes','wrong_case','wrong_mechanical_heat_sink'],
 maximum_local_allocation_residual_W=9.27e-18,maximum_source_scalar_difference=0,unchanged_noncapacitor_parent_rows=3648,
 rebind_review='Following actual outboard PTH edit, independent reviewer confirmed only3 input hashes changed, heat CSV byte-identical, all states and unknowns preserved.',geometry_reviewed=False,actual_temperature_qualified=False,whole_thermal_verified=False,whole_design_complete=False)
(A/'results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(status=result['status'],reviewed_files=len(files))))
