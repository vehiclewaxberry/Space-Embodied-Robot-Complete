from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V1.json').read_text())
c['schema']='WP09_INTEGRATION_HARNESS_CANDIDATE_V2'
c['revision_reason']='Pre-build geometric consistency: former DATA feedthrough overlapped deck edge notch; separate its flange from notch and PWR flange.'
c['upper_deck_notch_box'][0][1]=-48.5;c['upper_deck_notch_box'][1][1]=48.5
c['feedthrough_xy'][1][1]=56
c['routes']['PROP_DATA']['waypoints'][1][1]=56;c['routes']['PROP_DATA']['waypoints'][2][1]=56;c['routes']['PROP_DATA']['waypoints'][3][1]=56
c['clamp_stations'][1].update(ys=[56,69],y_bounds=[42,83],stud_ys=[46,79])
c['grommet']={'bore_d_mm':8,'neck_d_mm':9,'flange_d_mm':12,'flange_t_mm':1,'qualification':'CUSTOM_ELASTIC_CANDIDATE_MATERIAL_AND_RETENTION_UNVERIFIED'}
c['clamp']={'thickness_x_mm':12,'lower_z_mm':[38,45],'upper_z_mm':[45,52],'bore_d_mm':8,'post_od_mm':12,'post_id_mm':3.4,'post_z_mm':[-8.5,38],'tie_rod_z_mm':[-17.5,58.5],'tie_rod_nominal_d_mm':3,'thread':'M3 nominal smooth proxy, thread form/class/material/locking pending; custom rod, not sourced M3x70 screw'}
(R/'inputs/INTEGRATION_HARNESS_CONTRACT_V2.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
c['schema']='WP09_INTEGRATION_HARNESS_CANDIDATE_V3'
c['revision_reason']='V2 feedthrough correction retained; R21 centerline / OD6 gives nominal inner R18. Cable type and workmanship acceptance remain unknown.'
for r in c['routes'].values():r['radius_mm']=21
c['routes']['PROP_PWR']['waypoints'][-1][1]=48
(R/'inputs/INTEGRATION_HARNESS_CONTRACT_V3.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
