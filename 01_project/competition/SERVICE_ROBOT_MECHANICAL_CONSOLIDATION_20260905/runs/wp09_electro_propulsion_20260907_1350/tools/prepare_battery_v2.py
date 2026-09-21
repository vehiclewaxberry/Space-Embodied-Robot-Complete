from pathlib import Path
import json,hashlib,math
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=R/'inputs/BATTERY_MOUNT_CONTRACT.json';c=json.loads(old.read_text())
c['revision']='V2_SOURCE_CONE_MATCHED_AFTER_V2_ACTUAL_ZERO_CONTACT'
c['catalogue_matched_countersink']=dict(reference_top_radius_mm=3.199999444449,actual_semiangle_rad=.785398,throat_radius_mm=1.7,
    depth_mm=(3.199999444449-1.7)/math.tan(.785398),nominal_included_angle_deg=90,
    basis='SOURCE_CATALOGUE_ACTUAL_MAIN_CONE; match exported surface parameterization; nominal manufacturing callout90deg not yet tolerance-qualified')
c['source_inputs'].update({str(p):sha(p) for p in [old,R/'results/battery_mount/EMISSION.json',R/'results/battery_mount/CHECK.json',
 R/'results/battery_mount/CHECK_V2.json',R/'results/BATTERY_CONE_DIAGNOSTIC.json',R/'candidate/battery_mount_detail.py',Path(__file__)]})
cp=R/'inputs/BATTERY_MOUNT_CONTRACT_V2.json';assert not cp.exists();cp.write_text(json.dumps(c,indent=2),encoding='utf-8')
src=(R/'candidate/battery_mount_detail.py').read_text()
src=src.replace("import json,sys,hashlib,importlib.util","import json,sys,hashlib,importlib.util,math")
src=src.replace("inputs/BATTERY_MOUNT_CONTRACT.json","inputs/BATTERY_MOUNT_CONTRACT_V2.json")
src=src.replace("cone=g.Solid.make_cone(3.2,1.7,1.5,Plane(origin=(x,y,p['adapter_top_z_mm']),z_dir=(0,0,-1)))",
"""seat=c['catalogue_matched_countersink']
            cone=g.Solid.make_cone(seat['reference_top_radius_mm'],seat['throat_radius_mm'],seat['depth_mm'],Plane(origin=(x,y,p['adapter_top_z_mm']),z_dir=(0,0,-1)))""")
src=src.replace("results/battery_mount'","results/battery_mount_v2'").replace("candidate/battery_mount.step'","candidate/battery_mount_v2.step'")
src=src.replace("# Cone virtual topØ6.4 matches measured catalogue main-cone continuation.","# Match the source STEP analytic main cone, preserving nominal90deg callout.")
sp=R/'candidate/battery_mount_detail_v2.py';assert not sp.exists();sp.write_text(src,encoding='utf-8')
gen=(R/'candidate/battery_mount.step.py').read_text().replace('battery_mount_detail.py','battery_mount_detail_v2.py')
gp=R/'candidate/battery_mount_v2.step.py';assert not gp.exists();gp.write_text(gen,encoding='utf-8')
native=(R/'tools/build_module_native_bounded_v2.py').read_text()
native=native.replace("ap.add_argument('--local-check',type=Path);a=ap.parse_args()","ap.add_argument('--local-check',type=Path);ap.add_argument('--emission',type=Path);a=ap.parse_args()")
native=native.replace("ep=R/'results'/kind/'EMISSION.json';cp=","ep=a.emission or R/'results'/kind/'EMISSION.json';cp=")
np=R/'tools/build_module_native_bounded_v3.py';assert not np.exists();np.write_text(native,encoding='utf-8')
print(json.dumps(c['catalogue_matched_countersink']))

