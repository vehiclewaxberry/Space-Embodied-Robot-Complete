"""Record received independent review, with the exact source hashes the reviewer reported."""
from pathlib import Path
import hashlib,json
A=Path(__file__).resolve().parents[1]
expected={
'mechanical/INPUT_CAP_MOUNT_DESIGN.json':'342d187eb552701daf3f8bffea5a0dd50989298dc477480083c0b44a9f2b9965',
'mechanical/input_cap_mount_common.py':'54e0872ef908211c87a5056b2876471f4af6edd0e61620beb878c60afecc00f4',
'mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json':'a3949bc85ae7e914dce597352f845db2c0d8ae4456802254e5a203560321401a',
'tools/prepare_input_cap_mount.py':'211b3196ee803941b7cc87fbb5c3474d0782580eca701197fb48e19c355a1956',
'tools/check_input_cap_mount.py':'ec2654248c5e18c065a5d2e753deffb864f262b4641cc64da1de754d934f680d',
'results/INPUT_CAP_MOUNT_EXACT.json':'c23f6e2063c68b88c8ed4ef5e9ef06184645e832cf00c2498b3339ac40b5d4d2',
'mechanical/input_cap_deck.step':'9047ed512ace6208a8897f239365656ab1eb6701f9b881fe7d80f5fb4d9ca39a',
'mechanical/input_cap_carrier.step':'a1fb6003cc7a6ab353d75de30b0ce47792492b18c8b700df65839b9a11339968',
'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json':'c302bf5b4d5bf42ece6e9cec85c4c67d4b8b70631b79d7e838cadb3ce9151533',
'mechanical/INPUT_CAP_MOUNT_BRIEF.md':'30464b44544cd9e3f0d2e890391e3ed66dcf4fafe1b6c5349785d3407e7df904',
'tools/integrate_input_cap_mount.py':'52a8a6347125f1e7e41a3a68a2be1fa1bf47ee870687ceb910f5dd8a776f740f',
'mechanical/INPUT_CAP_INSTALLATION_BOM.csv':'ee9ad8d583b0051314e1b6512f82d7913b2e343c8d45c9f6fdf8d4914f860581',
'ecad/C203_MECHANICAL_INTERFACE.json':'91aaa92bf1648e6eb8b814e86c3b74e05f5308ba60c6a99bd261127fb52701a0',
'results/INPUT_CAP_FASTENER_STACK.json':'3d2984ddac9140082005119646f3026717a384967108aa8646e3bd7b934f2400'}
assert all(hashlib.sha256((A/q).read_bytes()).hexdigest()==h for q,h in expected.items())
out=dict(schema='WP10_C203_INSTALLATION_READONLY_REVIEW_V1',reviewer='/root/thermal_layout_readonly',recorded_by='root from read-only messages',review_complete=True,reviewed_files=expected,unrepaired_findings_in_declared_delta=[],fixed_findings=['Move deck screw heads off carrier legs; explicit through-hole and clamp-hole groups','Drill board holes after rail union','Bind actual footprint pads/drills and native isolated networks','Fail on undeclared parent-row changes, duplicate/missing IDs or wrong added list','Correct brief deck hole y and tool scope'],independent_algebra=dict(deck_removed_volume_mm3=108.950433226494,deck_bolt_projection_mm=2.1,lower_clamp_nominal_embed_mm=6,board_nominal_embed_mm=6.4),scope='Nominal source-defined installation delta only',open=['Unattributed previous OCP importer warning and whole old-source completeness','Whole965 assembly fit/native and full tool insertion','Actual clamp load, axial retention, creep, thermal/ripple environment and wiring','Maximum31mm envelope clearance is not clamp qualification for actual tolerance'],whole_design_complete=False,physical_tests_executed=False)
(A/'results/INPUT_CAP_MOUNT_READONLY_REVIEW.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print('Mechanical same-source read-only review recorded')
