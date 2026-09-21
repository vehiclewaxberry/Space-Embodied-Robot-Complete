# -*- coding: utf-8 -*-
"""R07-E3 v2 参数修复（探针 FAIL v1 闭环，非裁决）：
边1 端面盲孔 nominal/modeled 10/12 -> 7/7（贯入 8->5，SHORT_ENGAGEMENT 登记）；
边2 栓链 y -94.15 -> -90.65（杆-杆净距 3.5、孔-孔净距 1.25、耳座边缘 1.25、备用孔边缘 2.03）。
所有替换带断言，失配即 FAIL 不覆盖。"""
import io, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
PJ = ENG / 'design_parameters.json'
PM = ENG / 'spacecraft_model.py'

def patch(path, pairs):
    raw = path.read_bytes()
    n = 0
    for old, new in pairs:
        old_b = old.encode('utf-8'); new_b = new.encode('utf-8')
        cnt = raw.count(old_b)
        assert cnt == 1, f'{path.name}: pattern not unique ({cnt}): {old[:60]!r}'
        raw = raw.replace(old_b, new_b); n += 1
    path.write_bytes(raw)
    print(f'{path.name}: {n} replacements OK')

patch(PJ, [
    ('"beam_end_tapped_hole": {"diameter_mm": 3.4, "nominal_depth_mm": 10, "modeled_depth_mm": 12,',
     '"beam_end_tapped_hole": {"diameter_mm": 3.4, "nominal_depth_mm": 7, "modeled_depth_mm": 7,'),
    ('"note": "THREADLESS_ENVELOPE：Ø3.4 光孔+Ø3 杆零干涉包络；底孔/攻丝/有效啮合 UNKNOWN"},',
     '"note": "THREADLESS_ENVELOPE：Ø3.4 光孔+Ø3 杆零干涉包络；底孔/攻丝/有效啮合 UNKNOWN；v2 互避边2 竖栓链：名义贯入 8→5mm SHORT_ENGAGEMENT_REGISTERED（探针 FAIL v1：边1杆 vs 边2杆 16.37mm3 相贯）"},'),
    ('每足叉（k=0,1）2 枚 M4 候选竖栓（x=站心±5.5, y=-94.15）',
     '每足叉（k=0,1）2 枚 M4 候选竖栓（x=站心±5.5, y=-90.65）'),
    ('"bolt_y_S_mm": -94.15,', '"bolt_y_S_mm": -90.65,'),
    ('新孔 x±5.5 与其边缘距 1.0', '新孔(x±5.5, y=-90.65) 与其边缘距 2.03'),
    ('"e1_bolt_avoidance":',
     '"edge1_edge2_interference_avoidance_v2": "探针 FAIL v1（e3_clamp_bolt_J02/J04 vs e3_foot_bolt_C01/C02 各 16.37mm3）闭环：边2 栓链 y -94.15→-90.65 + 边1 盲孔深 12→7 → 栓杆-栓杆 y 净距 3.5、梁内孔-孔净距 1.25、耳座孔缘 1.25、备用中心孔缘 2.03；FAIL 归档 logs/s01b_probe_FAIL_v1.log",\r\n      "e1_bolt_avoidance":'),
])

patch(PM, [
    ("# R07-E3 边1/边2：横梁端面盲孔(Y 轴)与竖向对偶孔(x±5.5@y=-94.15)打孔 delta。",
     "# R07-E3 边1/边2：横梁端面盲孔(Y 轴)与竖向对偶孔(x±5.5@y=bolt_y_S_mm)打孔 delta；v2 盲孔心随 modeled_depth 参数化。"),
    ("for b in g['bolts']:xb=bore(xb,E3E1['hole_diameter_mm'],E3E1['beam_end_tapped_hole']['modeled_depth_mm'],(b['x_S_mm']-x,g['side_sy']*95.15,E3E1['bolt_z_S_mm']-101.15),(0,1,0))",
     "for b in g['bolts']:xb=bore(xb,E3E1['hole_diameter_mm'],E3E1['beam_end_tapped_hole']['modeled_depth_mm'],(b['x_S_mm']-x,g['side_sy']*(101.15-E3E1['beam_end_tapped_hole']['modeled_depth_mm']/2),E3E1['bolt_z_S_mm']-101.15),(0,1,0))"),
    ("for b in g['bolts']:xb=bore(xb,E3E2['hole_diameter_mm'],12,(b['x_S_mm']-x,-94.15,0))",
     "for b in g['bolts']:xb=bore(xb,E3E2['hole_diameter_mm'],12,(b['x_S_mm']-x,E3E2['bolt_y_S_mm'],0))"),
    ("for b in g['bolts']:lug=bore(lug,E3E2['hole_diameter_mm'],14,(b['x_S_mm']-x,0,0))",
     "for b in g['bolts']:lug=bore(lug,E3E2['hole_diameter_mm'],14,(b['x_S_mm']-x,E3E2['bolt_y_S_mm']+94.15,0))"),
    ("for b in g['bolts']:foot=bore(foot,E3E2['hole_diameter_mm'],E3E2['foot_tapped_hole']['modeled_depth_mm'],(b['x_S_mm']-x,4.85,-15+E3E2['foot_tapped_hole']['modeled_depth_mm']/2))",
     "for b in g['bolts']:foot=bore(foot,E3E2['hole_diameter_mm'],E3E2['foot_tapped_hole']['modeled_depth_mm'],(b['x_S_mm']-x,E3E2['bolt_y_S_mm']+99,-15+E3E2['foot_tapped_hole']['modeled_depth_mm']/2))"),
])
print('v2 param fix done')
