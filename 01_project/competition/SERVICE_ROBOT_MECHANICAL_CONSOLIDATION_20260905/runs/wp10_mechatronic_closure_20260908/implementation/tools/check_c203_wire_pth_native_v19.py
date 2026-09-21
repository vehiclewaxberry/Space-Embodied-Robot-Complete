"""Accept only the actual two-hole delta, while preserving remaining CAP errors."""
from pathlib import Path
import json,hashlib,collections
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
source=read('results/C203_WIRE_PTH_SOURCE_CHECK_V19.json')
assert source['passed'] and all(sha(p)==h for p,h in source['inputs'].items())
g=read('results/CAP_TERMINAL_NATIVE_GEOMETRY.json');s=read('results/CAP_TERMINAL_STACKUP.json');b=read('results/CAP_TERMINAL_NATIVE_BINDING.json')
assert g['board_sha256']==s['native_board_sha256']==b['board_sha256']==sha('ecad/wp10_c203_terminal.kicad_pcb')
assert g['extractor_sha256']==sha('tools/cap_terminal_native.py') and b['physical_holes_plated']==2 and b['physical_holes_nonplated']==6
cu=read('results/CAP_TERMINAL_COPPER_AUDIT.json')
assert cu['passed'] and cu['schema']=='WP10_C203_PHYSICAL_COPPER_AUDIT_V19_WIRE_PTH'
assert all(sha(p)==h for p,h in cu['inputs'].items()) and len(cu['fault_injections'])==5 and all(f['rejected'] for f in cu['fault_injections'])
exec_record=read('results/C203_WIRE_PTH_DRC_EXECUTION_V19.json');assert exec_record['native_DRC_executed'] and all(sha(p)==h for p,h in exec_record['inputs'].items())
drc=read('results/CAP_TERMINAL_DRC_NATIVE_V19.json');old=read('results/CAP_TERMINAL_DRC_NATIVE_V17.json')
assert drc['ignored_checks']==old['ignored_checks'] and not drc['unconnected_items']
assert drc['source']=='wp10_c203_terminal.kicad_pcb' and set(drc['included_severities'])>=set(old['included_severities'])
errors=drc['violations'];assert len(errors)==6 and collections.Counter(v['type'] for v in errors)=={'hole_clearance':4,'solder_mask_bridge':2}
assert all(v['severity']=='error' and any('NPTH' in item['description'] and (item['pos']['x'],item['pos']['y']) in [(95,100),(105,100)] for item in v['items']) for v in errors)
paths=['results/C203_WIRE_PTH_SOURCE_CHECK_V19.json','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_TERMINAL_STACKUP.json','results/CAP_TERMINAL_NATIVE_BINDING.json','results/CAP_TERMINAL_COPPER_AUDIT.json','results/C203_WIRE_PTH_DRC_EXECUTION_V19.json','results/CAP_TERMINAL_DRC_NATIVE_V19.json','ecad/wp10_c203_terminal.kicad_pcb','power/CAP_TERMINAL_DEFINITION.json','tools/check_c203_wire_pth_native_v19.py']
result=dict(passed=True,native_readback_executed=True,native_DRC_executed=True,PTH_wire_holes=2,NPTH_holes=6,rules_unchanged=True,remaining_DRC_errors=6,remaining_error_scope='Two under-body CAP NPTH plus rear-land groups only',whole_PCB_DRC_clean=False,whole_design_complete=False,inputs={p:sha(p) for p in paths})
(A/'results/C203_WIRE_PTH_NATIVE_CHECK_V19.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,remaining_DRC_errors=6,whole_PCB_DRC_clean=False)))
