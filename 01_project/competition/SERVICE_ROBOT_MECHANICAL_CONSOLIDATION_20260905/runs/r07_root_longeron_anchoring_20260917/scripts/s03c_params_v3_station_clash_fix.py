# -*- coding: utf-8 -*-
"""R07-E1 参数修正 V3：布尔干涉 FAIL(s04 二轮) 定位——G03/G09_1 与 G04/G10_1 同 x=154.85 站位、
z 间距 3.7 < 垫圈 Ø6，桥栓与梁栓头/垫圈/套互相侵入（最大 15.208 mm3）。
最小修改：桥第二栓 154.85→40（桥栓位 40/146：146 为不触 X150 竖孔(148.3..151.7)与
x=154.85 梁栓垫圈的最远可行位；40 改善端面载荷分布并避开 X30 竖孔）；G03/G04 二级防转
文本改为 M6 夹接+桥 x=40/146 双栓同板路径。组数/栓数/孔径/叠层不变。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

def main():
    raw = P.read_bytes().decode('utf-8')
    reps = [
        ('"bolts": [{"x_S_mm": 146, "z_S_mm": 109.0}, {"x_S_mm": 154.85, "z_S_mm": 109.0}]',
         '"bolts": [{"x_S_mm": 40, "z_S_mm": 109.0}, {"x_S_mm": 146, "z_S_mm": 109.0}]'),
        ('同站桥栓 G09@(154.85,109.0)+既有 M6 夹接@(160,±70)',
         '既有 M6 夹接@(160,±70)+桥 x=40/146 双栓锚固(同板载荷路径)'),
        ('同站桥栓 G10@(154.85,109.0)+既有 M6 夹接@(160,±70)',
         '既有 M6 夹接@(160,±70)+桥 x=40/146 双栓锚固(同板载荷路径)'),
        ('桥栓 x=146/154.85 避开纵梁 X150 Ø3.4 竖孔(孔缘 148.3..151.7)',
         '桥栓 x=40/146 避开纵梁 X30(孔缘 28.3..31.7)与 X150(孔缘 148.3..151.7) Ø3.4 竖孔及 x=154.85 梁栓垫圈(Ø6)；防压套/垫圈/栓头 z 间距不足禁同 x 站位（s04 二轮反例）'),
    ]
    for old, new in reps:
        if old not in raw:
            print('MISS:', old[:70]); continue
        raw = raw.replace(old, new)
    json.loads(raw)
    P.write_bytes(raw.encode('utf-8'))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e1 = data['root_anchoring_r07_e1']
    for g in e1['groups']:
        if g['id'] in ('G09', 'G10'):
            print(g['id'], g['bolts'])

if __name__ == '__main__':
    main()
