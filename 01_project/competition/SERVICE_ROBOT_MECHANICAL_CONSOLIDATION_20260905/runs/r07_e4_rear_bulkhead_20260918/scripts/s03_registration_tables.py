# -*- coding: utf-8 -*-
"""R07-E4 登记表生成（纯参数驱动，无 CAD）：
端框→后发射保留隔框（R07 connection_edges 第3边）：对偶孔 4 / 叠层 4 / 安装面 4 / 工具 4（每角一行）。
每角登记 A/B件、孔轴面、约束自由度、连接形式、标准件、材料 UNKNOWN、载荷 UNKNOWN、装配/工具路径、
来源与验证层级；与既有端塞/M4 螺钉链（E2 分段销同角区）的关系与装序写入登记。
任务书 §4.1 第4行逐边登记口径；供应方侧参数化不臆造孔系；图连通不等于承载，载荷 UNKNOWN。"""
import sys, json, csv, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E4 = sm.P['rear_bulkhead_clamp_r07_e4']
S = E4['clamp_sleeve']; RS = E4['rear_screw']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    spec = sm.rear_bulkhead_clamp_spec(sm.P)

    # ---------- 1) 对偶孔表（4 角） ----------
    pairs = []
    for r in spec:
        pairs.append({
            'pair_id': f"E4P-{r['group']}", 'edge': 'rear_frame_to_bulkhead 端框→后发射保留隔框 (R07 connection_edges 第3边)',
            'group': r['group'],
            'A_part': 'rear_launch_bulkhead (WP03 原生; 四角 Ø8 窗口既有，本包不改)',
            'B_part': 'RB_end_frame_-1 (pn WP01-RB-END-FRAME-R2; 四角 Ø4.5 M4 接口既有，本包不改) + RB_end_plug_-1_%s_%s (Ø3.3 X 导孔既有)' % (r['sy'], r['sz']),
            'hole_axis_S': {'point_mm': [-186, r['y'], r['z']], 'direction': [1, 0, 0]},
            'hole_diameter_mm': {'bulkhead_window': 8.0, 'end_frame_hole': 4.5, 'plug_pilot': 3.3},
            'A_hole': '隔框 Ø8 窗口（深10过钻，体 6）——既有；夹套筒 OD7.9 滑入（隙 0.05/边）',
            'B_hole': '端框 Ø4.5 X 向孔（深8过钻，体 6）——既有 M4 接口；端塞 Ø3.3 导孔——既有螺纹啮合惯例',
            'no_new_holes': E4['clamp_sleeve']['no_new_holes'],
            'datum': '隔框内面 x=-183 与端框后面 x=-183 面贴合（实读 Common=0.0 零体积；贴合区=端框环带扣除四角窗口）',
            'stack_order': E4['stack_order'],
            'fastener_candidate': f"{RS['thread']} 延长包络 22→{RS['length_mm']}（锚点 x=-183→-191，尖端 x=-161 不变）+ 阶梯夹套 筒OD{S['barrel_od_mm']}×{S['barrel_length_mm']}/法兰OD{S['flange_od_mm']}×{S['flange_thickness_mm']}/ID{S['id_diameter_mm']}",
            'material': 'UNKNOWN（夹套 AL_DENSITY_CANDIDATE 2.7e-6 仅候选估算）', 'grade': 'UNKNOWN', 'fit': 'UNKNOWN',
            'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'load': 'UNKNOWN (design loads pending; 本登记不代表承载通过)',
            'dof_registration': '面贴合(绕 Y/Z 转动+Y/Z 平移) + 4 套筒入窗口(X 以外自由度正定位 FOUR_SLEEVE_POSITIVE) + 栓链夹 X 向；几何登记非承载证明',
            'self_retention': '单头正向保持（头→套法兰→隔框→端框→端塞啮合 螺纹惯例）',
            'relation_to_existing_chains': '与既有端塞/M4 螺钉链同轴共存：原 M4×22 仅夹端框→端塞（头 recessed 于窗口，隔框游离）；本包延长为 M4×30 并加夹套后，同一栓链将隔框纳入夹紧；E2 分段销在 x=-164 角区 Z 向站位，与本堆栈 x∈[-195,-183] 不交、装序无冲突',
            'tool_path': '自 -x 星外侧沿 +X 拧入；工具轴 [1,0,0]；行程候选 ~50mm（隔框就位后先插套后拧栓）',
            'source': 'design_parameters.json rear_bulkhead_clamp_r07_e4 (provenance: issues.json R07 第3边; WP03 plan §4.1 第4行)',
            'verification_level': 'DIGITAL_GEOMETRY_CANDIDATE; 机器读回/布尔干涉见本 run acc 证据; 载荷/强度/配合 NOT_RUN; 供应方 ICD UNKNOWN',
        })
    cols = ['pair_id', 'edge', 'group', 'A_part', 'B_part', 'datum',
            'fastener_candidate', 'material', 'fit', 'preload', 'locking', 'load', 'self_retention', 'verification_level']
    with open(ev / 'e4_dual_hole_pairs_4.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(pairs)
    wlf(ev / 'e4_dual_hole_pairs_4.json', json.dumps({'run': 'r07_e4_rear_bulkhead_20260918', 'table': 'dual_hole_pairs', 'row_count': len(pairs), 'rows': pairs}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 2) 紧固叠层表（4 角） ----------
    stacks = []
    for r in spec:
        stacks.append({'pair_id': f"E4P-{r['group']}", 'sub_stacks': [
            {'sub_stack': 'aft(-x 星外,自外而内)', 'layers': [
                {'layer': 'head', 'x_interval_S_mm': [-195, -191], 'od_mm': RS['head_diameter_mm'], 'bearing_face': '头下面 → 夹套法兰'},
                {'layer': 'sleeve_flange', 'x_interval_S_mm': [-191, -189], 'od_mm': S['flange_od_mm'], 'bearing_face': '隔框外面 x=-189（承压环 8→12）'},
                {'layer': 'bulkhead', 'x_interval_S_mm': [-189, -183], 'thickness_mm': 6, 'note': '隔框（Ø8 窗口+夹套筒 OD7.9，隙 0.05/边）'},
                {'layer': 'end_frame', 'x_interval_S_mm': [-183, -177], 'thickness_mm': 6, 'note': '后端框（Ø4.5 M4 接口，既有）'},
                {'layer': 'plug_engagement', 'x_interval_S_mm': [-177, -161], 'engagement_mm': 16, 'note': 'Ø4 杆入端塞 Ø3.3 导孔（WP02 螺纹啮合惯例；与 M4×22 原啮合逐位不变）'}]}],
            'shank_diameter_mm': RS['shank_diameter_mm'], 'hole_diameter_mm': 4.5,
            'material_grade_fit_preload_locking': 'UNKNOWN'})
    wlf(ev / 'e4_fastener_stacks_4.json', json.dumps({'run': 'r07_e4_rear_bulkhead_20260918', 'table': 'fastener_stacks', 'row_count': len(stacks), 'rows': stacks}, ensure_ascii=False, indent=2) + '\n')
    with open(ev / 'e4_fastener_stacks_4.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pair_id', 'sub_stack', 'layer', 'x_interval_S_mm', 'od_or_thickness', 'bearing_face_or_note'])
        for s in stacks:
            for ss in s['sub_stacks']:
                for L in ss['layers']:
                    w.writerow([s['pair_id'], ss['sub_stack'], L['layer'], L['x_interval_S_mm'], L.get('od_mm', L.get('thickness_mm', '')), L.get('bearing_face', L.get('note', ''))])

    # ---------- 3) 安装面与约束方向登记（4 角） ----------
    mounts = []
    for r in spec:
        mounts.append({
            'group': r['group'], 'edge': 'rear_frame_to_bulkhead',
            'A_mating_face': {'instance': 'rear_launch_bulkhead', 'face': f'隔框内面 x=-183 角区（y,z=({r["y"]},{r["z"]})）+ 外面 x=-189（套法兰承压）+ Ø8 窗口柱面'},
            'B_mating_face': {'instance': 'RB_end_frame_-1', 'face': '端框后面 x=-183 环带角区（实读面贴合零体积）'},
            'sleeve_bearing_faces': [{'plane_x_S_mm': -189, 'note': '法兰 OD12 承压环（窗口缘 8→12）'},
                                     {'plane_x_S_mm': -191, 'note': '螺钉头 Ø7 承压面（法兰外面）'}],
            'screw_axis_S_mm': [[-186, r['y'], r['z']]],
            'constraint_directions': '面贴合(绕 Y/Z 转动+Y/Z 平移) + 4 套筒正定位 + 栓链夹 X 向；几何登记非承载证明',
            'note': '贴合关系实读：隔框∩端框 Common=0.0（x=-183 面贴合）；隔框∩原螺钉=0.0（头 recessed 于窗口，径向隙 0.5）；供应方侧保留体积 r60 不覆角区（径向 151.5）',
        })
    wlf(ev / 'e4_mounting_surfaces.json', json.dumps({'run': 'r07_e4_rear_bulkhead_20260918', 'table': 'mounting_surfaces_and_constraints', 'row_count': len(mounts), 'rows': mounts}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 4) 工具路径 + 具名检查集合 ----------
    named_set = [
        'e4 夹套筒 vs 隔框 Ø8 窗口（隙 0.05/边 零干涉）/ 夹套法兰 vs 隔框外面（贴面零体积）',
        'e4 夹套 ID Ø4.5 vs M4×30 栓杆 Ø4（隙 0.25/边 零干涉）/ 栓头 vs 套法兰（贴面零体积）',
        'M4×30 栓杆 vs 端框 Ø4.5 孔（零干涉）/ 栓杆头段 vs Ø8 窗口（零干涉）',
        'M4×30 vs 自有端塞 = E2 螺纹啮合惯例（E 节结转复算，尖端/啮合段不变应逐位一致）',
        'e4 件 vs rear_vertical/horizontal_rib（A/B 支承 x[-195,-189]，y/z 带不交）与 launch_interface_reserved_volume（r60 不覆角区）',
        'e4 件 vs E2 角区分段销 e2_stub/e2_washer/e2_pin（x=-164 站位，bbox 间隙 ~16.8）',
        'e4 件 vs E1 锚固件（e1_anchor_*，远场）与 e3 保持件（远场）',
        'E1 结转复算：RB_upper_beam_160 vs shear_web_screw_±1_150_94 两对既有干涉（逐位一致口径）',
        'e4 件两两（4 套+4 改件螺钉 combinations）',
    ]
    tools = []
    for r in spec:
        tools.append({
            'group': r['group'], 'edge': 'rear_frame_to_bulkhead',
            'insertion': '隔框就位贴合端框后面 → 夹套自 -x 插入 Ø8 窗口（法兰朝外贴隔框外面）→ M4×30 自 -x 过套 ID/端框孔拧入端塞 Ø3.3',
            'tool_axis_S': [1, 0, 0], 'tool_travel_candidate_mm': 50,
            'access': '自 -x 星外施装（部署器对接前）；与 E2 分段销（x=-164）无工序冲突；肋/供应方侧在栓链之后',
            'assembly_order': E4['assembly_order'],
            'exit': '工具沿 -X 退出；头/法兰留在隔框外面 x[-195,-189]，供应方保留体积（r60）不受侵',
            'named_check_set': named_set,
        })
    wlf(ev / 'e4_tool_paths.json', json.dumps({'run': 'r07_e4_rear_bulkhead_20260918', 'table': 'insertion_tool_exit_paths', 'row_count': len(tools), 'named_check_set': named_set, 'rows': tools}, ensure_ascii=False, indent=2) + '\n')
    print('tables written: pairs', len(pairs), 'stacks', len(stacks), 'mounts', len(mounts), 'tools', len(tools), 'elapsed_s', round(time.time() - t0, 2))

if __name__ == '__main__':
    main()
