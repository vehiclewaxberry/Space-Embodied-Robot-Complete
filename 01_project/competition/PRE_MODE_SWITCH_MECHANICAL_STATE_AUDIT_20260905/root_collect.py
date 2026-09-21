"""Read-only source collection; all writes restricted to this audit directory."""
from pathlib import Path
import csv, json, hashlib, subprocess, sys, datetime, importlib.util, importlib.metadata
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REF = Path('F:/SPACE_ROBOTICS_REFERENCE_LIBRARY')
R2 = ROOT/'20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2'
def dump(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest().upper()
def record(path):
    try:
        s=path.stat()
        return dict(path=str(path), bytes=s.st_size, mtime_ns=s.st_mtime_ns, sha256=digest(path), exists=True)
    except OSError as e: return dict(path=str(path), exists=False, error=str(e))
def csvout(name, rows):
    if not rows: return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def command(args,cwd=ROOT):
    p=subprocess.run(args,cwd=cwd,capture_output=True,encoding='utf-8',errors='replace')
    return dict(args=args,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)

mode=sys.argv[1]
if mode in ['snapshot','inventory']:
    protected=set(p for p in R2.iterdir() if p.is_file())
    for rel in ['20_engineering/config/geometry','20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1']:
        protected.update(p for p in (ROOT/rel).rglob('*') if p.is_file() and '__pycache__' not in str(p))
    protected.add(ROOT/'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf')
    rows=[record(p) for p in sorted(protected)]
    if mode=='snapshot': csvout('root_protected_before.csv',rows)
    git=command(['git','-c','core.quotepath=false','status','--porcelain=v1','--untracked-files=normal'])
    git['head']=command(['git','rev-parse','HEAD'])['stdout'].strip()
    git['branch']=command(['git','branch','--show-current'])['stdout'].strip()
    git['time_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if mode=='snapshot': dump('root_workspace_before.json',git)
    inventory=[]; coverage=[]
    for root in [ROOT,REF]:
        found=command(['rg','--files','--hidden','--no-ignore','-g','!.git/**','-g','!**/.git/**','-g','!**/__pycache__/**'],root)
        files=found['stdout'].splitlines(); errors=[];size=0;count=0
        for rel in files:
            p=root/rel
            if OUT==p or OUT in p.parents: continue
            try:
                s=p.stat();size+=s.st_size;count+=1
                inventory.append(dict(root=str(root),path=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,extension=p.suffix.lower()))
            except OSError as e:errors.append(dict(path=str(p),error=str(e)))
        coverage.append(dict(root=str(root),files=count,bytes=size,rg_exit_code=found['exit_code'],rg_errors=found['stderr'],stat_errors=errors,scope='rg no-ignore and hidden enabled; .git and pycache excluded; audit output excluded; metadata inventory only, not whole-disk forensic scan'))
    csvout('root_file_inventory.csv',inventory);dump('root_inventory_coverage.json',coverage)
    print(json.dumps(dict(protected=len(rows),roots=coverage),ensure_ascii=False))
elif mode=='capability':
    modules={}
    for m in ['yaml','vtk','fcl','OCP','numpy','trimesh','scipy']:
        spec=importlib.util.find_spec(m); modules[m]=dict(found=spec is not None,origin=spec.origin if spec else None)
    versions={}
    for d in ['vtk','cadquery-ocp','trimesh','numpy','scipy']:
        try: versions[d]=importlib.metadata.version(d)
        except importlib.metadata.PackageNotFoundError:versions[d]=None
    probe={}
    try:
        from vtkmodules.vtkFiltersModeling import vtkCollisionDetectionFilter
        from vtkmodules.vtkCommonCore import vtkVersion
        probe=dict(import_success=True,vtk_version=vtkVersion.GetVTKVersion(),class_name=vtkCollisionDetectionFilter.__name__,instantiation=False,query_executed=False)
    except Exception as e:probe=dict(import_success=False,error=repr(e))
    dump('root_collision_capability.json',dict(executable=sys.executable,python=sys.version,modules=modules,versions=versions,probe=probe,scope='Import capability only; no CAD inputs, no collision query, no qualification PASS'))
    print(json.dumps(probe))
elif mode=='mass':
    import yaml
    sources=[]; refs=[]
    for filename in ['07_SYSTEM_MASS_PROPERTIES.yaml','05_ACCEPTED_B601_URDF_REF.yaml']:
        p=R2/filename;sources.append(p); data=yaml.safe_load(p.read_text(encoding='utf-8-sig'))
        for k,v in data.items():
            if isinstance(v,dict) and 'path' in v:
                q=ROOT/v['path'];sources.append(q);rr=record(q)
                rr.update(role=k,expected_sha256=v.get('sha256'),hash_match=rr.get('sha256')==v.get('sha256'),expected_bytes=v.get('bytes'))
                refs.append(rr)
    csvout('root_mass_reference_hashes.csv',refs)
    u=ROOT/'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
    e=ET.parse(u).getroot();link=[]
    for node in e.findall('link'):
        m=node.find('inertial/mass');link.append(dict(name=node.get('name'),mass_kg=float(m.get('value')) if m is not None else None))
    d=yaml.safe_load((ROOT/'20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml').read_text(encoding='utf-8-sig'))
    c=d['configurations'][0]
    dump('root_mass_independent_readback.json',dict(accepted_urdf=str(u),links=link,total_kg=sum(x['mass_kg'] or 0 for x in link),joints=[dict(name=n.get('name'),type=n.get('type'),limit=n.find('limit').attrib if n.find('limit') is not None else None) for n in e.findall('joint')],ledger_values=d['mass_ledgers'],C01_mass=c['mass'],C01_members=[{k:x.get(k) for k in ['component_id','mass_kg','mass_class']} for x in c['composition']],C01_member_sum=sum(x['mass_kg'] for x in c['composition']),scope='XML and ledger readback; not geometry-derived mass or measurement'))
    sources += [ROOT/p for p in ['AGENTS.md','PROJECT_MAP.md','01_project/current/PROJECT_CURRENT_AUTHORITY_V1.yaml','01_project/current/CURRENT_RELEASE_POINTERS_V1.yaml','01_project/current/PROJECT_CURRENT_STATE_20260829.md','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/EQUIPMENT_LIST_V1.yaml','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/CG_INERTIA_CHECK_V1.json','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/70_c3_cad/GATE_C3_CHECK_V2.json','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/70_c3_cad/MASS_CG_REPORT_V1.json','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/70_c3_cad/BUILD_RECEIPT_V2.json','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/60_c2_panel/GATE_C2_CHECK.json','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/60_c2_panel/PANEL_MASS_LINE_RECONCILIATION_V1.md','20_engineering/config/geometry/flexible_appendage_v1.yaml','20_engineering/config/coupled_scene/coupled_model_v0.yaml','20_engineering/config/coupled_scene/scene_A2_capture.yaml','20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/19_OPEN_QUALIFICATION_HOLDS.csv']]
    sources += [REF/'REFERENCE_LIBRARY_START_HERE.md', Path('C:/Users/stude/.codex/attachments/5c4c8f8f-b95b-4643-9656-e0cd90647593/pasted-text.txt')]
    (OUT/'root_sources.txt').write_text('\n'.join(str(p) for p in sources)+'\n',encoding='utf-8')
    print(json.dumps(dict(refs=len(refs),hash_mismatches=sum(not r['hash_match'] for r in refs),arm_mass=sum(x['mass_kg'] or 0 for x in link),ledger_top_keys=list(d)),ensure_ascii=False))
elif mode=='finish':
    before=list(csv.DictReader((OUT/'root_protected_before.csv').open(encoding='utf-8-sig')))
    changed=[]
    for old in before:
        now=record(Path(old['path']))
        if now.get('sha256')!=old.get('sha256'):changed.append(dict(path=old['path'],before=old.get('sha256'),after=now.get('sha256')))
    dump('root_protected_after_check.json',dict(checked=len(before),changed=changed,scope='Selected protected source files; baseline taken after initial reads, before root audit processing'))
    paths=set()
    for f in OUT.glob('*sources.txt'):
        for line in f.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():paths.add(Path(line.strip()))
    tracked=set(command(['git','ls-files'])['stdout'].splitlines());rows=[]
    for p in sorted(paths):
        row=record(p)
        try:rel=p.relative_to(ROOT).as_posix();row['git_state']='TRACKED_CHECK_WORKSPACE_DIFF' if rel in tracked else 'LOCAL_ONLY_UNTRACKED'
        except ValueError:row['git_state']='EXTERNAL_REFERENCE_NOT_PROJECT_GIT'
        rows.append(row)
    csvout('09_SOURCE_SHA256.csv',rows)
    status=command(['git','-c','core.quotepath=false','status','--porcelain=v1','--untracked-files=normal'])
    old=json.loads((OUT/'root_workspace_before.json').read_text(encoding='utf-8'))['stdout'].splitlines()
    status['new_lines']=sorted(set(status['stdout'].splitlines())-set(old));status['removed_lines']=sorted(set(old)-set(status['stdout'].splitlines()))
    dump('root_workspace_after.json',status)
    print(json.dumps(dict(protected_checked=len(before),changed=changed,sources=len(rows),source_missing=sum(not r['exists'] for r in rows),git_delta=status['new_lines']),ensure_ascii=False))
