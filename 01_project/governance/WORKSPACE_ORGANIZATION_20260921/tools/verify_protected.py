"""Independent read-only checks of protected/source/package byte hashes.

Only emits this audit's JSON and Markdown. No CAD, simulations, permissions,
source files, or source manifests are modified.
"""
from pathlib import Path
import csv,datetime,hashlib,json,traceback

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'PROJECT_MAP.md').is_file() and (p/'20_engineering').is_dir())
OUT=ROOT/'01_project/governance/WORKSPACE_ORGANIZATION_20260921'
COMPACT=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921'
R6H=ROOT/'20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920'
BASELINE=OUT/'PROTECTED_BASELINE.json'
PACKAGE=COMPACT/'00_release/PACKAGE_SHA256.csv'
SOURCE=R6H/'SOURCE_DEPENDENCIES_SHA256.csv'
TOP=R6H/'native/SERVICE_STAR_SERVICE_R6H.SLDASM'
TOP_EXPECTED='30ccbcbcff047ef54a112b841cf4814646714b24141b822bacbca13e1a5e45a7'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def rel(p):return str(Path(p).relative_to(ROOT)).replace('\\','/')

def check_set(name,rows,base,expected_count):
    out=[];seen=set();dups=[]
    for i,row in enumerate(rows,1):
        entry={'row':i,'manifest_path':row.get('path'),'expected_sha256':row.get('sha256')}
        try:
            raw=Path(row['path']);assert not raw.is_absolute(),'Manifest path is not relative'
            p=(base/raw).resolve();assert p.is_relative_to(base.resolve()),'Path escapes declared base'
            entry['resolved_workspace_path']=rel(p)
            if str(p).casefold() in seen:dups.append(entry['resolved_workspace_path'])
            seen.add(str(p).casefold())
            assert p.is_file(),'Missing or non-file source'
            before=p.stat();actual=sha(p);after=p.stat()
            entry.update(actual_sha256=actual,actual_bytes=after.st_size,read_stable=(before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns),sha256_matches=(actual==row['sha256']))
            if 'bytes' in row:
                entry['expected_bytes']=int(row['bytes']);entry['bytes_match']=int(row['bytes'])==after.st_size
            entry['status']='PASS' if entry['sha256_matches'] and entry['read_stable'] and entry.get('bytes_match',True) else 'MISMATCH_OR_CHANGED_DURING_READ'
        except Exception as e:entry.update(status='READ_OR_SCHEMA_ERROR',error_type=type(e).__name__,error=str(e))
        out.append(entry)
    failed=[r for r in out if r['status']!='PASS']
    return {'name':name,'path_base':rel(base) if base!=ROOT else '.','expected_rows':expected_count,'actual_rows':len(rows),'count_matches':len(rows)==expected_count,'matched':len(out)-len(failed),'anomalies':failed,'duplicate_paths':dups,'status':'PASS' if not failed and len(rows)==expected_count and not dups else 'FAIL_OR_INCOMPLETE','checks':out}

def main():
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifests=[BASELINE,PACKAGE,SOURCE]
    before={rel(p):sha(p) for p in manifests}
    baseline=json.loads(BASELINE.read_text(encoding='utf-8-sig'));assert isinstance(baseline,list)
    with PACKAGE.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);package=list(reader);package_fields=reader.fieldnames
    with SOURCE.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);source=list(reader);source_fields=reader.fieldnames
    assert package_fields==['path','bytes','sha256']
    assert source_fields==['path','sha256','inside_R6H']
    sets=[check_set('PROTECTED_BASELINE',baseline,ROOT,544),check_set('COMPACT_PACKAGE_MANIFEST',package,COMPACT,959),check_set('R6H_NATIVE_SOURCE_LOCK',source,ROOT,790),check_set('R6H_ORIGINAL_TOP',[{'path':rel(TOP),'sha256':TOP_EXPECTED}],ROOT,1)]
    after={rel(p):sha(p) for p in manifests}
    unique={r['resolved_workspace_path'] for s in sets for r in s['checks'] if 'resolved_workspace_path' in r}
    ok=all(s['status']=='PASS' for s in sets) and before==after
    result={'schema':'WORKSPACE_PROTECTED_INTEGRITY_INDEPENDENT_REVIEW_V1','started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_ALL_PROTECTED_AND_CURRENT_NATIVE_HASHES_UNCHANGED' if ok else 'FAIL_OR_INCOMPLETE_PROTECTED_REVIEW','method':'Independent streamed SHA256/size checks of the listed bytes; no CAD, simulation, source mutation, permission change or manifest rewrite','source_manifest_sha256_before':before,'source_manifest_sha256_after':after,'source_manifests_unchanged_during_review':before==after,'manifest_path_bases':{'PROTECTED_BASELINE':'workspace root','COMPACT_PACKAGE_MANIFEST':'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921','R6H_NATIVE_SOURCE_LOCK':'workspace root'},'checks_total':sum(s['actual_rows'] for s in sets),'matched_total':sum(s['matched'] for s in sets),'distinct_resolved_files':len(unique),'groups':sets,'CAD_or_simulation_rerun':False,'source_files_modified':False,'manifest_files_modified':False,'permissions_modified':False,'public_or_engineering_release_credit':False}
    (OUT/'PROTECTED_INTEGRITY_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 保护资产独立只读完整性复核','',f"日期：{result['completed_utc']}。裁决：`{result['status']}`。",'','仅按既定清单独立流式计算SHA256与已提供的字节数，未运行CAD/仿真，未改源文件、清单或文件权限。','','| 核验组 | 清单行数 | 匹配 | 异常 | 路径基准 |','|---|---:|---:|---:|---|']
    for s in sets:lines.append(f"| {s['name']} | {s['actual_rows']} | {s['matched']} | {len(s['anomalies'])} | `{s['path_base']}` |")
    lines+=['',f"合计{result['checks_total']}次具名核验，{result['matched_total']}匹配；去重后{len(unique)}个实际文件。重复核验来自不同清单的交叉保护，不能把总核验次数称为不同文件数。",'',f"原R6H顶层仍为 `{TOP_EXPECTED}`；清单自身在复核前后字节一致={before==after}。",'','异常（若有）：']
    failures=[{'group':s['name'],**r} for s in sets for r in s['anomalies']]
    if failures:
        for f in failures:lines.append(f"- `{f['group']}` / `{f.get('manifest_path')}`：{f['status']}；{f.get('error','hash/size/read-stability mismatch')}")
    else:lines.append('- 无哈希/大小不匹配、缺文件、访问错误或重复清单路径。')
    lines+=['','本回执仅证明被列保护文件的字节完整性；不构成工程、科学、公开授权或全工作区逐文件内容验收。']
    (OUT/'PROTECTED_INTEGRITY_REVIEW.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','checks_total','matched_total','distinct_resolved_files','source_manifests_unchanged_during_review']},ensure_ascii=False))

if __name__=='__main__':main()
