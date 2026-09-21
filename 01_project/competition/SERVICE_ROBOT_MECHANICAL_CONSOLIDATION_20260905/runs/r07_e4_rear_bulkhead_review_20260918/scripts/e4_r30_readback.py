# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r30：exports 独立读回。
1) 钉固：ENG 现行 spacecraft_model.py / design_parameters.json sha256；EXPORT_MANIFEST 14 件 sha/体积/bbox 逐项复测。
2) 4 角×6 对同轴独立复测（窗口 Ø8 / 夹套筒 OD7.9 / 端框孔 Ø4.5 / 栓杆 Ø4 柱面轴两两比对），
   判据语义先读被审 acc v2 再定（E3 教训：v1 陷阱——尖端在 bbox max 侧；导孔被 E2 销孔劈 2 面按唯一轴计数）。
3) 夹套几何独立测量：柱面半径集 {3.95, 6.0, 2.25}、bbox x[-191,-183]、体积 vs 解析包络互证。
4) 尖端 -161：exports 改件 bbox max.X；改件∩解析基线包络 = π·2²·26（延长仅在头侧的直接几何证据）；
   啮合段 x[-177,-161] ∩ Ø8 包络 = π·2²·16 对改件与基线逐位一致。
5) 缺口登记复核：隔框∩端框 Common=0.0 实测复算（s00b fit_truth 声明）。
布尔一律 OCP 原生（勘误 O2）。"""
import json, math, time
from e4_common import (REV, RUN, ENG, SOURCE_SHA256_EXPECT, PARAMS_SHA256_EXPECT,
                       write_json, sha256_file, bbox, common_volume, cyl_faces,
                       axis_distance, import_step, stations, load_params,
                       screw_baseline_envelope, cylinder_at, sleeve_volume_analytic, C)

R_TOL = 1e-6


def axis_of(faces, r_target, y=None, z=None, r_tol=0.02):
    """从柱面集取半径匹配、且轴过 (y,z) 附近的面轴（loc, dir）；多面取首面并记录计数。"""
    hits = []
    for r, loc, d, f in faces:
        if abs(r - r_target) > r_tol:
            continue
        if y is not None and abs(loc[1] - y) > 2.0:
            continue
        if z is not None and abs(loc[2] - z) > 2.0:
            continue
        hits.append((loc, d))
    return hits


def pair_metrics(a1, a2):
    par, off = axis_distance(a1[0], a1[1], a2[0], a2[1])
    return {'parallel_deviation': par, 'axis_offset_mm': off}


def main():
    t0 = time.time()
    result = {'review': 'R07_E4_INDEPENDENT_REVERIFY', 'script': 'e4_r30_readback.py',
              'reviewed_run': RUN.name, 'failures': [], 'verdict': None}
    P, psha = load_params()
    ssha = sha256_file(ENG / 'spacecraft_model.py')
    result['basis_pins'] = {
        'design_parameters.json': {'actual': psha, 'expect': PARAMS_SHA256_EXPECT,
                                   'match': psha == PARAMS_SHA256_EXPECT},
        'spacecraft_model.py': {'actual': ssha, 'expect': SOURCE_SHA256_EXPECT,
                                'match': ssha == SOURCE_SHA256_EXPECT}}
    if not all(v['match'] for v in result['basis_pins'].values()):
        result['failures'].append(f"basis pin fail: {result['basis_pins']}")
    sts = stations(P)

    # ---- 1) EXPORT_MANIFEST 逐项复测 ----
    man = json.loads((RUN / 'exports' / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    files = man['parts']
    result['export_manifest_format_keys'] = list(man.keys())
    shape_by_name = {}
    man_recs = {}
    for f in files:
        name = f['name']
        fn = f['file']
        p = RUN / 'exports' / fn
        rec = {'file': fn, 'kind': f.get('kind')}
        if not p.exists():
            rec['error'] = 'missing export file'
            result['failures'].append(f'export missing: {fn}')
            man_recs[name] = rec
            continue
        actual_sha = sha256_file(p)
        expect_sha = f.get('sha256')
        rec['sha256_match'] = (actual_sha == expect_sha)
        if not rec['sha256_match']:
            result['failures'].append(f'sha mismatch {fn}: {actual_sha} vs {expect_sha}')
        sh = import_step(str(p))
        shape_by_name[name] = sh
        v = sh.volume
        rec['volume_mm3_measured'] = v
        rec['volume_mm3_registered'] = f.get('volume_mm3')
        if f.get('volume_mm3') is not None:
            # 登记值为 6 位小数舍入，判据取 5e-7
            rec['volume_abs_diff'] = abs(v - f['volume_mm3'])
            rec['volume_match'] = rec['volume_abs_diff'] <= 5e-7
            if not rec['volume_match']:
                result['failures'].append(f'volume mismatch {name}: {v} vs {f["volume_mm3"]}')
        bb = bbox(sh)
        rec['bbox_measured'] = [round(x, 6) for x in bb]
        reg_min, reg_max = f.get('bbox_min_mm'), f.get('bbox_max_mm')
        rec['bbox_registered'] = [reg_min, reg_max]
        if reg_min and reg_max:
            bb_ok = all(abs(bb[i] - reg_min[i]) <= 1e-6 for i in range(3)) and \
                    all(abs(bb[i + 3] - reg_max[i]) <= 1e-6 for i in range(3))
            rec['bbox_match'] = bb_ok
            if not bb_ok:
                result['failures'].append(f'bbox mismatch {name}: {bb} vs {reg_min}/{reg_max}')
        man_recs[name] = rec
    result['export_readback'] = man_recs

    # ---- 2) 4 角×6 对同轴独立复测 ----
    bk_faces = cyl_faces(shape_by_name['rear_launch_bulkhead'])
    fr_faces = cyl_faces(shape_by_name['RB_end_frame_-1'])
    coax = {}
    for st in sts:
        y, z = st['y'], st['z']
        sl_faces = cyl_faces(shape_by_name[st['sleeve']])
        sc_faces = cyl_faces(shape_by_name[st['screw']])
        axes = {
            'window': axis_of(bk_faces, 4.0, y, z),
            'sleeve': axis_of(sl_faces, 3.95),
            'frame': axis_of(fr_faces, 2.25, y, z),
            'screw': axis_of(sc_faces, 2.0),
        }
        rec = {'axis_face_counts': {k: len(v) for k, v in axes.items()}, 'pairs': {}}
        for k, v in axes.items():
            if len(v) < 1:
                result['failures'].append(f'{st["group"]}: no cylindrical axis for {k}')
        names = ['window', 'sleeve', 'frame', 'screw']
        for i in range(4):
            for j in range(i + 1, 4):
                a, b = names[i], names[j]
                if axes[a] and axes[b]:
                    m = pair_metrics(axes[a][0], axes[b][0])
                    m['pass'] = (m['parallel_deviation'] <= 1e-9 and m['axis_offset_mm'] <= 1e-6)
                    rec['pairs'][f'{a}_vs_{b}'] = m
                    if not m['pass']:
                        result['failures'].append(f'{st["group"]} {a}_vs_{b}: {m}')
        coax[st['group']] = rec
    result['coaxial_4x6'] = coax

    # ---- 3) 夹套几何独立测量 ----
    sleeves = {}
    v_an = sleeve_volume_analytic()
    for st in sts:
        sh = shape_by_name[st['sleeve']]
        radii = sorted(round(r, 6) for r, _, _, _ in cyl_faces(sh))
        bb = bbox(sh)
        ok_r = (len(radii) == 3 and abs(radii[0] - 2.25) < 1e-6 and abs(radii[1] - 3.95) < 1e-6
                and abs(radii[2] - 6.0) < 1e-6)
        ok_bb = (abs(bb[0] - (-191.0)) < 1e-9 and abs(bb[3] - (-183.0)) < 1e-9)
        rec = {'radii': radii, 'bbox': [round(x, 6) for x in bb],
               'volume_mm3': sh.volume, 'volume_analytic': v_an,
               'volume_abs_diff': abs(sh.volume - v_an),
               'radii_set_ok': ok_r, 'bbox_x_span_ok': ok_bb,
               'pass': ok_r and ok_bb and abs(sh.volume - v_an) <= 1e-6}
        sleeves[st['sleeve']] = rec
        if not rec['pass']:
            result['failures'].append(f'sleeve measure fail: {st["sleeve"]}: {rec}')
    result['sleeve_measurement'] = sleeves

    # ---- 4) 尖端 -161 与延长仅在头侧 ----
    v_engagement_expect = math.pi * 2.0**2 * 16   # Ø4 x[-177,-161]
    v_common_baseline_expect = math.pi * 2.0**2 * 26  # 改件∩基线 = Ø4 x[-187,-161]
    screws = {}
    for st in sts:
        sh = shape_by_name[st['screw']]
        bb = bbox(sh)
        base = screw_baseline_envelope(st['sy'], st['sz'])
        seg = cylinder_at(8, 16, (-169, st['y'], st['z']), (1, 0, 0))  # x[-177,-161] Ø8 包络
        v_base = common_volume(sh, base)
        v_seg_e4 = common_volume(sh, seg)
        v_seg_base = common_volume(base, seg)
        rec = {'bbox': [round(x, 6) for x in bb],
               'tip_max_x': bb[3], 'tip_minus_161_exact': bb[3] == -161.0,
               'common_with_baseline_mm3': v_base,
               'common_with_baseline_expect': v_common_baseline_expect,
               'engagement_seg_e4_mm3': v_seg_e4,
               'engagement_seg_baseline_mm3': v_seg_base,
               'engagement_seg_expect': v_engagement_expect,
               'engagement_abs_diff': (None if isinstance(v_seg_e4, dict) or isinstance(v_seg_base, dict)
                                       else abs(v_seg_e4 - v_seg_base)),
               'engagement_path_note': ('import-STEP 件 vs build123d 原生包络为不同求积路径，'
                                        '本项判据=求积路径容差 1e-9 内一致；'
                                        'bit-identical 预言属 build-vs-build 同路径命题，由 r32 承担'),
               'pass': (bb[3] == -161.0 and not isinstance(v_base, dict)
                        and abs(v_base - v_common_baseline_expect) <= 1e-6
                        and not isinstance(v_seg_e4, dict) and not isinstance(v_seg_base, dict)
                        and abs(v_seg_e4 - v_seg_base) <= 1e-9
                        and abs(v_seg_e4 - v_engagement_expect) <= 1e-9)}
        screws[st['screw']] = rec
        if not rec['pass']:
            result['failures'].append(f'screw tip/engagement fail: {st["screw"]}: {rec}')
    result['screw_tip_engagement'] = screws

    # ---- 5) 缺口登记复核：隔框∩端框 Common=0.0（fit_truth 声明）----
    v_bf = common_volume(shape_by_name['rear_launch_bulkhead'], shape_by_name['RB_end_frame_-1'])
    result['fit_truth_recheck'] = {
        'bulkhead_common_frame_mm3': v_bf,
        'declared': 0.0,
        'pass': (not isinstance(v_bf, dict)) and v_bf == 0.0}
    if not result['fit_truth_recheck']['pass']:
        result['failures'].append(f'bulkhead∩frame != 0: {v_bf!r}')

    n_pairs = sum(len(c['pairs']) for c in coax.values())
    result['summary'] = {
        'exports_checked': len(man_recs), 'coaxial_pairs': n_pairs,
        'coaxial_all_zero': all(m['pass'] for c in coax.values() for m in c['pairs'].values()),
        'sleeves_ok': all(r['pass'] for r in sleeves.values()),
        'screws_ok': all(r['pass'] for r in screws.values()),
        'fit_truth_ok': result['fit_truth_recheck']['pass']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_e4_readback.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    print('failures', result['failures'][:6])


if __name__ == '__main__':
    main()
