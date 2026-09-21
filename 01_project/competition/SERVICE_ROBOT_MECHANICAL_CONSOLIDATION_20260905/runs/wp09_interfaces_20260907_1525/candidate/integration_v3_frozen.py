"""WP09 source-first incremental layout and static harness geometry, world mm."""
from pathlib import Path
import json,hashlib,sys,importlib.util,math,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
CP=R/'inputs/INTEGRATION_HARNESS_CONTRACT_V3.json'
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def build():
    c=json.loads(CP.read_text());pins=dict(c['source_inputs'])
    assert all(sha(k)==v for k,v in pins.items()),'frozen source modified'
    rows={r['id']:r for r in c['states']['service']['instances']}
    spec=importlib.util.spec_from_file_location('wp09_geo',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    job={'parts':{k:{'path':v['step_path'],'sha256':v['source_sha256'],'T_S_local':v['T_S_local']} for k,v in rows.items()},'tolerances':c['acceptance']}
    for k,v in c['mips_sources'].items():job['parts'][k]={**v,'T_S_local':c['mips_transform']}
    for k,v in c['catalogue_parts'].items():job['parts']['CAT_'+k]={**v,'T_S_local':I}
    g=m.Geometry(job,pins)
    from build123d import Plane,Edge,Wire,Face,Vector,Color
    from cadgen.assembly import AssemblyHelper
    def box(b):return g.Solid.make_box(*(b[1][i]-b[0][i] for i in range(3)),Plane(origin=b[0]))
    def cyl(r,h,o,d=(0,0,1)):return g.Solid.make_cylinder(r,h,Plane(origin=o,z_dir=d))
    parts={};meta={};routes={};cuts={}
    def add(k,s,role='PHYSICAL_GEOMETRY',**kw):
        assert s.is_valid and len(s.solids())==1,(k,'invalid or disconnected',len(s.solids()))
        parts[k]=s;meta[k]=dict(representation_role=role,operation='ADD',**kw)
    floor=box([[136,-57,-98.15],[164,57,-96.15]])
    cradle=floor+box([[136,-49,-96.15],[139,49,-2.15]])
    for ylo,yhi in [(-46.7508,-44.7508),(44.7508,46.7508)]:
        for zl,zh in [(1,12),(77,88.5)]:cradle=cradle+box([[136,ylo,zl-94.15],[170,yhi,zh-94.15]])
    for z in [6.3754,82.5754]:cradle=cradle-cyl(1.6,110,(166.825,-55,z-94.15),(0,1,0))
    lower=g.load('lower_equipment_deck');upper=g.load('upper_equipment_deck')
    orig_lower=lower;orig_upper=upper
    for x,y in c['mips_floor_holes_xy']:
        cut=cyl(1.7,15,(x,y,-110));cradle=cradle-cut;lower=lower-cut
    add('MIPS_CRADLE_B',cradle,qualification='CUSTOM_NONPRESSURE_EXTERNAL_CARRIER; OEM_SIDE_SCREWS_UNRESOLVED')
    for k in c['mips_sources']:
        if k!='MIPS_EXTERNAL_CRADLE':add(k,g.load(k),c['mips_sources'][k]['representation_role'],source=c['mips_sources'][k],T_source_to_S=c['mips_transform'])
    add('P60_REFERENCE_B',box(c['eps_box']),'FUNCTIONAL_ENVELOPE',operation_reason='REPLACE equipment_power_distribution; source-covered 96x96x29 conservative reservation; selection and PCB mount open')
    tray=box(c['eps_carrier_box'])
    upper=upper-box(c['upper_deck_notch_box'])
    for x,y in c['eps_mount_xy']:
        tool=cyl(1.7,20,(x,y,-20));tray=tray-tool;upper=upper-tool
    add('P60_TRAY_B',tray,qualification='HOST_ATTACHMENT_ONLY_DEVICE_HOLES_UNBOUND')
    for n,(x,y) in enumerate(c['feedthrough_xy']):
        upper=upper-cyl(c['feedthrough_bore_d_mm']/2,10,(x,y,-15))
        p=c['grommet'];ring=cyl(p['neck_d_mm']/2,3,(x,y,-11.5))
        for z in [-12.5,-8.5]:ring=ring+cyl(p['flange_d_mm']/2,1,(x,y,z))
        ring=ring-cyl(p['bore_d_mm']/2,7,(x,y,-13.5));add(f'GROMMET_{n}',ring,qualification=p['qualification'])
    catalog={k:g.load('CAT_'+k) for k in c['catalogue_parts']}
    def hardware(prefix,xy,zhead,zdeckbottom):
        x,y=xy
        for role,tag,z,sgn in [('screw','SCREW',zhead,1),('washer','TOP_WASHER',zhead-.5,1),('washer','BOTTOM_WASHER',zdeckbottom,-1),('nut','NUT',zdeckbottom-.5,-1)]:
            loc=Plane(origin=(x,y,z),x_dir=(1,0,0),z_dir=(0,0,sgn)).location
            add(prefix+'_'+tag,catalog[role].moved(loc),'SIMPLIFIED_PROXY',catalogue=c['catalogue_parts'][role],thread_and_preload_verified=False)
    for n,xy in enumerate(c['mips_floor_holes_xy']):hardware('MIPS_FOOT_'+str(n),xy,-95.65,-101.15)
    for n,xy in enumerate(c['eps_mount_xy']):hardware('P60_HOST_'+str(n),xy,-6,-11.5)
    p=c['clamp'];dx=p['thickness_x_mm']
    for st in c['clamp_stations']:
        x=st['x'];lo,hi=st['y_bounds'];clamp=[]
        for tag,zs in [('BASE',p['lower_z_mm']),('LID',p['upper_z_mm'])]:
            s=box([[x-dx/2,lo,zs[0]],[x+dx/2,hi,zs[1]]])
            for y in st['ys']:s=s-cyl(p['bore_d_mm']/2,dx+2,(x-dx/2-1,y,45),(1,0,0))
            for y in st['stud_ys']:s=s-cyl(1.7,20,(x,y,36))
            add(f'CLAMP_{st["id"]}_{tag}',s,qualification='CUSTOM_SPLIT_SUPPORT_GEOMETRY; LINER_AND_CLAMP_FORCE_PENDING')
        for n,y in enumerate(st['stud_ys']):
            upper=upper-cyl(1.7,10,(x,y,-15))
            add(f'POST_{st["id"]}_{n}',cyl(6,46.5,(x,y,-8.5))-cyl(1.7,46.5,(x,y,-8.5)))
            add(f'TIEROD_{st["id"]}_{n}',cyl(1.5,76,(x,y,-17.5)),'SIMPLIFIED_PROXY',qualification=p['thread'])
            for role,tag,z,sgn in [('washer','TW',52,1),('nut','TN',52.5,1),('washer','BW',-11.5,-1),('nut','BN',-12,-1)]:
                loc=Plane(origin=(x,y,z),x_dir=(1,0,0),z_dir=(0,0,sgn)).location
                add(f'CLAMP_{st["id"]}_{n}_{tag}',catalog[role].moved(loc),'SIMPLIFIED_PROXY',catalogue=c['catalogue_parts'][role])
    add('lower_equipment_deck_B',lower,operation_reason='REPLACE lower_equipment_deck: four through bores only')
    add('upper_equipment_deck_B',upper,operation_reason='REPLACE upper_equipment_deck: service notch, eight fastener bores, two grommet bores')
    cuts['lower_removed_volume_mm3']=g.volume(orig_lower)-g.volume(lower);cuts['upper_removed_volume_mm3']=g.volume(orig_upper)-g.volume(upper)
    for k,p in c['routes'].items():
        pts=[Vector(*v) for v in p['waypoints']];r=p['radius_mm'];edges=[];start=pts[0];records=[]
        for i in range(1,len(pts)-1):
            u=(pts[i]-pts[i-1]).normalized();v=(pts[i+1]-pts[i]).normalized();assert abs(u.dot(v))<1e-12
            a=pts[i]-u*r;b=pts[i]+v*r;center=pts[i]-u*r+v*r;mid=center+((a-center)+(b-center)).normalized()*r
            if (a-start).length>1e-9:edges.append(Edge.make_line(start,a))
            edges.append(Edge.make_three_point_arc(a,mid,b));records.append(dict(start=list(a),mid=list(mid),end=list(b),center=list(center),radius_mm=r));start=b
        if (start-pts[-1]).length>1e-9:edges.append(Edge.make_line(start,pts[-1]))
        wire=Wire(edges)
        profile=Wire.make_circle(p['bundle_od_mm']/2,Plane(origin=pts[0],z_dir=pts[1]-pts[0]))
        s=g.Solid.sweep(Face(profile),wire)
        add(k+'_ROUTE',s,'FUNCTIONAL_ENVELOPE',qualification='STATIC_BUNDLE_RESERVATION_NOT_CUT_WIRE; OEM_ENDPOINTS_UNBOUND')
        routes[k]=dict(**p,actual_curve_length_mm=wire.length,edges=[dict(type=str(e.geom_type),length_mm=e.length) for e in edges],arcs=records,terminal_allowance_mm=None,cut_length_mm=None)
    a=AssemblyHelper('WP09_INTEGRATED_BAY_B')
    context=['adapter_battery','equipment_battery','adapter_adcs_propulsion_allocation','equipment_adcs_propulsion_allocation','equipment_arm_drive','equipment_compute_communications','equipment_navigation']
    # Exact existing IDs selected by bounds/roles below; never fabricate contextual boxes.
    contextual=[]
    for k,row in rows.items():
        if (k.startswith('equipment_') or k=='adapter_battery' or k=='adapter_adcs_propulsion_allocation' or k.startswith('RB_end_frame_')) and k!='equipment_power_distribution':
            s=g.load(k);contextual.append(k)
            a.add(type(s)(s.wrapped).located(s.global_location),'CONTEXT_'+k,color=Color(.40,.51,.59,.28))
    for k,s in parts.items():
        col=(.93,.32,.08) if k.startswith('PROP_PWR') else (.17,.5,.9) if k.startswith('PROP_DATA') else (.30,.63,.46,.25) if meta[k]['representation_role']=='FUNCTIONAL_ENVELOPE' else (.7,.72,.76)
        a.add(type(s)(s.wrapped).located(s.global_location),k,color=Color(*col))
    assert all(sha(k)==v for k,v in pins.items())
    return parts,meta,a.build(),g,dict(routes=routes,removal=cuts,context_ids=contextual)
def emit():
    parts,meta,a,g,extra=build()
    from build123d import export_step
    out=R/'candidate/parts';out.mkdir(exist_ok=True)
    assert not (R/'results/EMISSION_V3.json').exists()
    records={}
    for n,(k,s) in enumerate(parts.items()):
        p=out/(k+'.step');export_step(s,p)
        records[k]=dict(path=str(p),sha256=sha(p),**g.facts(s),**meta[k]);print(k,flush=True)
    p=R/'candidate/integrated_bay.step';export_step(a,p)
    write(R/'results/EMISSION_V3.json',dict(schema='WP09_INCREMENTAL_EMISSION_V3',status='EMITTED_NOT_INDEPENDENTLY_VERIFIED',parts=records,assembly_step=dict(path=str(p),sha256=sha(p)),contract_sha256=sha(CP),producer_sha256=sha(__file__),**extra))
    print('EMITTED',len(records),flush=True)
if __name__=='__main__':emit()
