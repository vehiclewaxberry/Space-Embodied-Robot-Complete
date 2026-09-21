"""Copy pinned CAD inputs into this candidate; never cache beside historical sources."""
from pathlib import Path
import hashlib, json, shutil
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
vendor=ROOT/'20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/vendor_reference_linklocal'
gripper=ROOT/'20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1/01_cad'
m3r=ROOT/'20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r'
sources={n:vendor/f'B50_REF_{n}_LINKLOCAL.step' for n in ['base_link']+[f'link{i}' for i in range(1,7)]}
sources.update(dict(gripper_link=gripper/'B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1.step',gripper_left=gripper/'B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1.step',gripper_right=gripper/'B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1.step',m3r_a=m3r/'M3R_STAGE_A_REVB_WORKING.step',m3r_b=m3r/'M3R_STAGE_B_REVB2_WORKING.step'))
out=HERE/'inputs';out.mkdir(exist_ok=True)
ledger=[]
for name,src in sources.items():
    dst=out/f'{name}.step';digest=hashlib.file_digest(src.open('rb'),'sha256').hexdigest()
    if not dst.exists() or hashlib.file_digest(dst.open('rb'),'sha256').hexdigest()!=digest:shutil.copy2(src,dst)
    ledger.append(dict(name=name,source=str(src.relative_to(ROOT)).replace('\\','/'),copy=str(dst.relative_to(HERE)),sha256=digest,bytes=src.stat().st_size,units='mm',classification='IMPORTED_NOMINAL_BREP_CANDIDATE'))
(HERE/'SOURCE_INPUTS.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
print(json.dumps(dict(copied=len(ledger),bytes=sum(x['bytes'] for x in ledger))))
