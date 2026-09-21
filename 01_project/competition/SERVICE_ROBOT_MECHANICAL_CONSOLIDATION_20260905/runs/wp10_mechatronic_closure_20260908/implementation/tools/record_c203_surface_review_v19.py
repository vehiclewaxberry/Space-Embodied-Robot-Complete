"""Write review records from actual reviewer messages; no retroactive result credit."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
reviewed={
 'tools/c203_surface_generation_contract_v19.py':'810673458b724f7a57c8c251e6b48497c009d09363c03f4bbfd820b3e948a1ff',
 'tools/generate_c203_surface_v19.py':'428b1e65032c659d848015d87b8318c93af05a8318a6e1e118987fd00d7ed99d',
 'tools/prepare_cap_harness_plan_v19.py':'18b0d7df9de78cc767f2930c1b49d033ca69b1626ee4e173bdc6c39163565ed6',
 'tools/check_c203_regeneration_contract_v19.py':'ecd2e84e56c24c2233ef234b7e73a90be70798d341d8bbca5142c303ac6029a1',
 'results/C203_REGENERATION_CONTRACT_TEST_V19.json':'2d3add57cfc08ad6fb6e7a3c115f3e4275746ae8524df3530dbcf85afb7922e1'}
assert all(hashlib.sha256((A/p).read_bytes()).hexdigest()==h for p,h in reviewed.items())
r=dict(status='PASS_SCOPED_GENERATION_RECEIPT_BINDING',reviewer='/root/cap_terminal_review',reviewed_files=reviewed,independent_counterexamples_rejected=17,
 actual_CAD_reviewed=False,live_plan_reviewed=False,prior_F1_F4_repair='Reviewer independently confirmed original seven bypasses rejected and outside-board query None, on the earlier source snapshot; later stage-aware state checks require their own current evidence.',
 scope='Full commands, guard identity/PID/time/cwd, Windows constraints, source hash and completed guard hash binding only. Root recorded the received independent review; not a native run.',
 whole_design_complete=False)
(A/'results/C203_SURFACE_READONLY_REVIEW_V19.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('Recorded actual scoped independent review; no native geometry or whole-system credit')
