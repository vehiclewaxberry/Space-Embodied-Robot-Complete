from pathlib import Path
import json,csv,hashlib,zipfile,html,datetime,psutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
c=json.loads((C/'CANDIDATE_V30.json').read_text());assert all(sha(p)==h for p,h in c['source_lock'].items())
g=json.loads((C/'LUG_GEOMETRY_CHECK_V30.json').read_text());cl=json.loads((C/'LUG_CLAMP_CHECK_V30.json').read_text());e=json.loads((C/'LUG_ELECTROMECHANICAL_CHECK_V30.json').read_text());top=json.loads((C/'LUG_TOPOLOGY_VALIDATION_V30.json').read_text());si=json.loads((C/'LUG_PROJECT_SELF_INTERSECTION_V30.json').read_text());visual=json.loads((C/'VISUAL_REVIEW_V30.json').read_text());assert all(x['passed'] for x in [g,cl,e]) and top['ok'] and si['ok'] and visual['reviewed']
assert all(sha(C/r['file'])==r['sha256'] for r in visual['images']);n=sum(len(x['checks']) for x in [g,cl,e]);assert n==21
v=json.loads((C/'VIEWER_V30.json').read_text());status=dict(revision='V30',time=datetime.datetime.now().astimezone().isoformat(),targeted_checks_passed=n,topology_checked_occurrences=top['occurrenceCount'],self_intersection_checked_occurrences=si['occurrenceCount'],total_module_self_intersection_checked=False,solids=g['solid_count'],occurrences=g['occurrence_count'],electrical_refs=211,pin_network_records=677,ERC_inherited_unchanged_sources=dict(errors=0,warnings=0),PCB_DRC_remaining_Kelvin_unconnected_items=4,continuous_thermal_closed=False,new_cover_thermal_solved=False,whole_design_complete=False,manufacturing_release=False,host_installed=False,whole_harness_complete=False,physical_tests_executed=False,available_memory_MiB=psutil.virtual_memory().available/2**20,viewer=v)
(C/'DELIVERY_STATUS_V30.json').write_text(json.dumps(status,indent=2))
status.update(visual_reviewed=visual['reviewed'],visual_method=visual['method'],browser_views=len(visual['images']),native_snapshot_CLI_completed=visual['native_snapshot_CLI_completed'])
(C/'DELIVERY_STATUS_V30.json').write_text(json.dumps(status,indent=2))
md=(C/'README_V30.md').read_text(encoding='utf-8');parts=[]
for line in md.splitlines():
 if not line:continue
 if line.startswith('## '):parts.append('<h2>'+html.escape(line[3:])+'</h2>')
 elif line.startswith('# '):parts.append('<h1>'+html.escape(line[2:])+'</h1>')
 else:parts.append('<p>'+html.escape(line)+'</p>')
gallery=''.join('<figure><img src="'+html.escape(r['file'],quote=True)+'"><figcaption>'+html.escape(r['view'])+'</figcaption></figure>' for r in visual['images'])
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10 V30 端接与局部线束</title><style>body{font:17px/1.7 system-ui;background:#f1f4f7;color:#1b2735;max-width:1100px;margin:40px auto;padding:0 24px}h1{font-size:30px}h2{font-size:21px;margin-top:32px}.bar{background:#fff4db;border-left:5px solid #c78622;padding:16px}a{color:#155a97}img{width:100%;background:white}figure{margin:20px 0}p{overflow-wrap:anywhere}</style><div class="bar">本轮数字设计增量已交付；整机闭环与制造放行仍未完成。</div><p><a href="'+html.escape(v['model_url'],quote=True)+'">交互查看装配</a> · <a href="main_input_lugs_v30.step">下载 STEP</a> · <a href="WP10_V30_LUG_HARNESS_DELTA.zip">下载增量包</a> · <a href="README_V30.md">完整说明与来源链接</a></p>'+''.join(parts)+gallery+'</html>'
(C/'REVIEW_V30.html').write_text(page,encoding='utf-8')
readme=A/'README.md';current=readme.read_text(encoding='utf-8-sig');notice='# 当前可查看候选：V30（2026-09-11）\n\n端接、绝缘盖与局部导线已纳入本候选和总 BOM。查看 [V30 报告](coupled_closure/REVIEW_V30.html)。整机热、布局及推进接口仍开放；旧 V29 选型 BOM 已留存历史，不将旧包哈希套用到现行追加 BOM。\n\n'
if not current.startswith('# 当前可查看候选：V30'):readme.write_text(notice+current,encoding='utf-8')
# Delta only. Include its dependencies and explicit evidence; never recursively zip the entire workspace.
paths={Path(p) for p in c['source_lock'] if Path(p).is_relative_to(A)}
paths.update(p for p in C.iterdir() if p.is_file() and 'v30' in p.name.lower() and p.suffix.lower() not in ['.zip'] and p.name not in ['SHA256_V30.csv','DELIVERY_PACKAGE_CHECK_V30.json'])
paths.update(p for p in (A/'tools').glob('*v30.py'));paths.update(p for p in (A/'sources/lugs_v30').iterdir() if p.is_file());paths.update([A/'CURRENT_WORKING_CANDIDATE.json',A/'README.md',C/'CANDIDATE_V29.json',C/'SOURCE_ACTIVATION_V29.json'])
paths.update(p for p in (A/'logs').glob('*lug30*') if p.is_file());paths.update(p for p in (A/'results').glob('*V30*') if p.is_file());paths.update(p for p in (A/'results').glob('*lug30*') if p.is_file());paths.update(p for p in (A/'history/20260910_V30_before_lugs').rglob('*') if p.is_file())
manifest=C/'SHA256_V30.csv'
with manifest.open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['file','sha256','bytes']);w.writeheader()
 for p in sorted(paths):w.writerow(dict(file=p.relative_to(A).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
zip_path=C/'WP10_V30_LUG_HARNESS_DELTA.zip';assert not zip_path.exists(),'Do not silently overwrite a published archive'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(paths|{manifest}):z.write(p,p.relative_to(A).as_posix())
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for r in csv.DictReader(manifest.read_text().splitlines()):assert hashlib.sha256(z.read(r['file'])).hexdigest()==r['sha256']
receipt=dict(passed=True,files=len(paths)+1,zip_bytes=zip_path.stat().st_size,zip_sha256=sha(zip_path),manifest_sha256=sha(manifest),scope='incremental package requiring existing WP10 dependencies; no whole-robot release',current_candidate_sources_verified=True,whole_design_complete=False)
(C/'DELIVERY_PACKAGE_CHECK_V30.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
