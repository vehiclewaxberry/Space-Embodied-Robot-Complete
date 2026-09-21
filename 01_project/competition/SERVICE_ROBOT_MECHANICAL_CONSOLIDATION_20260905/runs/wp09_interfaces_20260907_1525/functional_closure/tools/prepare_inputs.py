from pathlib import Path
import json,hashlib,shutil,requests
F=Path(__file__).resolve().parents[1];R=F.parent;B=R.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
parent_files=['results/DELIVERY_STATUS.json','results/NATIVE_BINDING_MANIFEST.json','results/INTEGRATION_MANIFEST_V6.json','inputs/INTEGRATION_HARNESS_CONTRACT_V6.json','results/EMISSION_V6.json','results/CLOSURE_ISSUE_LEDGER.json','results/OUTPUT_SHA256.csv']
write(F/'inputs/PARENT_BINDING.json',{'scope':'WP09 V6 bounded functional child; no parent assets overwritten','parent':str(R),'sources':{str(R/p):sha(R/p) for p in parent_files},'owner_choice':'2026-09-07: use official Seeed reBot-DevArm public DM electrical parts; not a shipment serial binding','physical_execution':False})
for p in ['run_guard.py','win_job.py']:shutil.copyfile(R/p,F/p)
for p in ['From-To.csv','DM_SELECTED_FROM_TO.csv','PROP_PWR_PREFAB_CHECKLIST.csv','PROP_DATA_PREFAB_CHECKLIST.csv']:shutil.copyfile(R/'ecad'/p,F/'ecad'/p)
src=B/'wp09_electro_propulsion_20260907_1350/inputs/electrical_sources'
out=F/'inputs/vendor_sources';out.mkdir(exist_ok=True)
for p in src.glob('*.pdf'):shutil.copyfile(p,out/p.name)
docs={'DM_J4310_20231116.pdf':'https://files.seeedstudio.com/products/Damiao/DM-J4310-en.pdf','RSP_500_20250926.pdf':'https://www.meanwell.com/Upload/PDF/RSP-500/RSP-500-SPEC.PDF'}
tree=json.loads((F/'research/rebot_repo_tree.json').read_text());commit=tree['sha']
for n,p in [('DM_PUBLIC_BOM.md','hardware/reBot_B601_DM/readme.md'),('DM_PUBLIC_BOM_ZH.md','hardware/reBot_B601_DM/readme_zh.md'),('DM_PERFORMANCE.md','hardware/reBot_B601_DM/performance_testing/Performance_Testing.md')]:docs[n]='https://raw.githubusercontent.com/Seeed-Projects/reBot-DevArm/'+commit+'/'+requests.utils.quote(p,safe='/')
records=[]
for n,u in docs.items():
 p=out/n
 if not p.exists():
  r=requests.get(u,timeout=45,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status();p.write_bytes(r.content)
 records.append({'file':str(p),'url':u,'sha256':sha(p)})
write(F/'research/ELECTRICAL_DOWNLOADS.json',{'repo_commit':commit,'sources':records})
from pypdf import PdfReader
for p in out.glob('*.pdf'):
 d=PdfReader(p);(out/(p.stem+'.txt')).write_text('\n'.join('PDF PAGE '+str(i+1)+'\n'+x.extract_text() for i,x in enumerate(d.pages)),encoding='utf-8')
print('Prepared',len(records),'downloads and parent binding')
