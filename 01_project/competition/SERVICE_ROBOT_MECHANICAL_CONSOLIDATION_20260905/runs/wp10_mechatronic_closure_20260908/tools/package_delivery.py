"""Package deliverables, update the existing entry, and seal verified outputs."""
from pathlib import Path
import csv,json,hashlib,zipfile,re,sys,urllib.parse
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1];BASE=D.parents[1];C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
ROOT=next(p for p in D.parents if (p/'PROJECT_MAP.md').exists())
Z=D/'WP10_ENGINEERING_RESEARCH_INPUTS.zip';RESULTS=D/'results'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def selected(p):
    r=p.relative_to(D)
    return p.is_file() and not any(x in ['__pycache__','runtime_config','logs','.cache'] for x in r.parts) and p.suffix not in ['.pyc','.kicad_prl','.lck','.log'] and p.name not in ['WP10_ENGINEERING_RESEARCH_INPUTS.zip','OUTPUT_SHA256.csv','FINAL_INTEGRITY.json','PACKAGE_INTEGRITY.json','PREVIEW_SERVER.json','VIEW_CHECK.json']
def verify_rows(base,rows):
    for r in rows:
        p=Path(r['path']);p=p if p.is_absolute() else base/p
        assert p.is_file(),str(p)
        assert sha(p)==r['sha256'],str(p)
    return len(rows)
mode=sys.argv[1]
if mode=='entry':
    p=BASE/'CURRENT_candidate.md';backup=RESULTS/'CURRENT_ENTRY_BEFORE.md'
    if not backup.exists():backup.write_bytes(p.read_bytes())
    rel='runs/wp10_mechatronic_closure_20260908'
    head=f'''# 当前工程入口：WP10 机电补全与研究交接

2026-09-08：从[本轮交付说明]({rel}/README.md)与[统一查看页]({rel}/REVIEW.html)进入。修订系统原理图99器件/97网/72外部接线，停止子页76器件；三态873实例SI入口与材料模型惯性补充见本轮数据包。原生873叶SolidWorks三态包继承上一封存版本，本轮没有重建原生总装。

**完整可装配工程样机的全部机电设计尚未交付。** 仍有23项开放工作包，含高功率能源链、推进受控ICD、真实运动link物性和驱动、完整线束及热/强度/动态停止等。可以进入声明假设的模型/验证与理论研究准备，并由动力学载荷反向支持工程收束；本轮没有执行控制、强化学习或实物动作，旧科学PASS不转移到当前873构型。

本轮[机器判定]({rel}/results/DELIVERY_DECISION.json)和[研究来源审计]({rel}/research_intake/RESEARCH_READINESS.md)分别记录工程缺口与107条历史原始SHA中的29条漂移；不改写旧Gate结论。

下方历次入口原样保留，其中“当前/本轮”均属于记录时刻。

---

'''
    p.write_bytes(head.encode('utf-8')+backup.read_bytes())
    assert p.read_bytes().endswith(backup.read_bytes())
    write(RESULTS/'CURRENT_ENTRY_UPDATE.json',{'status':'PASS_EXISTING_ENTRY_UPDATED_HISTORY_PRESERVED','path':str(p),'sha256':sha(p),'history_bytes':backup.stat().st_size,'history_sha256':sha(backup)})
    print('existing entry updated with byte-preserved history')
