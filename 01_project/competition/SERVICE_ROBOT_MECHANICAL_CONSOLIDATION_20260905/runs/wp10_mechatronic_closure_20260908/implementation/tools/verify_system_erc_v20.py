"""Fresh native ERC of the active hierarchy; no source export or schematic mutation."""
from pathlib import Path
import json,sys,subprocess
from c203_cam_contract_v20 import A,read,sha
from erc_source_contract import source_inventory
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file());CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def main():
 source=A/'ecad/wp10_system.kicad_sch';_,sheets,_=source_inventory(source)
 paths=[p.relative_to(A).as_posix() for p in sheets]+['ecad/wp10_system.kicad_pro','ecad/wp10_system.xml','tools/verify_system_erc_v20.py']
 before={p:sha(p) for p in paths};target='results/SYSTEM_ERC_NATIVE_V20.json'
 command=[str(CLI),'sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(A/target),str(source)]
 q=subprocess.run(command,cwd=A,capture_output=True,text=True,encoding='utf-8');assert q.returncode in [0,5],q.stderr
 assert before=={p:sha(p) for p in paths}
 report=read(target);v=[r for s in report['sheets'] for r in s['violations']]
 assert len(sheets)==len(report['sheets'])==12
 assert report['source']==source.name and {'error','warning'}<=set(report['included_severities'])
 assert report['ignored_checks']==read('results/POWER_LOOP_ERC.json')['ignored_checks']
 out=dict(passed=q.returncode==0 and not v,command=command,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr,errors=sum(r['severity']=='error' for r in v),warnings=sum(r['severity']=='warning' for r in v),pages=12,ignored_checks_unchanged=True,inputs={**before,target:sha(target)},whole_design_complete=False)
 (A/'results/SYSTEM_ERC_CHECK_V20.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(passed=out['passed'],errors=out['errors'],warnings=out['warnings'])));assert out['passed']
if __name__=='__main__':main()
