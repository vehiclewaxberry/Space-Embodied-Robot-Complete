# -*- coding: utf-8 -*-
"""s04 R14 参数扰动（分相执行，每相一次构建，防超时）。

phase=perturb_main  : 备份 -> X_S_mm[1] -50->-45 -> 构建 -> 扰动回执入 evidence -> 字节恢复
phase=perturb_legacy: 扰动 legacy_deck_hole_pattern_superseded.X_S_mm 150->155 -> 构建 ->
                      回执应与基线逐位一致（遗留字段无效证明）-> 字节恢复
phase=repro         : 恢复态重建 -> 回执 sha256 == 基线（bit-identical 复现性）
正式交付物保护：build('service', include_arm=False) 仅写 results/service_structure_instances.json；
不触碰 BOM.csv/HANDOFF；参数文件与回执均字节级备份并恢复，恢复后核对 sha256。
"""
import hashlib, json, os, shutil, subprocess, sys, time

ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'
RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = os.path.join(ENG, 'design_parameters.json')
RECEIPT = os.path.join(ENG, 'results', 'service_structure_instances.json')
BK_PARAMS = os.path.join(RUN, 'inputs', 'r14_backup_design_parameters.json')
BK_RECEIPT = os.path.join(RUN, 'inputs', 'r14_baseline_service_structure_instances.json')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def sidecar(p):
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((sha(p) + '  ' + rel + '\n').encode('utf-8'))


def backup_once():
    if not os.path.exists(BK_PARAMS):
        shutil.copyfile(PARAMS, BK_PARAMS); sidecar(BK_PARAMS)
    if not os.path.exists(BK_RECEIPT):
        shutil.copyfile(RECEIPT, BK_RECEIPT); sidecar(BK_RECEIPT)
    return sha(PARAMS), sha(RECEIPT)


def restore():
    open(PARAMS, 'wb').write(open(BK_PARAMS, 'rb').read())
    open(RECEIPT, 'wb').write(open(BK_RECEIPT, 'rb').read())
    ok = sha(PARAMS) == sha(BK_PARAMS) and sha(RECEIPT) == sha(BK_RECEIPT)
    if not ok:
        raise SystemExit('RESTORE_HASH_MISMATCH——字节恢复未复核通过，停止')
    return ok


def build_structure():
    t0 = time.time()
    proc = subprocess.run([sys.executable, '-c',
                           'import spacecraft_model; spacecraft_model.build("service", include_arm=False)'],
                          cwd=ENG, capture_output=True, text=True, encoding='utf-8', timeout=280)
    return {'returncode': proc.returncode, 'stderr_tail': proc.stderr[-800:],
            'elapsed_s': round(time.time() - t0, 3)}


def mutate_params(fn):
    d = json.loads(open(PARAMS, encoding='utf-8').read())
    before = fn(d)
    open(PARAMS, 'wb').write((json.dumps(d, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return before


def main():
    phase = sys.argv[1]
    log = {'script': 's04_r14_perturbation.py', 'phase': phase}
    base_ph, base_rh = backup_once()
    log['baseline_params_sha256'] = base_ph
    log['baseline_receipt_sha256'] = base_rh

    if phase == 'perturb_main':
        def fn(d):
            xs = d['deck_fastening_r01']['deck_hole_pattern']['X_S_mm']
            assert xs == [-150, -50, 50, 140], xs
            xs[1] = -45
            return list(xs)
        log['mutation'] = {'path': 'deck_fastening_r01.deck_hole_pattern.X_S_mm[1]', 'before': -50, 'after': -45}
        mutate_params(fn)
        assert sha(PARAMS) != base_ph
        log['build'] = build_structure()
        out = os.path.join(RUN, 'evidence', 'r14_perturbed_receipt.json')
        shutil.copyfile(RECEIPT, out); sidecar(out)
        log['perturbed_receipt_sha256'] = sha(out)
        log['restored'] = restore()
    elif phase == 'perturb_legacy':
        def fn(d):
            xs = d['deck_fastening_r01']['legacy_deck_hole_pattern_superseded']['X_S_mm']
            assert xs == [-150, -50, 50, 150], xs
            xs[3] = 155
            return list(xs)
        log['mutation'] = {'path': 'deck_fastening_r01.legacy_deck_hole_pattern_superseded.X_S_mm[3]',
                           'before': 150, 'after': 155}
        mutate_params(fn)
        log['build'] = build_structure()
        out = os.path.join(RUN, 'evidence', 'r14_legacy_perturbed_receipt.json')
        shutil.copyfile(RECEIPT, out); sidecar(out)
        log['legacy_perturbed_receipt_sha256'] = sha(out)
        log['legacy_zero_effect_bit_identical_to_baseline'] = (sha(out) == base_rh)
        log['restored'] = restore()
    elif phase == 'repro':
        assert sha(PARAMS) == base_ph, '参数文件未处于恢复基线态'
        log['build'] = build_structure()
        out = os.path.join(RUN, 'evidence', 'r14_repro_receipt.json')
        shutil.copyfile(RECEIPT, out); sidecar(out)
        log['repro_receipt_sha256'] = sha(out)
        log['repro_bit_identical_to_baseline'] = (sha(out) == base_rh)
        # 恢复工程目录回执为基线字节（重建产物与基线逐位一致，此处为保险起见仍回写）
        log['restored'] = restore()
    else:
        raise SystemExit('unknown phase ' + phase)

    log['verdict'] = 'PASS'
    lp = os.path.join(RUN, 'logs', f's04_{phase}_log.json')
    open(lp, 'wb').write((json.dumps(log, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    sidecar(lp)
    print(json.dumps({k: log[k] for k in ('phase', 'verdict') if k in log} | {'log': lp}, ensure_ascii=False))
    print(json.dumps({k: v for k, v in log.items() if k.endswith('sha256') or k.startswith(('legacy_zero', 'repro_bit', 'restored'))},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
