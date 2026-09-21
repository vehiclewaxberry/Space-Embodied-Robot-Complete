# -*- coding: utf-8 -*-
"""R07-E1 登记表生成（纯参数驱动，无 CAD）：
1) 对偶孔表 16 行（A件/B件、孔轴、基准、夹层、配对 ID、约束自由度、连接形式、标准件、材料、载荷、装配/工具路径、来源与验证层级）
2) 紧固叠层表 16 行（逐层 y 区间与承压面）
3) 安装面与约束方向登记（10 组）
4) 插入/工具/退出路径 + 具名检查集合
任务书 §4.1 第122行逐边登记口径；图连通不等于承载，载荷 UNKNOWN。"""
import sys, json, csv, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E1 = sm.P['root_anchoring_r07_e1']
F = E1['fastener_candidate']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def member_instance(r):
    if r['member'] == 'bridge':
        return 'WP01-RB-BRIDGE-R2'
    return f"RB_{r['member']}_{r['beam_x']}"

def dof_rows(r):
    two = len([b for b in E1['groups'] if b['id'] == r['group']][0]['bolts']) > 1
    base = [
        {'dof': 'Ty(拉出/轴向)', 'restraint': 'M3 螺栓拉伸 + 端面孔螺纹啮合(候选)', 'level': 'POSITIVE_INTENT; 有效啮合/预紧 UNKNOWN'},
        {'dof': 'Tx/Tz(面内剪切)', 'restraint': '螺栓杆剪切 + 端面/内腹面承压接触', 'level': 'POSITIVE_INTENT; 滑移/承压许用 UNKNOWN'},
    ]
    if two:
        base.append({'dof': 'Rx/Ry/Rz(转动)', 'restraint': '双栓间距 + 端面贴合', 'level': 'POSITIVE_INTENT (TWO_BOLT)'})
    else:
        base.append({'dof': 'Ry(绕栓轴)', 'restraint': '单栓不正向约束；二级路径见 anti_rotation 登记', 'level': 'REGISTERED_SECONDARY; 残余转角 UNKNOWN'})
        base.append({'dof': 'Rx/Rz', 'restraint': '端面贴合 + 单栓 + 二级夹接链', 'level': 'REGISTERED_SECONDARY; UNKNOWN'})
    return base

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    spec = sm.root_anchoring_spec(sm.P)
    groups = {g['id']: g for g in E1['groups']}

    # ---------- 1) 对偶孔表 ----------
    pairs = []
    for r in spec:
        g = groups[r['group']]
        sy = r['sy']
        b_inst = member_instance(r)
        pair = {
            'pair_id': f"E1P-{r['group']}-{r['index']}",
            'group': r['group'],
            'A_part': f"RB_longeron_{sy}_{r['sz']} (pn WP01-RB-LONGERON-R2_WP03_{'UPPER' if r['sz']>0 else 'LOWER'})",
            'B_part': b_inst,
            'hole_axis_S': {'point_mm': [r['x'], sy * 107.15, r['z']], 'direction': [0, 1, 0]},
            'hole_diameter_mm': E1['hole_diameter_mm'],
            'A_hole': '纵梁双壁贯穿孔 Ø3.4（外壁 y=±[111.15,113.15]，内壁 y=±[101.15,103.15]）',
            'B_hole': f"端面盲孔 Ø3.4，名义深 {E1['beam_end_tapped_hole']['nominal_depth_mm']}（建模 {E1['beam_end_tapped_hole']['modeled_depth_mm']}），THREADLESS_ENVELOPE",
            'datum': '纵梁内腹面 y=%+.3f 与 %s 端面 y=%+.3f 贴合为装配基准' % (sy * 101.15, b_inst, sy * 101.15),
            'stack_grip_mm': F['nominal_grip_mm'],
            'stack_order_outboard_to_inboard': ['M3 头', '垫圈 Ø6/Ø3.4×0.5', '外壁 2', '防压套 %s×8' % ('Ø%d' % r['sleeve_od']), '内壁 2', 'B件端面孔(名义啮合 8)'],
            'fastener_candidate': 'M3_UNSELECTED threadless envelope; underhead 22 candidate',
            'material': 'UNKNOWN', 'grade': 'UNKNOWN', 'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'thread_engagement': 'UNKNOWN (nominal 8 mm candidate)',
            'load': 'UNKNOWN (design loads pending; 本登记不代表承载通过)',
            'dof_registration': dof_rows(r),
            'anti_rotation': g['anti_rotation'],
            'tool_path': f"沿 {'−Y' if sy>0 else '+Y'} 自外侧穿入：垫圈+栓(套预挂于杆) → 外壁 → 套入位 → 内壁 → 端面孔拧紧；工具轴 Y，候选直线行程 ≥60 mm；退出反向",
            'source': 'design_parameters.json root_anchoring_r07_e1 (provenance: issues.json R07 edge1; WP03 plan §3.5/§4.1)',
            'verification_level': 'DIGITAL_GEOMETRY_CANDIDATE; 机器读回/布尔干涉见本 run acc 证据; 载荷/强度 NOT_RUN',
        }
        pairs.append(pair)
    cols = ['pair_id', 'group', 'A_part', 'B_part', 'hole_diameter_mm', 'datum', 'stack_grip_mm',
            'fastener_candidate', 'material', 'preload', 'locking', 'thread_engagement', 'load', 'anti_rotation', 'verification_level']
    with open(ev / 'e1_dual_hole_pairs_16.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(pairs)
    wlf(ev / 'e1_dual_hole_pairs_16.json', json.dumps({'run': 'r07_root_longeron_anchoring_20260917', 'table': 'dual_hole_pairs', 'row_count': len(pairs), 'rows': pairs}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 2) 紧固叠层表 ----------
    stacks = []
    for r in spec:
        sy = r['sy']
        def iv(a, b):
            return [round(sy * a, 3), round(sy * b, 3)] if sy > 0 else [round(-sy * b, 3), round(-sy * a, 3)]
        stacks.append({
            'pair_id': f"E1P-{r['group']}-{r['index']}",
            'layers': [
                {'layer': 'head', 'y_interval_S_mm': iv(113.65, 116.65), 'od_mm': F['head_diameter_mm'], 'bearing_face': '头下面 → 垫圈'},
                {'layer': 'washer', 'y_interval_S_mm': iv(113.15, 113.65), 'od_mm': F['washer']['outer_diameter_mm'], 'bearing_face': '纵梁外腹面 y=%+.3f（承压面 Ø6 环）' % (sy * 113.15)},
                {'layer': 'outer_wall', 'y_interval_S_mm': iv(111.15, 113.15), 'thickness_mm': 2, 'note': '纵梁管外壁'},
                {'layer': 'anti_crush_sleeve', 'y_interval_S_mm': iv(103.15, 111.15), 'od_mm': r['sleeve_od'], 'bearing_face': '套两端面 → 内外壁内侧面（防压/承压）'},
                {'layer': 'inner_wall', 'y_interval_S_mm': iv(101.15, 103.15), 'thickness_mm': 2, 'note': '纵梁管内壁'},
                {'layer': 'beam_end_thread', 'y_interval_S_mm': iv(93.15, 101.15), 'nominal_engagement_mm': 8, 'note': 'B件端面盲孔；THREADLESS_ENVELOPE；承压面=端面贴合面'},
            ],
            'grip_mm': 12, 'underhead_length_candidate_mm': 22,
            'material_grade_preload_locking_engagement': 'UNKNOWN',
        })
    wlf(ev / 'e1_fastener_stacks_16.json', json.dumps({'run': 'r07_root_longeron_anchoring_20260917', 'table': 'fastener_stacks', 'row_count': len(stacks), 'rows': stacks}, ensure_ascii=False, indent=2) + '\n')
    with open(ev / 'e1_fastener_stacks_16.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pair_id', 'layer', 'y_interval_S_mm', 'od_or_thickness', 'bearing_face_or_note'])
        for s in stacks:
            for L in s['layers']:
                w.writerow([s['pair_id'], L['layer'], L['y_interval_S_mm'], L.get('od_mm', L.get('thickness_mm', '')), L.get('bearing_face', L.get('note', ''))])

    # ---------- 3) 安装面与约束方向登记 ----------
    mounts = []
    for g in E1['groups']:
        sy = g['side_sy']
        b_inst = 'WP01-RB-BRIDGE-R2' if g['member'] == 'bridge' else f"RB_{g['member']}_{g['beam_x_mm']}"
        if g['member'] == 'upper_beam':
            zf = (95.15, 107.15); xf = (g['beam_x_mm'] - 7, g['beam_x_mm'] + 7)
        elif g['member'] == 'lower_beam':
            zf = (-107.15, -101.15); xf = (g['beam_x_mm'] - 7, g['beam_x_mm'] + 7)
        else:
            zf = (107.15, 113.15); xf = (5, 175)
        mounts.append({
            'group': g['id'], 'member': g['member'], 'B_instance': b_inst,
            'A_mating_face': {'instance': g['mate_instance'], 'face': '纵梁内腹面', 'plane_y_S_mm': sy * 101.15,
                              'patch_x_S_mm': list(xf), 'patch_z_S_mm': list(zf)},
            'B_mating_face': {'instance': b_inst, 'face': '端面', 'plane_y_S_mm': sy * 101.15,
                              'patch_x_S_mm': list(xf), 'patch_z_S_mm': list(zf)},
            'washer_bearing_face': {'plane_y_S_mm': sy * 113.15, 'note': '纵梁外腹面；垫圈 Ø6 环承压'},
            'constraint_directions': dof_rows({'group': g['id'], 'member': g['member']}),
            'anti_rotation': g['anti_rotation'],
            'note': '端面贴合(公共体积 0)只登记安装面，不作载荷链证明；承载按工况另验，设计载荷 UNKNOWN',
        })
    wlf(ev / 'e1_mounting_surfaces.json', json.dumps({'run': 'r07_root_longeron_anchoring_20260917', 'table': 'mounting_surfaces_and_constraints', 'row_count': len(mounts), 'rows': mounts}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 4) 工具路径 + 具名检查集合 ----------
    named_set = [
        'RB_longeron_±1_±1 既有孔系（X±164 Ø4.5 端塞对偶(E2)、X±150/±90/±30 Ø3.4 竖孔、下梁 X±144 Ø3.4）',
        'RB_end_plug_*/RB_end_screw_*（端塞 x≥157 与 M4 端栓）',
        'RB_pillar_tierod_*（M4×228 贯通杆 x∈{20,160}, y=±94.15）及顶/底垫圈、螺母',
        'M6_root_bolt/washer/nut_*（(20/160,±70) 既有 M6 夹接叠层）',
        'M5_interstage_bolt/washer/nut_*（桥 Ø62.5 环 8 组）',
        'shear_clip_*/shear_rail_screw_*/shear_web_screw_*（剪力夹与栓）',
        'shear_web_±1（R01 剪力板 y=±102.15）',
        'access_cover_±1 与 cover_mount_*（检修盖 z∈[-90,90]、盖座 z=±75 带）',
        'forward_roof_access（x≤1）',
        'wing_root_fork_* 及 wing_hinge_pin_*（下纵梁 x∈[138,174] 垫板/叉）',
        'radiator_spreader/battery_thermal_link（下外侧 x∈[-170,-60]）',
        'antenna_mount/communications_antenna（(-142,56)）',
        'B601 根 M3R m3r_a/m3r_b（(90,0,125.15) 输入 STEP）',
        'RB_pillar_*/RB_pillar_plug_*/RB_lower_spacer_*（柱/柱塞/垫块）',
        'R01 件：lower/upper_equipment_deck、deck_angle_*、deck_fastener_*、angle_web_fastener_*',
        '锚固件互查：e1_anchor_bolt/washer/sleeve_G**_* 48 件两两',
    ]
    tools = []
    for g in E1['groups']:
        sy = g['side_sy']
        tools.append({
            'group': g['id'],
            'insertion': f"栓+垫圈(防压套预挂栓杆)沿 {'−Y' if sy>0 else '+Y'} 自纵梁外腹面穿入，经外壁孔→套入管内位→内壁孔→拧入端面盲孔",
            'tool_axis_S': [0, -sy, 0], 'tool_travel_candidate_mm': 60,
            'access': '栓头 z=%+.2f 位于检修盖带(z∈[-90,90])之外，装拆免拆盖；盲孔无需星内通道' % (g['bolts'][0]['z_S_mm']),
            'assembly_order': '根框装配完成后均可装；与端塞/端框顺序无关（不穿端塞）；建议先锚固后装柱贯通杆以便复查扭矩(候选)',
            'exit': '反向旋出，套随栓带出；退出路径同插入',
            'named_check_set': named_set,
        })
    wlf(ev / 'e1_tool_paths.json', json.dumps({'run': 'r07_root_longeron_anchoring_20260917', 'table': 'insertion_tool_exit_paths', 'row_count': len(tools), 'named_check_set': named_set, 'rows': tools}, ensure_ascii=False, indent=2) + '\n')
    print('tables written: pairs', len(pairs), 'stacks', len(stacks), 'mounts', len(mounts), 'tools', len(tools), 'elapsed_s', round(time.time() - t0, 2))

if __name__ == '__main__':
    main()
