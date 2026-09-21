"""Byte-identical portable snapshot of current ECAD and offline DM implementation."""
import csv, hashlib, json, shutil, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
C=Path(__file__).resolve().parents[1]
N=C.parent/'reuse_closure'
D=C/'electrical_reference'
P=D/'package'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
exclude={'__pycache__','__cadgen__','runtime_config'}
source_files=[]
for sub in ['ecad','software','sources/motorbridge']:
    source_files += [p for p in (N/sub).rglob('*') if p.is_file() and not exclude.intersection(p.parts) and p.suffix not in ['.pyc','.kicad_prl']]
for rel in ['results/ECAD_VERIFICATION.json','results/ECAD_SYSTEM_GRAPH_TESTS.json','results/KICAD_RUN.json','results/DM_OFFLINE_TEST_RESULTS.json','results/DM_INTEGRATION_CONTRACT.json','results/DM_SOURCE_MANIFEST.json','results/NATIVE_BOARD_MATERIAL.json','mechanical/native/RS422_GSE_SPLICE_BOARD.SLDPRT','mechanical/RS422_GSE_SPLICE_BOARD.step']:
    source_files.append(N/rel)
rows=[]
for source in source_files:
    rel=source.relative_to(N); dest=P/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and sha(dest)!=sha(source):
        raise RuntimeError('Refuse to overwrite changed snapshot '+str(dest))
    if not dest.exists(): shutil.copy2(source,dest)
    rows.append({'path':rel.as_posix(),'source':str(source),'sha256':sha(source),'copy_sha256':sha(dest)})
(P/'results').mkdir(exist_ok=True)
# Run only offline code; preserve inherited receipts under evidence/, keeping source bytes intact.
(P/'evidence').mkdir(exist_ok=True)
for name in ['DM_OFFLINE_TEST_RESULTS.json']:
    shutil.copy2(P/'results'/name,P/'evidence'/('PARENT_'+name))
run=subprocess.run([sys.executable,'-B','-X','utf8',str(P/'software/test_dm_offline.py')],cwd=P,capture_output=True,text=True,encoding='utf-8',timeout=90)
(D/'DM_RELOCATION_TEST_LOG.txt').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
fresh=json.loads((P/'results/DM_OFFLINE_TEST_RESULTS.json').read_text(encoding='utf-8'))
# Restore inherited receipt bytes; relocated execution is a separate child receipt.
shutil.copy2(P/'results/DM_OFFLINE_TEST_RESULTS.json',D/'DM_RELOCATION_TEST_RESULTS.json')
shutil.copy2(P/'evidence/PARENT_DM_OFFLINE_TEST_RESULTS.json',P/'results/DM_OFFLINE_TEST_RESULTS.json')
cli=Path('F:/China Graduate Future Flight Vehicle Innovation Competition/70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe')
exports=D/'relocation_exports';exports.mkdir(exist_ok=True)
commands=[['sch','export','netlist','--format','kicadxml','--output',str(exports/'wp09_system.xml'),str(P/'ecad/wp09_system.kicad_sch')],['pcb','drc','--output',str(exports/'rs422_drc.json'),'--format','json',str(P/'ecad/rs422_gse_splice.kicad_pcb')]]
command_results=[]
for args in commands:
    proc=subprocess.run([str(cli),*args],cwd=P,capture_output=True,text=True,encoding='utf-8',timeout=90)
    command_results.append({'args':args,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    if proc.returncode: raise RuntimeError(proc.stderr)
import xml.etree.ElementTree as ET
def net_signature(path):
    doc=ET.parse(path)
    return sorted((n.attrib.get('name'),tuple(sorted((x.attrib['ref'],x.attrib['pin']) for x in n.findall('node')))) for n in doc.findall('./nets/net'))
net_match=net_signature(exports/'wp09_system.xml')==net_signature(N/'ecad/exports/wp09_system.xml')
drc=json.loads((exports/'rs422_drc.json').read_text(encoding='utf-8'))
drc_count=sum(len(drc.get(k,[])) for k in ['violations','unconnected_items','schematic_parity'])
assert run.returncode==0 and net_match and drc_count==0
for row in rows: assert sha(P/row['path'])==row['sha256'],row['path']
(P/'SNAPSHOT_MANIFEST.json').write_text(json.dumps({'parent':str(N),'identity':'BYTE_IDENTICAL_ECAD_DM_REFERENCE_SNAPSHOT','files':rows},ensure_ascii=False,indent=2),encoding='utf-8')
(P/'START_HERE_ZH.md').write_text('''# 原生电气与 DM 离线源可迁移参考包

这是已封存 WP09R 原生电气工程的原样快照，MASTER_FROM_TO.csv 的内容及身份保持不变。
打开 ecad/wp09_system.kicad_pro 查看总原理图，打开 ecad/rs422_gse_splice.kicad_pcb 查看独立地面转接板。
软件参考位于 software/，原样上游源码及 MIT 许可证位于 sources/motorbridge/。
本包在新的本机目录实际重新导出系统网表并核对全部网络、重新执行地面板 DRC 与 29 项 Python 离线测试。
系统仍有原有一项停止链电源边界 ERC 问题；没有新增真实停止驱动或推进控制电路，没有进行硬件 I/O。
离线测试为 Python 移植及 AST/假 ABI；Rust 本体、FFI 和设备后端没有运行。
原 README/来源回执中的绝对工作区路径属于来源记录，不代表另一台机器存在这些路径。
本包验证的是原生文件及上述离线路径可用，不代表完整系统功能或所有工程生成器可异机复现。
''',encoding='utf-8')
archive=D/'WP09_ECAD_DM_REFERENCE.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
    for p in sorted(P.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(P).as_posix())
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
report={'status':'PASS_BYTE_IDENTICAL_REFERENCE_COPY_NETLIST_DRC_AND_PYTHON_RELOCATION','utc':datetime.now(timezone.utc).isoformat(),'package':str(P),'archive':{'path':str(archive),'sha256':sha(archive),'bytes':archive.stat().st_size,'crc_verified':True},'source_files':len(rows),'all_source_bytes_unchanged':True,'netlist_nodes_and_names_equal':net_match,'nets':len(net_signature(exports/'wp09_system.xml')),'drc_violations_unconnected_parity_total':drc_count,'dm_python_tests_returncode':run.returncode,'dm_receipt':str(D/'DM_RELOCATION_TEST_RESULTS.json'),'commands':command_results,'system_ERC_inherited_open_errors':1,'full_electrical_design_complete':False,'rust_native_executed':False,'hardware_io':0}
(C/'results/ELECTRICAL_REFERENCE_DELIVERY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='commands'},ensure_ascii=False))
