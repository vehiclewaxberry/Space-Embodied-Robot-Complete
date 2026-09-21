"""Actual relocated KiCad exports; compare component identities and net partitions."""
from pathlib import Path
import os,json,hashlib,shutil,subprocess,xml.etree.ElementTree as ET
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1]; E=D/'ecad'; R=D/'ecad_relocation';R.mkdir(exist_ok=True)
rt=next(p/'70_tools/runtime_wp09_kicad/portable' for p in D.parents if (p/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe').exists())
names=['wp09_system.kicad_sch','wp09_stop_detail.kicad_sch','wp09_system.kicad_pro','WP09.kicad_sym','WP09STOP.kicad_sym','sym-lib-table']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
copied=[]
for name in names:
    shutil.copy2(E/name,R/name);assert sha(E/name)==sha(R/name)
    copied.append({'path':name,'sha256':sha(R/name)})
env=os.environ.copy();env['KICAD_CONFIG_HOME']=str(R/'runtime_config');env['KICAD10_SYMBOL_DIR']=str(rt/'share/kicad/symbols');env['KICAD10_FOOTPRINT_DIR']=str(rt/'share/kicad/footprints')
runs=[]
for args in [['sch','export','netlist','--format','kicadxml','-o','relocated.xml','wp09_system.kicad_sch'],['sch','erc','--format','json','--severity-all','--exit-code-violations','-o','relocated_erc.json','wp09_system.kicad_sch']]:
    p=subprocess.run([str(rt/'bin/kicad-cli.exe'),*args],cwd=R,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    runs.append({'args':args,'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
assert runs[0]['rc']==0,runs
def shape(p):
    x=ET.parse(p).getroot()
    parts={c.attrib['ref']:(c.findtext('value'),c.findtext('footprint')) for c in x.find('components')}
    nets=frozenset(frozenset((n.attrib['ref'],n.attrib['pin']) for n in net.findall('node')) for net in x.find('nets'))
    return parts,nets
old,new=shape(E/'exports/wp09_system.xml'),shape(R/'relocated.xml')
assert old==new and len(new[0])==99 and len(new[1])==97
def erc(p):
    j=json.loads(p.read_text(encoding='utf-8'));return sorted((v.get('severity',''),v.get('type',''),v.get('description','')) for s in j.get('sheets',[]) for v in s.get('violations',[]))
assert erc(E/'exports/wp09_system_erc.json')==erc(R/'relocated_erc.json')
result={'schema':'WP10_ACTUAL_ECAD_RELOCATION_V1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_NATIVE_ECAD_RELOCATED_IDENTITY_AND_CONNECTIVITY','copied_native_files':copied,'actual_components':99,'actual_net_partitions':97,'erc_diagnostics_retained':len(erc(R/'relocated_erc.json')),'erc_all_clear':False,'net_names_and_run_paths_not_identity':True,'hardware_io':0,'runs':runs}
(D/'results/ECAD_RELOCATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['runs','copied_native_files']},ensure_ascii=False))
