"""Two segregated ground umbilical glands; source-derived interface envelopes, mm."""
from pathlib import Path
import json,hashlib,importlib.util,sys,math
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];R=F.parent
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):Path(p).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
def build():
 c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());mf=json.loads((R/'results/INTEGRATION_MANIFEST_V6.json').read_text())
 old=next(x for x in mf['states']['service']['instances'] if x['id']=='front_service_cover')
 spec=importlib.util.spec_from_file_location('ports_geom_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 job={'parts':{'cover':dict(path=old['step_path'],sha256=old['source_sha256'],T_S_local=old['T_S_local'])},'tolerances':c['acceptance']};g=m.Geometry(job,{})
 from build123d import Plane,Color,Compound
 from cadgen.assembly import AssemblyHelper
 def cyl(rad,x0,x1,y,z):return g.Solid.make_cylinder(rad,x1-x0,Plane(origin=(x0,y,z),z_dir=(1,0,0)))
 source=g.load('cover');cover=source;parts={};meta={};locations=[('PWR',-70,55,7.5),('RS422',-70,-55,5.0)]
 for tag,y,z,od in locations:
  cover=cover-cyl(8.1,182,186,y,z)
  # Full outer circular envelopes contain the AF19 gland and AF22 nut. Internal seal is not reverse engineered.
  gland=(cyl(8,177,185,y,z)+cyl(11,185,211,y,z))-cyl(od/2,176,212,y,z)
  nut=cyl(12.75,179,183,y,z)-cyl(8,178,184,y,z)
  for suffix,s in [('GLAND',gland),('NUT',nut)]:
   k=tag+'_'+suffix;parts[k]=s;meta[k]=dict(representation_role='SIMPLIFIED_PROXY',pn='53111010' if suffix=='GLAND' else '53119010',qualification='SUPPLIER_INTERFACE_ENVELOPE; NUT_THICKNESS_4_MM_ASSUMED; NO_THREAD_OR_SEAL_MODEL',product_role='GSE_REMOVABLE')
 parts['front_service_cover_GSE']=cover;meta['front_service_cover_GSE']=dict(representation_role='PHYSICAL_GEOMETRY',pn='WP09_FRONT_GSE_PORTS',product_role='GROUND_CONFIGURATION_CANDIDATE',qualification='PARENT_COVER_WITH_TWO_ADDITIONAL_D16_2_BORES; STRENGTH_NOT_QUALIFIED')
 a=AssemblyHelper('WP09_GROUND_PORTS')
 for k,s in parts.items():
  col=Color(.69,.76,.83,.68) if 'cover' in k else Color(.22,.26,.32)
  a.add(type(s)(s.wrapped).located(s.global_location),k,color=col)
 for tag,y,z,od in locations:
  s=cyl(od/2,163,241,y,z);a.add(s,'VISUAL_ONLY_'+tag+'_STRAIGHT_CABLE',color=Color(.91,.28,.08) if tag=='PWR' else Color(.13,.50,.90))
 return parts,meta,a.build(),g,source,locations
def emit():
 p,meta,a,g,old,loc=build();out=F/'candidate/parts';out.mkdir(exist_ok=True);records={}
 from build123d import export_step
 for k,s in p.items():
  assert s.is_valid and len(s.solids())==1
  target=out/(k+'.step');export_step(s,target);records[k]=dict(path=str(target),sha256=sha(target),**g.facts(s),**meta[k])
 target=F/'candidate/functional_ports.step';export_step(a,target)
 write(F/'results/PORTS_EMISSION.json',dict(parts=records,assembly_step=str(target),assembly_sha256=sha(target),locations=loc,removed_parent_ids=['front_service_cover'],nominal_thread_length_mm=8,nominal_panel_mm=2,assumed_nut_height_mm=4,diametral_hole_clearance_mm=.2,unassigned_thread_length_mm=2,visual_cables_not_in_native=True,cover_removed_volume_mm3=g.volume(old)-g.volume(p['front_service_cover_GSE']),gland_interface_source='LAPP STM family: M16x1.5; clamp4..10; AF19; total34; thread8. Nut AF22; thickness4 design assumption',cut_length_mm=None,manufacturing_release=False))
 print('EMITTED',len(records),flush=True)
if __name__=='__main__':emit()
