"""Append scoped execution navigation without changing the 17 original issues."""
from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[1];base=R.parents[1]
status=R/'results/DELIVERY_STATUS.json';readme=R/'README.md'
assert status.is_file() and readme.is_file()
ledger=base/'issues.json';entry=base/'CURRENT_candidate.md'
old=json.loads(ledger.read_text(encoding='utf-8-sig'))
assert old['issue_count']==17 and len(old['issues'])==17 and 'wp07_execution' not in old
before=json.dumps(old['issues'],ensure_ascii=False,sort_keys=True)
archive=R/'inputs/history/navigation_before_wp07';archive.mkdir(parents=True,exist_ok=False)
pins=[]
for path in (ledger,entry):
    data=path.read_bytes();dest=archive/path.name;dest.write_bytes(data)
    pins.append(dict(original=str(path),archive=str(dest),sha256=hashlib.sha256(data).hexdigest()))
(archive/'ARCHIVE.json').write_text(json.dumps(pins,ensure_ascii=False,indent=2),encoding='utf-8')
relative=R.relative_to(base).as_posix()
old['wp07_execution']=dict(date='2026-09-07',readme=relative+'/README.md',fact_snapshot=relative+'/results/DELIVERY_STATUS.json',
    scope='CURRENT_RUN_FACTS_ONLY_NOT_A_RELEASE_GATE',original_17_issue_records_unchanged=True,
    no_mechanical_electrical_completion_or_manufacturing_release_credit=True)
assert json.dumps(old['issues'],ensure_ascii=False,sort_keys=True)==before
ledger.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
text=entry.read_text(encoding='utf-8-sig')
head,rest=text.split('\n',1)
new=(head+'\n\n更新：2026-09-07。当前机械与机电接口审阅从 [WP07 交付说明]('+relative+'/README.md) 进入；其中列出实际生成文件、原生回读、局部几何检查、参考 PCB 及尚未关闭的接口。\n\n本轮为工程样机候选执行，不表示整机机械、电气、实物装配或制造放行完成。原 17 项问题记录保持原样，新增执行链接见 [issues.json](issues.json) 的 `wp07_execution`。\n\n以下保留 2026-09-06 文件整理记录；其“本轮”及未运行 CAD 等表述只属于当时整理范围。\n'+rest)
entry.write_text(new,encoding='utf-8')
report=dict(schema='WP07_EXISTING_NAVIGATION_UPDATE',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    backup_manifest=str(archive/'ARCHIVE.json'),original_issue_rows_preserved=True,issue_count=17,
    files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (ledger,entry)])
(R/'results/NAVIGATION_UPDATE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
