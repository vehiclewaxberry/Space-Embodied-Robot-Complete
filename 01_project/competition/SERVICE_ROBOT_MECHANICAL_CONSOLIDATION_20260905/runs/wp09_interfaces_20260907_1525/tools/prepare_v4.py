"""Preserve V3 negative evidence; derive V4 only from measured interferences."""
from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parents[1]
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V3.json').read_text())
c['schema']='WP09_INTEGRATION_HARNESS_CANDIDATE_V4'
c['revision_reason']='Measured V3: 16 material overlaps and one old harness reservation overlap. Raised EPS tray above existing trunk supports; adjusted cradle holes/notch and two route handoff coordinates.'
c['mips_floor_holes_xy']=[[x,y] for x in (143,149) for y in (-53,53)]
c['upper_deck_notch_box'][0][1]=-50;c['upper_deck_notch_box'][1][1]=50
c['eps_box'][0][2]=57.5;c['eps_box'][1][2]=86.5
c['eps_carrier_box'][0][2]=53;c['eps_carrier_box'][1][2]=55
c['eps_support']={'post_od_mm':8,'post_id_mm':3.4,'post_z_mm':[-8.5,53],'rod_z_mm':[-17.5,61.5],'thread':'M3 nominal smooth custom tie-rod; thread class/material/locking not released'}
c['clamp_stations'][0]['x']=-40
c['feedthrough_xy'][0][0]=144
for p in c['routes']['PROP_PWR']['waypoints'][1:]:p[0]=144
c['routes']['PROP_DATA']['waypoints'][0][0]=78;c['routes']['PROP_DATA']['waypoints'][1][0]=78
(R/'inputs/INTEGRATION_HARNESS_CONTRACT_V4.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(R/'candidate/integration_detail.py',R/'candidate/integration_v3_frozen.py')
p=R/'candidate/integration_detail.py';s=p.read_text().replace('CONTRACT_V3','CONTRACT_V4').replace('EMISSION_V3','EMISSION_V4').replace('EMISSION_V3','EMISSION_V4').replace('EMISSION_V3','EMISSION_V4')
s=s.replace("out=R/'candidate/parts'","out=R/'candidate/v4parts'").replace("R/'candidate/integrated_bay.step'","R/'candidate/integrated_bay_v4.step'")
s=s.replace("for n,xy in enumerate(c['eps_mount_xy']):hardware('P60_HOST_'+str(n),xy,-6,-11.5)",'''for n,(x,y) in enumerate(c['eps_mount_xy']):
        prefix='P60_HOST_'+str(n)
        add(prefix+'_POST',cyl(4,61.5,(x,y,-8.5))-cyl(1.7,61.5,(x,y,-8.5)))
        add(prefix+'_ROD',cyl(1.5,79,(x,y,-17.5)),'SIMPLIFIED_PROXY',qualification=c['eps_support']['thread'])
        for role,tag,z,sgn in [('washer','TW',55,1),('nut','TN',55.5,1),('washer','BW',-11.5,-1),('nut','BN',-12,-1)]:
            loc=Plane(origin=(x,y,z),x_dir=(1,0,0),z_dir=(0,0,sgn)).location
            add(prefix+'_'+tag,catalog[role].moved(loc),'SIMPLIFIED_PROXY',catalogue=c['catalogue_parts'][role])''')
p.write_text(s,encoding='utf-8')
shutil.copyfile(R/'tools/check_integration.py',R/'tools/check_integration_v3_frozen.py')
p=R/'tools/check_integration.py';s=p.read_text().replace('CONTRACT_V3','CONTRACT_V4').replace('EMISSION_V3','EMISSION_V4').replace('CHECK_V3','CHECK_V4')
s=s.replace("for st in c['clamp_stations']:\n",'''for n in range(4):
            for tag in ['TN','BN']:
                if {ka,kb}=={f'P60_HOST_{n}_ROD',f'P60_HOST_{n}_{tag}'}:return 'DECLARED_SIMPLIFIED_THREAD_ENGAGEMENT'
        for st in c['clamp_stations']:
''')
p.write_text(s,encoding='utf-8')
