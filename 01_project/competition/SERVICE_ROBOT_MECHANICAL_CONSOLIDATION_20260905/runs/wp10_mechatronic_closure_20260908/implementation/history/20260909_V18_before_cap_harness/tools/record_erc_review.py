"""Record completed independent read-only review against literal reviewer hashes."""
from pathlib import Path
import hashlib,json
A=Path(__file__).resolve().parents[1]
expected=json.loads((A/'results/ERC_REVIEW_EXPECTED_SHA.json').read_text())
bad=[q for q,h in expected.items() if hashlib.sha256((A/q).read_bytes()).hexdigest()!=h]
assert not bad,bad
r=dict(schema='WP10_ERC_READONLY_REVIEW_V16',reviewer='/root/erc_power_review',agent_type='hardware-reviewer',recorded_by='root from final read-only reviewer messages',review_complete=True,reviewed_files=expected,unrepaired_findings=[],scope='V16 conditional ERC declaration design, source/regression guard fixes, same-version MCP evidence and V15 numeric/geometry equivalence only',
 areas={k:'PASS_WITHIN_ERC_REVISION_SCOPE' for k in ['Completeness','Risk Identification','Implementability','Cost Reasonableness','Validation Coverage']},
 repaired_findings=['Blanket XML-only flag detection replaced with native source whitelist','Successful empty/wrong-source/missing-sheet/wrong-severity ERC reports rejected','Fuse checker requires fresh source-audit inputs','No dynamic/whole-design credit flags locked false','MCP record now bound to 15 current files'],
 independent_checks=dict(entities_unchanged=201,pin_network_type_nodes_unchanged=657,existing_subsheets_byte_identical=10,conditional_BFS_states=256,BFS_mismatches=0,source_checks=53,connectivity_checks=436,regression_tests=16,MCP_bound_files=15,numeric_and_geometry_current_bindings_checked=39,shared_battery_cases_identical=192,heat_rows_byte_identical=4032),
 inherited_scope='V15 declared nominal geometry/static conditions and retained counterexamples only; no new physical qualification',
 remaining_engineering_issues=['Battery OEM cavities and Sys Detect','C203-to-CHB PCB and conductor termination','Fuse/BMS/MOSFET/wire coordination','STOP and regen dynamics and heat','PMM charging and propulsion ICD'],
 physical_tests_executed=False,whole_design_complete=False)
(A/'results/ERC_READONLY_REVIEW.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'reviewed_files':len(expected),'unrepaired_ERC_findings':0,'whole_design_complete':False}))
