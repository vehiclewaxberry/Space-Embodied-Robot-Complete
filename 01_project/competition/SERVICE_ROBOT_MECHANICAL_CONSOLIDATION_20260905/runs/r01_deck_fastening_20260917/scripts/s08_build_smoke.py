# -*- coding: utf-8 -*-
"""R01 烟测：修改后的 spacecraft_model.build() 代码路径可执行性验证。
副作用防护：运行前备份 results/ 下将被覆写的回执 JSON，运行后逐字节恢复并校验哈希。
不导出 STEP、不写 parts。结果仅写入本 run 日志。"""
import sys, json, hashlib, time, shutil
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    t0 = time.time()
    receipt = ENG / 'results' / 'service_structure_instances.json'
    backup = RUN / 'logs' / 'service_structure_instances.json.presmoke_bak'
    existed = receipt.exists()
    pre_sha = sha(receipt) if existed else None
    if existed:
        shutil.copy2(receipt, backup)
    log = {'run': 'r01_deck_fastening_20260917', 'check': 'build() smoke test (service, no arm, no exports)',
           'receipt_file': str(receipt), 'receipt_existed_before': existed, 'receipt_sha256_before': pre_sha}
    try:
        model, shapes, r = sm.build('service', include_arm=False, write_parts=False)
        names = [i['id'] for i in r['instances']]
        r01 = [n for n in names if 'fastener' in n or 'deck' in n or 'shear_web' in n]
        log['build_ok'] = True
        log['instance_count'] = len(names)
        log['r01_related_instances'] = sorted(r01)
        log['r01_fastener_count'] = sum(1 for n in names if '_fastener_' in n)
        log['deck_hole_param_source'] = 'design_parameters.json deck_fastening_r01'
        log['model_valid'] = bool(model.is_valid)
    except Exception as e:
        log['build_ok'] = False
        log['error'] = repr(e)
    finally:
        if existed:
            shutil.copy2(backup, receipt)
            log['receipt_restored'] = True
            log['receipt_sha256_after_restore'] = sha(receipt)
            log['restore_matches_before'] = log['receipt_sha256_after_restore'] == pre_sha
        elif receipt.exists():
            receipt.unlink()
            log['receipt_restored'] = 'deleted_new_file'
    log['elapsed_s'] = round(time.time() - t0, 3)
    suffix = sys.argv[1] if len(sys.argv) > 1 else ''
    log['candidate_version'] = suffix.lstrip('_') or 'V1'
    f = RUN / 'logs' / f's08_build_smoke_log{suffix}.json'
    wlf(f, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    sidecar(f)
    print('build_ok:', log.get('build_ok'), 'instances:', log.get('instance_count'),
          'r01_fasteners:', log.get('r01_fastener_count'),
          'restore_ok:', log.get('restore_matches_before'))
    if not log.get('build_ok'):
        print(log.get('error'))

if __name__ == '__main__':
    main()
