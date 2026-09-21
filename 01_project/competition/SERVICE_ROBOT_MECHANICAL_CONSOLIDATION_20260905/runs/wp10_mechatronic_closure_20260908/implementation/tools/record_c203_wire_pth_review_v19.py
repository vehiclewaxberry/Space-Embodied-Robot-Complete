"""Record completed source-level review; preserve contact-profile concern."""
from pathlib import Path
import hashlib,json
A=Path(__file__).resolve().parents[1]
files={
 'tools/apply_c203_wire_pth_v19.py':'db0c04a332ddfd8b9b4a815127b625e8cbdc822e96b7e88842280410bebd57c5',
 'tools/check_c203_wire_pth_source_v19.py':'c0a4d0a0631f1898bda39b882f439be67265f98ea9d8cedcee64c7fe48dedcac',
 'results/C203_WIRE_PTH_SOURCE_CHECK_V19.json':'5629f62249e755be01c59757646e54d1374177b5a7a5cf25c2109504348e4f8c',
 'ecad/wp10_c203_terminal.kicad_pcb':'268b5c5f02f72b62d3c2e4c8cc5725c3f21d3e53de3c2cf6283996c27502f831',
 'ecad/WP10_PASSIVES.pretty/C203_SingleFace_Terminal_D30_P10_W18.kicad_mod':'27478c868709c1e46bfa4c828abf4f76911a0722701bfd789fbb3f5c737767a5',
 'power/cap_terminal_sources/C203_SingleFace_Terminal_D30_P10_W18.kicad_mod':'27478c868709c1e46bfa4c828abf4f76911a0722701bfd789fbb3f5c737767a5',
 'power/CAP_TERMINAL_DEFINITION.json':'54373d104556986d4a0c18bd2363bfda9a126bfa077e2392c87d4342628ca617',
 'mechanical/INPUT_CAP_MOUNT_DESIGN.json':'95b2c61cc18439a2a22d267713fcb0634601142f7a3dbe241e3dd81c8e6f947e',
 'mechanical/input_cap_pcb.step.py':'72016d3fac0f9d316f2a972ee6937c159028679d7a0fae10903a9cde80d4668e',
 'tools/cap_terminal_native.py':'df870bbd3e4131dbf241215729920ebe4bdb8a2f95cc8c7939a8a6b52ad3c6b9',
 'tools/check_cap_terminal_copper.py':'1188a0a7922dd494690a6d61953c59ba29a843266e9125a17b6569ae29a119d9',
 'power/CAP_HARNESS_DEFINITION_V19.json':'c8403a5722a17fd018e13fc3767389d33f25ce1a16d3a04064da9af7395964f8',
 'results/CAP_HARNESS_PATH_V19.json':'846aad4f3ff5c6657e4b339172625c65a5fcbd17b0c1457b49027e0093f75d67',
 'power/CAP_HARNESS_ELECTROTHERMAL_V19.json':'881cf56469fe0337febee4db1e27ad028c7d8112af5d86eb8fb1892a9da1e698',
 'thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv':'3d3b23cddb71834be33eb66641cbd94be7dd2ef3dabdd5a621d19b25b9333993',
 'thermal/ACTIVE_HEAT_LOADS_V19.json':'112904048cfc0bfbfd66377e5b2410c3c29e9523c773fee9443ce8142811e142',
 'history/20260909_V19_before_wire_pth/ARCHIVE_SHA256.json':'149a75c66ec045b77101f5f7142487d458dc447ead2e93ad7b9025a1bd2695e4'}
assert all(hashlib.sha256((A/p).read_bytes()).hexdigest()==h for p,h in files.items())
record=dict(status='PASS_SCOPED_SOURCE_DELTA_WITH_CONTACT_PROFILE_OPEN',reviewer='/root/cap_terminal_review',reviewed_files=files,
 actual_method='Independent complete PCB AST comparison, library/canonical comparison and five in-memory counterexamples; compare route/heat outputs against archived bytes.',
 verified='Only two WIRE hole groups, footprint description and stackup changed; nets/traces/outline/rules/CAP groups identical. Heat CSV identical; only source bindings changed in route/heat reports.',
 nominal_front_land_to_max_body_mm=2.5489898732233307,
 contact_profile_concern='Adding70um front copper while reducing core thickness can create an approximately70um nominal surface-height step between copper and no-copper areas. Mask profile, finished thickness and flatness are unbound;70um is not a measured value or tolerance bound. STEP envelope and hole positions preserved do not prove physical CAP/frame contact preserved.',
 native_readback=False,native_DRC=False,copper_geometry_recomputed=False,physical_contact_verified=False,manufacturing_qualified=False,whole_design_complete=False)
(A/'results/C203_WIRE_PTH_READONLY_REVIEW_V19.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('Recorded17 reviewed file hashes; contact surface-profile concern retained')
