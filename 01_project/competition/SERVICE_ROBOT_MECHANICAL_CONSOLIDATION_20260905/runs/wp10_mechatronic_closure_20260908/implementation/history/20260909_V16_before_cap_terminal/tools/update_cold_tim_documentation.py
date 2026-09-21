"""Synchronize current candidate documentation with selected TIM, never alter history."""
from pathlib import Path
import json
A=Path(__file__).resolve().parents[1]
p=A/'tools/publish_cold_path_addendum.py'
s=p.read_text(encoding='utf-8')
for old,new in [
 ('台座面z=-96.379，真实TSP1600S名义厚0.229','台座面z=-96.353，TSP1800ST名义厚0.203mm（未验证压缩厚度）'),
 ('由0.229mm项目裁切TIM','由0.203mm项目裁切TIM'),
 ('冷指3.121mm/孔深5mm','冷指3.147mm/孔深5mm'),
]:
    assert old in s,old
    s=s.replace(old,new)
needle='新增螺钉复用Würth4123 53 20公开尺寸'
note='三处TIM同时选为TSP1800ST：25psi典型面积热阻0.28K·in²/W，已含两个接触界面；不额外叠加TIM的t/kA。它仍是绝缘材料，但典型击穿由原TSP1600S的5500Vac降到3000Vac，且贯穿的金属螺钉形成电气旁路，组件绝缘未经证明。目标25psi对应CHB总平均承压力557.524N、每侧234.455N，实际压强分布、压缩厚度和预紧未验证。厂家放气TML0.23%/CVCM0.05%是材料筛选数据。[厂家资料与选择](sources/COLD_TIM_SELECTION.json)。\n\n'
s=s.replace(needle,note+needle)
p.write_text(s,encoding='utf-8')
p=A/'sources/COLD_TIM_SELECTION.json'
d=json.loads(p.read_text(encoding='utf-8-sig'))
d['dielectric_tradeoff']={'old_TSP1600S_typical_breakdown_Vac':5500,'selected_TSP1800ST_typical_breakdown_Vac':3000,'method':'ASTM D149 typical material breakdown; not interface working voltage','metal_screws_bypass_TIM':True,'assembly_electrical_isolation_verified':False}
d['compression_scope']='0.203mm is nominal TDS thickness, not established thickness at25psi; no torque-preload calibration or pressure distribution verified.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('TIM documentation and explicit material tradeoff synchronized')
