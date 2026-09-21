from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parents[1]
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V5.json').read_text())
c['schema']='WP09_INTEGRATION_HARNESS_CANDIDATE_V6'
c['revision_reason']='Measured V5: one EPS post intersects existing arm-drive adapter. Move that post +3 mm in X and extend elevated tray edge to preserve a closed bore.'
c['eps_mount_xy']=[[-49,y] if x==-52 and y==-8 else [x,y] for x,y in c['eps_mount_xy']]
c['eps_carrier_box'][1][0]=-44
(R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
for folder,file in [('candidate','integration_detail.py'),('tools','check_integration.py'),('candidate','whole_integration.py')]:
    p=R/folder/file;shutil.copyfile(p,p.with_name(p.stem+'_v5_frozen.py'))
    s=p.read_text().replace('_V5','_V6').replace('/v5parts','/v6parts').replace('_v5.step','_v6.step')
    p.write_text(s,encoding='utf-8')