elif mode=='package':
    files=sorted(p for p in D.rglob('*') if selected(p))
    assert (D/'README.md') in files and (D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json') in files
    manifest=[{'path':p.relative_to(D).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    with zipfile.ZipFile(Z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(D).as_posix())
        z.writestr('PACKAGE_CONTENTS_SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(Z) as z:
        assert z.testzip() is None
        for r in manifest:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256'],r['path']
    write(RESULTS/'PACKAGE_INTEGRITY.json',{'status':'PASS_ZIP_CRC_AND_EACH_ENTRY_SHA256','utc':datetime.now(timezone.utc).isoformat(),'path':str(Z),'sha256':sha(Z),'bytes':Z.stat().st_size,'source_file_count':len(files),'zip_entries':len(files)+1,'all_generation_scripts_standalone':False,'native_CAD_parent_pack_duplicated':False,'exclusions':'volatile runtime/log/cache, archive self, archive/final/view receipts; package contents manifest is embedded'})
    print(json.dumps({'zip_entries':len(files)+1,'zip_bytes':Z.stat().st_size,'sha256':sha(Z)}))
elif mode=='seal':
    decision=read(RESULTS/'DELIVERY_DECISION.json');assert not decision['complete_mechatronic_design_deliverable']
    checks={}
    checks['decision_evidence']=verify_rows(D,decision['evidence'])
    checks['parent_files']=verify_rows(C,list(csv.DictReader((C/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig'))))
    checks['electrical_final_bound_files']=verify_rows(D/'electrical',read(D/'electrical/results/STOP_SUPPLY_FINAL_BINDING.json')['files'])
    checks['sealed_mechanical_intake_files']=verify_rows(D/'mechanical_intake',list(csv.DictReader((D/'mechanical_intake/SHA256.csv').open(encoding='utf-8-sig'))))
    checks['sealed_material_inertia_files']=verify_rows(D/'mechanical_inertia',list(csv.DictReader((D/'mechanical_inertia/SHA256.csv').open(encoding='utf-8-sig'))))
    checks['research_source_bindings']=verify_rows(ROOT,read(D/'research_intake/SOURCE_BINDINGS.json')['files'])
    package=read(RESULTS/'PACKAGE_INTEGRITY.json');assert sha(Z)==package['sha256']
    with zipfile.ZipFile(Z) as z:
        assert z.testzip() is None
        entries=json.loads(z.read('PACKAGE_CONTENTS_SHA256.json'))
        checks['package_sources_unchanged']=verify_rows(D,entries)
    entry=read(RESULTS/'CURRENT_ENTRY_UPDATE.json');assert sha(Path(entry['path']))==entry['sha256']
    links=[]
    for p in [D/'README.md',D/'REVIEW.html',D/'ecad/README.md',D/'ENGINEERING_RESEARCH_LOOP_ZH.md']:
        t=p.read_text(encoding='utf-8')
        targets=re.findall(r'href="([^"]+)"',t) if p.suffix=='.html' else re.findall(r'\]\(([^)]+)\)',t)
        for target in targets:
            target=urllib.parse.unquote(target.strip('<>')).split('#')[0]
            if not target or target.startswith(('https://','http://','mailto:')):continue
            q=(p.parent/target).resolve()
            # The final receipt is created below; all other links must already resolve.
            assert q.is_file() or q==RESULTS/'FINAL_INTEGRITY.json',(str(p),target)
            links.append({'source':p.relative_to(D).as_posix(),'target':target})
    files=sorted(p for p in D.rglob('*') if (selected(p) or p==Z or p in [RESULTS/'PACKAGE_INTEGRITY.json',RESULTS/'VIEW_CHECK.json']) and p.is_file())
    rows=[{'path':p.relative_to(D).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    manifest=RESULTS/'OUTPUT_SHA256.csv'
    with manifest.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
    checks['final_files']=verify_rows(D,rows)
    write(RESULTS/'FINAL_INTEGRITY.json',{'schema':'WP10_FINAL_FILE_INTEGRITY_V1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_FILES_LINKS_PACKAGE_AND_SEALED_PARENT_PRESERVATION__NO_FULL_DESIGN_RELEASE','checks':checks,'local_links_checked':len(links),'links':links,'parent_mutations':0,'output_manifest':str(manifest),'output_manifest_sha256':sha(manifest),'package_sha256':sha(Z),'full_mechatronic_design_complete':False,'hardware_io':0,'integrity_is_not_engineering_acceptance':True,'volatile_runtime_logs_and_final_receipt_self_excluded':True})
    print(json.dumps({'status':'PASS_FINAL_INTEGRITY','checks':checks,'links':len(links)},ensure_ascii=False))
else:raise ValueError(mode)
