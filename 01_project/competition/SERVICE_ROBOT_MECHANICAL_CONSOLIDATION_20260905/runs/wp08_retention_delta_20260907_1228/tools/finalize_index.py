"""Preserve prior navigation verbatim, publish WP08 entry, seal completed artifacts."""
from pathlib import Path
import json,csv,hashlib,datetime,re,socket
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    final=R/'results/FINAL_INTEGRITY.json';seal=R/'results/DELIVERY_SHA256.csv';navrec=R/'results/NAVIGATION_UPDATE.json'
    assert not final.exists() and not seal.exists() and not navrec.exists()
    report=json.loads((R/'results/DELIVERY_STATUS.json').read_text())
    assert report['status']=='RETENTION_THREE_STATE_INTEGRATED__ONE_REAR_RIB_LOCAL_VERIFIED__WHOLE_ENGINEERING_OPEN'
    assert report['full_mechanical_design_complete'] is False and report['electrical_design_complete'] is False
    nav=R.parents[1]/'CURRENT_candidate.md'
    assert str(nav.resolve()) not in report['source_input_sha256']
    old=nav.read_bytes();oldsha=sha(nav)
    prefix=('# 当前机械工程入口：WP08\n\n'
      '2026-09-07：从 [WP08 实际交付说明](runs/wp08_retention_delta_20260907_1228/README.md) 查看三态 SolidWorks 装配、后肋局部实体及检查记录。两站保持器已回装，每态625实例/1006实体；后肋11实例局部连接已验证但尚未回装整机。\n\n'
      '整星机械与电气尚未完成。后续具体实体任务见 [下一批机械执行单](runs/wp08_retention_delta_20260907_1228/docs/NEXT_MECHANICAL_EXECUTION.md)。WP07与更早结果、失败记录及原问题账本继续保留。\n\n'
      '以下为此前入口与文件整理历史，其中“当前/本轮”表述仅属于当时记录。\n\n---\n\n').encode('utf-8')
    assert b'wp08_retention_delta_20260907_1228' not in old
    nav.write_bytes(prefix+old)
    assert nav.read_bytes()[len(prefix):]==old
    dump(navrec,dict(path=str(nav),before_sha256=oldsha,after_sha256=sha(nav),prior_bytes_preserved_verbatim=True,added_prefix_bytes=len(prefix),old_issue_rows_modified=False))
    files=[]
    for p in sorted(R.rglob('*')):
        if not p.is_file() or p in (final,seal):continue
        if any(x in ('__cadgen__','__pycache__') for x in p.relative_to(R).parts):continue
        if p.suffix.lower() in ('.tmp','.lock'):continue
        files.append(dict(relative_path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    with seal.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['relative_path','bytes','sha256']);w.writeheader();w.writerows(files)
    links=re.findall(r'\]\(<([^>]+)>\)',(R/'README.md').read_text())
    missing=[p for p in links if not Path(p).exists()]
    assert not missing,missing
    changed=[p for p,h in report['source_input_sha256'].items() if not Path(p).is_file() or sha(p)!=h]
    assert not changed,changed
    with socket.create_connection(('127.0.0.1',3245),timeout=3):pass
    dump(final,dict(schema='WP08_FINAL_FILE_INTEGRITY',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='PASS_FILE_INTEGRITY_AND_LOCAL_HANDOFF_ONLY',sealed_files=len(files),seal_path=str(seal),seal_sha256=sha(seal),
        source_inputs_current_and_unchanged=True,verified_source_inputs=len(report['source_input_sha256']),local_readme_links_checked=len(links),
        cad_viewer_port_listening=3245,navigation_update=str(navrec),excluded=['Derived __cadgen__ cache','Python bytecode cache','Temporary/lock files','Seal and final receipt self-hashes'],
        engineering_design_complete=False,manufacturing_release=False))
    print(json.dumps(dict(status='PASS_FILE_INTEGRITY_AND_LOCAL_HANDOFF_ONLY',sealed_files=len(files),source_inputs=len(report['source_input_sha256']),links=len(links))))
if __name__=='__main__':main()
