"""Bind public lower-impedance TIM and edit actual mounting dimensions."""
from pathlib import Path
import json,hashlib,shutil,urllib.request,datetime
A=Path(__file__).resolve().parents[1]
archive=A/'history/20260909_cold_path_TSP1600S_thermal_failure';archive.mkdir(parents=True,exist_ok=True)
paths=['thermal/BOTTOM_RADIATOR_MOUNT.json','thermal/FIXED_HEAT_PATH.json','thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json','thermal/RADIATOR_MESH_VIEW_SCREEN.json','results/COLD_PATH_GEOMETRY.json','results/COLD_PATH_TOOL_ACCESS.json','results/BOTTOM_MOUNT_GEOMETRY.json','results/FIXED_HEAT_GEOMETRY.json','mechanical/FIXED_HEAT_INSTANCE_PLAN.json','mechanical/NATIVE_COLD_INPUTS.json','mechanical/bottom_radiator.step','mechanical/fixed_heat_installation.step','mechanical/bottom_mount_assembly.step','mechanical/fixed_heat_bay.step','mechanical/cold_finger_tim.step']
for rel in paths:
    dst=archive/rel;dst.parent.mkdir(parents=True,exist_ok=True)
    if not dst.exists():shutil.copy2(A/rel,dst)
sources=[]
for name,url in [('TIM_TSP1800ST.pdf','https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-1800ST-en_GL.pdf'),('TIM_HENKEL_OUTGASSING.pdf','https://dm.henkel-dam.com/is/content/henkel/product-sheet-nasa-outgassing-5011-products-a4'),('TIM_TSP3500_COMPARISON.pdf','https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-3500-en_GL.pdf')]:
    path=A/'sources'/name
    if not path.exists():
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request,timeout=40) as r:blob=r.read()
        assert blob.startswith(b'%PDF');path.write_bytes(blob)
    sources.append(dict(path='sources/'+name,url=url,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
def read(rel):return json.loads((A/rel).read_text(encoding='utf-8-sig'))
def write(rel,x):(A/rel).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
p=read('thermal/BOTTOM_RADIATOR_MOUNT.json');c=p['chb_path']
c.update(TIM_family='BERGQUIST SIL PAD TSP 1800ST',TIM_thickness_mm=.203,wall_TIM_thickness_mm=.203,seat_z_mm=-96.353,
 TIM_impedance_C_in2_W_at25psi=.28,TIM_impedance_vs_pressure=[{'psi':10,'C_in2_W':.37},{'psi':25,'C_in2_W':.28},{'psi':50,'C_in2_W':.23},{'psi':100,'C_in2_W':.21},{'psi':200,'C_in2_W':.20}],
 wall_TIM_material='TSP1800ST project cut,0.203mm nominal, naturally tacky;25psi0.28 K in2/W typical reference, not guaranteed mounted resistance',
 previous_TIM_disposition='TSP1600S actual cold-path result105.141870C at2.5mm in folded330K/+Ysun CHB-only scenario; retained history. Material changed, task and105C limit not reduced.')
p['qualification']['revision_state']='TSP1800ST_SOURCE_EDITED_READBACK_PENDING';write('thermal/BOTTOM_RADIATOR_MOUNT.json',p)
f=read('thermal/FIXED_HEAT_PATH.json');d=next(d for d in f['devices'] if d['id']=='U202_CHB');d['TIM_mm'][2]=.203;d.update(TIM_family=c['TIM_family'],seat_origin_S_mm=[-25,0,-96.353],metal_path_mm=17.797);write('thermal/FIXED_HEAT_PATH.json',f)
write('sources/COLD_TIM_SELECTION.json',dict(schema='WP10_COLD_TIM_PUBLIC_SELECTION_V1',selected=c['TIM_family'],sources=sources,selection_basis='At same25psi reference pressure,0.28 vs0.75 forTSP1600S; remains electrically insulating; nominal0.203mm used in actual source dimensions; no extra PSA layer',TDS_revision='November2018',comparison={'TSP3500_0p254mm_25psi_C_in2_W':.43,'TSP1800ST_0p203mm_25psi_C_in2_W':.28,'Q2500':'Not selected atCHB: conductive/non-insulating; existing brake use unchanged'},manufacturer_outgassing_table={'TML_percent':.23,'CVCM_percent':.05,'testing_cure_schedule':'N/A','scope':'Manufacturer reported material screening, not NASA certification of purchased lot or spacecraft'},supplier_lot_and_compression_verified=False,preload_verified=False,flight_release=False))
print(json.dumps(dict(selected=c['TIM_family'],thickness_mm=.203,source_count=len(sources),archive=str(archive))))
