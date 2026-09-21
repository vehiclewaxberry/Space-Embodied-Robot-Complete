# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r31：三个负控（检测器灵敏度证明 + 真实对照零干涉复算）。
NC-a 法兰内侵变异：夹套整体 +x 移 1（法兰 x[-190,-188] 压入隔框 x[-189,-183] 1mm）vs exports 隔框
    → 阳性 ≈ π·(6²-2.25²)·1 ≈ 97.19；真实对照（dx=0）= 0。
    （设计勘误：原拟 -x 移 1 在 x 向与隔框无交，变异无效；内侵方向=法兰越外面向 +x，已改正并如实登记。）
NC-b 缺对偶/错轴：
  b1 Ø8 填窗柱（假想窗口未开）vs 夹套筒 → 阳性 ≈ π·3.95²·6 ≈ 294.03；真实对照 0（窗口既有、隙 0.05/边）。
  b2 夹套平移 y+0.5（ID 隙 0.25/边 → 撞 ID 壁）vs 改件螺钉 → 阳性；真实对照 0。
NC-c 栓头侧延长冲突变异：
  c1 改件螺钉平移到 rear 肋带（y/z 带入 [77,95]）vs rear 肋（build 件）→ 阳性；真实位 0（bbox DISJOINT 已登记）。
  c2 E2 分段销 z 向平移变异进入螺钉 z 带 [105.15,109.15] vs 改件螺钉 → 阳性；真实 E2 销 vs 改件螺钉 = 0
    （E2 栓尖让隙设计：销在螺钉 z 带内无材料，非十字相贯）。
