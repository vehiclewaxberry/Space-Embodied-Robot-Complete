# -*- coding: utf-8 -*-
"""R07-E2 登记表生成（纯参数驱动，无 CAD）：
1) 对偶孔表 8 行（A件/B件、孔/轴/面、约束自由度、连接形式、标准件、材料、载荷、装配/工具路径、来源及验证层级）
2) 紧固叠层表 8 行（每站上/下两段子叠层，逐层 z 区间与承压面）
3) 安装面与约束方向登记（8 站）
4) 插入/工具/退出路径 + 具名检查集合
任务书 §4.1 第2行逐边登记口径；图连通不等于承载，载荷 UNKNOWN。"""
import sys, json, csv, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

E2 = sm.P['transverse_retention_r07_e2']
F = E2['fastener_candidate']
ST = E2['stack_z_intervals_mm']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def main():
    t0 = time.time()
    ev = RUN / 'evidence'
    spec = sm.transverse_retention_spec(sm.P)

    # ---------- 1) 对偶孔表 ----------
    pairs = []
    for r in spec:
        sid = r['id']; sz = r['sz']
        if sz > 0:
            stack_desc = ['外短栓头 Ø7×4', '垫圈 OD9/Ø4.5×1', '外壁(z 111.15..113.15)', '端塞入塞 1.8(尖 z=109.25 让 M4 螺钉 0.1)',
                          '舱内短栓头 Ø7×4', '垫圈 OD7/Ø4.5×1', '内壁(z 101.15..103.15)', '端塞入塞 1.8(尖 z=105.05 让 M4 螺钉 0.1)']
            retention = '双头正向保持（外头+舱内头）'
        else:
            stack_desc = ['舱内短栓头 Ø7×4', '垫圈 OD7/Ø4.5×1', '内壁(z -103.15..-101.15)', '端塞入塞 1.8(尖 z=-105.05 让 M4 螺钉 0.1)',
                          '无头压装销 Ø4.4', '外壁(z -113.15..-111.15)', '端塞入塞 1.8(顶 z=-109.25 让 M4 螺钉 0.1；底 z=-112.95 距翼根垫板 0.2)']
            retention = '舱内头正向 + 翼侧压配候选(PRESS_FIT UNKNOWN) + 翼根叉垫板物理止动(REGISTERED_SECONDARY)'
        pair = {
            'pair_id': f'E2P-{sid}',
            'station': sid,
            'A_part': f"RB_longeron_{r['sy']}_{sz} (pn WP01-RB-LONGERON-R2_WP03_{'UPPER' if sz>0 else 'LOWER'})",
            'B_part': r['plug'] + ' (pn WP01-RB-END-PLUG-R2_WP03; 现行 7.8×7.8 重建体)',
            'hole_axis_S': {'point_mm': [r['x'], r['y'], r['z']], 'direction': [0, 0, 1]},
            'hole_diameter_mm': E2['hole_diameter_mm'],
            'A_hole': '纵梁双壁贯穿 Ø4.5（既有，WP02 L18；E2 未改）',
            'B_hole': '端塞竖向贯穿 Ø4.5（既有，局部 x=-sx*3；E2 未改）',
            'crossing_truth': '孔轴与既有 M4 端面螺钉包络(Ø4,x∈[161,183])十字相交；分段短销尖端让开 0.1 mm（几何真相 T3）',
            'datum': '端塞 7.8×7.8 与纵梁 8×8 内孔套合（单边 0.1，SLIP_FIT_CANDIDATE）为装配基准',
            'stack_order': stack_desc,
            'fastener_candidate': F['type'] + f"; shank Ø{F['shank_diameter_mm']} in Ø4.5 hole (隙 0.05/边)",
            'material': 'UNKNOWN', 'grade': 'UNKNOWN', 'fit': F['fit'], 'preload': 'UNKNOWN', 'locking': 'UNKNOWN',
            'load': 'UNKNOWN (design loads pending; 本登记不代表承载通过)',
            'dof_registration': E2['dof_registration'],
            'self_retention': retention,
            'tool_path': E2['assembly_tool']['insertion'],
            'source': 'design_parameters.json transverse_retention_r07_e2 (provenance: issues.json R07 edge2; WP03 plan §4.1 第2行)',
            'verification_level': 'DIGITAL_GEOMETRY_CANDIDATE; 机器读回/布尔干涉见本 run acc 证据; 载荷/强度/配合 NOT_RUN',
        }
        pairs.append(pair)
    cols = ['pair_id', 'station', 'A_part', 'B_part', 'hole_diameter_mm', 'datum',
            'fastener_candidate', 'material', 'fit', 'preload', 'locking', 'load', 'self_retention', 'verification_level']
    with open(ev / 'e2_dual_hole_pairs_8.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader(); w.writerows(pairs)
    wlf(ev / 'e2_dual_hole_pairs_8.json', json.dumps({'run': 'r07_e2_endplug_retention_20260918', 'table': 'dual_hole_pairs', 'row_count': len(pairs), 'rows': pairs}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 2) 紧固叠层表 ----------
    def layers_for(r):
        sz = r['sz']
        if sz > 0:
            return [
                {'sub_stack': 'out(+z 星外)', 'layers': [
                    {'layer': 'head', 'z_interval_S_mm': ST['top_out']['head'], 'od_mm': F['head']['diameter_mm'], 'bearing_face': '头下面 → 垫圈'},
                    {'layer': 'washer', 'z_interval_S_mm': ST['top_out']['washer'], 'od_mm': F['washer_out']['outer_diameter_mm'], 'bearing_face': '纵梁外顶面 z=113.15（承压环 OD9）'},
                    {'layer': 'outer_wall', 'z_interval_S_mm': [111.15, 113.15], 'thickness_mm': 2, 'note': '纵梁管外壁（Ø4.5 既有孔）'},
                    {'layer': 'plug_engagement', 'z_interval_S_mm': [109.25, 111.05], 'engagement_mm': 1.8, 'note': '端塞内承压；尖 z=109.25 让 M4 螺钉包络 0.1'}]},
                {'sub_stack': 'bay(-z 舱内)', 'layers': [
                    {'layer': 'head', 'z_interval_S_mm': ST['top_bay']['head'], 'od_mm': F['head']['diameter_mm'], 'bearing_face': '头上面 → 垫圈'},
                    {'layer': 'washer', 'z_interval_S_mm': ST['top_bay']['washer'], 'od_mm': F['washer_bay']['outer_diameter_mm'], 'bearing_face': '纵梁内顶面 z=101.15（承压环 OD7，剪力板隙 0.5）'},
                    {'layer': 'inner_wall', 'z_interval_S_mm': [101.15, 103.15], 'thickness_mm': 2, 'note': '纵梁管内壁（Ø4.5 既有孔）'},
                    {'layer': 'plug_engagement', 'z_interval_S_mm': [103.25, 105.05], 'engagement_mm': 1.8, 'note': '端塞内承压；尖 z=105.05 让 M4 螺钉包络 0.1'}]}]
        return [
            {'sub_stack': 'bay(+z 舱内)', 'layers': [
                {'layer': 'head', 'z_interval_S_mm': ST['bot_bay']['head'], 'od_mm': F['head']['diameter_mm'], 'bearing_face': '头下面 → 垫圈'},
                {'layer': 'washer', 'z_interval_S_mm': ST['bot_bay']['washer'], 'od_mm': F['washer_bay']['outer_diameter_mm'], 'bearing_face': '纵梁内底面 z=-101.15（承压环 OD7，剪力板隙 0.5）'},
                {'layer': 'inner_wall', 'z_interval_S_mm': [-103.15, -101.15], 'thickness_mm': 2, 'note': '纵梁管内壁（Ø4.5 既有孔）'},
                {'layer': 'plug_engagement', 'z_interval_S_mm': [-105.05, -103.25], 'engagement_mm': 1.8, 'note': '端塞内承压；尖 z=-105.05 让 M4 螺钉包络 0.1'}]},
            {'sub_stack': 'wing(-z 翼侧)', 'layers': [
                {'layer': 'outer_wall', 'z_interval_S_mm': [-113.15, -111.15], 'thickness_mm': 2, 'note': '纵梁管外壁（Ø4.5 既有孔）'},
                {'layer': 'plug_engagement', 'z_interval_S_mm': [-111.05, -109.25], 'engagement_mm': 1.8, 'note': '端塞内承压；顶 z=-109.25 让 M4 螺钉包络 0.1'},
                {'layer': 'headless_pin', 'z_interval_S_mm': ST['bot_wing_pin']['shank'], 'od_mm': F['shank_diameter_mm'], 'note': '无头压装销；底 z=-112.95 距翼根叉垫板顶面(-113.15) 0.2；保持=压配候选+垫板物理止动(REGISTERED_SECONDARY)'}]}]
    stacks = []
    for r in spec:
        stacks.append({'pair_id': f"E2P-{r['id']}", 'sub_stacks': layers_for(r),
                       'shank_diameter_mm': F['shank_diameter_mm'], 'hole_diameter_mm': E2['hole_diameter_mm'],
                       'material_grade_fit_preload_locking': 'UNKNOWN'})
    wlf(ev / 'e2_fastener_stacks_8.json', json.dumps({'run': 'r07_e2_endplug_retention_20260918', 'table': 'fastener_stacks', 'row_count': len(stacks), 'rows': stacks}, ensure_ascii=False, indent=2) + '\n')
    with open(ev / 'e2_fastener_stacks_8.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pair_id', 'sub_stack', 'layer', 'z_interval_S_mm', 'od_or_thickness', 'bearing_face_or_note'])
        for s in stacks:
            for ss in s['sub_stacks']:
                for L in ss['layers']:
                    w.writerow([s['pair_id'], ss['sub_stack'], L['layer'], L['z_interval_S_mm'], L.get('od_mm', L.get('thickness_mm', '')), L.get('bearing_face', L.get('note', ''))])

    # ---------- 3) 安装面与约束方向登记 ----------
    mounts = []
    for r in spec:
        sz = r['sz']; sx = r['sx']; sy = r['sy']
        mounts.append({
            'station': r['id'],
            'A_mating_face': {'instance': r['longeron'], 'face': '纵梁 8×8 内孔两端开口(x=±177)及双壁 Ø4.5 孔',
                              ' bore_axis_S': [r['x'], r['y'], 'z'], 'note': '内孔 y/z=±107.15 周边 8×8'},
            'B_mating_face': {'instance': r['plug'], 'face': '端塞 7.8×7.8 外表面与内孔套合段(x∈[157,177] 全局)',
                              'clearance_per_side_mm': 0.1, 'fit': 'SLIP_FIT_CANDIDATE'},
            'washer_bearing_faces': ([{'plane_z_S_mm': 113.15, 'note': '外顶面 OD9 承压环'}, {'plane_z_S_mm': 101.15, 'note': '内顶面 OD7 承压环'}]
                                     if sz > 0 else [{'plane_z_S_mm': -101.15, 'note': '内底面 OD7 承压环'}]),
            'physical_stop': None if sz > 0 else {'instance': f'wing_root_fork_{"1" if sy>0 else "-1"}_{"1" if sx>0 else "-1"}',
                'note': '翼根叉垫板顶面 z=-113.15 与销底(z=-112.95)距 0.2；仅作销 -z 向物理止动登记，不作承载依据'},
            'constraint_directions': E2['dof_registration'],
            'note': '套合/贴面只登记安装面，不作载荷链证明；承载按工况另验，设计载荷 UNKNOWN',
        })
    wlf(ev / 'e2_mounting_surfaces.json', json.dumps({'run': 'r07_e2_endplug_retention_20260918', 'table': 'mounting_surfaces_and_constraints', 'row_count': len(mounts), 'rows': mounts}, ensure_ascii=False, indent=2) + '\n')

    # ---------- 4) 工具路径 + 具名检查集合 ----------
    named_set = [
        'RB_end_screw_±1_±1_±1（M4 端面螺钉包络 Ø4 x∈[161,183]，与孔轴十字相交：E2 短销尖端让开 0.1）',
        'RB_end_frame_±1（x∈[177,183] 端框）',
        'e1_anchor_bolt/washer/sleeve_G**_*（E1 锚固件 48 件；最近 G03/G04 x=154.85 栓）',
        'shear_web_±1（R01 剪力板 y≤±103.15；舱侧垫圈 OD7 隙 0.5）',
        'wing_root_fork_*（下纵梁 x∈[138,174] 垫板/叉；翼侧无头销底距垫板 0.2）与 wing_hinge_pin_*',
        'RB_pillar_tierod_*（M4×228 贯通杆 x∈{20,160}, y=±94.15）及垫圈/螺母',
        'M6_root_bolt/washer/nut_*、M5_interstage_bolt/washer/nut_*（既有夹接叠层）',
        'shear_clip_*/shear_rail_screw_*/shear_web_screw_*（剪力夹与栓）',
        'access_cover_±1 与 cover_mount_*（检修盖 y=±112.4 z∈[-90,90]）',
        'lower/upper_equipment_deck、deck_angle_*、deck_fastener_*、angle_web_fastener_*（R01 件）',
        'forward_roof_access（x≤1）/rear_launch_bulkhead/肋',
        'radiator_spreader/battery_thermal_link（下外侧 x∈[-170,-60]）',
        'hold_*（压紧机构 y=-99 带）/B601 根 M3R',
        'E2 件互查：e2_stub_*/e2_washer_*/e2_pin_* 28 件两两',
    ]
    tools = []
    for r in spec:
        sz = r['sz']
        tools.append({
            'station': r['id'],
            'insertion': E2['assembly_tool']['insertion'],
            'tool_axis_S': E2['assembly_tool']['tool_axis_S'], 'tool_travel_candidate_mm': E2['assembly_tool']['tool_travel_candidate_mm'],
            'access': ('外栓自 +z 星外无阻；舱内栓在甲板/设备装入前经开放舱施装（z 96..101 带）' if sz > 0 else
                       '舱内栓在甲板/设备装入前经开放舱施装（z -101..-96 带）；翼侧无头销自 -z 压入，须在 wing_root_fork 装入前'),
            'assembly_order': E2['assembly_tool']['sequence'],
            'exit': E2['assembly_tool']['exit'],
            'named_check_set': named_set,
        })
    wlf(ev / 'e2_tool_paths.json', json.dumps({'run': 'r07_e2_endplug_retention_20260918', 'table': 'insertion_tool_exit_paths', 'row_count': len(tools), 'named_check_set': named_set, 'rows': tools}, ensure_ascii=False, indent=2) + '\n')
    print('tables written: pairs', len(pairs), 'stacks', len(stacks), 'mounts', len(mounts), 'tools', len(tools), 'elapsed_s', round(time.time() - t0, 2))

if __name__ == '__main__':
    main()
