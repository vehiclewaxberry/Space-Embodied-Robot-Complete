"""Prepare a bounded, additive revision without modifying V28/V32 evidence."""
from pathlib import Path
import hashlib,json
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def put(p,t):
 with p.open('x',encoding='utf-8') as f:f.write(t)
p=read(C/'SPREADER_PARAMETERS_V28.json')
assert all(sha(A/k)==v for k,v in p['source_lock'].items()),'Parent source drift'
v32=read(C/'CANDIDATE_V32.json')
for k,v in v32['source_lock'].items():assert sha(k)==v,k
put(C/'CAD_BRIEF_V33.md','''# V33 底板导热截面改件

同一 WP10 候选；电气保持 V32。整机 S 坐标，毫米。原底板外侧面 z=-114.15，原板顶 z=-106.15。将现行一体加工散热加厚区从 x=[-166,10] 扩展到 [-166,168]，y=[-85.5,85.5]，加厚3.5，顶面z=-102.65。保留所有梁槽、安装孔、沉孔、CHB座及冷指。作为一体加工替代件，不是粘贴补片。

用既有6061-T6项目假设密度2700 kg/m³、导热率130 W/(m K)，不赋予材料批次资格。预期新增质量相对V28约0.207003 kg。辐射面积、环境、载荷、TIM典型压力假设保持不变。

验收：一个有效闭合实体；相对V28无减材；新金属与现行三态973个其他实例无体积碰撞；甲板名义间隙1.5；侧角件至少1.5。逐项绑定STEP差集体积、热网格体积、能量平衡、双网格及同工况回放。零碰撞仅覆盖新增金属，整机配合/公差/预紧/强度不据此通过。主输入板+Y热源块仍未实际安装，整机热闭环保持未完成。
''')
p.update(schema='WP10_V33_INTEGRAL_BOTTOM_SPREADER_DELTA',region_xy_mm=[-166,-85.5,168,85.5],revision_reason='Extend existing same-height integral spreader into available right-hand plate; retain every relief and interface.',parent_geometry='coupled_closure/spreader_v28.step',electrical_revision='V32')
for rel in ['coupled_closure/spreader_v28.step','coupled_closure/SPREADER_PARAMETERS_V28.json','coupled_closure/SPREADER_INSTANCE_PLAN_V28.json','coupled_closure/CANDIDATE_V30.json','coupled_closure/CANDIDATE_V32.json','power/MAIN_INPUT_COPPER_LOSS_V32.json','tools/spatial_radiator_network.py','tools/shared_battery_path.py','coupled_closure/coupled_adapter.py','thermal/RADIATOR_MESH_VIEW_SCREEN.json','thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json']:
 p['source_lock'][rel]=sha(A/rel)
put(C/'SPREADER_PARAMETERS_V33.json',json.dumps(p,indent=2))
src=(C/'spreader_v28.step.py').read_text().replace('V28','V33').replace('v28','v33').replace('LEFT_SPREADER','WIDE_SPREADER')
put(C/'spreader_v33.step.py',src)
src=(C/'check_spreader_v28.py').read_text().replace('V28','V33').replace('v28','v33')
old="expected=(((x1-x0)*(y1-y0))-(58*62)-(2*58*14)-(2*math.pi*4**2))*p['height_mm']"
new="expected=(((x1-x0)*(y1-y0))-(2*14.5*(y1-y0))-(58*62)-(2*58*14)-(2*math.pi*4**2)-(4*math.pi*3.5**2))*p['height_mm']"
assert old in src;src=src.replace(old,new)
src=src.replace('# Independent exact volume for this left-region design, excluding original\n    # 58x62 seat, two 58x14 feet and the two internal radius4 support bosses.', '# Independent full-width prism minus two beam slots, CHB seat, two feet,\n    # two radius4 support bosses and four radius3.5 MIPS pockets.')
src=src.replace("addv=volume(added);remv=volume(removed);bb=bbox(added)","addv=volume(added);remv=volume(removed);bb=bbox(added)\n    v28=step(HERE/'spreader_v28.step');increment=op(BRepAlgoAPI_Cut,new,v28)\n    assert abs(volume(op(BRepAlgoAPI_Cut,v28,new)))<1e-3\n    assert abs(volume(increment)-76667.71685990934)<1e-3")
src=src.replace("parent=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')", "parent=read(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json')\n    # Current host lineage audited independently: 973 unchanged rows, replacement skipped.\n    current_plan_sha=sha(HERE/'SPREADER_INSTANCE_PLAN_V28.json')")
src=src.replace('added_mass_kg=addv*2700e-9,','increment_vs_V28_volume_mm3=volume(increment),increment_vs_V28_mass_kg=volume(increment)*2700e-9,\n        current_plan_sha256=current_plan_sha,added_mass_kg=addv*2700e-9,')
put(C/'check_spreader_v33.py',src)
print('Prepared V33 source, parameters, brief and native delta checker.')
