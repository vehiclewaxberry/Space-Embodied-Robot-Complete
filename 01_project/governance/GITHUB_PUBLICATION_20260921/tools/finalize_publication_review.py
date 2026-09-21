"""Append bounded manual evidence to this review; never modifies compact files."""
from pathlib import Path
import json, datetime, hashlib

OUT = Path(__file__).resolve().parents[1]
p = OUT / 'PUBLICATION_REVIEW.json'
r = json.loads(p.read_text('utf-8'))
r['status'] = 'REVIEW_COMPLETE_WITH_SPECIFIC_ACTIONS_AND_UNRESOLVED_OEM_TERMS'
r['manual_review_completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
r['user_publication_authorization'] = {
    'public_github_requested': True,
    'scope': 'Complete hardware design and all necessary dependencies; replace obsolete remote content.',
    'repository': 'https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete',
    'authorization_does_not_select_owner_license': True,
    'this_reviewer_uploaded_or_modified_compact': False,
}
r['summary'] = {
    'high_specificity_secret_findings': len(r['high_specificity_secret_findings']),
    'windows_user_profile_path_files': len({x['path'] for x in r['personal_or_machine_path_findings'] if x['category']=='WINDOWS_USER_PROFILE_PATH'}),
    'F_G_absolute_path_files': len({x['path'] for x in r['personal_or_machine_path_findings'] if x['category']=='FG_ABSOLUTE_PATH'}),
    'privacy_scope_limit': 'Pattern scan of current 960 compact files, including UTF16 visible native strings. No original Git history or exhaustive native OLE/custom-property semantic review.',
    'engineering_complete_claim_supported': False,
    'publication_of_development_snapshot_requires_flight_qualification': False,
    'blanket_MIT_or_CERN_license_for_all_assets_supported': False,
}
r['plotly_license'] = json.loads((OUT/'license_candidates/Plotly.js_v3.1.0_LICENSE_SOURCE.json').read_text('utf-8'))
r['plotly_license']['candidate_path'] = 'license_candidates/Plotly.js_v3.1.0_LICENSE.txt'
r['plotly_license']['action'] = 'Add the exact license and copyright notice to publication staging and explicitly bind it to embedded Plotly.js 3.1.0 in the R6H viewer. Compact source remains unchanged.'
r['named_upstream_review'] = [
    {'upstream':'reBot-DevArm / B601','evidence':'Local LICENSE and README plus current official upstream README identify CERN-OHL-W-2.0 hardware; software separately Apache-2.0. Hardware STEP/BOM are public upstream assets.','source_url':'https://github.com/Seeed-Projects/reBot-DevArm','decision':'Do not repeat the obsolete blanket internal-only/nonredistributable claim. Preserve applicable CERN text, actual source/version mappings and modification notices; does not relicense unrelated OEM components.'},
    {'upstream':'BIRDSX-CAD','license':'MIT','decision':'Retain existing named notice and exact copyright/license text only for applicable BIRDS source/derivatives.'},
    {'upstream':'LC2102','license':'CERN-OHL-W-2.0','decision':'Retain existing separately sourced license and bind actual covered source/derivative assets.'},
    {'upstream':'motorbridge','license':'MIT','decision':'Retain existing named notice and exact copyright/license text for applicable files, not adjacent EDA/OEM assets.'},
    {'upstream':'oresat-kicad','evidence':'Only LICENSE_FETCH.json declaration, not a complete project- and version-bound license text.','decision':'Keep as reference declaration; do not claim the stored SPDX pointer proves complete project licensing.'},
    {'upstream':'KiCad libraries','selected_system_items':32,'source_url':'https://www.kicad.org/libraries/license/','evidence':'02_electrical/third_party_notices/KICAD_LIBRARIES_LICENSE.md and LICENSE_SOURCE_RECEIPT.json already exist.','decision':'Retain CC-BY-SA-4.0 library notices and design exception. Separate redistributable library collection obligations from project designs using it.'},
]
r['wurth_terms_review'] = {
    'product_page':'https://www.we-online.com/en/components/products/WP-THRSH',
    'footprint_download':'https://www.we-online.com/components/products/download/KiCad_WP-THRSH%20%28rev26b%29.zip',
    'model_download':'https://www.we-online.com/components/products/download/74651195%20%28rev1%29.stp',
    'datasheet_url':'https://www.we-online.com/components/products/datasheet/74651195R.pdf',
    'local_zip_entries':17,
    'local_zip_license_readme_terms_notice_named_entries':0,
    'imprint_url':'https://www.we-online.com/en/service/imprint',
    'imprint_finding':'Reserves copyright and restricts copying/distribution/modification/third-party availability of website contents for commercial purposes. It does not supply a specific public CAD redistribution license.',
    'general_terms_url':'https://www.we-online.com/files/pdf1/gtc-we-eisos-germany-en.pdf',
    'general_terms_section':'8.3',
    'general_terms_finding':'Documents and aids including drawings and models supplied to customers are restricted to contractual performance and require written consent for disclosure to third parties.',
    'applicability_limit':'General terms concern customers and contracts; applicability to these freely offered public CAD downloads is not established by this review. No CAD-download-specific redistributable license or prohibition for this exact public noncommercial GitHub scenario was located.',
    'conclusion':'UNRESOLVED_OEM_REDISTRIBUTION_SCOPE_WITH_REAL_RESTRICTIVE_TERMS_EVIDENCE',
    'not_concluded':['NOT_CLEARED alone proves prohibition','public download proves unrestricted redistribution','public noncommercial GitHub publication is categorically forbidden','project owns or can sublicense OEM models'],
    'practical_action':'Keep exact OEM source URLs, attribution and non-relicensing notice separate from project license. To make affirmative unrestricted redistribution claims, obtain model-specific permission or replace with independently authored interface-equivalent geometry/footprint. Do not silently remove only two standalone files while embedded copies remain.',
    'embedded_native_main':'01_mechanical/native/P_f011e65d5e5452c37d2b_e3e9a9.SLDPRT',
    'embedded_step_main':'01_mechanical/step/R6H_MAIN_PCBA_INSTALLED.step',
    'embedded_viewer':'01_mechanical/views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html',
    'embedded_board':'02_electrical/kicad/wp10/wp10_main_input.kicad_pcb',
    'source_geometry_references':['J204','J205','J206','J207'],
    'source_geometry_input':'R6H inputs/MAIN_GEOMETRY_COVERAGE.json, EXISTING_KICAD_MODEL, source rows V36_013/014/015/018',
}
r['missing_models_manual_review'] = {
    'installed_directory':'G:/Windows_program_file/Kicad/share/kicad/3dmodels/Connector_Molex.3dshapes',
    'files_in_installed_directory':89,
    'exact_required_models_found':0,
    'search_scope':'This installed Connector_Molex.3dshapes directory and compact MODEL_DEPENDENCIES.json; no assertion about every disk directory.',
    'action':'Acquire the exact five model identities, verify provenance/license and expected geometry before adding to publication staging; do not use a similarly named connector or rename another extension as STEP.',
    'blocks_schematic_or_PCB_parse':False,
    'blocks_complete_3D_dependencies_claim':True,
}
r['custom_material_library_review'] = {
    'path':'01_mechanical/docs/source_materials/GROUND_CANDIDATE_MATERIALS.sldmat',
    'generator':'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools/assign_native_materials.py::make_database',
    'evidence':'Generated XML with four candidate density entries; not identified as a copied commercial SolidWorks material database.',
    'decision':'No exclusion solely on old local_only tag. Preserve candidate-material limitations and project provenance.',
}
r['execution_recommendations'] = [
    {'id':'PUB-01','type':'CONCRETE_NOTICE_FIX','action':'Copy prepared Plotly MIT license into staging and link from third-party notices; keep existing named licenses.'},
    {'id':'PUB-02','type':'DEPENDENCY_COMPLETENESS','action':'Resolve the five exact Molex 3D dependencies or explicitly disclose that 3D completeness is not yet achieved; no effect on source PCB/schematic preservation.'},
    {'id':'PUB-03','type':'OEM_RIGHTS_SCOPE_UNRESOLVED','action':'Record Wurth restrictive terms and exact source provenance without misrepresenting either permission or prohibition. Any source-link-only replacement must cover embedded PCB and merged mechanical/viewer geometry and be revalidated.'},
    {'id':'PUB-04','type':'PUBLICATION_HYGIENE','action':'In staging, rewrite necessary executable paths as relative and retain a source-to-publication mapping. Preserve historical source hashes and do not treat all F/G references as secrets.'},
    {'id':'PUB-05','type':'ENGINEERING_TRUTH','action':'Keep existing OPEN_ITEMS and false full-spacecraft/ready-to-power/flight-ready fields. Describe the repository as an evolving integrated hardware design candidate.'},
    {'id':'PUB-06','type':'OWNER_RIGHTS_NOT_ASSIGNED','action':'Publishing owner-authored material does not require the reviewer to select an open-source license. Do not apply MIT/CERN blanket coverage or promise third-party unrestricted reuse.'},
]
r['review_limits'] = [
    'No CAD/ECAD application launched in this review; native portability relies on builder cold-open evidence.',
    'No final staged repository, remote history, final commit or upload was audited here.',
    'No patent, export-control or complete copyright-chain opinion; review is a bounded asset/provenance/notice inspection.',
    'Selected system-item tags cover 146 source items and are not a license census of all 960 compact files.',
]
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'status':r['status'],'review_file':str(p),'plotly_license_hash_verified':hashlib.sha256((OUT/r['plotly_license']['candidate_path']).read_bytes()).hexdigest()==r['plotly_license']['sha256']},ensure_ascii=False))
