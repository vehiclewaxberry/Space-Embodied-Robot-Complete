"""Independent STEP readback of bottom mount contacts and actual dimensions."""
from pathlib import Path
import json,hashlib,runpy,itertools,math
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
A=Path(__file__).resolve().parents[1]
core=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
read=core['read'];parts=core['parts'];prop=core['prop'];common=core['common']
p=json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text());checks=[]
def ck(n,v,**kw):checks.append(dict(name=n,passed=bool(v),**kw))
def zfaces(s,z):
    e=TopExp_Explorer(s,TopAbs_FACE);out=[]
    while e.More():
        f=TopoDS.Face_s(e.Current());ad=BRepAdaptor_Surface(f)
        if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Z())>.999 and abs(ad.Plane().Location().Z()-z)<1e-5:out.append(f)
        e.Next()
    return out
def contact(a,b,z):return sum(common(x,y,False) for x in zfaces(a,z) for y in zfaces(b,z))
shapes={k:read(A/'mechanical'/f'{v}.step') for k,v in [('plate','bottom_radiator'),('deck','lower_deck_bottom_mount'),('screw','bottom_mount_screw'),('washer','bottom_mount_washer'),('nut','bottom_mount_nut')]}
f={k:prop(s) for k,s in shapes.items()}
ck('five_leaf_sources_each_one_valid_positive_solid',all(len(parts(s))==1 and BRepCheck_Analyzer(s).IsValid() and f[k]['measure']>0 for k,s in shapes.items()))
asm=parts(read(A/'mechanical/bottom_mount_assembly.step'));af=[prop(s) for s in asm]
active_cold_path=p.get('chb_path',{}).get('enabled',False)
expected_count=34 if active_cold_path else 24
ck(f'{expected_count}_valid_positive_assembly_solids',len(asm)==expected_count and all(BRepCheck_Analyzer(s).IsValid() and v['measure']>0 for s,v in zip(asm,af)))
expected=[-172,-98.15,-114.15,172,98.15,p['chb_path']['finger_arm_z_mm'][1] if active_cold_path else -101.15]
ck('plate_bbox_matches_S_design',max(abs(x-y) for x,y in zip(f['plate']['bbox'],expected))<1e-5)
ck('washer_true_thickness_0p5',abs(f['washer']['bbox'][5]-f['washer']['bbox'][2]-.5)<1e-6)
ck('screw_inclusive_head_length_20',abs(f['screw']['bbox'][5]-f['screw']['bbox'][2]-20)<1e-6)
ck('screw_max_head_diameter_6p72',abs(f['screw']['bbox'][3]-f['screw']['bbox'][0]-6.72)<1e-6)
ck('nut_height_2p4',abs(f['nut']['bbox'][5]-f['nut']['bbox'][2]-2.4)<1e-6)
ca=contact(shapes['plate'],shapes['deck'],p['deck_bottom_z_mm']);one_area=math.pi*(p['boss_radius_mm']**2-1.7**2)
ck('two_annular_boss_deck_contacts',abs(ca-2*one_area)<1e-4,area_mm2=ca,expected_mm2=2*one_area)
angle_contacts=[]
for key in p['baseline_angles']:
    s=read(A/'mechanical'/f'bottom_{key}.step');area=contact(shapes['plate'],s,-104.15)
    ck(key+'_boss_bearing_contact',abs(area-one_area)<1e-4,area_mm2=area)
    ck(key+'_one_valid_solid',len(parts(s))==1 and BRepCheck_Analyzer(s).IsValid())
    angle_contacts.append(dict(id=key,area_mm2=area))
mount=[]
for i,(x,y) in enumerate(p['mount_centers_xy_mm']):
    group={}
    for tag,z in [('screw',p['outer_z_mm']),('washer',p['deck_top_z_mm']),('nut',p['deck_top_z_mm']+.5)]:
        bbox=f[tag]['bbox'];expected_bbox=[bbox[0]+x,bbox[1]+y,bbox[2]+z,bbox[3]+x,bbox[4]+y,bbox[5]+z]
        matches=[j for j,b in enumerate(af) if max(abs(v-w) for v,w in zip(b['bbox'],expected_bbox))<1e-5]
        ck(f'mount_{i}_{tag}_source_mate_placement',len(matches)==1)
        group[tag]=asm[matches[0]]
    dw=contact(shapes['deck'],group['washer'],p['deck_top_z_mm']);wn=contact(group['washer'],group['nut'],p['deck_top_z_mm']+.5)
    # Bearing annulus is limited by deck boreR1.7, not washer's smallerR1.6.
    ck(f'mount_{i}_washer_two_bearing_faces',abs(dw-math.pi*(3.5**2-1.7**2))<1e-4 and wn>15,deck_washer_mm2=dw,washer_nut_mm2=wn)
    sc=common(shapes['plate'],group['screw'],False)
    # Face common is intentionally not used to infer contact pressure.
    protrusion=prop(group['screw'])['bbox'][5]-prop(group['nut'])['bbox'][5]
    ck(f'mount_{i}_tip_protrusion',abs(protrusion-1.1)<1e-5,value_mm=protrusion)
    mount.append(dict(index=i,center_xy_mm=[x,y],deck_washer_area_mm2=dw,washer_nut_area_mm2=wn,nominal_tip_protrusion_mm=protrusion,nominal_plate_screw_common_surface_mm2=sc))
overlaps=[]
for i,j in itertools.combinations(range(len(asm)),2):
    b,c=af[i]['bbox'],af[j]['bbox']
    if not all(min(b[k+3],c[k+3])-max(b[k],c[k])>1e-5 for k in range(3)):continue
    v=common(asm[i],asm[j]);overlaps.append(dict(pair=[i,j],common_volume_mm3=v))
ck('zero_internal_positive_common_volume',all(abs(r['common_volume_mm3'])<1e-5 for r in overlaps),positive=[r for r in overlaps if abs(r['common_volume_mm3'])>=1e-5])
area=sum(prop(s,False)['measure'] for s in zfaces(shapes['plate'],p['outer_z_mm']))
ck('actual_outer_face_less_than_uncut_rectangle',64000<area<344*196.3)
out=dict(schema='WP10_BOTTOM_MOUNT_GEOMETRY_V1',source_config_sha256=hashlib.sha256((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_bytes()).hexdigest(),
 source_steps={k:dict(sha256=hashlib.sha256((A/'mechanical'/f'{v}.step').read_bytes()).hexdigest(),path=f'mechanical/{v}.step') for k,v in [('plate','bottom_radiator'),('deck','lower_deck_bottom_mount'),('assembly','bottom_mount_assembly')]},
 checks=checks,checks_passed=all(q['passed'] for q in checks),check_count=len(checks),facts=f,mounts=mount,angle_contacts=angle_contacts,overlaps=overlaps,actual_outward_planar_radiating_area_mm2=area,
 plate_mass_estimate_kg=f['plate']['measure']*2700e-9,mass_density_assumed_kg_m3=2700,CHB_to_bottom_thermal_link_installed=active_cold_path,
 actual_thread_or_tolerance_verified=False,load_or_preload_verified=False,whole_assembly_verified=False)
(A/'results/BOTTOM_MOUNT_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(checks_passed=out['checks_passed'],count=len(checks),failed=[c for c in checks if not c['passed']],area_mm2=area,mass_kg=out['plate_mass_estimate_kg'])));assert out['checks_passed']
