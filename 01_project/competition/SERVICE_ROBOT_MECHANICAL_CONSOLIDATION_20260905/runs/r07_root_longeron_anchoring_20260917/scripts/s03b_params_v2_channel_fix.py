# -*- coding: utf-8 -*-
"""R07-E1 参数修正 V2：布尔干涉 FAIL(20260917 s04 首轮) 定位——纵梁为 12×12/8×8 四壁方管，
管内腔 z/y∈[103.15,111.15]；原栓位 z=±104.15/110.15 + 套 OD5 侵入管上/下壁。
最小修改：栓位 z→±105.3(横梁)/109.0(桥)；防压套 OD5→Ø4(ID3.4,壁0.3 候选薄壁)；
登记套自管端预置的装配顺序。其余孔位/叠层/组数不变。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
P = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'

def main():
    raw = P.read_bytes().decode('utf-8')
    eol = '\r\n' if '\r\n' in raw else '\n'
    reps = [
        ('"outer_diameter_mm": 5,', '"outer_diameter_mm": 4,'),
        ('"length_mm": 8,' + eol +
         '        "reduced_outer_diameter_mm": 4,' + eol +
         '        "reduced_note": "x=154.85 站邻近端塞(x>=157)，套外径降至 4.0（壁 0.3 mm 候选薄壁，制造审查项；防压功能 UNKNOWN）"',
         '"length_mm": 8,' + eol +
         '        "wall_mm": 0.3,' + eol +
         '        "note": "Ø4/Ø3.4 薄壁 0.3 mm 候选（制造审查项）；须置于 8×8 管内腔(y/z 103.15..111.15)并避开端塞(x>=157)；防压有效性 UNKNOWN",' + eol +
         '        "assembly": "套预置于纵梁管内腔螺栓站位：自管端(x=±177)在端塞装入前送入并定位；穿栓前的定位/防滚保持 UNKNOWN"'),
        ('"z_S_mm": 104.15', '"z_S_mm": 105.3'),
        ('"z_S_mm": -104.15', '"z_S_mm": -105.3'),
        ('"z_S_mm": 110.15', '"z_S_mm": 109.0'),
        (', "sleeve_od_mm": 4', ''),
        ('z=±104.15/110.15', 'z=±105.3/109.0'),
        ('同站桥栓 G09@(154.85,110.15)', '同站桥栓 G09@(154.85,109.0)'),
        ('同站桥栓 G10@(154.85,110.15)', '同站桥栓 G10@(154.85,109.0)'),
        ('（滑移/残余转角 UNKNOWN）",', '（滑移/残余转角 UNKNOWN）",'),
    ]
    for old, new in reps:
        if old not in raw:
            print('MISS:', old[:60]); continue
        raw = raw.replace(old, new)
    # concept 追加防压套装配顺序
    old_c = '（滑移/残余转角 UNKNOWN）"\r' if False else None
    anchor = '防转由同站桥栓与既有 M6/贯通杆夹接链二级承担（滑移/残余转角 UNKNOWN）'
    if anchor in raw and '管内腔站位' not in raw:
        raw = raw.replace(anchor, anchor + '；防压套 Ø4/Ø3.4×8 须在端塞装入前自管端预置于管内腔站位')
    json.loads(raw)
    P.write_bytes(raw.encode('utf-8'))
    data = json.loads(P.read_bytes().decode('utf-8'))
    e1 = data['root_anchoring_r07_e1']
    print('OK sleeve OD', e1['fastener_candidate']['anti_crush_sleeve']['outer_diameter_mm'])
    print('z values:', sorted({b['z_S_mm'] for g in e1['groups'] for b in g['bolts']}))
    print('overrides left:', sum(1 for g in e1['groups'] for b in g['bolts'] if 'sleeve_od_mm' in b))

if __name__ == '__main__':
    main()
