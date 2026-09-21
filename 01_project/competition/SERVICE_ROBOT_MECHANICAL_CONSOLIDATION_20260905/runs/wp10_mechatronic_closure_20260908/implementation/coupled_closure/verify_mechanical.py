"""Check designed parts, interfaces and conservative host envelope intersections."""
from pathlib import Path
import csv,json,itertools,math
from OCP.BRepCheck import BRepCheck_Analyzer
from mechanical_parts import main_parts,propulsion_parts,main_carrier,propulsion_carrier
from coupled_adapter import HERE,A,sha,read,dump,load_candidate

def bbox(s):
    b=s.bounding_box();return [*b.min,*b.max]

def run():
    c=load_candidate();groups=dict(main=main_parts(),propulsion=propulsion_parts())
    facts=[];overlaps=[]
    for group,parts in groups.items():
        for i,s in enumerate(parts):
            b=bbox(s)
            facts.append(dict(group=group,index=i,label=s.label,bbox_mm=b,volume_mm3=s.volume,
                 valid=BRepCheck_Analyzer(s.wrapped).IsValid(),solids=len(s.solids()),
                 mass_kg=(s.volume*(2700 if i==0 else 1300)*1e-9)
                    if (i==0 or ('PEEK' in s.label)) else None,
                 mass_status='GEOMETRY_DENSITY_DESIGN_VALUE' if (i==0 or 'PEEK' in s.label) else 'UNKNOWN_OR_REFERENCE_NO_MASS_CREDIT'))
        for i,j in itertools.combinations(range(len(parts)),2):
            a,b=parts[i],parts[j];ba,bb=bbox(a),bbox(b)
            if any(min(ba[k+3],bb[k+3])-max(ba[k],bb[k])<=1e-6 for k in range(3)):continue
            common=a.intersect(b);vol=0. if common is None else common.volume
            if vol>1e-3:overlaps.append(dict(group=group,a=a.label,b=b.label,volume_mm3=vol))
    # The C-POD blank has a fully independent analytic plate-minus-four-bores volume.
    expected=(116*112-4*math.pi*(3.4/2)**2)*4
    actual=propulsion_carrier().volume
    nominal=main_carrier();wide=main_carrier(width=134)
    # 2mm more width x92mm x4mm adds volume; holes/thermal arch unaffected.
    perturb=wide.volume-nominal.volume
    checks=dict(valid_positive_solids=all(r['valid'] and r['solids']==1 and r['volume_mm3']>0 for r in facts),
      local_no_unintended_volume_intersections=not overlaps,
      propulsion_blank_analytic_volume=abs(expected-actual)<1e-6,
      carrier_width_parameter_drives_geometry=abs(perturb-2*92*4)<1e-6,
      shoulder_min_radial_clearance_mm=(3.55-3.4)/2,
      Q201_nominal_TIM_gap_mm=.203,board_underbody_standoff_mm=6.)
    # Parent full-array bounds are only used as a reject screen. This prospective
    # placement is not inserted into the parent assembly or called fit-verified.
    parent=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')
    assert sha(A/parent['source_plan'])==parent['source_plan_sha256']
    pose=[[1,0,0,-148],[0,0,-1,92],[0,1,0,85],[0,0,0,1]]
    hits={};worldparts=[]
    for s in groups['main']:
        bb=bbox(s);pts=[]
        for v in itertools.product(*[(bb[k],bb[k+3]) for k in range(3)]):
            pts.append([sum(pose[i][k]*v[k] for k in range(3))+pose[i][3] for i in range(3)])
        worldparts.append((s.label,[min(v[k] for v in pts) for k in range(3)]+[max(v[k] for v in pts) for k in range(3)]))
    for state,rows in parent['states'].items():
        hh=[]
        for label,bb in worldparts:
            for r in rows:
                b=r['bbox_S_mm']
                if all(min(bb[k+3],b[k+3])-max(bb[k],b[k])>1e-5 for k in range(3)):
                    hh.append(dict(new_part=label,parent_id=r['id']))
        hits[state]=hh
    from host_narrowphase import run as host_check
    host=host_check(groups['main'],pose,parent)
    out=dict(candidate_sha256=sha(HERE/'CANDIDATE.json'),source_sha256=sha(HERE/'mechanical_parts.py'),
       parts=facts,checks=checks,intersections=overlaps,
       main_aluminum_carrier_mass_kg=nominal.volume*2700e-9,
       propulsion_blank_mass_kg=actual*2700e-9,
       host_placement=dict(T_S_module=pose,broadphase_hits=hits,
          status=host['status'],narrowphase_file='HOST_NARROWPHASE.json',
          narrowphase_sha256=sha(HERE/'HOST_NARROWPHASE.json'),
          collision_counts={k:len(v['collisions']) for k,v in host['states'].items()},
          narrowphase_performed=True,installed=False),
       whole_vehicle_mass_updated=False,native_SolidWorks_created=False,manufacturing_release=False,
       incomplete_population='Q201 and five capacitors as reference bodies; remaining25 main-board refs not geometrically represented')
    dump('MECHANICAL_VERIFICATION.json',out)
    fields=['group','index','label','volume_mm3','mass_kg','mass_status']
    with (HERE/'MECHANICAL_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(facts)
    print(json.dumps(dict(checks=checks,intersections=overlaps,main_carrier_kg=out['main_aluminum_carrier_mass_kg'],
                         host_broadphase_counts={s:len(v) for s,v in hits.items()})))
    assert checks['valid_positive_solids'] and checks['propulsion_blank_analytic_volume'] and checks['carrier_width_parameter_drives_geometry']
    assert not overlaps

if __name__=='__main__':run()