布尔一律 OCP 原生（勘误 O2）。"""
import json, math, sys, time
from e4_common import (REV, RUN, ENG, write_json, common_volume, bbox, overlap,
                       import_step, stations, load_params, clamp_sleeve_envelope,
                       screw_e4_envelope, cylinder_at, C)
from build123d import Location  # noqa: E402  须在 e4_common（cadgen 坏字体守卫）之后

RIB = {'1_1': 'rear_vertical_rib_86', '1_-1': 'rear_vertical_rib_86',
       '-1_1': 'rear_vertical_rib_-86', '-1_-1': 'rear_vertical_rib_-86'}
PIN = {'1_1': 'e2_stub_bay_H02', '1_-1': 'e2_stub_bay_H06',
       '-1_1': 'e2_stub_bay_H01', '-1_-1': 'e2_stub_bay_H05'}


def main():
    t0 = time.time()
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r31_negative_controls.py',
              'reviewed_run': RUN.name, 'failures': [], 'controls': {}, 'verdict': None}
    P, _ = load_params()
    sts = stations(P)
    st = sts[0]  # group 1_1
    exp = RUN / 'exports'
    sleeve = import_step(str(exp / f"{st['sleeve']}.step"))
    screw = import_step(str(exp / f"{st['screw']}.step"))
    bulkhead = import_step(str(exp / 'rear_launch_bulkhead.step'))

    def rec(key, variant_desc, v_var, expect_positive, v_real, note=None):
        ok_var = (not isinstance(v_var, dict)) and (v_var > 1.0 if expect_positive else v_var == 0.0)
        ok_real = (not isinstance(v_real, dict)) and v_real == 0.0
        entry = {'variant': variant_desc, 'variant_common_mm3': v_var,
                 'expect_positive': expect_positive, 'variant_fired': ok_var,
                 'real_common_mm3': v_real, 'real_zero': ok_real,
                 'pass': ok_var and ok_real}
        if note:
            entry['note'] = note
        result['controls'][key] = entry
        if not entry['pass']:
            result['failures'].append(f'{key}: {entry}')
        return entry

    # NC-a 法兰内侵变异（+x 方向；原拟 -x 无效已勘正）
    v_var = common_volume(clamp_sleeve_envelope(st['sy'], st['sz'], dx=1.0), bulkhead)
    v_real = common_volume(sleeve, bulkhead)
    rec('NC_a_flange_intrusion', 'clamp_sleeve_envelope(dx=+1) vs bulkhead exports',
        v_var, True, v_real,
        note=f'解析估计=承压环 π·(6²-4²)·1 = {math.pi * (36 - 16):.6f}（Ø8 窗口去除内圈 r4 部分）；'
             '原拟 dx=-1 在 x 向与隔框无交属无效变异，方向勘正为 +x 并登记')

    # NC-b1 填窗柱（假想 Ø8 窗口未开）vs 夹套筒
    filler = cylinder_at(8, 6, (-186, st['y'], st['z']), (1, 0, 0))
    v_var = common_volume(filler, sleeve)
    rec('NC_b1_window_filler', 'Ø8×6 window filler vs sleeve exports',
        v_var, True, v_real,
        note=f'解析估计=筒壁环 π·(3.95²-2.25²)·6 = {math.pi * (3.95**2 - 2.25**2) * 6:.6f}（夹套 ID Ø4.5 通孔去除内圈）；真实对照同 NC-a 零')

    # NC-b2 夹套错轴 y+0.5 vs 改件螺钉
    v_var = common_volume(clamp_sleeve_envelope(st['sy'], st['sz'], dy=0.5), screw)
    v_real2 = common_volume(sleeve, screw)
    rec('NC_b2_sleeve_off_axis', 'clamp_sleeve_envelope(dy=+0.5) vs modified screw exports',
        v_var, True, v_real2, note='ID 隙 0.25/边，错轴 0.5 > 0.5 边界 → 栓杆撞 ID 壁')

    # NC-c 需要 build 件（rear 肋、E2 分段销）
    sys.path.insert(0, str(ENG))
    import spacecraft_model as sm
    model, shapes, receipt = sm.build('service', include_arm=False)

    # NC-c1 螺钉平移到 rear 肋带
    rib = shapes[RIB[st['group']]]
    rb = bbox(rib)
    dy = (rb[1] + rb[4]) / 2 - st['y']
    dz = (rb[2] + rb[5]) / 2 - st['z']
    var_screw = screw_e4_envelope(st['sy'], st['sz']).moved(Location((0, dy, dz)))
    assert overlap(bbox(var_screw), rb), 'c1 variant bbox disjoint from rib — design error'
    v_var = common_volume(var_screw, rib)
    v_real3 = common_volume(screw, rib)
    rec('NC_c1_screw_into_rib', f'modified-screw envelope moved (dy={dy:.3f}, dz={dz:.3f}) into rib band vs {RIB[st["group"]]}',
        v_var, True, v_real3,
        note=f'rib bbox={[round(x,3) for x in rb]}；真实螺钉 y/z 带 [103.65,110.65] 与肋带不交')

    # NC-c2 E2 分段销 z 向平移进入螺钉 z 带
    pin = shapes[PIN[st['group']]]
    pb = bbox(pin)
    # 螺钉 z 带 [105.15,109.15]（杆 Ø4 @ z=107.15）；把销 z 中心平移到 107.15
    dz2 = st['z'] - (pb[2] + pb[5]) / 2
    var_pin = pin.moved(Location((0, 0, dz2)))
    assert overlap(bbox(var_pin), bbox(screw)), 'c2 variant bbox disjoint from screw — design error'
    v_var = common_volume(var_pin, screw)
    v_real4 = common_volume(pin, screw)
    rec('NC_c2_e2_pin_extended', f'{PIN[st["group"]]} moved dz={dz2:.3f} into screw z-band vs modified screw exports',
        v_var, True, v_real4,
        note=f'pin bbox={[round(x,3) for x in pb]}；真实销尖让隙设计 → 销在螺钉 z 带内无材料，真实零干涉非相贯漏检')

    fired = sum(1 for c in result['controls'].values() if c['variant_fired'])
    realz = sum(1 for c in result['controls'].values() if c['real_zero'])
    result['summary'] = {'controls': len(result['controls']), 'variant_fired': fired,
                         'real_zero': realz,
                         'all_pass': fired == len(result['controls']) and realz == len(result['controls'])}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_negative_controls.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    for k, c in result['controls'].items():
        print(k, 'variant=', c['variant_common_mm3'], 'real=', c['real_common_mm3'], 'pass=', c['pass'])
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
