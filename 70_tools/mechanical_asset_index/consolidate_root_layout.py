"""Reviewed physical root consolidation with byte backups in the existing catalog.

Only this task's explicit mapping is applied. No recursive deletion, CAD execution,
version-store cleanup, or semantic replacement of frozen scientific receipts.
"""
from pathlib import Path
import argparse, ast, hashlib, json, os, sqlite3, subprocess, zlib
from full_project_catalog import ROOT, DB, SESSION, backup, digest, now, meta

STAGE='BEFORE_ROOT_PHYSICAL_CONSOLIDATION_20260906'
HISTORY='01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md'
KNOWLEDGE='10_research/knowledge_base/spacecraft_mechanical_design/legacy_structure_methods_20260728.md'
LEGACY='70_tools/legacy_f3r2_root_scripts'
CANONICAL='20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/00_BASELINE/AUTHORIZATION_PACKAGE'
PREFIXES={
 'structure':'20_engineering/system_design/legacy_root_structure',
 '90_competition_closeout':'01_project/competition/archive/90_competition_closeout',
}
PS=r'''
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$request=[Console]::In.ReadToEnd() | ConvertFrom-Json
$projectRoot=(Resolve-Path -LiteralPath $request.root).ProviderPath.TrimEnd('\')
$prefix=$projectRoot+'\'
function Check-Path([string] $rel) {
  $full=[IO.Path]::GetFullPath((Join-Path $projectRoot $rel))
  if (-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) {throw 'OUTSIDE_WORKSPACE'}
  $cursor=$full
  while ($cursor -ne $projectRoot) {
    if (Test-Path -LiteralPath $cursor) {
      $info=Get-Item -Force -LiteralPath $cursor
      if (($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {throw 'REPARSE_POINT'}
    }
    $cursor=[IO.Path]::GetDirectoryName($cursor)
    if (-not $cursor) {throw 'MISSING_ROOT_ANCESTOR'}
  }
  return $full
}
function File-Sha([string] $path) {
  $s=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  $h=[Security.Cryptography.SHA256]::Create()
  try {return [BitConverter]::ToString($h.ComputeHash($s)).Replace('-','').ToLowerInvariant()}
  finally {$h.Dispose();$s.Dispose()}
}
$outcomes=@()
foreach($item in $request.items) {
  try {
    $src=Check-Path $item.path
    if($item.kind -eq 'REMOVE_EMPTY_ROOT_DIRECTORY') {
      $info=Get-Item -Force -LiteralPath $src
      if(-not $info.PSIsContainer -or @(Get-ChildItem -Force -LiteralPath $src).Count -ne 0) {throw 'NOT_EMPTY_DIRECTORY'}
      Remove-Item -Force -LiteralPath $src
      $status='DELETED'
    } else {
      $info=Get-Item -Force -LiteralPath $src
      if($info.PSIsContainer -or $info.Length -ne $item.bytes -or (File-Sha $src) -ne $item.sha256) {throw 'SOURCE_CHANGED'}
      if($item.kind -eq 'MOVE_TO_DOMAIN') {
        $dst=Check-Path $item.target
        if(Test-Path -LiteralPath $dst) {throw 'DESTINATION_EXISTS'}
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($dst)) | Out-Null
        Move-Item -LiteralPath $src -Destination $dst
        if((File-Sha $dst) -ne $item.sha256) {throw 'MOVED_HASH_MISMATCH'}
        $status='MOVED'
      } else {
        if($item.target) {
          $retained=Check-Path $item.target
          if((File-Sha $retained) -ne $item.target_sha256) {throw 'RETAINED_TARGET_CHANGED'}
        }
        Remove-Item -Force -LiteralPath $src
        $status='DELETED'
      }
    }
    $outcomes += [PSCustomObject]@{path=$item.path;status=$status;error=$null}
  } catch {$outcomes += [PSCustomObject]@{path=$item.path;status='CHECK_FAILED';error=$_.Exception.Message}}
}
ConvertTo-Json -InputObject @($outcomes) -Depth 5 -Compress
'''

