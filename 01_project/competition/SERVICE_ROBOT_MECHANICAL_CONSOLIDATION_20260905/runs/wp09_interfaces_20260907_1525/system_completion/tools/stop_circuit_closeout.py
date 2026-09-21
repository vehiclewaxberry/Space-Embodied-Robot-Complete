from pathlib import Path
import json,hashlib,shutil,datetime
C=Path(__file__).resolve().parents[1];E=C/'electrical_delta';S=E/'sources'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(C/'sources/power_intake/TPS3431_datasheet.pdf',S/'tps3431.pdf')
urlmap={}
for fn in ['MANIFEST.json','MANIFEST_ADDITIONAL.json']:
 for r in json.loads((S/fn).read_text()):
  if r.get('path'):urlmap[Path(r['path']).name]=r['url']
urlmap.update({'tps3431.pdf':'https://www.ti.com/lit/ds/symlink/tps3431.pdf','sn74lvc1g07.pdf':'https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf','sn74ahct1g125.pdf':'https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf'})
sources=[]
for p in sorted(S.glob('*.pdf')):
 assert p.read_bytes()[:4]==b'%PDF'
 sources.append(dict(file=p.name,path=str(p),sha256=sha(p),url=urlmap[p.name],bytes=p.stat().st_size))
dump(S/'FINAL_SOURCE_LOCK.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),official_pdf_count=len(sources),sources=sources,GX11_pdf_not_downloaded=True,GX11_text_receipt_sha256=sha(C.parent/'reuse_closure/sources/power/CONTACTOR_OFFICIAL_WEB_RETRIEVAL.json')))
v=json.loads((C/'results/STOP_CIRCUIT_VERIFICATION.json').read_text())
assert v['all_checks_pass'] and v['components']==71 and v['erc_errors']==3
calc=json.loads((E/'STOP_CIRCUIT_CALCULATIONS.json').read_text())
files=[p for p in E.rglob('*') if p.is_file()]
dump(C/'results/STOP_CIRCUIT_DELIVERY.json',dict(status='EDITABLE_PIN_LEVEL_STOP_CIRCUIT_CANDIDATE_AND_OFFLINE_EVIDENCE_DELIVERED__NOT_FULL_ELECTRICAL_RELEASE',components=71,connected_pins=222,nets=39,local_from_to_edges=183,checks_passed=v['passed'],checks_total=v['checks'],ERC_errors=3,ERC_warnings=0,ERC_PASS=False,source_pdfs=len(sources),schematic=str(E/'wp09_stop_circuit.kicad_sch'),netlist=str(E/'wp09_stop_circuit.net.xml'),pdf=str(E/'WP09_STOP_CIRCUIT.pdf'),overview=str(E/'STOP_CIRCUIT_OVERVIEW.png'),port_map=str(E/'STOP_PORT_MAP.json'),assembly_parent_master_mutated=False,actual_power_or_hardware_io=0,actual_PCB_layout=False,watchdog_component_model_ms=calc['watchdog_ms'],watchdog_CWD_leakage_not_bounded=True,UCC_input_current_upper_bound_unbound=True,full_chain_100ms_pass=False,full_electrical_design_complete=False,full_spacecraft_mechatronics_complete=False,scope='Commercial ground/prototype stop control; independent latch and driver schematic, no qualification',source_generators=[str(C/'tools/stop_circuit_build_r2.py'),str(C/'tools/stop_circuit_verify_r2.py')],files=[dict(path=str(p),sha256=sha(p)) for p in files]))
print(json.dumps(dict(status='CIRCUIT_CANDIDATE_DELIVERED',files=len(files),official_pdfs=len(sources),checks=v['passed'],ERC_errors=3)))

