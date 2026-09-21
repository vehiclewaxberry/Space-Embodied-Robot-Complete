# -*- coding: utf-8 -*-
"""R07-E3 登记表生成（纯参数驱动，无 CAD）：
边1（保持横梁→上纵梁，R07 connection_edges[3]）：对偶孔 8 / 叠层 8 / 安装面 4 / 工具 4
边2（保持足叉→屋顶耳座，R07 connection_edges[4]）：对偶孔 4 / 叠层 4 / 安装面 2 / 工具 2
每边登记 A/B件、孔轴面、约束自由度、连接形式、标准件、材料 UNKNOWN、载荷 UNKNOWN、装配/工具路径、
来源与验证层级；枢轴(运动铰) vs 脚座栓链(释放前保持)关系写入边2 登记（INTERLOCK_REGISTERED）。
任务书 §4.1 第3行逐边登记口径；图连通不等于承载，载荷 UNKNOWN。"""
import sys, json, csv, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E3 = sm.P['retention_joints_r07_e3']
E1 = E3['edge1_clamp']; E2 = E3['edge2_foot']
F1 = E1['fastener_candidate']; W1 = F1['washer']
F2 = E2['fastener_candidate']; W2 = F2['washer']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    spec1 = sm.retention_clamp_spec(sm.P)
    spec2 = sm.retention_foot_spec(sm.P)

    # ---------- 1) 对偶孔表（边1 八行 + 边2 四行） ----------
    pairs = []
    for r in spec1:
        sy = r['sy']
        pairs.append({
            'pair_id': f"E3P-{r['group']}-{r['index']}", 'edge': 'edge1_clamp 保持横梁→上纵梁 (R07 connection_edges[3])',
            'group': r['group'],
            'A_part': f"{r['mate']} (pn WP01-RB-LONGERON-R2_WP03_UPPER; 本 run +4 Y 向贯穿孔)",
            'B_part': f"{r['beam']} (WP03 原生; 本 run +4 端面盲孔 +2 竖孔)",
            'hole_axis_S': {'point_mm': [r['x'], sy * 101.15, r['z']], 'direction': [0, 1, 0]},
            'hole_diameter_mm': E1['hole_diameter_mm'],
            'A_hole': '上纵梁双壁 Y 向贯穿 Ø3.4（本 run 新增；外腹面 y=±113.15 → 内腹面 y=±101.15）',
            'B_hole': '横梁端面盲孔 Ø3.4 深 7（v2：名义贯入 5，SHORT_ENGAGEMENT_REGISTERED；THREADLESS_ENVELOPE 底孔/攻丝 UNKNOWN）',
            'interference_avoidance_v2': E3['registered_constraints']['edge1_edge2_interference_avoidance_v2'],
            'datum': f"横梁端面与纵梁内腹面 y={'+' if sy>0 else '-'}101.15 贴合，贴合带 z∈[101.15,106.15]（5mm；栓位 z=103.65 居中）",
            'stack_order': [f"栓头 Ø{F1['head_diameter_mm']}×{F1['head_height_mm']}（y {sy*113.65}..{sy*116.65}）",
                            f"垫圈 OD{W1['outer_diameter_mm']}/Ø{W1['inner_diameter_mm']}×{W1['thickness_mm']} @外腹面 y={sy*113.15}",
                            '纵梁外壁 y∈[111.15,113.15]（Ø3.4 贯穿）', '纵梁内壁 y∈[101.15,103.15]（Ø3.4 贯穿）',
                            '横梁端面盲孔啮合 5（y 自 101.15 至 96.15；孔底 94.15）'],
            'fastener_candidate': f"{F1['thread']}; shank Ø{F1['shank_diameter_mm']} in Ø{E1['hole_diameter_mm']} hole (隙 0.2/边); NO_ANTI_CRUSH_SLEEVE_REGISTERED",
            'material': 'UNKNOWN', 'grade': 'UNKNOWN', 'fit': 'UNKNOWN', 'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'load': 'UNKNOWN (design loads pending; 本登记不代表承载通过)',
            'dof_registration': '端面贴合(Y 平移+绕 X/Z 转动) + TWO_BOLT_POSITIVE 防转(绕 Y)；几何登记非承载证明',
            'self_retention': '单头正向保持（星外头+垫圈 / 盲孔啮合）',
            'tool_path': f"自 y={'+' if sy>0 else '-'} 星外侧沿 ∓Y 插入；工具轴 [0,{'∓1' if sy>0 else '±1'},0]；行程候选 ~30mm（翼板收拢态）",
            'source': 'design_parameters.json retention_joints_r07_e3.edge1_clamp (provenance: issues.json R07 edge4; WP03 plan §4.1 第3行)',
            'verification_level': 'DIGITAL_GEOMETRY_CANDIDATE; 机器读回/布尔干涉见本 run acc 证据; 载荷/强度/配合/压溃 NOT_RUN',
        })
    for r in spec2:
        pairs.append({
            'pair_id': f"E3P-{r['group']}-{r['index']}", 'edge': 'edge2_foot 保持足叉→屋顶耳座 (R07 connection_edges[4])',
            'group': r['group'],
            'A_part': f"{r['foot']} 脚座 (WP03 原生; 本 run +2 盲孔打通至槽底)",
            'B_part': f"{r['lug']} (本 run +2 竖孔) + {r['beam']} (本 run +2 竖孔)——栓链：横梁→耳座→脚座",
            'hole_axis_S': {'point_mm': [r['x'], r['y'], 106.15], 'direction': [0, 0, 1]},
            'hole_diameter_mm': E2['hole_diameter_mm'],
            'A_hole': '脚座盲孔 Ø4.5 深 7 打通至槽底（名义啮合 5，SHORT_ENGAGEMENT_REGISTERED；栓尖距槽底 2，槽内零凸出——轮毂 r10 干涉域 z≥125.15）',
            'B_hole': f"耳座竖向对偶孔 Ø4.5（y={E2['bolt_y_S_mm']}，孔缘距座外面 1.25 REGISTERED）+ 横梁竖向对偶孔 Ø4.5（均为本 run 新增）",
            'interference_avoidance_v2': E3['registered_constraints']['edge1_edge2_interference_avoidance_v2'] + '；既有中心 Ø4.5 孔留备用 UNUSED_EXISTING_SPARE（边缘距 2.03）',
            'datum': '脚座底面 z=118.15 与耳座顶面贴合；耳座底面 z=106.15 与横梁顶面贴合',
            'stack_order': [f"栓头 Ø{F2['head_diameter_mm']}×{F2['head_height_mm']}（z 91.15..95.15，舱内横梁底面下）",
                            f"垫圈 OD{W2['outer_diameter_mm']}/Ø{W2['inner_diameter_mm']}×{W2['thickness_mm']}（z 95.15..96.15）@横梁底面 z=96.15",
                            '横梁 z∈[96.15,106.15]（Ø4.5 竖孔）', '耳座 z∈[106.15,118.15]（Ø4.5 竖孔）',
                            '脚座啮合 5（z 118.15..123.15；尖距槽底 125.15 为 2）'],
            'fastener_candidate': f"{F2['thread']}; shank Ø{F2['shank_diameter_mm']} in Ø{E2['hole_diameter_mm']} hole (隙 0.25/边)",
            'material': 'UNKNOWN', 'grade': 'UNKNOWN', 'fit': 'UNKNOWN', 'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'load': 'UNKNOWN (design loads pending; 本登记不代表承载通过)',
            'dof_registration': '栓链约束 z 向拉脱与 x/y 平移 + TWO_BOLT_POSITIVE 防转(绕 Z)；几何登记非承载证明',
            'pivot_relationship': E2['pivot_relationship'],
            'self_retention': '单头正向保持（舱内头+垫圈 / 脚座盲孔啮合）；释放互锁：栓链未拆则机构不可折 INTERLOCK_REGISTERED',
            'tool_path': '自舱内由下向上(+Z)插入；工具轴 [0,0,1]；行程候选 ~40mm；须在甲板/设备装入前且足叉就位于耳座后施装',
            'source': 'design_parameters.json retention_joints_r07_e3.edge2_foot (provenance: issues.json R07 edge5; WP03 plan §4.1 第3行)',
            'verification_level': 'DIGITAL_GEOMETRY_CANDIDATE; 机器读回/布尔干涉见本 run acc 证据; 载荷/强度/配合 NOT_RUN; 释放互锁顺序实物验证 NOT_RUN',
        })
    cols = ['pair_id', 'edge', 'group', 'A_part', 'B_part', 'hole_diameter_mm', 'datum',
            'fastener_candidate', 'material', 'fit', 'preload', 'locking', 'load', 'self_retention', 'verification_level']
    with open(ev / 'e3_dual_hole_pairs_12.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(pairs)
    wlf(ev / 'e3_dual_hole_pairs_12.json', json.dumps({'run': 'r07_e3_retention_joints_20260918', 'table': 'dual_hole_pairs', 'row_count': len(pairs), 'rows': pairs}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 2) 紧固叠层表（边1 八行 + 边2 四行） ----------
    stacks = []
    for r in spec1:
        sy = r['sy']
        stacks.append({'pair_id': f"E3P-{r['group']}-{r['index']}", 'sub_stacks': [
            {'sub_stack': f"out({'+' if sy>0 else '-'}y 星外)", 'layers': [
                {'layer': 'head', 'y_interval_S_mm': sorted([sy*113.65, sy*116.65]), 'od_mm': F1['head_diameter_mm'], 'bearing_face': '头下面 → 垫圈'},
                {'layer': 'washer', 'y_interval_S_mm': sorted([sy*113.15, sy*113.65]), 'od_mm': W1['outer_diameter_mm'], 'bearing_face': f'纵梁外腹面 y={sy*113.15}（承压环 OD6）'},
                {'layer': 'outer_wall', 'y_interval_S_mm': sorted([sy*111.15, sy*113.15]), 'thickness_mm': 2, 'note': '纵梁管外壁（Ø3.4 本 run 新增孔）'},
                {'layer': 'inner_wall', 'y_interval_S_mm': sorted([sy*101.15, sy*103.15]), 'thickness_mm': 2, 'note': '纵梁管内壁（Ø3.4 本 run 新增孔）'},
                {'layer': 'beam_engagement', 'y_interval_S_mm': sorted([sy*96.15, sy*101.15]), 'engagement_mm': 5, 'note': '横梁端面盲孔内承压；v2 贯入 8→5 SHORT_ENGAGEMENT_REGISTERED'}]}],
            'shank_diameter_mm': F1['shank_diameter_mm'], 'hole_diameter_mm': E1['hole_diameter_mm'],
            'material_grade_fit_preload_locking': 'UNKNOWN'})
    for r in spec2:
        stacks.append({'pair_id': f"E3P-{r['group']}-{r['index']}", 'sub_stacks': [
            {'sub_stack': 'bay(-z 舱内,自下而上)', 'layers': [
                {'layer': 'head', 'z_interval_S_mm': [91.15, 95.15], 'od_mm': F2['head_diameter_mm'], 'bearing_face': '头上面 → 垫圈'},
                {'layer': 'washer', 'z_interval_S_mm': [95.15, 96.15], 'od_mm': W2['outer_diameter_mm'], 'bearing_face': '横梁底面 z=96.15（承压环 OD9）'},
                {'layer': 'crossbeam', 'z_interval_S_mm': [96.15, 106.15], 'thickness_mm': 10, 'note': '保持横梁（Ø4.5 本 run 新增竖孔）'},
                {'layer': 'roof_lug', 'z_interval_S_mm': [106.15, 118.15], 'thickness_mm': 12, 'note': '屋顶耳座（Ø4.5 本 run 新增竖孔；孔缘距座外面 1.25）'},
                {'layer': 'foot_engagement', 'z_interval_S_mm': [118.15, 123.15], 'engagement_mm': 5, 'note': '脚座盲孔内承压；打通至槽底，尖距槽底 2；SHORT_ENGAGEMENT_REGISTERED'}]}],
            'shank_diameter_mm': F2['shank_diameter_mm'], 'hole_diameter_mm': E2['hole_diameter_mm'],
            'material_grade_fit_preload_locking': 'UNKNOWN'})
    wlf(ev / 'e3_fastener_stacks_12.json', json.dumps({'run': 'r07_e3_retention_joints_20260918', 'table': 'fastener_stacks', 'row_count': len(stacks), 'rows': stacks}, ensure_ascii=False, indent=2) + '\n')
    with open(ev / 'e3_fastener_stacks_12.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pair_id', 'sub_stack', 'layer', 'interval_S_mm', 'od_or_thickness', 'bearing_face_or_note'])
        for s in stacks:
            for ss in s['sub_stacks']:
                for L in ss['layers']:
                    w.writerow([s['pair_id'], ss['sub_stack'], L['layer'], L.get('y_interval_S_mm', L.get('z_interval_S_mm')), L.get('od_mm', L.get('thickness_mm', '')), L.get('bearing_face', L.get('note', ''))])

    # ---------- 3) 安装面与约束方向登记（边1 四行 + 边2 两行） ----------
    mounts = []
    for g in E1['groups']:
        sy = g['side_sy']
        mounts.append({
            'group': g['id'], 'edge': 'edge1_clamp',
            'A_mating_face': {'instance': g['mate_instance'], 'face': f'纵梁内腹面 y={sy*101.15}（贴合带 z∈[101.15,106.15]）+ 外腹面 y={sy*113.15}（垫圈承压）'},
            'B_mating_face': {'instance': f"hold_crossbeam_{g['k']}", 'face': f'横梁端面 y={sy*101.15}（x∈[{g["beam_x_mm"]-11},{g["beam_x_mm"]+11}], z∈[96.15,106.15]）'},
            'washer_bearing_faces': [{'plane_y_S_mm': sy*113.15, 'note': '外腹面 OD6 承压环'}],
            'bolt_positions_S_mm': [[b['x_S_mm'], sy*101.15, E1['bolt_z_S_mm']] for b in g['bolts']],
            'constraint_directions': '端面贴合(Y 平移+绕 X/Z 转动) + 双栓防转(绕 Y)；几何登记非承载证明',
            'note': '贴合带仅 5mm 高（耳座 z≥106.15 占位）；无防压套（REGISTERED）；管壁压溃控制 NOT_RUN',
        })
    for g in E2['groups']:
        mounts.append({
            'group': g['id'], 'edge': 'edge2_foot',
            'A_mating_face': {'instance': f"hold_pivot_clevis_{g['k']}", 'face': '脚座底面 z=118.15（x∈[站心±15], y∈[-112,-86]）'},
            'B_mating_face': {'instance': f"hold_roof_lug_{g['k']}_-94.15", 'face': '耳座顶面 z=118.15 与底面 z=106.15（x∈[站心±11], y∈[-101.15,-87.15]）'},
            'washer_bearing_faces': [{'plane_z_S_mm': 96.15, 'note': '横梁底面 OD9 承压环（舱内侧）'}],
            'bolt_positions_S_mm': [[b['x_S_mm'], E2['bolt_y_S_mm'], 106.15] for b in g['bolts']],
            'constraint_directions': '栓链约束 z 向拉脱与 x/y 平移 + 双栓防转(绕 Z)；几何登记非承载证明',
            'pivot_relationship': E2['pivot_relationship'],
            'note': '槽内 z≥125.15 轮毂 r10 干涉域零凸出；与边1 栓链互避 v2（见 registered_constraints）',
        })
    wlf(ev / 'e3_mounting_surfaces.json', json.dumps({'run': 'r07_e3_retention_joints_20260918', 'table': 'mounting_surfaces_and_constraints', 'row_count': len(mounts), 'rows': mounts}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 4) 工具路径 + 具名检查集合 ----------
    named_set = [
        'e3 栓杆 vs 各对偶孔（边1：纵梁贯穿孔/横梁盲孔；边2：横梁竖孔/耳座竖孔/脚座盲孔）——具名零间隙(间隙 0.2/0.25 每边)',
        'e3 边1 栓/垫 vs hold_roof_lug_*（耳座 z≥106.15 邻接）、hold_fold_mast_*（轮毂 r10 干涉域 z≥125.15）、hold_pivot_pin_*（z[131.15,139.15]）',
        'e3 边2 栓/垫 vs hold_fold_mast_*（槽内零凸出）、hold_pivot_pin_*、shear_web_±1、access_cover_±1',
        'e3 边1(J01-J04) vs 边2(C01-C02) 互查——v2 互避闭环项（FAIL v1 16.37mm3 → 净距 3.5）',
        'e3 边1 vs e1_anchor_bolt/washer/sleeve_G*（E1 最近梁栓 x=154.85；x/z 无交叠登记）',
        'e3 边2 vs hold 既有中心备用孔（UNUSED_EXISTING_SPARE，边缘距 2.03）',
        'E1 结转复算：RB_upper_beam_160 vs shear_web_screw_±1_150_94 两对既有干涉 + 8 对端塞/M4 螺钉螺纹啮合惯例（逐位一致口径）',
        'e3 件两两（24 件 combinations）',
    ]
    tools = []
    for g in E1['groups']:
        sy = g['side_sy']
        tools.append({
            'group': g['id'], 'edge': 'edge1_clamp',
            'insertion': f"栓+垫圈自 y={'+' if sy>0 else '-'} 星外侧沿 {'-' if sy>0 else '+'}Y 插入纵梁双壁孔，拧入横梁端面盲孔",
            'tool_axis_S': [0, -sy, 0], 'tool_travel_candidate_mm': 30,
            'access': '翼板收拢态自星外施装；与边2 栓链无工序冲突（不同侧）',
            'assembly_order': '保持横梁就位贴合纵梁内腹面 → 每端 2 栓对角预拧 → 终拧（力矩 UNKNOWN）',
            'exit': '工具沿 ∓Y 退出；头/垫圈留在星外侧 y=±113.15 以外',
            'named_check_set': named_set,
        })
    for g in E2['groups']:
        tools.append({
            'group': g['id'], 'edge': 'edge2_foot',
            'insertion': '栓+垫圈自舱内横梁底面下沿 +Z 穿横梁/耳座对偶孔，拧入足叉脚座盲孔',
            'tool_axis_S': [0, 0, 1], 'tool_travel_candidate_mm': 40,
            'access': '须在甲板/设备装入前经开放舱施装；足叉已就位于耳座（枢轴销已穿）后施装',
            'assembly_order': '足叉枢轴销就位 → 2 栓对角预拧 → 终拧（力矩 UNKNOWN）；释放互锁：拆栓链后方可折叠 INTERLOCK_REGISTERED',
            'exit': '工具沿 -Z 退出；头/垫圈留在横梁底面下 z<96.15，槽内零凸出',
            'named_check_set': named_set,
        })
    wlf(ev / 'e3_tool_paths.json', json.dumps({'run': 'r07_e3_retention_joints_20260918', 'table': 'insertion_tool_exit_paths', 'row_count': len(tools), 'named_check_set': named_set, 'rows': tools}, ensure_ascii=False, indent=2) + '\n')
    print('tables written: pairs', len(pairs), 'stacks', len(stacks), 'mounts', len(mounts), 'tools', len(tools), 'elapsed_s', round(time.time() - t0, 2))

if __name__ == '__main__':
    main()
