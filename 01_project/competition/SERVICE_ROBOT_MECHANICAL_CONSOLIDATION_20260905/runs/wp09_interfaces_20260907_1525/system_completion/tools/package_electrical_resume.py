"""Verify native KiCad files from a second directory, then package reviewed electrical sources."""
import argparse,csv,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
C=Path(__file__).resolve().parents[1]
ROOT=C.parents[5]
K=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def netidentity(p):
    x=ET.parse(p).getroot()
    components=sorted((c.attrib['ref'],c.findtext('value'),c.findtext('libsource')) for c in x.find('components'))
    nets=sorted(sorted((v.attrib['ref'],v.attrib['pin']) for v in n.findall('node')) for n in x.find('nets'))
    return components,nets
ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['verify','package']);a=ap.parse_args()
receipt=C/'results/ELECTRICAL_RESUME_RELOCATION.json'
if a.mode=='verify':
    dest=C/'ecad_move'
    assert not dest.exists(),'Existing relocation result must be inspected, not overwritten.'
    dest.mkdir()
    files=[]
    for p in sorted((C/'ecad').iterdir()):
        if p.is_file() and (p.suffix in {'.kicad_sch','.kicad_sym','.kicad_pro'} or p.name=='sym-lib-table'):
            q=dest/p.name;shutil.copy2(p,q)
            assert sha(p)==sha(q)
            files.append({'source':str(p.relative_to(C)),'relocated':str(q.relative_to(C)),'sha256':sha(p)})
    assert K.is_file(),str(K)
    out=dest/'relocated.xml'
    commands=[['sch','export','netlist','--format','kicadxml','-o',str(out),str(dest/'wp09_system.kicad_sch')],
              ['sch','erc','--format','json','-o',str(dest/'relocated_erc.json'),str(dest/'wp09_system.kicad_sch')]]
    runs=[]
    for args in commands:
        r=subprocess.run([str(K),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=120)
        runs.append({'args':args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    assert runs[0]['returncode']==0,runs
    original=netidentity(C/'ecad/exports/wp09_system.xml');moved=netidentity(out)
    assert original==moved,'Relocated component or net partition changed'
    erc=read(dest/'relocated_erc.json')
    original_erc=read(C/'ecad/exports/wp09_system_erc.json')
    def violations(x):return sorted((v.get('severity'),v.get('type'),v.get('description')) for sheet in x['sheets'] for v in sheet.get('violations',[]))
    assert violations(erc)==violations(original_erc)
    assert len(violations(erc))==3
    write(receipt,{'status':'PASS_NATIVE_ECAD_RELOCATED_EXPORT_AND_NET_PARTITION__ERC3_RETAINED','utc':datetime.now(timezone.utc).isoformat(),
      'native_files':files,'actual_component_count':len(moved[0]),'actual_net_count':len(moved[1]),'original_and_relocated_partition_equal':True,
      'ERC_open_errors':3,'runs':runs,'scope':'Native schematics and local symbol libraries exported from a second directory; does not prove hardware functionality or every Python generator independently relocatable.'})
    print(receipt)
else:
    r=read(receipt)
    assert r['status'].startswith('PASS')
    for f in r['native_files']:
        assert sha(C/f['source'])==f['sha256']
        assert sha(C/f['relocated'])==f['sha256']
    assert (C/'ecad/MASTER_BOM.csv').is_file()
    assert (C/'results/DELIVERY_STATUS.json').is_file()
    roots=['ecad','electrical_delta','software_native','propulsion','sources/propulsion_intake']
    selected=[]
    for d in roots:
        for p in sorted((C/d).rglob('*')):
            if not p.is_file() or any(x in {'__pycache__','.git','runtime_config'} for x in p.parts):continue
            if p.name.startswith('~') or p.suffix in {'.pyc','.kicad_prl','.lck'} or 'cp310' in p.name:continue
            selected.append(p)
    results=['DELIVERY_STATUS','STOP_ECAD_INTEGRATION','STOP_CIRCUIT_DELIVERY','STOP_CIRCUIT_VERIFICATION','STOP_CIRCUIT_GX11_ERRATUM','STOP_BOM_INTEGRATION','DM_NATIVE_INTAKE','DM_NATIVE_VERIFICATION','DM_PUBLIC_REFERENCE_DELTA','PROPULSION_RESUME_20260908','ELECTRICAL_RESUME_RELOCATION']
    selected += [C/'results'/f'{x}.json' for x in results]
    selected += [C/'review'/f for f in ['DM_NATIVE_REVIEW.json','DM_NATIVE_REVIEW_ZH.md','DM_NATIVE_REVIEW.py','STOP_CIRCUIT_REVIEW.json','STOP_CIRCUIT_REVIEW_ZH.md','STOP_CIRCUIT_REVIEW.py']]
    selected += [C/'tools'/f for f in ['integrate_stop_ecad.py','verify_stop_ecad_integration.py','package_electrical_resume.py','stop_circuit_build_r2.py','stop_circuit_verify_r2.py','build_stop_bom.py','dm_native_intake.py']]
    assert all(p.is_file() for p in selected),[str(p) for p in selected if not p.is_file()]
    selected=sorted(set(selected))
    entries=[{'path':p.relative_to(C).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in selected]
    archive=C/'electrical_reference/WP09_ELECTRICAL_RESUME.zip'
    assert not archive.exists(),'Do not overwrite a sealed prior archive.'
    intro='''# 电气 / B601 DM / 推进接口增量
解压后以 ecad/wp09_system.kicad_sch 打开实际系统原理图，或 ecad/exports/WP09_SYSTEM_AND_STOP.pdf 阅读。
ecad/MASTER_FROM_TO.csv 是当前72条外部接线主表；MASTER_BOM.csv是分层BOM。
software_native/upstream 为官方cp313 Windows x64本地解包，不自动安装或打开硬件。
propulsion/resume_20260908/README_ZH.md给出本轮受来源约束的接口合同。
results/DELIVERY_STATUS.json明确整机设计未完成。
原生KiCad文件在第二目录重新导出且94元件/96网分区一致，保留3项ERC供源错误。没有将原理图可迁移扩大为所有计算脚本脱离原父工程可执行；引用父N/R/F绝对路径的脚本仍需原项目依赖。
本轮 sources/propulsion_intake 原厂来源及 electrical_delta/sources 原厂PDF随包。仍引用原父N/R/F工程的证据和生成依赖在原项目中，不保证所有脚本独立运行。本包未包含机械CAD、用户到货修订或未知推进ICD，不能据此上电或执行推进。
'''
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected:z.write(p,p.relative_to(C).as_posix())
        z.writestr('START_HERE_ZH.md',intro)
        z.writestr('PACKAGE_SHA256.json',json.dumps(entries,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(entries)+2
        for e in entries:assert hashlib.sha256(z.read(e['path'])).hexdigest()==e['sha256'],e['path']
    write(C/'results/ELECTRICAL_RESUME_DELIVERY.json',{'status':'PASS_RELOCATED_NATIVE_ECAD_AND_HASH_VERIFIED_SOURCE_ARCHIVE','utc':datetime.now(timezone.utc).isoformat(),
      'archive':{'path':str(archive),'bytes':archive.stat().st_size,'sha256':sha(archive)},'source_files':len(entries),'archive_entries':len(entries)+2,'CRC_verified':True,'entry_SHA_verified':True,
      'relocation_receipt':{'path':str(receipt),'sha256':sha(receipt)},'schematic_components':94,'nets':96,'external_connections':72,'ERC_errors_retained':3,'hardware_io':0,'full_mechatronic_design_complete':False,
      'all_generators_standalone_relocatable':False})
    print(json.dumps({'archive':str(archive),'source_files':len(entries),'bytes':archive.stat().st_size}))
