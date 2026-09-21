"""Bind current sources, create nominal passage design, emit explicit generators or instance plan."""
import json,copy,argparse,hashlib
from pathlib import Path
from battery_variant_context import A,read,sha,translation
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['design','plan'],required=True);a=p.parse_args()
names=['BUSH_LEFT','BUSH_RIGHT','KEEPER_LEFT','KEEPER_RIGHT','SCREW_8','BRIDGE']
if a.phase=='design':
    source='mechanical/TRUNK_SUPPORT_INSTANCE_PLAN.json';old=read(source);bridge=next(r for r in old['states']['service']['rows'] if r['id']=='WP01-RB-BRIDGE-R2')
    c=dict(schema='WP10_ROOT_PASSAGE_SPLIT_BUSHING_V1',parent_source_plan=source,parent_source_sha256=sha(A/source),
        bridge_source=bridge,frame='S_mm',datum_S_mm=[65,-80,107.15],stem_OD_mm=9.8,flange_OD_mm=14,bore_ID_mm=6.6,
        stem_z_local_mm=[0,8],flange_z_local_mm=[-2,0],keeper_z_local_mm=[-4,-2.1],keeper_boss_z_local_mm=[-2.1,0],
        keeper_throat_ID_mm=7,flange_axial_float_mm=.1,screw_xy_S_mm=[[53,-80],[77,-80]],screw_nominal_total_length_mm=8,
        thread_representation='M3 major diameter cylindrical envelope in blind bore; actual thread form, runout, torque and locking NOT QUALIFIED',
        material_candidate=dict(bushing='Unfilled PEEK based on VICTREX 450G; machined stock grade/process and batch traceability pending',
            keeper='Aluminium alloy candidate, grade/temper/finish and strength pending',screw='Nominal M3 countersunk geometry; catalogue/grade pending'),
        material_source=dict(url='https://www.victrex.com/-/media/downloads/datasheets/victrex_tds_450g.pdf?rev=66e2f2641768427097e4ad8ce08deb49',
            file='sources/victrex_450g_202603.pdf',revision='March 2026',density_g_cm3=1.30,CLTE_below_Tg_average_per_K=55e-6,
            specimen_properties_not_finished_part_qualification=True),
        declared_dimensional_scenarios=dict(hole_D_mm=[9.95,10.05],stem_D_mm=[9.77,9.83],bore_D_mm=[6.6,6.7],
            bundle_OD_mm=[5.8,6.2],bundle_OD_measured=False,flange_D_mm=[13.95,14.05],axial_capture_gap_mm=[.05,.15]),
        protected_scope='bridge through-hole and first2mm of M3RB relief only; 115.15..125.15mm upper relief remains pending release junction',
        strain_relief_verified=False,release_route_verified=False,thread_strength_qualified=False,whole_design_complete=False)
    if (A/c['material_source']['file']).exists():c['material_source']['sha256']=sha(A/c['material_source']['file'])
    (A/'mechanical/ROOT_BUSHING_DESIGN.json').write_text(json.dumps(c,indent=2),encoding='utf-8')
    for name in names:(A/f'mechanical/root_{name.lower()}.step.py').write_text("from root_bushing_common import make\n\ndef gen_step():return make("+repr(name)+")\n",encoding='utf-8')
    print(json.dumps(dict(design=True,entries=names)))
else:
    c=read('mechanical/ROOT_BUSHING_DESIGN.json');assert sha(A/c['parent_source_plan'])==c['parent_source_sha256'];parent=read(c['parent_source_plan']);states={}
    for state,sp in parent['states'].items():
        rows={r['id']:copy.deepcopy(r) for r in sp['rows']};added=[];changed=[]
        def put(k,stem,T):
            new=k not in rows;r=rows.get(k,dict(id=k,is_ground_only=False,predecessor_ids=[]));path=A/f'mechanical/{stem}.step'
            r.update(step_path=str(path),source_sha256=sha(path),T_S_step=T.tolist(),representation_role='PROJECT_PASSAGE_CAPTURE_GEOMETRY__THREAD_AND_PHYSICAL_QUALIFICATION_OPEN',mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',native_geometry_current=False)
            rows[k]=r;(added if new else changed).append(k)
        import numpy as np
        put('WP01-RB-BRIDGE-R2','root_bridge',np.eye(4))
        for name in names[:4]:put('ROOT_'+name,'root_'+name.lower(),translation(*c['datum_S_mm']))
        for i,(x,y) in enumerate(c['screw_xy_S_mm']):put(f'ROOT_SCREW_{i}','root_screw_8',translation(x,y,103.15))
        assert len(rows)==937 and len(changed)==1 and len(added)==6
        states[state]=dict(rows=list(rows.values()),changed_ids=changed,added_ids=added,retained_release_ids=[k for k in rows if k.startswith('release_power_data_route_')])
    out=dict(schema='WP10_ROOT_BUSHING_SOURCE_VARIANT_V1',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in [c['parent_source_plan'],'mechanical/ROOT_BUSHING_DESIGN.json','mechanical/root_bushing_common.py']},states=states,component_count=937,component_count_identity='931 +2 split sleeve halves +2 metal keeper halves +2 nominal screws; original bridge ID replaced',whole_fit_verified=False,thermal_mass_native_requalified=False,whole_design_complete=False)
    (A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(source_instances=937)))
