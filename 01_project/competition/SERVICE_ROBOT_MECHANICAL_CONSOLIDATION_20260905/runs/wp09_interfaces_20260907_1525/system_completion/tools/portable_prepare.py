"""Prepare deterministic portable native-copy mapping, never change sealed parents."""
from pathlib import Path
import json,hashlib,shutil
C=Path(__file__).resolve().parents[1];N=C.parent/'reuse_closure'
P=C/'mechanical/portable';P.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
states={};parts={};pins={}
for state,name in [('service','NATIVE_SERVICE_RECOVERY_V2.json'),('parking','NATIVE_PARKING.json'),('released','NATIVE_RELEASED.json')]:
 p=N/'results'/name;j=json.loads(p.read_text(encoding='utf-8-sig'))
 assert j['status']=='PASS_FIXED_NATIVE_DELTA_WITH_HASH_BOUND_PARENT' and j['component_count']==705
 assembly=Path(j['native_save']['path']);assert sha(assembly)==j['native_save']['sha256']
 pins[str(p)]=sha(p);pins[str(assembly)]=sha(assembly)
 old={r['id']:r for r in j['rows']};rows=[]
 for observed in j['cold_components']:
  source=Path(observed['path']);digest=sha(source);assert digest==observed['sha256']
  key=str(source.resolve()).casefold()
  if key not in parts:
   parts[key]={'source':str(source),'source_sha256':digest,'copy_name':'P_'+digest[:20]+'.SLDPRT','bytes':source.stat().st_size}
  t=observed['transform_sw16'];assert len(t)==16
  T=[[t[3*k+i] for k in range(3)]+[t[9+i]*1000] for i in range(3)]+[[0,0,0,1]]
  rows.append({'id':observed['id'],'source':str(source),'source_sha256':digest,'copy_name':parts[key]['copy_name'],
               'transform_sw16':t,'native_T_local_to_S':T,'fixed':observed['fixed'],
               'expected_solids':old[observed['id']].get('expected_solids',1),
               'representation_role':old[observed['id']].get('representation_role')})
 assert len(rows)==705 and sum(r['expected_solids'] for r in rows)==1086
 states[state]={'source_assembly':str(assembly),'source_assembly_sha256':sha(assembly),
                'source_receipt':str(p),'source_receipt_sha256':sha(p),'target_name':'WP09_'+state.upper()+'.SLDASM','rows':rows}
byname={}
for p in parts.values():
 assert p['copy_name'] not in byname or byname[p['copy_name']]==p['source_sha256']
 byname[p['copy_name']]=p['source_sha256']
guard=(N/'run_guard.py').read_text(encoding='utf-8')
guard=guard.replace('from win_job import OwnedJob','from portable_win_job import OwnedJob').replace('R=Path(__file__).resolve().parent','R=Path(__file__).resolve().parents[1]')
(C/'tools/portable_guard.py').write_text(guard,encoding='utf-8')
shutil.copy2(N/'win_job.py',C/'tools/portable_win_job.py')
result={'status':'SOURCE_NATIVE_HASHES_VERIFIED','states':states,'parts':list(parts.values()),'unique_source_paths':len(parts),
 'unique_native_hashes':len(byname),'input_sha256':pins,'copy_root':str(P/'package'),
 'method_candidate':'ISldWorks.CopyDocument explicit FromChildren/ToChildren; controlled native copies, not geometry regeneration',
 'body_count_credit':'1081 inherited parent solids + 5 previously cold-read port solids; this task does not remeasure solids',
 'reference_docs':['https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~copydocument.html',
                   'https://help.solidworks.com/2025/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swMoveCopyOptions_e.html']}
(C/'results').mkdir(exist_ok=True);(C/'logs').mkdir(exist_ok=True)
(C/'results/PORTABLE_INPUTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'states':len(states),'source_paths':len(parts),'unique_native_hashes':len(byname),'bytes':sum(p['bytes'] for p in parts.values())}))
