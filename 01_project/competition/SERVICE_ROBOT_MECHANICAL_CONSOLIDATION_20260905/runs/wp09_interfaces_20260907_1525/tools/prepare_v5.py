from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parents[1]
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V4.json').read_text())
c['schema']='WP09_INTEGRATION_HARNESS_CANDIDATE_V5'
c['revision_reason']='Measured V4: extend tray bores through its new elevation, separate four MIPS washer circles, move two EPS posts clear of retained harness reservation.'
c['mips_floor_holes_xy']=[[x,y] for x in (141,149) for y in (-53,53)]
c['eps_carrier_box'][0][1]=-13
c['eps_mount_xy']=[[x,-8 if y==-3 else y] for x,y in c['eps_mount_xy']]
(R/'inputs/INTEGRATION_HARNESS_CONTRACT_V5.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
for folder,file in [('candidate','integration_detail.py'),('tools','check_integration.py')]:
    p=R/folder/file;shutil.copyfile(p,p.with_name(p.stem+'_v4_frozen.py'))
    s=p.read_text().replace('CONTRACT_V4','CONTRACT_V5').replace('EMISSION_V4','EMISSION_V5').replace('CHECK_V4','CHECK_V5').replace('candidate/v4parts','candidate/v5parts').replace('integrated_bay_v4.step','integrated_bay_v5.step')
    if folder=='candidate':s=s.replace('tool=cyl(1.7,20,(x,y,-20))','tool=cyl(1.7,90,(x,y,-20))')
    p.write_text(s,encoding='utf-8')
