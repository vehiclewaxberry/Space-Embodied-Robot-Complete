"""Bind actual V9 source and derive explicit trunk support placements."""
import json,numpy as np
from battery_variant_context import A,read,sha,translation
parent=read('mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json');rows={r['id']:r for r in parent['states']['service']['rows']}
c=dict(schema='WP10_TRUNK_SPLIT_SUPPORT_DESIGN_V1',parent_source_plan='mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json',parent_source_sha256=sha(A/'mechanical/BATTERY_ROUTE_INSTANCE_PLAN.json'),route_source_sha256=sha(A/'mechanical/battery_internal_route.step'),frame='S_mm',bundle_OD_mm=6,saddle_bore_mm=7,liner_radial_mm=.5,cap_thickness_mm=4,material_and_clamp_preload_qualified=False,catalogue_fastener_release=False,deck_holes_xy_mm=[[-105,-11],[-85,-11],[-30,-6.5],[-30,9.5],[25,-6.5],[25,9.5],[57,-40],[73,-40]],adapter_cut_window_mm=[-111.5,-15.5,-12,-78.5,-6.5,-4],stations=[],modified_sources={})
for suffix,p,rz in [('-140',[-95,1.5,45],0),('-70',[-30,1.5,-2],0),('0',[25,1.5,-2],0),('65',[65,-40,-2],-90)]:
    t=np.deg2rad(rz);T=translation(*p);T[:3,:3]=[[np.cos(t),-np.sin(t),0],[np.sin(t),np.cos(t),0],[0,0,1]]
    c['stations'].append(dict(previous_suffix=suffix,axis_S_mm=p,T_S_local=T.tolist(),base_kind='HIGH_BASE' if suffix=='-140' else 'LOW_BASE',clamp_screw_length_mm=14 if suffix=='-140' else 20))
for name,k in [('DECK','upper_equipment_deck_B'),('DRIVE_ADAPTER','adapter_arm_drive'),('COMPUTE_ADAPTER','adapter_compute_communications')]:
    r=rows[k];c['modified_sources'][name]=dict(id=k,path=r['step_path'],sha256=r['source_sha256'],T_S_step=r['T_S_step'])
(A/'mechanical/TRUNK_SUPPORT_DESIGN.json').write_text(json.dumps(c,indent=2),encoding='utf-8')
stems={q:'trunk_'+q.lower() for q in ['LOW_BASE','HIGH_BASE','CAP','LINER_LOW','LINER_HIGH','SCREW_12','SCREW_14','SCREW_20','DECK','DRIVE_ADAPTER','COMPUTE_ADAPTER']}
for q,stem in stems.items():(A/f'mechanical/{stem}.step.py').write_text(f"from trunk_support_common import make\n\ndef gen_step():return make({q!r})\n",encoding='utf-8')
print(json.dumps(dict(entry_count=len(stems),stations=len(c['stations']),new_deck_holes=len(c['deck_holes_xy_mm']))))
