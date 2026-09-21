"""Preserve an observed scheduling deviation and scope its serial rerun."""
from pathlib import Path
import json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
paths=['logs/native_delta_cap19_surface_exact_p01_a1.run.json','logs/native_delta_cap19_surface_assembly_p01_a1.run.json']
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
runs=[json.loads((A/p).read_text()) for p in paths]
intervals=[(datetime.datetime.fromisoformat(r['started_local']).timestamp(),datetime.datetime.fromisoformat(r['started_local']).timestamp()+r['elapsed_s']) for r in runs]
overlap=max(0,min(t[1] for t in intervals)-max(t[0] for t in intervals));assert overlap>0
out=dict(status='OBSERVED_SERIAL_POLICY_DEVIATION__RERUN_REQUIRED',overlap_seconds=overlap,original_runs={p:sha(p) for p in paths},
 actual_original_commands_completed=all(r['status']=='COMPLETED' and r['returncode']==0 for r in runs),native_results_fabricated=False,
 no_unknown_process_terminated=True,original_pair_accepted_as_serial_evidence=False,correction='Use workspace mutex plus legacy-native-guard precheck, then rerun exact and assembly serially.',
 required_serial_receipts=['logs/CAP19_SERIAL_surface_exact_p02.json','logs/CAP19_SERIAL_surface_assembly_p02.json'],whole_design_complete=False)
(A/'results/C203_NATIVE_SERIAL_CORRECTION_V19.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(overlap_seconds=overlap,original_serial_credit=False)))
