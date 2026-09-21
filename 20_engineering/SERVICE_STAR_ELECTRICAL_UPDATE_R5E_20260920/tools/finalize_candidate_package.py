"""Finalize a bounded candidate package after independent reviews, not hardware release."""
from build_electrical_update import D, ROOT, read, write, sha, require
import csv

review=read(D/'results/reviewer/SELECTION_STAGE_REVIEW.json')
final_review=read(D/'results/reviewer/FINAL_REVIEW.json')
native=read(D/'results/reviewer/ECAD_CANDIDATE_INDEPENDENT_REVIEW.json')
local=read(D/'results/ECAD_CANDIDATE_VERIFICATION.json')
build=read(D/'results/BUILD_RECEIPT.json')
require(local['status']=='PASS', 'Local source/native checks failed')
require(native['status']=='PASS__CANDIDATE_PROPERTIES_ONLY' and not native['failed'], 'Independent native review failed')
require(review['independent_checks']['passed']==review['independent_checks']['total'], 'Independent component checks failed')
require('PENDING' not in str(review['candidate_schematic_xml_review']), 'Final independent appendix pending')
require(final_review['candidate_package_deliverable'] is True, 'Independent candidate delivery not accepted')
for path, expected in final_review['reviewed_current_files'].items():
    require(sha(ROOT/path)==expected, 'Final reviewed input changed: '+path)
for path, expected in review['reviewed_hashes'].items():
    require(sha(ROOT/path)==expected, 'Reviewed input changed: '+path)
for row in local['source_unchanged_checks']:
    require(row['unchanged'] and sha(ROOT/row['path'])==row['sha256'], 'Protected source changed')
require(sha(D/'results/ECAD_CANDIDATE.xml')==local['candidate_xml_sha256'], 'Native candidate changed')
require(sha(D/review['report'])==review['report_sha256'], 'Independent report changed')
evidence=['results/BUILD_RECEIPT.json','results/GAP_DISPOSITION_45.json',
          'results/ECAD_CANDIDATE.xml','results/ECAD_CANDIDATE_VERIFICATION.json',
          'results/reviewer/SELECTION_STAGE_REVIEW.json','results/reviewer/FINAL_REVIEW.json','results/reviewer/ECAD_CANDIDATE_INDEPENDENT_REVIEW.json',
          'results/ELECTROTHERMAL_INPUT_UPDATE.json','results/NEXT_ELECTRICAL_WORK.json',
          'bom/ELECTRICAL_SELECTION_BOM_R5E.csv','bom/ECAD_ECO_R5E.csv','inputs/PRIMARY_SOURCES.json']
status={
    'schema':'R5E_FINAL_CANDIDATE_DELIVERY_V1','date':'2026-09-20',
    'delivery_status':'CANDIDATE_SELECTION_AND_ANNOTATED_ECAD_DELIVERED',
    'engineering_status':'HOLD__FUNCTIONAL_ECO_PCB_CAPACITANCE_PROTECTION_AND_THERMAL_VALIDATION_OPEN',
    'scope':'地面工程样机的电源/STOP子系统候选更新；不是整星电气完成裁决',
    'historical_45_dispositions':{'direct_passive_candidates':32,'IC_rating_updates':7,'composite_R305_ECO':1,'interface_or_board_copper_classifications':5},
    'supplemental_identity_recovered':['U301'],
    'BOM_rows':249,'logical_real_candidate_refs':219,'candidate_pieces_if_R305_split_implemented':220,
    'candidate_sheets':15,'annotated_sheets':11,'annotated_refs':46,'candidate_property_count':278,
    'pin_net_pairs':795,'nets':197,'functional_ECAD_changed':False,'PCB_changed':False,
    'candidate_custom_properties_applied':True,
    'local_verification':{'passed':local['checks_passed'],'total':local['checks_total']},
    'independent_component_checks':review['independent_checks'],
    'independent_candidate_XML_checks':{'passed':native['checks_passed'],'total':native['checks_total']},
    'independent_engineering_review_status':review['status'],'review_dimensions':review['rounds'],
    'independent_candidate_data_status':final_review['candidate_data_status'],
    'candidate_package_deliverable':True,
    'primary_source_records':len(read(D/'inputs/PRIMARY_SOURCES.json')),
    'local_primary_PDFs':len(list((D/'docs/hardware/datasheets').glob('*.pdf'))),
    'current_CAD':'20_engineering/SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920',
    'CAD_geometry_updated':False,'mass_properties_updated':False,
    'historical_HANDOFF_or_Gates_rewritten':False,
    'ready_to_power':False,'manufacturing_release':False,'procurement_release':False,'flight_ready':False,
    'evidence':{p:sha(D/p) for p in evidence},
}
write('results/RELEASE_STATUS.json',status)
manifest=D/'PACKAGE_SHA256.csv'
files=sorted(p for p in D.rglob('*') if p.is_file() and p!=manifest and '__pycache__' not in p.parts)
report=ROOT/'01_project/competition/电气选型更新_R5E_20260920.md'
files.append(report)
with manifest.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['workspace_relative_path','sha256','bytes']);w.writeheader()
    for p in files:
        w.writerow({'workspace_relative_path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
pointer=ROOT/'20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json'
if pointer.exists():
    old=read(pointer)
    require(old.get('package')==D.relative_to(ROOT).as_posix(),'Do not overwrite another electrical release pointer')
import json
pointer.write_text(json.dumps({'schema':'SERVICE_STAR_ELECTRICAL_CANDIDATE_POINTER_V1',
    'package':D.relative_to(ROOT).as_posix(),'scope':status['scope'],
    'release_status':(D/'results/RELEASE_STATUS.json').relative_to(ROOT).as_posix(),
    'release_status_sha256':sha(D/'results/RELEASE_STATUS.json'),
    'manifest':manifest.relative_to(ROOT).as_posix(),'manifest_sha256':sha(manifest),
    'user_report':report.relative_to(ROOT).as_posix(),'user_report_sha256':sha(report),
    'procurement_release':False,'manufacturing_release':False,'ready_to_power':False,'flight_ready':False},
    ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print({'delivery_status':status['delivery_status'],'engineering_status':status['engineering_status'],
       'manifest_file_count':len(files),'pointer':str(pointer),'review_status':review['status']})
