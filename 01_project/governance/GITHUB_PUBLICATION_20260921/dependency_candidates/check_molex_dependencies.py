"""Read/download five exact public KiCad model candidates only; never edit compact."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,hashlib,json,urllib.request,urllib.parse,urllib.error

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'PROJECT_MAP.md').is_file())
OUT=Path(__file__).resolve().parent
MANIFEST=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/02_electrical/MODEL_DEPENDENCIES.json'
COMMIT='8d4070daa0fa3f7a7f3c176f4ca7bffc4df392be'
GH_COMMIT='b8b3cfdfad88ba66f21002b3de51dc6f7d55ba5a'
REPO='https://gitlab.com/kicad/libraries/kicad-packages3D'
API='https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-packages3D/repository'

def sha(data):return hashlib.sha256(data).hexdigest()
def save(name,data):
    p=(OUT/name).resolve();assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return {'path':p.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':sha(data)}
def request(url,method='GET'):
    assert urllib.parse.urlparse(url).hostname in {'gitlab.com','raw.githubusercontent.com'}
    record={'url':url,'method':method}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'service-star-exact-model-read-only-audit'},method=method)
        with urllib.request.urlopen(req,timeout=25) as r:
            data=r.read(12*1024*1024+1)
            assert len(data)<=12*1024*1024,'Response over bounded download limit'
            record.update(http_status=r.status,final_url=r.url,bytes=len(data),sha256=sha(data))
            return record,data
    except urllib.error.HTTPError as e:record.update(http_status=e.code,error=str(e))
    except Exception as e:record.update(http_status=None,error_type=type(e).__name__,error=str(e))
    return record,None

def check_one(row):
    path=row['source'].split('}/',1)[1]
    result={'required_reference':row['source'],'expected_compact_destination':row['destination'],'exact_library_path':path,'required_exact_filename':Path(path).name,'official_repository':REPO,'commit':COMMIT,'candidate_saved':False,'license_expression':None,'attempts':[]}
    raw=REPO+'/-/raw/'+COMMIT+'/'+path
    attempt,data=request(raw);result['attempts'].append(attempt)
    if data is not None:
        assert data.lstrip().startswith(b'ISO-10303-21;'),'Downloaded response is not STEP'
        assert b'END-ISO-10303-21;' in data,'STEP end marker missing'
        result.update(candidate_saved=True,status='EXACT_OFFICIAL_FILENAME_DOWNLOADED_PENDING_MODEL_REVIEW',source_url=raw,license_expression='CC-BY-SA-4.0 WITH KiCad-libraries-exception',candidate=save('models/'+path,data))
    else:
        legacy='https://raw.githubusercontent.com/KiCad/kicad-packages3D/'+GH_COMMIT+'/'+path
        gh_attempt,gh_data=request(legacy);result['attempts'].append(gh_attempt)
        if gh_data is not None:
            assert gh_data.lstrip().startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in gh_data
            result.update(candidate_saved=True,status='EXACT_ARCHIVED_OFFICIAL_FILENAME_DOWNLOADED_PENDING_LEGACY_LICENSE_REVIEW',source_url=legacy,commit=GH_COMMIT,candidate=save('legacy_models/'+path,gh_data))
        else:
            result['status']='EXACT_STEP_NOT_FOUND_AT_CHECKED_OFFICIAL_COMMITS' if all(a.get('http_status')==404 for a in result['attempts']) else 'EXACT_STEP_NOT_RETRIEVED_NETWORK_OR_ABSENCE_UNRESOLVED'
    history_url=API+'/commits?ref_name='+COMMIT+'&path='+urllib.parse.quote(path,safe='')+'&per_page=1'
    history_attempt,history_data=request(history_url);result['attempts'].append(history_attempt)
    if history_data is not None:
        history=json.loads(history_data);result['path_history_at_ref_count_returned']=len(history)
        result['path_history_latest_commit']=history[0]['id'] if history else None
    return result

def main():
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    before=MANIFEST.read_bytes();m=json.loads(before.decode('utf-8-sig'))
    rows=[r for r in m['records'] if not r['exists']];assert len(rows)==5
    assert all('/Connector_Molex.3dshapes/' in r['source'] and r['source'].endswith('.step') for r in rows)
    evidence=[]
    for name,url in [
        ('official_commit.json',API+'/commits/'+COMMIT),
        ('official_molex_tree.json',API+'/tree?path=Connector_Molex.3dshapes&ref='+COMMIT+'&per_page=100'),
        ('LICENSE.KICAD_LIBRARIES.md',REPO+'/-/raw/'+COMMIT+'/LICENSE.md'),
        ('MOLEX_CREDITS.md',REPO+'/-/raw/'+COMMIT+'/Connector_Molex.3dshapes/CREDITS.md')]:
        attempt,data=request(url)
        if data is not None:attempt['saved']=save('evidence/'+name,data)
        evidence.append(attempt)
    with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(check_one,rows))
    candidates=sum(r['candidate_saved'] for r in results)
    report={'schema':'EXACT_KICAD_MOLEX_DEPENDENCY_CANDIDATES_V1','started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'EXACT_MODELS_NOT_RETRIEVED' if not candidates else 'CANDIDATES_RETRIEVED_NOT_INSTALLED','required':len(rows),'downloaded':candidates,'remaining':len(rows)-candidates,'source_manifest':MANIFEST.relative_to(ROOT).as_posix(),'source_manifest_sha256_before':sha(before),'source_manifest_sha256_after':sha(MANIFEST.read_bytes()),'compact_manifest_unchanged':before==MANIFEST.read_bytes(),'official_gitlab_commit':COMMIT,'archived_official_github_commit':GH_COMMIT,'github_archive_note':'Official GitHub repository README moved to GitLab on 2020-10-02; not a current mirror.','library_license_expression':'CC-BY-SA-4.0 WITH KiCad-libraries-exception','library_license_url':'https://www.kicad.org/libraries/license/','redistribution_note':'A redistribution of library files as a collection retains attribution and library license documents; the electronic-design exception does not relicense the collected library files. No generic library license is assigned to an absent file.','evidence':evidence,'records':results,'scope_limits':['No approximate replacement','No ECAD/MCAD edit','No original compact modification','No upload','Filename existence and STEP header checks do not validate model dimensions or footprint alignment','Absence verdict only covers checked pinned official repository refs and reported path history; it does not prove that no OEM or other source model exists anywhere']}
    save('MOLEX_DEPENDENCY_CANDIDATES.json',json.dumps(report,ensure_ascii=False,indent=2).encode())
    lines=['# KiCad 精确 Molex STEP 依赖核验','',f'核验日期：{report["completed_utc"]}。精确候选下载：{candidates}/5。','',f'官方 GitLab 固定提交：`{COMMIT}`。官方 GitHub 为 2020 年迁移前归档，固定提交：`{GH_COMMIT}`。','', '| 原引用精确文件 | 结果 | GitLab / GitHub HTTP |','|---|---|---|']
    for r in results:lines.append('| `'+r['required_exact_filename']+'` | '+r['status']+' | '+' / '.join(str(a.get('http_status')) for a in r['attempts'][:2])+' |')
    lines+=['','未下载近似件、未重命名其他型号、未修改或安装到 compact；原依赖清单 SHA256 前后相同='+str(report['compact_manifest_unchanged'])+'。','',f'许可依据：[KiCad 官方说明]({report["library_license_url"]})；固定提交的原始许可证保存在 `evidence/LICENSE.KICAD_LIBRARIES.md`（若该 GET 成功，见 JSON 回执）。原库采用 CC-BY-SA-4.0 和 KiCad libraries exception。作为模型库集合再分发时应保留许可与署名；不能因是电路设计依赖就删除库的署名/许可。此许可并不自动授予任何未取得的 OEM 模型。','','目录和 URL 的具体响应、内容哈希、逐型号历史查询见 JSON。此结果不证明其他 OEM 或非官方来源不存在同型号模型，也不评价电气/机械尺寸正确性。']
    save('README.md',('\n'.join(lines)+'\n').encode())
    print(json.dumps({k:report[k] for k in ['status','required','downloaded','remaining','compact_manifest_unchanged']},ensure_ascii=False))
    for r in results:print(json.dumps({'file':r['required_exact_filename'],'status':r['status'],'http':[a.get('http_status') for a in r['attempts']],'history_count':r.get('path_history_at_ref_count_returned')},ensure_ascii=False))

if __name__=='__main__':main()
