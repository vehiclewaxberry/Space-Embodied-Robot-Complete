"""Import SES into a temporary board; merge only allowed signal copper into fixed source."""
from pathlib import Path
import json,hashlib
import pcbnew as k
from erc_source_contract import parse,enc,children,val
A=Path(__file__).resolve().parents[1]
ALLOWED={'WP10_CHB_ENABLE','WP10_CHB_ENABLE_GATE','WP10_STARTUP_ADJ','WP10_STARTUP_BIAS',
 'WP10_STARTUP_INPUT_SENSE','WP10_HS_TIMER','WP10_STARTUP_PG_RECEIVER','WP10_HS_OVLO',
 'WP10_HS_POWER_LIMIT','WP10_HS_UVLO','WP10_HS_PGD'}
fixed=A/'ecad/wp10_main_input_v26_fixed.kicad_pcb';ses=A/'ecad/wp10_main_input_v26_signals.ses'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Freerouting 2.0.1 emits an empty, unquoted component identifier for the
# project's unnamed wire landings. Restore the DSN's quoted empty identifier.
t=ses.read_text(encoding='utf-8');assert t.count('(component \n')==1
normalized=A/'ecad/wp10_main_input_v26_signals_normalized.ses'
normalized.write_text(t.replace('(component \n','(component ""\n'),encoding='utf-8')
b=k.LoadBoard(str(fixed));assert k.ImportSpecctraSES(b,str(normalized))
raw=A/'ecad/wp10_main_input_v26_router_raw.kicad_pcb';k.SaveBoard(str(raw),b)
f=parse(fixed.read_text(encoding='utf-8'));r=parse(raw.read_text(encoding='utf-8'))
# Native KiCad 10 stores the net name directly in each copper item.
def net(n):
 x=children(n,'net')[0]
 return val(x[-1])
original=[v for v in f if isinstance(v,list) and v[0] in ['segment','via']]
assert not [n for n in original if net(n) in ALLOWED],'Fixed-copper assumptions changed'
added=[v for v in r if isinstance(v,list) and v[0] in ['segment','via'] and net(v) in ALLOWED]
assert added,'No allowed signal copper returned'
out=A/'ecad/wp10_main_input_v26_routed.kicad_pcb';out.write_text(enc(f+added)+'\n',encoding='utf-8')
record=dict(schema='WP10_V26_SIGNAL_ONLY_ROUTING_MERGE',fixed_PCB_sha256=sha(fixed),SES_sha256=sha(ses),raw_router_PCB_sha256=sha(raw),
 candidate_sha256=sha(out),fixed_copper_count=len(original),added_copper_count=len(added),allowed_nets=sorted(ALLOWED),
 footprints_imported_from_router=0,fixed_copper_mutated=False,DRC_passed=None)
(A/'results/MAIN_INPUT_SIGNAL_MERGE_V26.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