def connection():
    c=sqlite3.connect(DB,timeout=120);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS root_layout_actions(path TEXT PRIMARY KEY,kind TEXT,target TEXT,bytes INTEGER,sha256 TEXT,target_sha256 TEXT,basis TEXT,status TEXT,executed_utc TEXT,error TEXT)')
    return c

def bounded(p):
    p.resolve().relative_to(ROOT.resolve())
    while p!=ROOT:
        if p.exists() and (p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Reparse point')
        p=p.parent

def plan(c):
    items=[]
    def add(path,kind,target,basis):
        p=ROOT/path
        if not p.exists():return
        bounded(p);assert p.is_file()
        dst=ROOT/target if target else None
        if dst:bounded(dst)
        if kind=='MOVE_TO_DOMAIN':assert not dst.exists(),target
        elif target:assert dst.is_file(),target
        backup(c,p,STAGE)
        item={'path':path,'kind':kind,'target':target,'bytes':p.stat().st_size,'sha256':digest(p),
              'target_sha256':digest(dst) if dst and dst.exists() else None,'basis':basis}
        saved=c.execute('SELECT * FROM snapshots WHERE path=? AND stage=?',(path,STAGE)).fetchone()
        raw=zlib.decompress(saved['compressed_blob'])
        assert saved['sha256']==item['sha256']==hashlib.sha256(raw).hexdigest(),('snapshot identity changed',path)
        assert saved['bytes']==item['bytes']==len(raw),('snapshot length changed',path)
        items.append(item)
    root_md=[p for p in ROOT.glob('*.md') if p.name not in {'AGENTS.md','CLAUDE.md','PROJECT_MAP.md'}]
    assert len(root_md)==7, [p.name for p in root_md]
    for p in root_md:add(p.name,'DELETE_AFTER_CONTENT_MERGE',HISTORY,'Reviewed unique historical information merged; current entry is PROJECT_MAP; original raw bytes in snapshots')
    for p in (ROOT/'PROJECT_ONBOARDING_PACKAGE').glob('*.md'):
        add(p.relative_to(ROOT).as_posix(),'DELETE_AFTER_CONTENT_MERGE',HISTORY,'Ten onboarding narratives reviewed and deduplicated into dated history')
    for p in (ROOT/'knowledge').glob('*.md'):
        add(p.relative_to(ROOT).as_posix(),'DELETE_AFTER_CONTENT_MERGE',KNOWLEDGE,'Two methodology notes reviewed and merged; old raw bytes recoverable')
    for p in (ROOT/'PROJECT_ONBOARDING_PACKAGE').iterdir():
        if p.is_file() and p.suffix!='.md':add(p.relative_to(ROOT).as_posix(),'MOVE_TO_DOMAIN','01_project/competition/archive/onboarding_20260729/'+p.name,'Unique machine-readable/visual snapshot retained byte-identically')
    add('PROJECT_MODEL_TRUTH_HIERARCHY.yaml','MOVE_TO_DOMAIN','01_project/current/archive/PROJECT_MODEL_TRUTH_HIERARCHY_20260808.yaml','Historical YAML values preserved; live consumers redirected')
    for p in sorted(ROOT.glob('F3R2_V5*.py')):add(p.name,'MOVE_TO_DOMAIN',LEGACY+'/'+p.name,'Distinct legacy root-script version; not replaced by different 99_tools source')
    add('F3R2_V5_G0_ADMIN_MEMORY_RELEASE.ps1','MOVE_TO_DOMAIN',LEGACY+'/F3R2_V5_G0_ADMIN_MEMORY_RELEASE.ps1','Historical administrative script retained, never executed')
    for old,new in PREFIXES.items():
        for p in sorted((ROOT/old).rglob('*')):
            if p.is_file():add(p.relative_to(ROOT).as_posix(),'MOVE_TO_DOMAIN',new+'/'+p.relative_to(ROOT/old).as_posix(),'Unique contracts/audit evidence retained without changing bytes')
    zipname='B51R1_PHASE1_START_PACKAGE.zip'
    assert digest(ROOT/zipname)==digest(ROOT/CANONICAL/zipname)
    add(zipname,'DELETE_BYTE_DUPLICATE',CANONICAL+'/'+zipname,'Exact ZIP identity verified; verifier now consumes canonical copy with frozen expected SHA')
    for p in (ROOT/'B51R1_PHASE1_START_PACKAGE').iterdir():
        if not p.is_file():continue
        target=ROOT/CANONICAL/p.name
        assert p.read_bytes().replace(b'\r\n',b'\n')==target.read_bytes().replace(b'\r\n',b'\n')
        add(p.relative_to(ROOT).as_posix(),'DELETE_LINE_ENDING_EQUIVALENT_COPY',target.relative_to(ROOT).as_posix(),'Canonical source retained; equivalence is CRLF/LF normalization only; original bytes saved')
    for p in (ROOT/'.pytest_cache').rglob('*'):
        if p.is_file():add(p.relative_to(ROOT).as_posix(),'DELETE_ROOT_PYTEST_CACHE',None,'Generated root pytest metadata; earlier historical file listings remain historical, not runtime consumers')
    meta(c,'root_layout_before',{'at':now(),'root_entries':sorted(p.name for p in ROOT.iterdir()),'planned_files':len(items)})
    for x in items:c.execute('INSERT OR REPLACE INTO root_layout_actions VALUES(?,?,?,?,?,?,?,?,?,?)',(x['path'],x['kind'],x['target'],x['bytes'],x['sha256'],x['target_sha256'],x['basis'],'PREPARED',None,None))
    c.commit();return items

def execute(c,items):
    failure=None
    try:
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',PS],input=json.dumps({'root':str(ROOT),'items':items},ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        if r.returncode:raise RuntimeError(r.stderr[-500:])
        outcomes=json.loads(r.stdout)
    except Exception as exc:failure=str(exc);outcomes=[]
    records={x['path']:x for x in outcomes};errors=[]
    for x in items:
        o=records.get(x['path'],{'status':'EXECUTION_UNCERTAIN','error':failure or 'Missing per-path receipt'})
        source=ROOT/x['path'];target=ROOT/x['target'] if x.get('target') else None
        valid=not source.exists() and (o['status']=='DELETED' or (o['status']=='MOVED' and target.is_file() and digest(target)==x['sha256']))
        if not valid:
            o['observed_source_exists']=source.exists()
            o['observed_target_exists']=target.exists() if target else None
            errors.append({'path':x['path'],**o})
        c.execute('UPDATE root_layout_actions SET status=?,executed_utc=?,error=? WHERE path=?',(o['status'],now(),o.get('error'),x['path']))
        if valid:c.execute('UPDATE entries SET post_state=?,action=?,reason=? WHERE path=?',('MOVED_TO_DOMAIN' if o['status']=='MOVED' else 'DELETED_RECOVERABLE_FROM_SQLITE',x['kind'],x.get('basis'),x['path']))
        c.commit()
    if errors:
        c.execute('INSERT INTO events(at,kind,detail) VALUES(?,?,?)',(now(),'ROOT_LAYOUT_PARTIAL_OR_FAILED_EXECUTION',json.dumps(errors,ensure_ascii=False)));c.commit()
        raise RuntimeError('Review partial actions before retry: '+json.dumps(errors,ensure_ascii=False))
    return outcomes

def empty_directories(c):
    roots=list(PREFIXES)+['PROJECT_ONBOARDING_PACKAGE','knowledge','B51R1_PHASE1_START_PACKAGE','.pytest_cache','08_REVIEWS']
    for old in roots:
        p=ROOT/old
        if not p.exists():continue
        dirs=sorted([p]+[x for x in p.rglob('*') if x.is_dir()],key=lambda x:-len(x.parts))
        for d in dirs:
            bounded(d)
            if any(d.iterdir()):continue
            rel=d.relative_to(ROOT).as_posix();item={'path':rel,'kind':'REMOVE_EMPTY_ROOT_DIRECTORY','target':None,'bytes':0,'sha256':None,'basis':'Verified empty after per-file actions; no recursive delete'}
            c.execute('INSERT OR REPLACE INTO root_layout_actions VALUES(?,?,?,?,?,?,?,?,?,?)',(rel,item['kind'],None,0,None,None,item['basis'],'PREPARED',None,None));c.commit()
            execute(c,[item])

def change_source(c,relative,pairs):
    p=ROOT/relative;backup(c,p,STAGE);raw=p.read_bytes();old=hashlib.sha256(raw).hexdigest()
    for before,after,count in pairs:
        a=before.encode();b=after.encode();assert raw.count(a)==count,(relative,before,raw.count(a));raw=raw.replace(a,b)
    ast.parse(raw.decode('utf-8-sig'));c.commit();p.write_bytes(raw)
    c.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?,?,?)',(relative,'root_physical_path_refactor_20260906','FULL_SOURCE_STATIC_PATH_PATCH_AND_AST',json.dumps({'before_sha256':old,'after_sha256':digest(p),'replacements':pairs,'business_execution':False,'old_receipts_not_rewritten':True}), 'Path-bearing statements only changed; no flight/software release credit'))
    c.commit()

