# -*- coding: utf-8 -*-
"""R07-E4 模型补丁（带断言，失配即 FAIL 不覆盖）：
1) spacecraft_model.py 新增 rear_bulkhead_clamp_spec/parts（build 前）；
2) rootadd 拦截 RB_end_screw_-1_*：M4×22→M4×30 包络，锚点 x=-183→-191，pn 换 E4 候选；
3) build() 读取 E4 参数块并消费夹套件（ROOT_STRUCTURE, GOLD, AL_DENSITY_CANDIDATE）。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
PM = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py'

FUNCS = '''
def rear_bulkhead_clamp_spec(P):
    """R07-E4 (rear end frame -> rear launch retention bulkhead) corner clamp stack table, driven by
    design_parameters.json rear_bulkhead_clamp_r07_e4; ticket R07 connection_edges 第3边."""
    E4=P['rear_bulkhead_clamp_r07_e4'];out=[]
    for g in E4['groups']:
        out.append(dict(group=g['id'],sy=g['sy'],sz=g['sz'],y=g['sy']*107.15,z=g['sz']*107.15,
            screw=f"RB_end_screw_-1_{g['sy']}_{g['sz']}",plug=f"RB_end_plug_-1_{g['sy']}_{g['sz']}",
            frame='RB_end_frame_-1',bulkhead='rear_launch_bulkhead'))
    return out

def rear_bulkhead_clamp_parts(P):
    """R07-E4 stepped clamp sleeves (real Al candidates, E1 sleeve precedent): barrel slips into the
    existing Ø8 window (x[-189,-183]), flange bears on the bulkhead outer face (x[-191,-189]),
    ID Ø4.5 passes the lengthened M4 screw; no new holes in any member."""
    E4=P['rear_bulkhead_clamp_r07_e4'];S=E4['clamp_sleeve'];out=[]
    for r in rear_bulkhead_clamp_spec(P):
        y,z=r['y'],r['z'];gid=r['group']
        barrel=cylinder(S['barrel_od_mm'],S['barrel_length_mm'],(-186,y,z),(1,0,0))
        flange=cylinder(S['flange_od_mm'],S['flange_thickness_mm'],(-189-S['flange_thickness_mm']/2,y,z),(1,0,0))
        sleeve=(barrel+flange)-cylinder(S['id_diameter_mm'],12,(-186,y,z),(1,0,0))
        out.append(dict(name=f'e4_clamp_sleeve_{gid}',shape=sleeve,mount='REAR_END_FRAME_M4_CONNECTION_E4_CLAMP_STACK',
            basis='E4_CLAMP_SLEEVE_CANDIDATE_BARREL_OD%sX%s_FLANGE_OD%sX%s; AL_DENSITY_CANDIDATE; MATERIAL/CRUSH/BEARING UNKNOWN'%(
                S['barrel_od_mm'],S['barrel_length_mm'],S['flange_od_mm'],S['flange_thickness_mm']),
            kw=dict(group=gid,y=y,z=z,screw=r['screw'],plug=r['plug'])))
    return out

'''

pairs = [
    ("def build(state='service',view='complete',include_arm=True,write_parts=False):",
     FUNCS + "def build(state='service',view='complete',include_arm=True,write_parts=False):"),
    ("""        if name and name.startswith('RB_end_plug_'):
            s=box((20,7.8,7.8));s=bore(s,3.3,24,(0,0,0),(1,0,0));s=bore(s,4.5,12,(-np.sign(xyz[0])*3,0,0))
""",
     """        if name and name.startswith('RB_end_plug_'):
            s=box((20,7.8,7.8));s=bore(s,3.3,24,(0,0,0),(1,0,0));s=bore(s,4.5,12,(-np.sign(xyz[0])*3,0,0))
        # R07-E4: 后场 M4 螺钉包络延长 22→30（锚点 x=-183→-191 压夹套法兰），尖端 x=-161 与端塞啮合不变。
        if name and name.startswith('RB_end_screw_-1_'):
            _L=E4['rear_screw']['length_mm']
            s=cylinder(4,_L,(0,0,-_L/2))+cylinder(7,4,(0,0,2));xyz=(-E4['rear_screw']['anchor_abs_x_mm'],xyz[1],xyz[2]);pn=E4['rear_screw']['pn_candidate']
"""),
    ("    E3=P['retention_joints_r07_e3'];E3E1=E3['edge1_clamp'];E3E2=E3['edge2_foot'];E3G1=E3E1['groups'];E3G2=E3E2['groups']",
     "    E3=P['retention_joints_r07_e3'];E3E1=E3['edge1_clamp'];E3E2=E3['edge2_foot'];E3G1=E3E1['groups'];E3G2=E3E2['groups']\n    E4=P['rear_bulkhead_clamp_r07_e4']"),
    ("""    # R07-E3 retention joint hardware: clamp bolts (crossbeam -> longeron) + foot bolts (clevis -> lug).
    for p in retention_clamp_parts(P)+retention_foot_parts(P):
        add(p['shape'],p['name'],parent='ONBOARD_RETENTION',mount=p['mount'],rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis=p['basis'])
""",
     """    # R07-E3 retention joint hardware: clamp bolts (crossbeam -> longeron) + foot bolts (clevis -> lug).
    for p in retention_clamp_parts(P)+retention_foot_parts(P):
        add(p['shape'],p['name'],parent='ONBOARD_RETENTION',mount=p['mount'],rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis=p['basis'])
    # R07-E4 rear bulkhead clamp sleeves: real Al candidates (E1 sleeve precedent), no new holes.
    for p in rear_bulkhead_clamp_parts(P):
        add(p['shape'],p['name'],parent='ROOT_STRUCTURE',mount=p['mount'],color=GOLD,basis=p['basis'])
"""),
]

def main():
    raw = PM.read_bytes()
    n = 0
    for old, new in pairs:
        old_b = old.encode('utf-8'); new_b = new.encode('utf-8')
        cnt = raw.count(old_b)
        assert cnt == 1, f'pattern not unique ({cnt}): {old[:60]!r}'
        raw = raw.replace(old_b, new_b); n += 1
    PM.write_bytes(raw)
    print(f'spacecraft_model.py: {n} replacements OK')

if __name__ == '__main__':
    main()
