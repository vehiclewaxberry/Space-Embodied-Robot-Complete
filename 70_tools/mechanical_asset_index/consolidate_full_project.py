"""Reversible, narrowly scoped cleanup backed by the full-project SQLite catalog.

No CAD/simulation execution. File deletion is performed only by a fixed PowerShell
program after path, reparse, source and hash checks. Original bytes stay in SQLite.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, re, sqlite3, subprocess, sys, zlib
from full_project_catalog import ROOT, DB, SESSION, DOMAINS, RUNTIME_NAMES, now, digest, backup, meta

STAGE='BEFORE_REDUNDANT_CACHE_CLEANUP_20260906'
PS=r'''
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
function Get-CheckedSha256([string] $literalFile) {
  $stream = [IO.File]::Open($literalFile, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
  $algorithm = [Security.Cryptography.SHA256]::Create()
  try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
  finally { $algorithm.Dispose(); $stream.Dispose() }
}
$projectRoot = (Resolve-Path -LiteralPath $request.root).ProviderPath.TrimEnd('\')
$prefix = $projectRoot + '\'
$results = @()
foreach ($item in $request.items) {
  try {
    $target = [IO.Path]::GetFullPath((Join-Path $projectRoot $item.path))
    if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'OUTSIDE_WORKSPACE' }
    $info = Get-Item -Force -LiteralPath $target
    $ancestor = $info
    while ($null -ne $ancestor -and $ancestor.FullName -ne $projectRoot) {
      if (($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_POINT' }
      if ($ancestor.PSIsContainer) { $ancestor = $ancestor.Parent } else { $ancestor = $ancestor.Directory }
    }
    if ($item.kind -eq 'DELETE_EMPTY_DIRECTORY') {
      if (-not $info.PSIsContainer) { throw 'NOT_DIRECTORY' }
      if (@(Get-ChildItem -Force -LiteralPath $target).Count -ne 0) { throw 'NOT_EMPTY' }
      Remove-Item -Force -LiteralPath $target
    } else {
      if ($info.PSIsContainer) { throw 'NOT_FILE' }
      if ($info.Length -ne $item.size) { throw 'SIZE_CHANGED' }
      if ((Get-CheckedSha256 $target) -ne $item.sha256) { throw 'HASH_CHANGED' }
      if ($item.source) {
        $source = [IO.Path]::GetFullPath((Join-Path $projectRoot $item.source))
        if (-not $source.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'SOURCE_OUTSIDE' }
        if ((Get-CheckedSha256 $source) -ne $item.source_sha256) { throw 'SOURCE_CHANGED' }
      }
      Remove-Item -Force -LiteralPath $target
    }
    $results += [PSCustomObject]@{path=$item.path;status='DELETED';error=$null}
  } catch {
    $results += [PSCustomObject]@{path=$item.path;status='RETAINED_CHECK_FAILED';error=$_.Exception.Message}
  }
}
ConvertTo-Json -InputObject @($results) -Depth 5 -Compress
'''

def db():
    c=sqlite3.connect(DB,timeout=120);c.row_factory=sqlite3.Row
    return c

def bounded(p):
    p.resolve().relative_to(ROOT.resolve())
    q=p
    while q!=ROOT:
        if q.is_symlink() or getattr(q.lstat(),'st_file_attributes',0)&0x400:raise ValueError('reparse')
        q=q.parent
    return p

def prepare(c):
    if not c.execute("SELECT value FROM meta WHERE key='content_pass_finished_utc'").fetchone():
        raise RuntimeError('Finish the global static reference pass before cleanup preparation.')
    git=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,timeout=60)
    if git.returncode:raise RuntimeError('Cannot establish current Git ownership; cleanup stopped.')
    tracked={os.path.normcase(x.decode('utf-8')) for x in git.stdout.split(b'\0') if x}
    referenced={os.path.normcase(os.path.abspath(r[0])) for r in c.execute("SELECT target FROM refs WHERE source NOT LIKE '70_tools/mechanical_asset_index/%'") if Path(r[0]).is_absolute()}
    candidates=[];held=[]
    # Exclude third-party, nested repositories, environments and frozen evidence.
    for r in c.execute("SELECT * FROM entries WHERE kind='file' AND tracked=0 AND git_scope='ROOT_GIT' AND (path LIKE '%__pycache__/%' OR path LIKE '%.pytest_cache/%')"):
        rel=r['path'];p=ROOT/rel;parts=p.relative_to(ROOT).parts
        if rel.startswith('70_tools/mechanical_asset_index/__pycache__/'):continue
        if os.path.normcase(rel) in tracked:continue
        if parts[0] not in DOMAINS and parts[0]!='.pytest_cache':continue
        if parts[0]=='80_third_party' or any(x in RUNTIME_NAMES|{'results','artifacts','archive','_archive','MECHANICAL_ENGINEERING_RELEASE_R2'} for x in parts):continue
        if not p.exists():continue
        try:bounded(p)
        except (ValueError,OSError):continue
        source=None;kind=None
        if '__pycache__' in parts and p.suffix=='.pyc':
            if not p.name.isascii():held.append((rel,'NON_ASCII_CACHE_NAME_ENCODING_REVIEW_REQUIRED'));continue
            stem=re.sub(r'\.(?:cpython|pypy)-[^.]+(?:\.opt-\d+)?\.pyc$','',p.name)
            if stem==p.name:continue
            source=p.parent.parent/(stem+'.py')
            if not source.is_file():held.append((rel,'SOURCE_ABSENT'));continue
            try:bounded(source)
            except (ValueError,OSError):continue
            kind='DELETE_REGENERABLE_PYTHON_BYTECODE'
        elif '.pytest_cache' in parts and p.name in {'nodeids','lastfailed','stepwise','README.md','CACHEDIR.TAG','.gitignore'}:
            kind='DELETE_REGENERABLE_PYTEST_CACHE'
        if not kind:continue
        incoming=os.path.normcase(os.path.abspath(p)) in referenced
        if incoming:held.append((rel,'EXPLICIT_REFERENCE_PRESENT'));continue
        s=p.stat();item={'path':rel,'kind':kind,'size':s.st_size,'sha256':digest(p),'mtime_ns':s.st_mtime_ns,
          'source':source.relative_to(ROOT).as_posix() if source else None,'source_sha256':digest(source) if source else None}
        candidates.append(item)
    # A second, literal text search catches cache filenames and pinned hashes that
    # may not be recognized by the generic path parser. No-hit alone is not proof:
    # cache semantics, source presence, ownership, backups and live guards also apply.
    patterns=sorted({x['sha256'] for x in candidates}|{Path(x['path']).name for x in candidates if x['kind'].endswith('BYTECODE')})
    if patterns:
        cmd=['rg','--hidden','--no-ignore','-i','-l','-F','-f','-',
             '-g','!**/.git/**','-g','!**/__pycache__/**','-g','!**/.pytest_cache/**',
             '-g','!**/.pytest_cache','-g','!**/.pytest-tmp*','-g','!**/.pytest_tmp*',
             '-g','!**/__cadgen__/**','-g','!**/node_modules/**','-g','!**/site-packages/**',
             '-g','!80_third_party/**','-g','!70_tools/mechanical_asset_index/**',
             '-g','!**/full_project_catalog.sqlite*',str(ROOT)]
        result=subprocess.run(cmd,input='\n'.join(patterns)+'\n',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        if result.returncode not in {0,1}:raise RuntimeError('Literal dependency search incomplete: '+result.stderr[-500:])
        hits=[]
        for filename in result.stdout.splitlines():
            try:
                raw=Path(filename).read_bytes()
                if raw.startswith((b'\xff\xfe',b'\xfe\xff')):content=raw.decode('utf-16').lower()
                else:
                    try:content=raw.decode('utf-8-sig').lower()
                    except UnicodeDecodeError:content=raw.decode('gb18030',errors='replace').lower()
            except OSError:raise RuntimeError('Dependency search input changed: '+filename)
            for x in candidates:
                if x['sha256'] in content or (x['kind'].endswith('BYTECODE') and Path(x['path']).name.lower() in content):hits.append(x['path'])
        marked=set(hits)
        held.extend((x,'LITERAL_FILENAME_OR_HASH_REFERENCE') for x in marked)
        candidates=[x for x in candidates if x['path'] not in marked]
    for item in candidates:
        p=ROOT/item['path'];backup(c,p,STAGE)
        record=c.execute('SELECT sha256 FROM snapshots WHERE path=? AND stage=?',(item['path'],STAGE)).fetchone()
        if record['sha256']!=item['sha256']:raise RuntimeError('Snapshot mismatch')
        basis=json.dumps({'ownership':'untracked_project_cache','static_incoming_refs':0,'literal_filename_hash_search':'NO_HIT','source':item['source'],'source_sha256':item['source_sha256'],'native_and_dynamic_dependencies_not_globally_closed':True},ensure_ascii=False)
        c.execute('INSERT OR REPLACE INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
          (item['path'],item['kind'],None,basis,item['sha256'],item['mtime_ns'],'PREPARED',f'SQLite snapshots stage {STAGE}; --restore-file PATH',item['size'],None,None))
        c.execute('UPDATE entries SET action=?,reason=?,sha256=? WHERE path=?',(item['kind'],basis,item['sha256'],item['path']))
    for path,reason in held:c.execute('UPDATE entries SET action=?,reason=? WHERE path=?',('HOLD_UNRESOLVED',reason,path))
    meta(c,'cleanup_preparation',{'at':now(),'files':len(candidates),'bytes':sum(x['size'] for x in candidates),'held':held,'literal_search_patterns':len(patterns)})
    c.commit();return candidates

def execute(c,items):
    if not items:return []
    failure=None;reported={}
    try:
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',PS],input=json.dumps({'root':str(ROOT),'items':items},ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        if r.returncode:raise RuntimeError(r.stderr[-1200:])
        reported={x['path']:x for x in json.loads(r.stdout)}
    except Exception as exc:failure=str(exc)
    results=[]
    for item in items:
        path=ROOT/item['path'];x=reported.get(item['path'],{'path':item['path'],'status':'EXECUTION_UNCERTAIN','error':failure})
        if not path.exists():
            if x['status']!='DELETED':x['status']='ABSENT_AFTER_FAILED_CHECK' if item['path'] in reported else 'ABSENT_AFTER_INTERRUPTED_EXECUTION'
        elif x['status']=='DELETED':x.update(status='PRESENT_AFTER_DELETE_REGENERATED_OR_CHANGED',error='Path exists again; not counted as reclaimed.')
        c.execute('UPDATE actions SET status=?,executed_utc=?,error=? WHERE path=?',(x['status'],now(),x.get('error'),x['path']))
        if x['status']=='DELETED':
            c.execute("UPDATE entries SET post_state='DELETED_RECOVERABLE_FROM_SQLITE' WHERE path=?",(x['path'],))
        elif x['status'].startswith('ABSENT_'):
            c.execute("UPDATE entries SET post_state='ABSENT_RECOVERABLE_FROM_SQLITE_CAUSE_UNCERTAIN' WHERE path=?",(x['path'],))
        c.commit();results.append(x)
    if failure:
        c.execute('INSERT INTO events(at,kind,detail) VALUES(?,?,?)',(now(),'PARTIAL_OR_INTERRUPTED_DELETION',failure));c.commit()
        raise RuntimeError('Execution interrupted; per-path post-state reconciled and backups preserved: '+failure)
    return results

def clean_empty(c):
    dirs={str(Path(r[0]).parent).replace('\\','/') for r in c.execute("SELECT path FROM actions WHERE status='DELETED' AND kind!='DELETE_EMPTY_DIRECTORY'")}
    # Only empty generated-cache directories and the observed accidental literal $out.
    dirs.add('$out');items=[]
    for rel in sorted(dirs,key=lambda x:-x.count('/')):
        p=ROOT/rel
        if not p.is_dir() or any(p.iterdir()):continue
        if p.name not in {'__pycache__','$out'}:continue
        bounded(p)
        if c.execute('SELECT tracked FROM entries WHERE path=?',(rel,)).fetchone() is None:continue
        c.execute('INSERT OR REPLACE INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rel,'DELETE_EMPTY_DIRECTORY',None,'Verified empty generated/accidental directory',None,p.stat().st_mtime_ns,'PREPARED','Recreate empty directory at original path',0,None,None))
        items.append({'path':rel,'kind':'DELETE_EMPTY_DIRECTORY'})
    c.commit();return execute(c,items)

def hash_native(c):
    count=0
    for row in c.execute("SELECT path,size,mtime_ns FROM entries WHERE kind='file' AND sha256 IS NULL AND read_status IN ('CAD_REFERENCE_METADATA_READ','NATIVE_CONTENT_NOT_READ','UNSUPPORTED_FORMAT')").fetchall():
        p=ROOT/row['path']
        if not p.is_file():continue
        s=p.stat()
        if (s.st_size,s.st_mtime_ns)!=(row['size'],row['mtime_ns']):
            c.execute("UPDATE entries SET read_status='CHANGED_DURING_READ',reason='Changed since enumeration; new bytes not assigned to old snapshot identity' WHERE path=?",(row['path'],));continue
        sha=digest(p);t=p.stat()
        if (s.st_size,s.st_mtime_ns)!=(t.st_size,t.st_mtime_ns):continue
        c.execute("UPDATE entries SET sha256=?,read_method=CASE WHEN read_method='BINARY_IDENTITY_AND_HEADER' OR read_method='HEADER_ONLY_IDENTITY_PENDING' THEN 'SHA256_AND_HEADER_ONLY' ELSE read_method END WHERE path=?",(sha,row['path']));count+=1
        if count%200==0:c.commit()
    meta(c,'additional_binary_identity_hashing',{'at':now(),'files':count,'content_semantics_not_upgraded':True});c.commit()
    return count

def restore(c,rel):
    p=ROOT/rel
    if p.exists():raise ValueError('Refusing to overwrite existing file')
    p.resolve().relative_to(ROOT.resolve())
    row=c.execute('SELECT * FROM snapshots WHERE path=? AND stage=?',(rel,STAGE)).fetchone()
    if not row:raise ValueError('No cleanup snapshot')
    raw=zlib.decompress(row['compressed_blob']);assert hashlib.sha256(raw).hexdigest()==row['sha256']
    p.parent.mkdir(parents=True,exist_ok=True);bounded(p.parent)
    with p.open('xb') as f:f.write(raw)
    assert digest(p)==row['sha256']
    c.execute("UPDATE actions SET status='RESTORED' WHERE path=?",(rel,));c.execute("UPDATE entries SET post_state='RESTORED' WHERE path=?",(rel,));c.commit()

def report(c):
    """Update the existing shared entry/ledgers, retaining their previous scope."""
    from full_project_catalog import finalize
    if c.execute("SELECT count(*) FROM entries WHERE kind='file' AND read_status='NOT_YET_READ'").fetchone()[0]:
        raise RuntimeError('Unprocessed files remain; do not publish a completed pass.')
    c.execute("UPDATE entries SET read_status='DIRECTORY_CONTENTS_REGISTERED' WHERE kind='directory' AND read_status='NOT_YET_READ'")
    c.execute("UPDATE entries SET purpose_summary=replace(purpose_summary,'SHA身份待补','SHA身份已补（见sha256）') WHERE sha256 IS NOT NULL AND read_method='SHA256_AND_HEADER_ONLY'")
    c.executescript('''
    CREATE TABLE IF NOT EXISTS post_changes(path TEXT PRIMARY KEY,kind TEXT,prior_size INTEGER,current_size INTEGER,prior_mtime_ns INTEGER,current_mtime_ns INTEGER,current_sha256 TEXT,reason TEXT);
    CREATE TABLE IF NOT EXISTS directory_exceptions(path TEXT PRIMARY KEY,read_status TEXT,reason TEXT,action TEXT);
    CREATE INDEX IF NOT EXISTS refs_normalized_target ON refs(lower(replace(target,char(92),'/')));
    DROP VIEW IF EXISTS file_ledger;
    CREATE VIEW file_ledger AS SELECT
      e.path,COALESCE(e.sha256,'CONTENT_HASH_NOT_COMPUTED; metadata identity='||e.device||':'||e.inode) AS content_identity,
      e.read_status,e.read_method,e.coverage,e.domain AS business_domain,e.role AS artifact_role,
      COALESCE(NULLIF(e.configuration,'[]'),'UNRESOLVED_FROM_STATIC_CONTENT') AS product_or_configuration,
      e.purpose_summary,e.declared_status,e.verified_status,
      (SELECT group_concat(target,char(10)) FROM refs r WHERE r.source=e.path) AS source_inputs_or_text_references,
      (SELECT group_concat(source,char(10)) FROM refs r WHERE lower(replace(r.target,char(92),'/'))=lower((SELECT replace(json_extract(value,'$'),char(92),'/') FROM meta WHERE key='root')||'/'||e.path)) AS known_text_consumers,
      COALESCE(e.unresolved_dependencies,'Dynamic/native consumers unresolved; no-reference is not unused') AS unresolved_dependencies,
      CASE WHEN e.role='CACHE' THEN 'Cache producer inferred from path; see actions.basis for verified source' ELSE 'NOT_ESTABLISHED_PER_FILE; inspect source references/receipts' END AS generated_by,
      'NO_UNIVERSAL_SUPERSESSION_PROVEN' AS superseded_by_if_supported,
      CASE WHEN e.sha256 IS NOT NULL AND (SELECT count(*) FROM entries d WHERE d.sha256=e.sha256 AND d.size>0)>1 THEN e.sha256 END AS exact_duplicate_group,
      'NOT_GLOBALLY_ASSESSED; selected conflicts in reviews' AS semantic_similarity_group,
      'entries / refs / reviews / snapshots / actions in this database' AS evidence_location,
      e.action AS proposed_action,(SELECT target FROM actions a WHERE a.path=e.path) AS proposed_target_path,
      e.reason,e.confidence,e.semantic_review,e.post_state
    FROM entries e WHERE e.kind='file';
    DROP VIEW IF EXISTS directory_ledger;
    CREATE VIEW directory_ledger AS SELECT d.*,e.parent,e.domain,
      'Claimed purpose requires README/source review; see reviews' AS claimed_purpose_scope,
      CASE WHEN EXISTS(SELECT 1 FROM directory_exceptions x WHERE d.path='' OR x.path=d.path OR x.path LIKE d.path||'/%') THEN 'PARTIAL_ENUMERATION; inaccessible subtrees registered separately' ELSE 'Accessible static membership registered; activity/native dependencies remain bounded' END AS verified_purpose_scope,
      (SELECT sum(size) FROM entries f WHERE f.kind='file' AND (d.path='' OR f.path LIKE d.path||'/%') AND f.read_status!='NOT_YET_READ') AS processed_bytes,
      (SELECT count(*) FROM entries f WHERE f.kind='file' AND (d.path='' OR f.path LIKE d.path||'/%') AND f.post_state='DELETED_RECOVERABLE_FROM_SQLITE') AS deleted_files
    FROM dir_review d LEFT JOIN entries e ON e.path=d.path;
    DROP VIEW IF EXISTS exceptions;
    CREATE VIEW exceptions AS SELECT path,read_status,read_method,coverage,reason,unresolved_dependencies FROM entries
      WHERE kind='file' AND read_status IN ('NOT_YET_READ','PARTIALLY_READ','PERMISSION_DENIED','CHANGED_DURING_READ','UNSUPPORTED_FORMAT','NATIVE_CONTENT_NOT_READ','ARCHIVE_MEMBER_LISTED_ONLY','CAD_REFERENCE_METADATA_READ');
    DROP VIEW IF EXISTS exact_duplicate_groups;
    CREATE VIEW exact_duplicate_groups AS SELECT sha256,count(*) AS paths,max(size) AS bytes_per_copy,
      (count(*)-1)*max(size) AS logical_duplicate_bytes_NOT_reclaimable,
      group_concat(path,char(10)) AS members,'KEEP_PATHS_UNLESS_DEPENDENCIES_AND_ROLE_PROVE_RETIREMENT' AS disposition
      FROM entries WHERE sha256 IS NOT NULL AND size>0 AND kind='file' GROUP BY sha256 HAVING count(*)>1;
    ''')
    enum_row=c.execute("SELECT value FROM meta WHERE key='enumeration_errors'").fetchone()
    enumeration_errors=json.loads(enum_row[0]) if enum_row else []
    for err in enumeration_errors:
        rel=Path(err['path']).relative_to(ROOT).as_posix()
        c.execute('INSERT OR REPLACE INTO directory_exceptions VALUES(?,?,?,?)',(rel,'PERMISSION_DENIED',err['error'],'KEEP_INACCESSIBLE_NO_CLEANUP'))
        c.execute("UPDATE entries SET scan_status='ENUMERATION_INCOMPLETE',read_status='PERMISSION_DENIED',reason=?,action='KEEP_INACCESSIBLE_NO_CLEANUP' WHERE path=?",(err['error'],rel))
    # Navigation revisions retain their pre-edit snapshot/hash. Do not rewrite old
    # mechanical receipts whose source manifest included an older navigation page.
    nav=[]
    for r in c.execute("SELECT * FROM snapshots WHERE stage='BEFORE_NAVIGATION_CONSOLIDATION_20260906'").fetchall():
        p=ROOT/r['path'];s=p.stat();sha=digest(p);nav.append({'path':r['path'],'before_sha256':r['sha256'],'after_sha256':sha})
        c.execute("UPDATE entries SET sha256=?,post_state='AUTHORIZED_NAVIGATION_REVISION',action='NAVIGATION_CONSOLIDATED',reason='Original identity anchored by pre-edit snapshot; current hash in post_changes; old mechanical manifest remains historical.' WHERE path=?",(r['sha256'],r['path']))
        c.execute('INSERT OR REPLACE INTO post_changes VALUES(?,?,?,?,?,?,?,?)',(r['path'],'AUTHORIZED_NAVIGATION_REVISION',r['bytes'],s.st_size,None,s.st_mtime_ns,sha,'Original bytes saved before edit'))
    # Register incremental tool files separately from the fixed initial denominator.
    for name in ['scan_service_robot_assets.py','full_project_catalog.py','consolidate_full_project.py']:
        p=ROOT/'70_tools/mechanical_asset_index'/name;s=p.stat();old=c.execute('SELECT * FROM entries WHERE path=?',(p.relative_to(ROOT).as_posix(),)).fetchone()
        c.execute('INSERT OR REPLACE INTO post_changes VALUES(?,?,?,?,?,?,?,?)',(p.relative_to(ROOT).as_posix(),'CATALOG_TOOL_IMPLEMENTATION',old['size'] if old else None,s.st_size,old['mtime_ns'] if old else None,s.st_mtime_ns,digest(p),'Static catalog, reversible cleanup and reporting implementation; outside original business evidence'))
    snapshot_errors=[]
    for r in c.execute('SELECT * FROM snapshots'):
        raw=zlib.decompress(r['compressed_blob'])
        if len(raw)!=r['bytes'] or hashlib.sha256(raw).hexdigest()!=r['sha256']:snapshot_errors.append(r['path'])
    if snapshot_errors:raise RuntimeError('Snapshot validation failed: '+repr(snapshot_errors))
    finalize(c)
    summary=json.loads(c.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0])
    file_actions=c.execute("SELECT count(*),coalesce(sum(bytes),0) FROM actions WHERE status='DELETED' AND kind!='DELETE_EMPTY_DIRECTORY'").fetchone()
    dir_actions=c.execute("SELECT count(*) FROM actions WHERE status='DELETED' AND kind='DELETE_EMPTY_DIRECTORY'").fetchone()[0]
    action_kinds=[dict(r) for r in c.execute("SELECT kind,status,count(*) AS paths,sum(bytes) AS bytes FROM actions GROUP BY kind,status")]
    dup=c.execute('SELECT count(*),coalesce(sum(logical_duplicate_bytes_NOT_reclaimable),0) FROM exact_duplicate_groups').fetchone()
    record={'scope':'FULL_WORKSPACE_INVENTORY_STATIC_CONTENT_HANDLING_AND_BOUNDED_ACTUAL_CLEANUP','at':now(),'catalog':DB.relative_to(ROOT).as_posix(),
      'initial_snapshot':summary,'actual_deleted_files':file_actions[0],'actual_deleted_file_logical_bytes':file_actions[1],'deleted_empty_directories':dir_actions,
      'physical_disk_space_reclaimed':'NOT_MEASURED; SQLite recovery copies and catalog occupy space',
      'navigation_revisions':nav,'actions_by_kind':action_kinds,'snapshot_roundtrip_errors':snapshot_errors,
      'exact_duplicate_groups':dup[0],'duplicate_logical_bytes_not_delete_credit':dup[1],
      'inaccessible_subtrees':enumeration_errors,'coverage_claim':'All accessible registered files handled; inaccessible subtree contents are outside the counted denominator.',
      'limits':['Automated text/structure extraction is not expert review of every document','PDF figures/layout and native CAD interiors are not fully reviewed','Static text edges include weak/unresolved matches; no-hit does not prove unused','Environment/Git/cache entries may be metadata-only','Historical scope/hash receipts are retained, not retroactively rewritten'],
      'rollback':'consolidate_full_project.py --restore-file <original relative cache path>; navigation original bytes in snapshots',
      'status':'BOUNDED_CLEANUP_EXECUTED__NAVIGATION_CONSOLIDATED__NATIVE_AND_DYNAMIC_REVIEW_OPEN'}
    meta(c,'full_project_consolidation',record)
    c.execute('INSERT INTO events(at,kind,detail) VALUES(?,?,?)',(now(),'CLEANUP_AND_NAVIGATION_SUMMARY',json.dumps(record,ensure_ascii=False)))
    c.commit()
    # This is a new scope supplement; old WP03 mode and evidence values stay intact.
    for filename in ['dependency_manifest.json','run_manifest.json']:
        p=SESSION/filename;backup(c,p,'BEFORE_FULL_PROJECT_REPORT_20260906');c.commit()
        obj=json.loads(p.read_text(encoding='utf-8-sig'))
        obj['full_project_consolidation_20260906']={'catalog':'runs/loop0_20260905/screening/full_project_catalog.sqlite','status':record['status'],
          'actual_deleted_files':file_actions[0],'actual_deleted_file_logical_bytes':file_actions[1],'deleted_empty_directories':dir_actions,
          'human_root_entry':'../../../PROJECT_MAP.md','record_in_catalog':'meta.full_project_consolidation',
          'old_fields_scope':'Earlier WP03 review snapshot only. Do not interpret its dry_run/no_deletion or CURRENT hashes as the post-cleanup global state.'}
        p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    statuses='\n'.join(f'| `{k}` | {v:,} |' for k,v in summary['read_status_counts'].items())
    groups='\n'.join(f"| `{r['kind']}` | `{r['status']}` | {r['paths']:,} | {r['bytes'] or 0:,} |" for r in action_kinds)
    domain_rows=[]
    for domain in DOMAINS:
        rr=c.execute('SELECT files,bytes FROM dir_review WHERE path=?',(domain,)).fetchone()
        if rr:domain_rows.append(f'| [{domain}](../../../{domain}/README.md) | {rr[0]:,} | {rr[1]/1024**3:.3f} |')
    body=f'''# 全项目文件整理：当前入口与已执行清理

更新：2026-09-06。日常从 [PROJECT_MAP.md](../../../PROJECT_MAP.md) 进入，再选八个业务域。

本轮处理整个项目，已执行下列有限清理。原 WP03 机械问题与历史证据继续保留；本次文件整理不改变机械设计成熟度。

## 实际结果

- 初始快照成功登记 **{summary['files']:,} 个文件、{summary['directories']:,} 个目录、{summary['root_entries']} 个根级项目**，已登记文件逻辑体积 {summary['logical_bytes']/1024**3:.3f} GiB。包括隐藏项和嵌套版本库；另有 **{len(enumeration_errors)} 个子目录拒绝访问**，其未知内容不计入分母。F:\\ 父层只记录一层元数据。
- 实际删除 **{file_actions[0]:,} 个可恢复缓存文件、{dir_actions} 个空目录**，被删除文件逻辑字节合计 **{file_actions[1]:,} B**。原字节压缩保存在 SQLite；该数字不是净释放磁盘空间。
- 整理 **{len(nav)} 份根/域导航**，当前总入口统一到 PROJECT_MAP；旧导航原文与修改前字节均保留。106 个新增导航链接经过存在性检查。
- 全部快照文件已获得明确处理状态；自动全文提取、结构解析、元数据登记与专家审阅分开计数，**不宣称所有文件均已专业精读**。
- 同字节候选 **{dup[0]:,} 组**，路径职责逐项保留。重复逻辑字节不作为可删除体积。

| 已执行操作 | 落盘状态 | 路径数 | 文件逻辑字节 |
|---|---|---:|---:|
{groups}

## 八域与详细账本

| 导航入口 | 初始文件数 | 初始逻辑 GiB |
|---|---:|---:|
{chr(10).join(domain_rows)}

统一明细仅保存在 [full_project_catalog.sqlite](runs/loop0_20260905/screening/full_project_catalog.sqlite)：`file_ledger` 为逐文件账本，`directory_ledger` 为逐层目录账本，`refs` 保存静态引用，`reviews` 保存人工专项审阅，`exact_duplicate_groups` 为同字节候选，`exceptions` 为未完成内容验证的文件，`directory_exceptions` 为拒绝访问的子树，`actions`/`snapshots` 为动作和恢复原件，`post_changes` 为快照后的导航/工具变化。`entries` 保留初始登记分母与处理状态；`meta.full_project_consolidation` 记录本轮实际结果。

## 已筛明但继续保留的文件

| 对象 | 判定与实际处置 |
|---|---|
| 根级九个 F3R2 Python 脚本 | 与 99_tools 同名副本存在实质差异，Loop3 等读取根脚本；保留原路径，退出当前日常入口 |
| 根 B51 ZIP | 与规范目录 ZIP 字节重复，但验证脚本直接读取根 ZIP；保留 |
| 根 B51 三个展开文本 | 仅换行归一化后等价，并非同字节；引用和包职责保留，未凭名称删除 |
| structure、knowledge、PROJECT_ONBOARDING_PACKAGE、90_competition_closeout | 有唯一合同、参考方法、历史输入和消费者；保留路径，在主导航标明范围 |
| WP01/WP02 与 WP03 | 存在上游依赖；保持模型/参数/反例/原始收据，不将旧包整目录清空 |
| __cadgen__、第三方代码、运行环境、.git、原生 CAD 与图纸 | 冷重建、ABI 或内部引用尚未闭合；只登记与导航分类，继续保留 |

## 内容处理覆盖与例外

| 处理状态 | 文件数 |
|---|---:|
{statuses}

PDF 文字提取不包含图形/版式专业审阅；压缩包列成员不等于成员已读；CAD 文件头和 SHA 不证明内部外参正确。敏感配置仅登记结构、不把值写入报告。解析超时、未知格式及动态路径均留在明细里，未被当成垃圾。静态引用可能含相对基准不明的弱匹配，不能将数量解释成已确认断链。

## 恢复与复查

单个已删缓存可用 `70_tools/mechanical_asset_index/consolidate_full_project.py --restore-file 原相对路径` 恢复；工具拒绝覆盖已有文件。导航的原始字节在 `snapshots` 的 `BEFORE_NAVIGATION_CONSOLIDATION_20260906` 阶段，全部已做解压与 SHA-256 回验。恢复副本与索引同盘，不能替代异地备份。

旧 run_manifest/dependency_manifest 的 WP03 三包统计、只读模式和输入哈希属于之前的范围；本轮新增 `full_project_consolidation_20260906` 字段指向实际清理记录。旧冻结清单若绑定过导航原字节，其历史哈希仍保留，不能冒充导航改版后的相同哈希。

<details><summary>展开上一轮 WP03 机械审阅记录（历史范围，不代表本轮全仓统计或清理状态）</summary>

'''
    original=c.execute("SELECT compressed_blob FROM snapshots WHERE path=? AND stage='BEFORE_FULL_PROJECT_CONSOLIDATION'",((SESSION/'CURRENT_candidate.md').relative_to(ROOT).as_posix(),)).fetchone()
    if not original:raise RuntimeError('Original shared entry snapshot missing')
    history=zlib.decompress(original[0]).decode('utf-8-sig')
    (SESSION/'CURRENT_candidate.md').write_text(body+history+'\n</details>\n',encoding='utf-8')
    for filename in ['CURRENT_candidate.md','dependency_manifest.json','run_manifest.json']:
        p=SESSION/filename;meta(c,'post_report_sha256:'+p.relative_to(ROOT).as_posix(),digest(p))
    c.commit()
    print(json.dumps(record,ensure_ascii=False,indent=2),flush=True)

def main():
    a=argparse.ArgumentParser();a.add_argument('--prepare-and-clean',action='store_true');a.add_argument('--hash-native',action='store_true');a.add_argument('--report',action='store_true');a.add_argument('--restore-file');args=a.parse_args();c=db()
    if args.hash_native:print(json.dumps({'binary_identities_added':hash_native(c)}),flush=True)
    if args.prepare_and_clean:
        items=prepare(c);print(json.dumps({'prepared_files':len(items),'bytes':sum(x['size'] for x in items)}),flush=True)
        results=execute(c,items);dirs=clean_empty(c)
        print(json.dumps({'deleted_files':sum(x['status']=='DELETED' for x in results),'deleted_empty_directories':sum(x['status']=='DELETED' for x in dirs),'held_at_execution':[x for x in results+dirs if x['status']!='DELETED']}),flush=True)
    if args.restore_file:restore(c,args.restore_file)
    if args.report:report(c)
    c.close()

if __name__=='__main__':main()