def consumers(c):
    e='F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py';grip='F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY.py'
    change_source(c,LEGACY+'/F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py',[(f'LOOP1C0_SCRIPT = ROOT / "{grip}"',f'LOOP1C0_SCRIPT = ROOT / "{LEGACY}/{grip}"',1)])
    pair=(f'LOOP1E_SCRIPT = ROOT / "{e}"',f'LOOP1E_SCRIPT = ROOT / "{LEGACY}/{e}"',1)
    change_source(c,LEGACY+'/F3R2_V5_NATIVE_LOOP3_RELEASE_EVIDENCE_ATTACH_ONLY.py',[pair])
    change_source(c,'20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/99_tools/F3R2_V5_NATIVE_LOOP3_RELEASE_EVIDENCE_ATTACH_ONLY.py',[pair])
    change_source(c,'20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/99_tools/V5R_PHASE_A_SCRIPT_PROVENANCE_PROBE.py',[(f'"src": os.path.join(ROOT, "{e}")',f'"src": os.path.join(ROOT, "{LEGACY}/{e}")',1)])
    change_source(c,'20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/99_tools/m3r_evidence_inventory.py',[( 'PROJECT / "structure/', 'PROJECT / "20_engineering/system_design/legacy_root_structure/',2)])
    assert digest(ROOT/LEGACY/e).upper()=='675EBCC3B95984EAB301378518B5DE2E11EDA8ACE1E73AD7950FBFDDC5AFF0A2'
    assert digest(ROOT/LEGACY/grip).upper()=='59BCAED201D58B7B585E34A3C1904B934E60D6E535A1A0A2784937934C403023'

def main():
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');args=a.parse_args()
    if not args.apply:raise SystemExit('Explicit --apply required for reviewed root mapping.')
    c=connection();items=plan(c);print(json.dumps({'prepared_files':len(items)}),flush=True)
    execute(c,items);empty_directories(c);consumers(c)
    record={'at':now(),'remaining_root_entries':sorted(p.name for p in ROOT.iterdir()),'actions':[
      dict(r) for r in c.execute('SELECT kind,status,count(*) AS paths,sum(bytes) AS bytes FROM root_layout_actions GROUP BY kind,status')],
      'pinned_legacy_loop1c_and_loop1e_bytes_unchanged':True,'old_receipts_scope':'Prior paths/hashes preserved in frozen records; consumers have new code identity, no inherited run result',
      'historical_missing_helpers':'Root base helper and Loop1A were already absent; not replaced by different 99_tools versions',
      'complete_business_or_CAD_execution':False}
    meta(c,'root_layout_physical_execution',record);c.commit();print(json.dumps(record,ensure_ascii=False,indent=2));c.close()

if __name__=='__main__':main()
