"""Explain remaining ERC source diagnostics without waivers or simulated energization."""
import json,csv,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1];E=D/'ecad'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=list(csv.DictReader((E/'MASTER_FROM_TO.csv').open(encoding='utf-8-sig')))
by={r['wire_id']:r for r in rows}
required={
 'A01':('PS1.TB2.4','Q1.1'),'A02':('Q1.2','K1.A2(+)'),
 'A03':('K1.A1(-)','U1.IN+'),'SC_PWR24':('Q1.2','STOPBOARD.J101.3'),
 'SC_RET':('PS1.TB2.1','STOPBOARD.J101.4')}
for k,p in required.items():assert (by[k]['from_endpoint'],by[k]['to_endpoint'])==p
erc=json.loads((E/'exports/wp09_system_erc.json').read_text(encoding='utf-8'))
items=[v for sh in erc['sheets'] for v in sh.get('violations',[])]
out={'schema':'WP10_ERC_DIAGNOSTIC_DISPOSITION_V1','status':'OPEN_DIAGNOSTICS_NO_WAIVER_NO_PWR_FLAG',
 'actual_violations':items,'count':len(items),'actual_master_row_bindings':{k:by[k] for k in required},
 'interpretations':[
 {'node':'U1.IN+ (top-level generated U23 IN+)','source_path':'PS1 -> Q1 -> K1 polarized main contacts -> U1',
  'meaning':'Switched contact output has no declared KiCad power-output driver in the abstract equipment symbol. The drawn path exists conditionally; this is not a voltage measurement, and main-contact operating/fault states require independent design verification.'},
 {'node':'U120 VIN (and shared U121 supply net)','source_path':'PS1 -> Q1 -> STOPBOARD J101.3 -> actual regulator VIN',
  'meaning':'Protected upstream source crosses the abstract breaker. New module power-input pin exposes the source-propagation diagnostic. It does not mean the regulator output is still only a placeholder, and it does not certify the upstream branch protection or transient envelope.'}],
 'count_is_not_required_function_coverage':True,'no_waiver_applied':True,'PWR_FLAG_added':False,
 'static_auxiliary_output_selection_does_not_close':['Q1 branch budget/protection coordination','connector and harness build dimensions','module output ripple and startup/transient guarantee','MCU and bus-health observation','complete PCB/thermal and hardware timing'],
 'sources':[{'path':str(p),'sha256':sha(p)} for p in [E/'MASTER_FROM_TO.csv',E/'exports/wp09_system_erc.json']],
 'hardware_voltage_or_current_measured':False,'electrical_design_complete':False}
(E/'ERC_DISPOSITION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print({'ERC_retained':len(items),'status':out['status']})

