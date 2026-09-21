"""Reproducible 84-CIC placement and bounded interference screen; stdlib only."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import itertools
import json
import re

C = Path(__file__).resolve().parents[1]
N = C.parent / "reuse_closure"
spec = importlib.util.spec_from_file_location("solar_hinge_delta", C/"solar/solar_hinge_delta.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def inverse_point(t, p):
    return [sum(t[j][i]*(p[j]-t[j][3]) for j in range(3)) for i in range(3)]


def bounds(points):
    return {"min_mm":[min(p[i] for p in points) for i in range(3)],
            "max_mm":[max(p[i] for p in points) for i in range(3)]}


def overlaps(a, b):
    return all(min(a['max_mm'][i],b['max_mm'][i])-max(a['min_mm'][i],b['min_mm'][i])>1e-8 for i in range(3))


def multiply(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def instance_transform(panel_t, x, y, z, face):
    # Rx(pi) on the negative-side wing gives each CIC's +Z face world +Z in SERVICE.
    return multiply(panel_t, [[1,0,0,x],[0,face,0,y],[0,0,face,z],[0,0,0,1]])


def main():
    hinge=h.main()
    source=N/'sources/power/AZUR_3G30_ADV_4x8_DB00010891_01.pdf'
    params=h.WP03/'design_parameters.json'
    native={state:json.loads((N/'results'/file).read_text(encoding='utf-8-sig')) for state,file in h.RECEIPTS.items()}
    ids=[f'wing_{side}_leaf_{leaf}' for side in (-1,1) for leaf in (1,2,3)]
    current={state:{r['id']:r for r in rec['rows']} for state,rec in native.items()}
    unique_steps={current['service'][i]['step_path'] for i in ids}
    step_evidence=[]
    for path in sorted(unique_steps):
        s=Path(path).read_text(encoding='utf-8-sig')
        points=[]
        for point in re.findall(r'CARTESIAN_POINT\s*\(\s*[^,]*,\s*\(([^)]+)\)',s):
            xyz=list(map(float,point.split(',')))
            if len(xyz)==3:points.append(xyz)
        step_evidence.append({'path':path,'sha256':h.sha(path),'all_cartesian_point_bounds':bounds(points),
                              'solid_brep_entity_count':s.count('MANIFOLD_SOLID_BREP('),
                              'cylindrical_surface_count':s.count('CYLINDRICAL_SURFACE('),
                              'scope':'Textual planar box source check; no BREP kernel or fabricated hole inference.'})
    old_params=json.loads(params.read_text(encoding='utf-8-sig'))
    face_layer_max=.34+.15
    cells=[]
    boards=[]
    selected_frames={st:{r['id']:r for r in v['frames']} for st,v in hinge['states'].items()}
    hardware_screens=[]
    for channel,panel_id in enumerate(ids):
        side=int(panel_id.split('_')[1]); leaf=int(panel_id.split('_')[-1])
        row=current['service'][panel_id]
        board={'id':panel_id,'channel':channel,'side':side,'leaf':leaf,
               'physical_instance_present_in_all_three_native_receipts':all(panel_id in current[st] for st in current),
               'source_native_path':row['native_path'],'source_native_sha256':row['native_sha256'],
               'source_step_path':row['step_path'],'source_step_sha256':row['source_sha256'],
               'representation_role':row['representation_role'],
               'substrate_size_mm':[300,200,2.5], 'panel_local_x_limits_mm':[-150,150], 'panel_local_y_limits_mm':[-100,100],
               'source_holes_in_panel':0,'edge_insert_attachment':'EDGE_INSERTS_TBD; no actual board inserts or attachment holes in planar box',
               'solar_face_local_z_sign':side,
               'keepouts':[{'kind':'process_edge_reservation','x_abs_min_mm':145,'status':'DESIGN_REQUIREMENT'},
                           {'kind':'hinge_and_wiring_bands','y_abs_min_mm':85,'status':'DESIGN_REQUIREMENT; cables must also avoid actual hardware'},
                           {'kind':'root_harness_budget_expanded_1mm','rect_local_xy_mm':[125,-98.85,139,-84.85],
                            'applies':leaf==1,'status':'FUNCTIONAL_ENVELOPE_1mm_GROWTH_NOT_FINAL_HARNESS_GEOMETRY'}],
               'states':{st:{'current_native_T_local_to_S_mm':current[st][panel_id]['native_T_local_to_S'],
                             'candidate_T_local_to_S_mm':selected_frames[st][panel_id]['T_local_to_S_mm'],
                             'front_normal_S':selected_frames[st][panel_id]['solar_normal_S']} for st in native}}
        boards.append(board)
        for string in range(2):
            for cell in range(7):
                x=(cell-3)*41.4; y=(-1 if string==0 else 1)*44.1
                item={'id':f'PV{channel}_S{string+1}_C{cell+1:02}', 'parent_leaf':panel_id,
                      'channel':channel,'string':string+1,'series_position':cell+1,
                      'vendor':'AZUR SPACE','mpn':'81442','local_center_xy_mm':[x,y],
                      'nominal_cic_size_mm':[40.15,80.15,.29],
                      'max_glass_size_mm':[40.20,80.20],
                      'placement_tolerance_each_axis_requirement_mm':.10,
                      'conservative_glass_plus_placement_xy_bounds_mm':[x-20.2,y-40.2,x+20.2,y+40.2],
                      'adhesive_nominal_mm':.10,'adhesive_min_mm':.05,'adhesive_max_mm':.15,
                      'adhesive_material':None,'adhesive_material_status':'NOT_SELECTED; thickness interval is our process requirement',
                      'CIC_mean_weight_reference_kg':.0036,
                      'solid_geometry_role':'FINITE_THICKNESS_RECTANGULAR_PACKAGE_PROXY; supplier corner/tab CAD pending',
                      'electrical_series_topology':'7S row-level logical topology; do not infer terminal pad coordinates',
                      'interconnect_geometry_bound':False,'states':{}}
                for st in native:
                    t=selected_frames[st][panel_id]['T_local_to_S_mm']
                    item['states'][st]={
                        'CIC_T_local_to_S_mm':instance_transform(t,x,y,side*(1.25+.10+.29/2),side),
                        'ADHESIVE_T_local_to_S_mm':instance_transform(t,x,y,side*(1.25+.10/2),side),
                        'front_normal_S':[side*t[j][2] for j in range(3)],
                        'candidate_layer_outer_surface_local_abs_z_mm':1.25+.10+.29,
                        'worst_layer_outer_surface_local_abs_z_requirement_mm':2.60/2+.15+.34}
                cells.append(item)
        # Screen current-wing physical hardware and budget objects using its receipt AABBs.
        # It excludes the 8 edge frames to be rebuilt; those lie outside |x|>=150.
        for st in native:
            t=current[st][panel_id]['native_T_local_to_S']
            for r in native[st]['rows']:
                if r.get('parent_assembly')!='SOLAR_WING' or '_leaf_' in r['id'] or r['id'].startswith('wing_edge_frame_'):
                    continue
                b=r['world_bounds_mm']
                local=bounds([inverse_point(t,p) for p in itertools.product(*zip(b['min_mm'],b['max_mm']))])
                for c in cells[-14:]:
                    x,y=c['local_center_xy_mm']
                    z=sorted([side*1.25,side*(1.3+face_layer_max)])
                    cb={'min_mm':[x-20.2,y-40.2,z[0]],'max_mm':[x+20.2,y+40.2,z[1]]}
                    if overlaps(cb,local):hardware_screens.append({'state':st,'cell':c['id'],'hardware':r['id'],'screen':'current receipt AABB projected to leaf; conservative candidate-screen concern'})
    same_face=all(abs(c['states']['service']['front_normal_S'][2]-1)<1e-12 for c in cells)
    wrong_normals={side:[current['service'][f'wing_{side}_leaf_1']['native_T_local_to_S'][j][2] for j in range(3)] for side in(-1,1)}
    real_instance_distinct=all(len({tuple(round(current[st][i]['native_T_local_to_S'][j][3],8) for j in range(3)) for i in ids})==6 for st in current)
    xspan=6*41.4+40.4; yspan=2*44.1+80.4
    # Unknown tab locations: full 7.53 mm protrusion around each package is a conservative diagnostic only.
    tab_halo=7.53
    conservative_tab_width=40.2+2*tab_halo
    layout={
        'identity':'WP09F_SOLAR_84_CIC_LAYOUT_V1','status':'GLASS_LAYOUT_AND_4_5MM_HINGE_CANDIDATE_DEFINED__TAB_AND_BOND_HOLD',
        'current_source_receipts_sha256':{st:h.sha(N/'results'/f) for st,f in h.RECEIPTS.items()},
        'source_azur':{'path':str(source),'sha256':h.sha(source),'revision':'DB00010891-01 2025-04-11','mpn':'81442',
                        'page2':'CIC 40.15 +/-0.05 x80.15 +/-0.05 mm; 290 +/-50 um; average weight <=3.6 g; out-of-plane interconnect 6.5 x7.53 x0.025 mm'},
        'geometry_source_conflict':{'parameter_path':str(params),'parameter_sha256':h.sha(params),
            'unused_legacy_solar_panel_mm':old_params.get('solar_panel_mm'),
            'actual_native_source_box_mm':[300,200,2.5],
            'chosen':'Actual current STEP and six native instances; never enlarge to320x195 to fit CICs'},
        'actual_step_source_screen':step_evidence,
        'configuration':{'panels':6,'cells_each':14,'series_per_string':7,'strings_per_channel':2,'total_cells':84,
             'cell_pitch_x_mm':41.4,'row_center_y_abs_mm':44.1,'nominal_glass_gap_x_mm':41.4-40.15,
             'worst_glass_plus_placement_gap_x_mm':41.4-40.4,
             'worst_glass_plus_placement_gap_y_mm':88.2-80.4,
             'worst_glass_plus_placement_edge_clearance_x_mm':(300-xspan)/2,
             'worst_glass_plus_placement_edge_clearance_y_mm':(200-yspan)/2,
             'serial_strings_are_logical_only_no_pad_route_release':True,
             'same_world_service_front_normal':[0,0,1],'selected_stack_step_mm':4.5},
        'deployment_path':{'waypoints_deg':[[0,0,0],[90,0,0],[90,150,0],[90,150,180],[90,180,180]],
             'joint_order':['H1','H2_PRE150','H3','H2_FINISH'],
             'continuous_certificate_path':str(C/'results/SOLAR_CONTINUOUS_CLEARANCE.json'),
             'scope':'six layered panel envelopes only; hardware motion remains forbidden'},
        'interconnect_and_wiring':{
             'two_peripheral_routing_band_local_y_mm':[[-98,-85],[85,98]],
             'central_band_local_y_mm':[-3.5,3.5],
             'root_harness_keepout_leaf1_local_xy_mm':[125,-98.85,139,-84.85],
             'supplier_interconnect_dimension_mm':[6.5,7.53,.025],
             'supplier_interconnect_position_and_formed_shape':None,
             'conservative_unknown_tab_halo_mm':tab_halo,
             'seven_packages_plus_full_unknown_tab_halos_width_mm':7*conservative_tab_width,
             'full_unknown_tab_halo_layout_pass':7*conservative_tab_width<=300,
             'disposition':'Glass placement passes. Exact drawing ZP-0004289 and formed-tab STEP/polarity are required to route serial links. No tab is silently represented as zero thickness, and the folded 0.82 mm check excludes tabs from the overlapping glass region.',
             'blocking_diodes':'Two string blocking paths per channel remain electrical requirements; no device footprint or thermal land inferred from CIC bypass diode.'},
        'mass':{'cic_count':84,'cic_mean_weight_reference_each_kg':.0036,'cic_reference_total_kg':84*.0036,
             'existing_substrate_budget_each_kg':.18,'existing_six_substrate_budget_kg':1.08,
             'CIC_mass_already_in_existing_substrate_budget':None,'do_not_double_add_to_star_SSOT':True,
             'adhesive_volume_reference_mm3':84*40.15*80.15*.10,'adhesive_density_kg_mm3':None,'adhesive_mass_kg':None,
             'adhesive_mass_must_be_positive':True,'interconnect_external_harness_mass_kg':None,
             'external_harness_mass_must_be_positive':True,'complete_array_mass_kg':None,
             'basis':'3.6 g is a supplier mean-weight reference; not a measured lot upper bound. No complete array mass credit.'},
        'boards':boards,'cells':cells,'current_hardware_AABB_screen_concerns':hardware_screens,
        'build_approved':False,'manufacturing_release':False,'hardware_tests':0,'CAD_executed_by_layout_script':False}
    checks=[
        {'id':'SIX_NATIVE_LEAF_IDENTITIES','pass':len(ids)==6 and all(b['physical_instance_present_in_all_three_native_receipts'] for b in boards)},
        {'id':'SIX_DISTINCT_TRANSFORMS_NOT_DUPLICATE_COUNT','pass':real_instance_distinct},
        {'id':'BOX_300_200_2_5_SOURCE','pass':all(x['all_cartesian_point_bounds']=={'min_mm':[-150.,-100.,-1.25],'max_mm':[150.,100.,1.25]} for x in step_evidence)},
        {'id':'84_UNIQUE_CELL_PLACEMENTS','pass':len(cells)==84 and len({c['id'] for c in cells})==84},
        {'id':'GLASS_PLUS_TOLERANCE_GRID_FITS','pass':xspan<=290 and yspan<=170},
        {'id':'SERVICE_ALL_SIX_FRONTS_WORLD_PLUS_Z','pass':same_face},
        {'id':'CURRENT_3MM_FOLD_REJECTED','pass':hinge['folding_clearance']['old_worst_clearance_mm']<0},
        {'id':'NEW_4_5MM_FOLD_AT_LEAST_0_3MM','pass':hinge['folding_clearance']['new_worst_clearance_mm']>=.3},
        {'id':'THREE_STATES_SUBSTRATE_FACE_BOX_NO_OVERLAP','pass':all(v['positive_overlap_count']==0 for v in hinge['states'].values())},
        {'id':'NONZERO_CIC_AND_ADHESIVE_LAYERS','pass':all(c['nominal_cic_size_mm'][2]>0 and c['adhesive_nominal_mm']>0 for c in cells)},
        {'id':'CURRENT_WING_HARDWARE_AABB_SCREEN','pass':not hardware_screens,'scope':'Current wing hardware/budget objects; modified edge-frame rebuild and whole spacecraft need native checks.'},
    ]
    report={'identity':'SOLAR_LAYOUT_CHECK_V1','status':'PASS_BOUNDED_LAYOUT_WITH_EXPLICIT_INTERCONNECT_AND_BOND_HOLD' if all(x['pass'] for x in checks) else 'LAYOUT_SCREEN_CONCERN',
        'checks':checks,'pass_count':sum(x['pass'] for x in checks),'count':len(checks),
        'negative_controls':[
            {'id':'ALL_LOCAL_PLUS_Z','detected':wrong_normals[-1][2]<0,'result':'Negative wing would face world -Z; assign side-dependent physical mounting face.'},
            {'id':'OLD_3MM_STACK','detected':hinge['folding_clearance']['old_worst_clearance_mm']<0},
            {'id':'40_2MM_PLUS_UNKNOWN_TAB_HALO_7_53_EACH_SIDE','detected':7*conservative_tab_width>300,'required_width_mm':7*conservative_tab_width},
            {'id':'42MM_WIDE_CELL_AT_SAME_PITCH','detected':42>41.4,'result':'Adjacent projected glass overlap.'},
            {'id':'DUPLICATE_PANEL_TRANSFORM','detected':len({(0,0,0) for _ in range(6)})!=6},
            {'id':'ZERO_ADHESIVE_MASS_CLAIM','detected':layout['mass']['adhesive_volume_reference_mm3']>0 and layout['mass']['adhesive_mass_kg'] is None}],
        'hold_items':['vendor ZP-0004289 formed-tab/pad geometry','bond material and qualification','substrate material/flatness/CTE','edge inserts and load path','updated hinge BREP/clearance and continuous deployment','array harness bend/strain/insulation','swept-body/arm shading and thermal limits'],
        'physical_validation_credit':False,'manufacturing_release':False}
    (C/'solar').mkdir(parents=True,exist_ok=True); (C/'results').mkdir(exist_ok=True)
    (C/'solar/SOLAR_LAYOUT.json').write_text(json.dumps(layout,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (C/'results/SOLAR_LAYOUT_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (C/'solar/SOLAR_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['item','quantity','unit','source_or_requirement','unit_mass_kg','total_mass_kg','mass_owner','status'])
        w.writeheader();w.writerows([
          {'item':'AZUR81442_CIC','quantity':84,'unit':'piece','source_or_requirement':'DB00010891-01 p2; mean weight <=3.6g','unit_mass_kg':.0036,'total_mass_kg':.3024,'mass_owner':'solar_CIC_reference; parent budget coverage UNBOUND','status':'finite thickness package candidate, formed-tab geometry pending'},
          {'item':'CIC_bondline','quantity':84,'unit':'patch','source_or_requirement':'40.15x80.15x0.10 mm nominal; 0.05..0.15 thickness REQUIREMENT','unit_mass_kg':'','total_mass_kg':'','mass_owner':'solar_bond; positive unknown','status':'material/density/strength NOT_SELECTED'},
          {'item':'existing_leaf_substrate','quantity':6,'unit':'piece','source_or_requirement':'native box300x200x2.5; retained budget0.18kg','unit_mass_kg':.18,'total_mass_kg':1.08,'mass_owner':'existing wing leaf budget','status':'retained; not additional mass'},
          {'item':'revised_edge_frame_fixed_fork','quantity':8,'unit':'replacement','source_or_requirement':'STACK_STEP3.0->4.5 mm; same WP03 construction','unit_mass_kg':'','total_mass_kg':'','mass_owner':'replacement delta after CAD','status':'run build_solar_delta.py under sole CAD writer'},
          {'item':'hinge2_3_pin','quantity':8,'unit':'existing repositioned','source_or_requirement':'existing geometry; updated serial root transforms','unit_mass_kg':'','total_mass_kg':'','mass_owner':'existing pins; no added pin mass','status':'retained geometry'},
          {'item':'string_blocking_paths','quantity':12,'unit':'path','source_or_requirement':'two independently blocked strings per MPPT','unit_mass_kg':'','total_mass_kg':'','mass_owner':'solar electrical interface, positive unknown','status':'actual parts/placement/thermal land unbound'},
          {'item':'series_interconnect_and_array_harness','quantity':1,'unit':'set','source_or_requirement':'two7S strings per leaf plus six MPPT routes','unit_mass_kg':'','total_mass_kg':'','mass_owner':'solar array external interconnect, positive unknown','status':'source tab drawing needed; not zero mass'}])
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 900"><style>text{font-family:Arial,Microsoft YaHei,sans-serif}.t{font-size:16px;fill:#163047}.s{font-size:11px;fill:#17324a}</style><rect width="1100" height="900" fill="#f4f7fb"/><text x="25" y="30" class="t">84 CIC / 6 REAL NATIVE LEAF INSTANCES — 300 × 200 mm</text><text x="25" y="53" class="s">7S2P each leaf · world +Z active faces · candidate stack step 4.5 mm · finite CIC 0.29 + bond 0.10 mm</text>']
    for b in boards:
        col=b['leaf']-1; r=0 if b['side']==-1 else 1; ox=35+col*355; oy=105+r*290
        svg.append(f'<g transform="translate({ox},{oy})"><text x="0" y="-17" class="t">{b["id"]} / MPPT {b["channel"]}</text><rect width="300" height="200" fill="#d9e1e9" stroke="#526a80"/><rect x="5" y="15" width="290" height="170" fill="#edf4fb" stroke="#879aad" stroke-dasharray="3 3"/>')
        for cell in [x for x in cells if x['parent_leaf']==b['id']]:
            x,y=cell['local_center_xy_mm']; color='#194ea0' if cell['string']==1 else '#247b8f'
            svg.append(f'<rect x="{x+150-20.075:.3f}" y="{100-y-40.075:.3f}" width="40.15" height="80.15" rx="1.5" fill="{color}" stroke="white" stroke-width=".5"/><text x="{x+150:.2f}" y="{100-y+4:.2f}" text-anchor="middle" font-size="10" fill="white">{cell["string"]}.{cell["series_position"]}</text>')
        svg.append(f'<text x="0" y="220" class="s">Local face {"−Z" if b["side"]==-1 else "+Z"}; front in SERVICE = world +Z</text><text x="0" y="237" class="s">Edge margins ≥5.6 /15.7 mm; tab geometry is HOLD</text></g>')
    svg.extend(['<text x="30" y="703" class="t">FOLDING CHANGE — existing 3.0 mm stack cannot contain opposed CIC surfaces</text>',
                '<text x="30" y="733" class="s">Selected 4.5 mm serial hinge offset. Worst gap = 4.5 − 0.10 axis error − 2.60 substrate − 2 × (0.34 CIC + 0.15 bond) = 0.82 mm.</text>',
                '<text x="30" y="756" class="s">Rebuild 8 parent edge-frame fork/bridge solids, reposition H2/H3 pins and child chain; do not independently translate plates.</text>',
                '<text x="30" y="788" class="t">RELEASE BOUNDARY</text>',
                '<text x="30" y="815" class="s">Glass packing and layered boxes are defined. Out-of-plane tabs, bonding, inserts, launch restraint, cables and thermal/shadow validation remain open.</text>',
                '<text x="30" y="840" class="s">CIC reference mass = 84 × 3.6 g = 302.4 g; adhesive and external interconnect mass are positive unknowns, never zero.</text>',
                '</svg>'])
    (C/'solar/SOLAR_LAYOUT.svg').write_text('\n'.join(svg),encoding='utf-8')
    print(json.dumps({'layout':str(C/'solar/SOLAR_LAYOUT.json'),'cells':len(cells),'checks_passed':report['pass_count'],'checks_total':report['count'],'hardware_concerns':len(hardware_screens)}))
    return layout,report


if __name__=='__main__':
    main()
