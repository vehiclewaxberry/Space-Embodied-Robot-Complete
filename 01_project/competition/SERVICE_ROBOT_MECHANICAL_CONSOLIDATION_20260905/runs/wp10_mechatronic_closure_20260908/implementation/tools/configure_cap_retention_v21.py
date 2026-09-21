"""Bind a same-candidate retention delta; no change to V20 electrical geometry."""
from pathlib import Path
import json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
parent='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json'
p=json.loads((A/parent).read_text());r=next(r for r in p['states']['service']['rows'] if r['id']=='C203_LOWER_B')
assert all(next(x for x in s['rows'] if x['id']==r['id'])==r for s in p['states'].values())
d=dict(schema='WP10_CAP_RETENTION_CANDIDATE_V21',frame='S_mm',parent_plan=parent,parent_plan_sha256=sha(parent),parent_lower=r,
 wire_definition='power/CAP_HARNESS_DEFINITION_V19.json',wire_definition_sha256=sha('power/CAP_HARNESS_DEFINITION_V19.json'),
 design=dict(saddle_x_mm=[-31.9,-28.1],saddle_center_abs_y_mm=17.78,wire_z_mm=-64.,saddle_width_y_mm=3.,saddle_depth_mm=3.,saddle_edge_radius_mm=.4,
  arm_x_mm=[-31.9,-22.8],arm_abs_y_mm=[21.5,26.],arm_z_mm=[-53.5,-50.5],
  drop_abs_y_mm=[21.5,25.5],bridge_x_mm=[-31.9,-30.8],bridge_front_margin_to_channel_mm=.3,
  tie_center_x_mm=-29.45,tie_channel_x_mm=[-30.5,-28.4],channel_depth_mm=.45,
  knot_keepout_mm=[3.,4.,2.],knot_gap_below_saddle_mm=.4,
  tool_approach='Lace off-board before soldering; provisional knot envelope below saddle; tool/hand path not qualified'),
 lacing=dict(manufacturer='HellermannTyton',MPN='LTHT3A4NA',article='174-00011',material='PTFE high-tenacity multifilament, uncoated',
  width_min_max_mm=[1.32,1.78],thickness_min_max_mm=[.26,.40],catalog_min_tensile_N=66.,catalog_mass_g_per_m=.6,
  project_cut_allowance_mm_each=150.,quantity=2,installed_grip_rating_N=None,
  source_url='https://www.hellermanntyton.com/products/cable-ties-without-serration/ltht3a4na/174-00011',
  source_checked_local_date=datetime.date.today().isoformat(),catalog_search=dict(url='https://api.step.parts/v1/parts?q=LTHT3A4NA&pageSize=5',reachable=True,total=0),
  representation='Maximum tape cross-section around nominal maximum-diameter wire and saddle; not a vendor installed knot model'),
 material=dict(candidate='Unfilled PEEK machined stock',E_sensitivity_MPa=[2000.,3500.,4500.],strength_allowable_MPa=None,density_for_mass_estimate_kg_m3=1300.,flight_qualified=False),
 force_scenarios_N=[.1,1.,5.],
 scope=dict(geometry_verified=False,installed_grip_verified=False,strain_relief_complete=False,whole_design_complete=False,manufacturing_release=False),
 assembly_sequence=['Machine two integral saddle outriggers on retained lower B; retain original clamp bore geometry.',
 'Install cap and lower bands, then dress two white wires to the source route without terminal preload.',
 'Tie at the channel before soldering; keep proposed knot and trimmed tails in the under-saddle envelope.',
 'Solder by separately qualified PTH process; inspect insulation, knot slip and absence of terminal load. No operation executed.'],
 limitations=['No assigned creep, outgassing or stock allowable; beam calculation is sensitivity only.',
 '66 N is catalog straight-tape strength, not knot strength, wire pull-out capacity or approved tension.',
 'Maximum wire and tape dimensions used; minimum wire OD, knot tension, creep and vibration retention need qualification.',
 'Existing main power protection, STOP/regen, thermal, propulsion and whole-body gates remain open.'])
target=A/'power/CAP_HARNESS_RETENTION_V21.json';assert not target.exists()
target.write_text(json.dumps(d,indent=2),encoding='utf-8')
(A/'mechanical/CAP_RETENTION_BRIEF_V21.md').write_text("""# C203—CHB 导线固定座 V21 设计输入

在当前 972 行父清单内替换 C203_LOWER_B，增加两段绑扎带；保留两根导线、电气板和全部既有孔位。坐标均为 S 系毫米。两侧悬臂连接到现有下半夹环外侧，鞍座仅位于约 3.985 mm 的导线直段，通道宽 2.1 mm，绑扎带最大宽 1.78 mm。鞍座接触边名义 R0.4。

交付：参数 JSON、三个 STEP 源和 STEP、974 行派生清单、局部精确邻件检查、带结及工具空间记录、装配 STEP 和查看图。检查保留原下夹环材料与通孔、单实体连通、导线及螺钉无体积穿透、三态邻件、实际通道宽度。绑扎带由目录尺寸建包络；step.parts 精确查询返回零条，没有厂家安装态 STEP。

PEEK 库存材料、绑扎张力、带结防滑、线材最小外径、公差、疲劳及振动仍待确认。目录 66 N 不作为安装态承载值；该设计不自动获得应变释放或制造放行结论。
""",encoding='utf-8')
print('V21 retention definition written; no parent source changed')

