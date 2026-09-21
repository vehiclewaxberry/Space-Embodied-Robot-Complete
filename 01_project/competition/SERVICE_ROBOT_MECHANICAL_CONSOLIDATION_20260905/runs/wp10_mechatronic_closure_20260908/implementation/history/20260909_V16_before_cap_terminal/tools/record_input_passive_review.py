from pathlib import Path
import json,hashlib,datetime,shutil
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
expected={
 'tools/shared_battery_path.py':'24414c83ee6beefbde5bdda58f65d4219744f8b0a9c9129b8a2afb56d0da1ef4',
 'tools/check_input_passives.py':'00d7b2589454013b034ec5ec1fa4e14f45429bf7b9d624b508f41892c8eb1e50',
 'tools/integrate_power_loop.py':'56cc9427c63bd331cdc73736513ce85bd0c39f7f6037b6ed3ed650da98f54d48',
 'power/SHARED_BATTERY_PATH_CALCULATIONS.json':'08cfe8f1c4dd6cb0698645213d2f98d616ddb302c0c25824194a4d60f9102a4d',
 'power/INPUT_PASSIVE_CALCULATIONS.json':'22670b87a1e6745288404ab7673bd2806bac8b2a3b00b3dc8ceac4cdadda8e94',
 'thermal/INPUT_PASSIVE_HEAT_LOADS.csv':'a8805c81210ed7b119f91607ae5db1ef5edb38119098ecbb8e81f3e59f90a1e9',
 'ecad/wp10_system.xml':'4e30bdd280ed5cf7ee2c0a826bb9f0955ae06b906427a76b6a0f1a6d41c70382',
 'ecad/WP10_PASSIVES.pretty/CP_ChemiCon_VS_D30_P10_2mm_Candidate.kicad_mod':'eba2d69b55e45697dc297444b4adef4ab85c83f78ed41bb90b1c11d217aa2e8c'}
assert all(sha(p)==v for p,v in expected.items())
dump('results/INPUT_PASSIVE_READONLY_REVIEW.json',dict(
 schema='WP10_INPUT_PASSIVE_READONLY_REVIEW_V13',reviewer='/root/sw_volume_api_readonly',
 mode='READ_ONLY; root alone wrote sources and this receipt',
 review_complete=True,unrepaired_findings=[],reviewed_files=expected,
 method='Independent two-current Newton, no import of root solver; separate segmented Simpson ideal-precharge integration; OEM figures p1/p3 and native XML/footprint review.',
 states=384,max_voltage_difference_V=7.11e-15,max_current_difference_A=1.42e-14,
 max_saved_KVL_residual_V=5.33e-15,max_constant_power_residual_W=1.14e-13,
 heat_rows=3648,heat_case_states=384,max_heat_balance_residual_W=1.71e-13,
 max_precharge_time_difference_s=1.73e-18,max_precharge_I2t_difference_A2s=2.22e-12,
 initial_ESR120_upper_ohm=.113036,endurance_ESR120_upper_ohm=.376787,
 publication_clarifications=['Detailed INPUT heat CSV replaces the corresponding aggregate SHARED ledger; never add them.',
  'COLD C203 heat zero means no current battery-source contribution, not zero stored-charge discharge heat.',
  'C203 terminal-seal copper keepout, vent space and actual retention must be implemented in PCB/installation; footprint candidate is not release.'],
 physical_tests_executed=False,whole_design_complete=False))
