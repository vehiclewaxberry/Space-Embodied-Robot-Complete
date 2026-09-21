from pathlib import Path
import json,csv,hashlib,collections,re,urllib.parse
N=Path(__file__).resolve().parents[1];R=N.parent;F=R/'functional_closure';B=R.parent.parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def bind(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))

# One current BOM. Received hardware is UNKNOWN, not inferred from absence of a purchase action.
bom=list(csv.DictReader((F/'ecad/ELECTRICAL_BOM.csv').open(encoding='utf-8-sig')))
for row in bom:
 row.pop('ordered',None);row.pop('qualified',None)
 if row['ref']=='K1':row.update(pn='Sensata GIGAVAC GX11CAB',role='EXTERNAL_GSE_SINGLE_POSITIVE_CONTACTOR_CANDIDATE',source='GX11 Rev6 2015-10-23 p3-4; power/POWER_DESIGN_ZH.md')
 if row['ref']=='PDU':row.update(pn='P60 PDU200 8S / Dock X2 / Reg0 12V CH1/6 / Reg1 3.3V CH2 / Reg2 5V CH0/3/5',source='PDU DS2.6/OSF4.5; Dock3.1')
 if row['ref'] in ['RS_A','RS_B']:row['role']='EXTERNAL_RS422_ELECTRICAL_LOOP; no VACCO protocol claim'
 row.update(actual_received='UNCONFIRMED',build_approved=False)
for ref,pn,qty,role,source in [
 ('DOCK','NanoPower P60 Dock 8S',1,'LOW_POWER_CANDIDATE','DS3.1 OSF5.2'),('ACU','NanoPower ACU200 8S / X1',1,'LOW_POWER_CANDIDATE','DS2.3 OSF4.0'),('BPX','NanoPower BPX100Wh 8S1P',1,'LOW_POWER_CANDIDATE','DS1076870 1.1.0'),
 ('L01_L02_SRC','Samtec SFSD-15-28-G-03.00-S',1,'GROUND_P1_SHORT_LEAD; total hot-loop<=180mOhm','POWER_CONTRACT / manufacturer source'),('L01_L02_DST','Molex510210400',1,'GROUND_P1_HOUSING','A3200 DS2.0; Molex PS RevAD'),('L01_L02_CONTACT','Molex500798000',2,'GROUND_P1_CRIMP','Molex PS51021-024 RevAD'),
 ('GSE_PCB','WP09R RS422 splice R1 40x30mm',1,'NEW_DERIVED_GROUND_BOARD; no manufacturing release','ecad/rs422_gse_splice.kicad_pcb'),('CIC_REF','AZUR81442 3G30A Advanced 4x8 CIC',84,'REFERENCE_ARRAY_ONLY; not integrated/purchase authorization','AZUR DB00010891-01 2025-04-11'),
 ('STOP_CONTROL','UNBOUND controller / monitored24V coil supply',1,'OPEN_HARDWARE_RESPONSIBILITY','GX11 minimum contact5V0.1mA; POWER_DESIGN'),('FPP','UNBOUND full FPP/RBF/dearm realization',1,'OPEN_GSE_RESPONSIBILITY','Dock DS3.1'),('PV_BLOCKING','UNBOUND 12 string blocking diodes',12,'ARRAY_DESIGN_REQUIREMENT; PN not frozen','ACU2.3 input contract')]:
 bom.append(dict(ref=ref,pn=pn,quantity=qty,role=role,source=source,actual_received='UNCONFIRMED',build_approved=False))
