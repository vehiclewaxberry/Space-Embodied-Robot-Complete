from pathlib import Path
import hashlib,json,math,itertools
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
A=Path(__file__).resolve().parents[1];p=A/'mechanical/brake_resistor_installation.step'
r=STEPControl_Reader();assert int(r.ReadFile(str(p)))==1;r.TransferRoots();s=r.OneShape()
e=TopExp_Explorer(s,TopAbs_SOLID);solids=[]
def prop(s,vol=True):
    q=GProp_GProps();(BRepGProp.VolumeProperties_s if vol else BRepGProp.SurfaceProperties_s)(s,q)
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b)
    return dict(measure=q.Mass(),bbox=list(b.Get()) if not b.IsVoid() else None,COM=list(q.CentreOfMass().Coord()))
while e.More():solids.append(e.Current());e.Next()
facts=[prop(s) for s in solids];checks=[]
def ck(n,b,**kw):checks.append(dict(name=n,passed=bool(b),**kw))
ck('19_solids',len(solids)==19)
plate=[i for i,f in enumerate(facts) if f['measure']>100000];pads=[i for i,f in enumerate(facts) if abs(f['measure']-56*51*.152)<1e-5]
ck('one_plate_three_TIM',len(plate)==1 and len(pads)==3)
assert len(plate)==1 and len(pads)==3
centers=[(-37.5,-37.),(37.5,-37.),(0.,37.)];oem=[i for i in range(len(solids)) if i not in plate+pads]
groups=[[i for i in oem if math.hypot(facts[i]['COM'][0]-x,facts[i]['COM'][1]-y)<30] for x,y in centers]
ck('OEM_groups_five_each',all(len(g)==5 for g in groups) and len(set(sum(groups,[])))==15)
if not all(len(g)==5 for g in groups):
    (A/'results/BRAKE_CONTACT_GEOMETRY.json').write_text(json.dumps(dict(checks=checks,checks_passed=False,facts=facts),indent=2),encoding='utf-8')
    raise AssertionError('OEM group placements do not match authored assembly datums')
overlap=[]
for i,j in [(plate[0],k) for k in pads+oem]+[(i,j) for i in pads for j in oem]:
    op=BRepAlgoAPI_Common(solids[i],solids[j]);op.Build();assert op.IsDone()
    ss=TopExp_Explorer(op.Shape(),TopAbs_SOLID);vol=0.
    while ss.More():vol+=prop(ss.Current())['measure'];ss.Next()
    overlap.append(dict(pair=[i,j],common_volume_mm3=vol))
ck('plate_TIM_OEM_zero_overlap',all(abs(x['common_volume_mm3'])<1e-6 for x in overlap),tested_pairs=len(overlap))
def hfaces(s,z):
    e=TopExp_Explorer(s,TopAbs_FACE);fs=[]
    while e.More():
        f=TopoDS.Face_s(e.Current());ad=BRepAdaptor_Surface(f)
        if str(ad.GetType()).endswith('Plane') and abs(ad.Plane().Axis().Direction().Z())>.999 and abs(ad.Plane().Location().Z()-z)<1e-6:fs.append(f)
        e.Next()
    return fs
contacts=[]
for i in pads:
    area=0.
    for f in hfaces(solids[i],6.152):
        for j in oem:
            for of in hfaces(solids[j],6.152):
                op=BRepAlgoAPI_Common(f,of);op.Build();assert op.IsDone();area+=prop(op.Shape(),False)['measure']
    contacts.append(dict(pad=i,area_mm2=area))
ck('each_TIM_contacts_2856mm2',all(abs(c['area_mm2']-2856)<1e-5 for c in contacts))
distances=[]
for gi,gj in itertools.combinations(range(3),2):
    vals=[]
    for i in groups[gi]:
        for j in groups[gj]:
            d=BRepExtrema_DistShapeShape(solids[i],solids[j]);d.Perform();assert d.IsDone();vals.append(d.Value())
    distances.append(dict(pair=[gi+1,gj+1],minimum_mm=min(vals)))
ck('resistor_groups_do_not_touch',all(d['minimum_mm']>0 for d in distances))
bb=facts[plate[0]]['bbox'];ck('plate_dimensions',all(abs(g-w)<1e-5 for g,w in zip([bb[3]-bb[0],bb[4]-bb[1],bb[5]-bb[2]],[150,160,6])))
areas=[c['area_mm2'] for c in contacts]
thermal=dict(material='BERGQUIST SIL PAD TSP Q2500',source_pdf='sources/bergquist_q2500.pdf',
    source_sha256=hashlib.sha256((A/'sources/bergquist_q2500.pdf').read_bytes()).hexdigest(),nominal_thickness_mm=.152,
    OEM_recommended_Q_PAD_II=True,electrical_insulation_credit=False,pressure_target_psi=50.,
    uniform_clamp_force_each_N=[a*1e-6*50*6894.757293 for a in areas],
    typical_Rth_each_K_per_W=[.22*25.4**2/a for a in areas],
    installed_pressure_verified=False,thermal_performance_verified=False,external_radiator_connected=False,
    OEM_torque_Nm=2.,OEM_max_torque_Nm=2.5,torque_not_converted_to_guaranteed_contact_force=True)
o=dict(source_step_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),facts=facts,checks=checks,check_count=len(checks),
    checks_passed=all(c['passed'] for c in checks),external_pairs=overlap,contacts=contacts,inter_resistor_distances=distances,
    TIM_interface=thermal,carrier_volume_mm3=facts[plate[0]]['measure'],carrier_density_assumed_kg_per_m3=2700.,
    carrier_mass_estimate_kg=facts[plate[0]]['measure']*2700e-9,three_resistor_OEM_mass_kg=.249,
    mass_not_added_to_873=True,sensors_and_fasteners_not_installed=True,mechanical_heat_path_closed=False)
(A/'results/BRAKE_CONTACT_GEOMETRY.json').write_text(json.dumps(o,indent=2),encoding='utf-8')
print(json.dumps(dict(checks=len(checks),passed=o['checks_passed'],contacts=contacts,distances=distances,plate_mass_kg=o['carrier_mass_estimate_kg'])))
assert o['checks_passed'],[x for x in checks if not x['passed']]