dump('sources/INPUT_PASSIVE_DECISION_RECORD.json',dict(
 schema='WP10_PUBLIC_INPUT_PASSIVE_DECISION_RECORD_V1',date='2026-09-09',
 kind='ROOT_RECORDED_SOURCE_FACTS_AND_DECISION; not an OEM document or source PDF byte archive',
 active_F201=dict(MPN='1025HC30-RTR',source_url='https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf',
 revision='Technical Data10572 Effective June2025, supersedes June2017, 9pp',
 evidence='Official web tool parsed pp1-9; read-only reviewer independently checked same publication.',
 local_PDF_archive=False,local_download_attempt='urllib request timed out after35s; reviewer reported2 earlier timeouts; screenshot unavailable',
 selected_as='Engineering circuit candidate with protection and space qualification OPEN',
 facts=dict(rated_A=30,rated_VDC=72,interrupt_A=500,test_tau_s_lt=1e-6,cold_R_typical_ohm=.0017,melting_I2t_typical_A2s=112,
 cold_R_test='20C <10%In reference only',melting_test='10In, not total clearing',
 recommended_copper_oz=3,recommended_min_trace_width_mm=10,
 aerospace_exclusion_found=False,aerospace_qualified=False,unread_recommended_pad_diagram=True)),
 rejected_F201=dict(MPN='0456030.ER',source_url='https://www.littelfuse.com/assetdocs/littelfuse_fuse_456_datasheet.pdf?assetguid=d86b18f9-14fa-4764-87ff-8aec12e9a89d',
 revision='Revised September18 2025, p3',reason='Explicit aerospace application exclusion in manufacturer document; not adopted into current F201.',
 source_PDF_local_archive=False,local_download='403; official web document read'),
 C203=dict(MPN='ELXG101VSN222MR50S',facts_from_local_files=['sources/lxg_2026.pdf','sources/chemi_al_precautions_2026.pdf','sources/lxg_2200_100_product.html'],
 aerospace_consultation_required=True,OEM_CAD_download='Maintenance HTML, not ZIP; no OEM BRep acquired',
 catalog_exact_search='step.parts query reachable, zero exact matches; see INPUT_PASSIVE_SOURCE_MANIFEST.json'),
 vendor_contact_executed=False,purchase_executed=False))
# Preserve legacy publisher but route the current entry to V13.
p=A/'tools/publish_shared_battery_addendum.py'
h=A/'history/20260909_V12_before_input_passives/tools/publish_shared_battery_addendum.py'
if not h.exists():shutil.copy2(p,h)
p.write_text('"""Current publisher bridge; V12 implementation is archived."""\nfrom pathlib import Path\nimport runpy\nrunpy.run_path(str(Path(__file__).resolve().with_name("publish_input_passive_addendum.py")),run_name="__main__")\n',encoding='utf-8')
# Explicitly retain the independent reviewer's COLD and seal-face cautions in prose.
p=A/'tools/publish_input_passive_addendum.py';s=p.read_text(encoding='utf-8')
s=s.replace('冷态开关断开时不从电池端虚构电容泄漏供电，电容电压保持为空。','冷态开关断开时不从电池端虚构电容泄漏供电，电容电压保持为空。COLD泄漏热记0仅指电池输入贡献；未知储能电容的实际放电热没有被算成0。')
s=s.replace('套管不能当绝缘保证。','套管不能当绝缘保证。端封面下的铜箔避让尚未进入实际PCB，封装的二维外框不能代替该项检查。')
p.write_text(s,encoding='utf-8')
p=A/'tools/seal_completed_package.py';s=p.read_text(encoding='utf-8')
s=s.replace('native_delta_shared_battery_publish','native_delta_input_passive_build')
s=s.replace("review=json.loads((A/'results/SHARED_BATTERY_READONLY_REVIEW.json').read_text())","review=json.loads((A/'results/INPUT_PASSIVE_READONLY_REVIEW.json').read_text())")
s=s.replace("assert sha(A/'power/SHARED_BATTERY_PATH_CALCULATIONS.json')==review['reviewed_calculations_sha256']\nassert sha(A/'thermal/SHARED_BATTERY_HEAT_LOADS.csv')==review['reviewed_thermal_csv_sha256']", "assert all(sha(A/p)==v for p,v in review['reviewed_files'].items())\nassert json.loads((A/'results/DELIVERY_DECISION.json').read_text())['revision']=='V13_INPUT_PASSIVE_SELECTION'")
s=s.replace('wp10_shared_battery_final_package.tmp.zip','wp10_input_passive_final_package.tmp.zip')
p.write_text(s,encoding='utf-8')
print('Read-only review SHA matched; current publisher and finalizer now target V13.')