csvout(N/'ecad/MASTER_BOM.csv',bom)
sourcefiles=[dict(path=p.relative_to(N).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((N/'sources').rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
csvout(N/'results/REUSE_SOURCE_FILES.csv',sourcefiles)

native={};parent_bindings=js(R/'results/NATIVE_BINDING_MANIFEST.json')['states'];newids=None
for state,receiptname in [('service','NATIVE_SERVICE_RECOVERY_V2.json'),('parking','NATIVE_PARKING.json'),('released','NATIVE_RELEASED.json')]:
 p=N/'results'/receiptname;j=js(p);target=N/'mechanical/native'/('WP09R_'+state.upper()+'.SLDASM')
 assert j['status']=='PASS_FIXED_NATIVE_DELTA_WITH_HASH_BOUND_PARENT' and j['component_count']==705 and j['expected_solid_count']==1086
 assert j['new_body_count_actual']==5 and j['retained_solid_count_hash_bound']==1081 and j['all_metadata_verified'] and j['parent_unchanged']
 assert sha(target)==j['native_save']['sha256'];assert len({x['id'] for x in j['cold_components']})==705
 assert all(sha(Path(x['native_path']))==x['native_sha256'] for x in j['rows'])
 parent={x['id']:x for x in parent_bindings[state]}
 for row in j['rows'][:700]:assert row['T_S_local']==parent[row['id']].get('native_T_local_to_S',parent[row['id']]['T_S_local'])
 native[state]=dict(native=bind(target),receipt=bind(p),component_count=705,expected_solids=1086,current_new_solids_actual=5,retained_solids_hash_bound=1081,representation_counts=dict(collections.Counter(x['representation_role'] for x in j['rows'])),all_metadata_verified=True,all_solids_reopened_this_turn=False,continuous_motion=False)
dm=js(N/'results/DM_OFFLINE_TEST_RESULTS.json');power=js(N/'results/POWER_CALCULATIONS.json');prop=js(N/'results/PROP_REUSE_CLOSURE.json');ecad=js(N/'results/ECAD_VERIFICATION.json');board=js(N/'results/NATIVE_BOARD_MATERIAL.json')
assert dm['tests_run']==29 and dm['failures']==0 and dm['errors']==0 and power['all_negative_controls_detected'] and prop['checks_passed']==36
assert ecad['exact_partition_match'] and board['status']=='PASS_NATIVE_BOARD_MATERIAL_AND_HOLE_VOLUME'
status=dict(status='FIXED_POSE_STRUCTURAL_DELTA_ACCEPTED__MATURE_REUSE_CANDIDATE_DELIVERED__FULL_SYSTEM_FUNCTION_OPEN',scope='current engineering candidate; no scientific/flight/manufacturing Gate transfer',native_states=native,standalone_board=dict(native=bind(N/'mechanical/native/RS422_GSE_SPLICE_BOARD.SLDPRT'),material_receipt=bind(N/'results/NATIVE_BOARD_MATERIAL.json'),current_assembly_member=False,total_nominal_stackup_mm=1.6,exported_substrate_mm=1.51),electrical=dict(connection_rows=70,endpoints=117,nets=47,old_rows_accounted=23,system_ERC_errors=1,splice_ERC_DRC_parity_unconnected_violations=0,graph_negative_controls=22,build_approved=False),protocol=dict(offline_tests=29,physical_io=0,rust_executed=False),power=dict(negative_controls=19,obc_voltage_conditionally_accepted=True,actual_supply_qualification=False,arm_flight_EPS_supported=False),propulsion=dict(source_checks=36,actual_flight_capability='UNKNOWN',mips_balanced_couple_envelope_required_case='NECESSARY_CONDITION_NOT_MET',full_mass_COM_inertia_complete=False),mechanical_main_status='CURRENT_FIXED_POSE_CANDIDATE_BOUNDED_FREEZE; change only against concrete remaining interface requirements',whole_mechanical_design_complete=False,whole_electrical_design_complete=False,continuous_motion_verified=False,manufacturing_release=False,flight_release=False,physical_tests_executed=0,legacy_physical_checklist_count=24,legacy_physical_checklists_status='NOT_EXECUTED',hardware_operations=0,scientific_gates_modified=False,accepted_URDF_modified=False,resource_guard='1400MiB own-child maximum /512MiB global floor retained; CAD serialized',opened_review_url='http://127.0.0.1:3251/REVIEW.html',source_file_count=len(sourcefiles),important_open_items=['GSE AC/PE and stop-control realization','K1/regen lost-input and thermal energy path','DM shipping cavity/revision/termination','P60/BPX same-configuration pins and protection','in-orbit arm power insufficient for360Wscreen','actual RCS position/concurrency/command/plume ICD','complete705 mass/COM/inertia','continuous harness/tool/strength verification'])
dump(N/'results/DELIVERY_STATUS.json',status)

# Verify the existing two frozen deliveries, without altering them.
parent_checks=[]
for base in [R,F]:
 for row in csv.DictReader((base/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')):
  p=base/row['path'];ok=p.is_file() and sha(p)==row['sha256'];parent_checks.append(dict(path=str(p),ok=ok))
assert all(x['ok'] for x in parent_checks),[x for x in parent_checks if not x['ok']]
dump(N/'results/PARENT_PRESERVATION.json',dict(status='PASS_FROZEN_PARENT_OUTPUT_HASHES',count=len(parent_checks),checks=parent_checks,scope='R646 and F162 published outputs; not a whole-project audit'))

# Update only the existing CURRENT, retaining exact old bytes in this package.
current=B/'CURRENT_candidate.md';backup=N/'inputs/CURRENT_before.md'
prefix='''# 当前工程入口：WP09R 成熟模块复用与结构候选收束

2026-09-07：从[本轮完整交付](runs/wp09_interfaces_20260907_1525/reuse_closure/README.md)与[可视化查看页](runs/wp09_interfaces_20260907_1525/reuse_closure/REVIEW.html)进入。三态SolidWorks各705组件/1086预期实体已完成本轮增量验收：全组件身份/哈希/变换冷读，新5实体实读，旧1081实体继承父本证据。另有独立RS422地面转接板原生SLDPRT。

实际KiCad系统含70连接记录/117端点/47网络，派生地面板ERC/DRC/板图一致性零违规；系统ERC保留1项停止链供电边界错误。完成29项真实DM协议离线测试、19项电源参数反例及36项推进源/需求核对。K1、P60板位和BPX针位冲突已定点修订；现有EPS不能承担360W机械臂在轨负载，真实推进ICD/功能仍开放。

本轮固定姿态结构候选可冻结；整机完整机械/电气功能、连续动作、制造与飞行放行仍未完成。详见[机器状态](runs/wp09_interfaces_20260907_1525/reuse_closure/results/DELIVERY_STATUS.json)。下方历史入口原样保留，“当前/本轮”均属于其记录时间。

---

'''
if not backup.exists():
 old=current.read_bytes();backup.write_bytes(old);current.write_bytes(prefix.encode('utf8')+old)
else:assert current.read_bytes()==prefix.encode('utf8')+backup.read_bytes(),'CURRENT changed after this run; leave untouched'
dump(N/'results/CURRENT_POINTER_UPDATE.json',dict(path=str(current),before_sha256=sha(backup),after_sha256=sha(current),prior_bytes_preserved=True,backup=str(backup)))

# Link checks on present Markdown/HTML deliverables, not on upstream research text.
if not (N/'results/FINAL_INTEGRITY.json').exists():dump(N/'results/FINAL_INTEGRITY.json',dict(status='PENDING_FINAL_LINK_AND_HASH_CHECKS'))
linkchecks=[]
for p in [N/'README.md',N/'ecad/README.md',N/'sources/REUSE_PACKAGE.md',N/'REVIEW.html']:
 s=p.read_text(encoding='utf8')
 targets=re.findall(r'\]\(([^)]+)\)',s) if p.suffix=='.md' else re.findall(r'(?:href|src)="([^"]+)"',s)
 for target in targets:
  target=target.strip('<>');u=urllib.parse.urlsplit(target)
  if u.scheme or target.startswith('#'):continue
  path=(p.parent/urllib.parse.unquote(u.path)).resolve();linkchecks.append(dict(source=str(p),target=str(path),ok=path.exists()))
assert all(x['ok'] for x in linkchecks),[x for x in linkchecks if not x['ok']]
# Active server logs/cache/staging are deliberately not immutable deliverables.
files=[]
for p in sorted(N.rglob('*')):
 rel=p.relative_to(N).as_posix()
 if not p.is_file() or any(x in p.parts for x in ['__pycache__','__cadgen__','runtime_config']) or rel.startswith('mechanical/native/work/') or 'review_server.' in p.name or rel in ['results/OUTPUT_SHA256.csv','results/FINAL_INTEGRITY.json']:continue
 files.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
csvout(N/'results/OUTPUT_SHA256.csv',files)
assert all(sha(N/r['path'])==r['sha256'] for r in files)
dump(N/'results/FINAL_INTEGRITY.json',dict(status='PASS_DELIVERY_HASHES_LINKS_AND_PARENT_PRESERVATION',sealed_files=len(files),parent_files_unchanged=len(parent_checks),local_links_checked=len(linkchecks),all_links_pass=True,link_checks=linkchecks,manifest_sha256=sha(N/'results/OUTPUT_SHA256.csv'),exclusions=['active review server logs','runtime_config','__pycache__','__cadgen__','native working copies','hash manifest itself and this receipt'],scope='integrity is not hardware qualification'))
print(json.dumps(dict(status=status['status'],files=len(files),parent_unchanged=len(parent_checks),local_links=len(linkchecks)),ensure_ascii=False))
