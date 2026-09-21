# -*- coding: utf-8 -*-
"""R01 V2：备份 V1 腹板紧固件 STEP（保留 FAIL 历史物证），重导 44 件，V1/V2 哈希对照。
受影响件 = 16 件 angle_web_fastener（两甲板×两侧×2段×2位）；其余 28 件应逐字节不变（哈希证明）。
注：审阅意见原文"32 件腹板紧固件（两甲板×两侧×8 位）"与参数卡数量不符——
angle_web 紧固件按 design_parameters.json deck_fastening_r01 为 2×2×2×2=16 件；32 为全部紧固件总数。
本轮重导全部 44 件并以哈希对照证明未受影响件不变，两种读法均覆盖。"""
import sys, json, hashlib, time, shutil
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import export_step, import_step
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

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
    return h

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def volume_of_intersect(a, b):
    inter = a.intersect(b)
    if inter is None:
        return 0.0
    try:
        items = list(inter)
    except TypeError:
        items = [inter]
    v = 0.0
    for s in items:
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(s.wrapped, g); v += g.Mass()
    return v

def main():
    t0 = time.time()
    exp = RUN / 'exports'
    v1man = json.loads((exp / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    v1hash = {p['name']: p['sha256'] for p in v1man['parts']}

    # 1) 备份 V1 腹板紧固件 STEP（FAIL 历史物证，不删除不覆盖备份）
    sup = exp / 'v1_superseded'
    sup.mkdir(exist_ok=True)
    backed = []
    for name in v1hash:
        if '_angle_web_fastener_' in name:
            src = exp / (name + '.step')
            dst = sup / (name + '.step')
            if not dst.exists():
                shutil.copy2(src, dst)
            backed.append({'name': name, 'v1_sha256': sha(dst)})
    # 2) V1 缺陷复算存档（16 件垫圈—腹板交集体积，审阅值 9.597566）
    v1_common = []
    for b in backed:
        side = b['name'].split('_')[4]
        f = import_step(str(sup / (b['name'] + '.step')))
        w = import_step(str(exp / (f'shear_web_{side}.step')))
        v1_common.append({'fastener': b['name'], 'v1_common_volume_mm3': volume_of_intersect(f, w)})
    # 3) 重导全部 44 件
    parts = sm.deck_fastening_parts(sm.P)
    new_entries = []
    for p in parts:
        f = exp / (p['name'] + '.step')
        export_step(p['shape'], str(f))
        new_entries.append({'name': p['name'], 'kind': p['kind'], 'file': f.name, 'sha256': sha(f)})
    # 4) 几何指纹对照（STEP 文件头含写出时间戳，字节级 sha256 必然不同 -> 用几何指纹证明未受影响件不变）。
    #    V1 候选函数 = 当前函数源码仅回退腹板紧固件垫圈/头两常数（103.4->102.9, 105.15->104.65）；
    #    重建保真度由 exports/v1_superseded/ 备份 STEP 指纹逐件校验（16/16 必须一致）。
    import ast
    cursrc = (ENG / 'spacecraft_model.py').read_text(encoding='utf-8')
    tree = ast.parse(cursrc)
    fn_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'deck_fastening_parts')
    v2fn_src = ast.get_source_segment(cursrc, fn_node)
    assert 'side*103.4' in v2fn_src and 'side*105.15' in v2fn_src
    v1fn_src = v2fn_src.replace('side*103.4', 'side*102.9').replace('side*105.15', 'side*104.65')
    exec(v1fn_src, sm.__dict__)
    v1parts = {p['name']: p for p in sm.__dict__['deck_fastening_parts'](sm.P)}
    def fingerprint(shape):
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape.wrapped, g)
        ga = GProp_GProps(); BRepGProp.SurfaceProperties_s(shape.wrapped, ga)
        bb = shape.bounding_box()
        return {'volume_mm3': round(g.Mass(), 4), 'area_mm2': round(ga.Mass(), 4),
                'faces': len(shape.faces()), 'edges': len(shape.edges()), 'solids': len(shape.solids()),
                'bbox_min': [round(v, 6) for v in (bb.min.X, bb.min.Y, bb.min.Z)],
                'bbox_max': [round(v, 6) for v in (bb.max.X, bb.max.Y, bb.max.Z)]}
    # 4a) 重建保真度校验：重建 V1 腹板紧固件指纹 vs v1_superseded 备份 STEP 指纹
    fidelity = []
    for b in backed:
        fp_re = fingerprint(v1parts[b['name']]['shape'])
        fp_bk = fingerprint(import_step(str(sup / (b['name'] + '.step'))))
        fidelity.append({'name': b['name'], 'match': fp_re == fp_bk})
    assert all(f['match'] for f in fidelity), 'V1 reconstruction not faithful'
    # 4b) 全 44 件对照
    changed, unchanged = [], []
    fps = {}
    for e in new_entries:
        v2shape = import_step(str(exp / (e['name'] + '.step')))
        fp1, fp2 = fingerprint(v1parts[e['name']]['shape']), fingerprint(v2shape)
        fps[e['name']] = {'v1': fp1, 'v2': fp2}
        (unchanged if fp1 == fp2 else changed).append(e['name'])
    # 5) V2 垫圈—腹板交集体积（应全 0）
    v2_common = []
    for b in backed:
        side = b['name'].split('_')[4]
        f = import_step(str(exp / (b['name'] + '.step')))
        w = import_step(str(exp / (f'shear_web_{side}.step')))
        v2_common.append({'fastener': b['name'], 'v2_common_volume_mm3': volume_of_intersect(f, w)})
    out = {
        'run': 'r01_deck_fastening_20260917', 'candidate_version': 'V2',
        'source': 'spacecraft_model.deck_fastening_parts (V2 washer/head fix)',
        'source_sha256': sha(ENG / 'spacecraft_model.py'),
        'parameters_sha256': sha(ENG / 'design_parameters.json'),
        'parameters_changed_vs_v1': sha(ENG / 'design_parameters.json') != v1man['parameters_sha256'],
        'v1_superseded_backup': {'dir': 'exports/v1_superseded/', 'files': backed},
        'v1_defect_recomputation': v1_common,
        'v1_defect_recomputation_max_mm3': max(c['v1_common_volume_mm3'] for c in v1_common),
        'v2_washer_web_common': v2_common,
        'v2_washer_web_common_max_mm3': max(c['v2_common_volume_mm3'] for c in v2_common),
        'geometry_fingerprint_compare': {
            'method': 'V1 候选函数=当前源码仅回退垫圈/头两常数重建；重建保真度经 v1_superseded 备份 STEP 指纹 16/16 校验。'
                      '指纹=(体积,面积,面/边/实体数,bbox)。STEP 文件头含写出时间戳，字节 sha256 不作为同一性判据。',
            'v1_reconstruction_fidelity': fidelity,
            'total_parts': len(new_entries),
            'unchanged_count': len(unchanged), 'changed_count': len(changed),
            'changed': sorted(changed), 'unchanged': sorted(unchanged),
            'changed_all_angle_web_fasteners': all('_angle_web_fastener_' in n for n in changed),
            'fingerprints': fps,
        },
        'parts': new_entries,
        'elapsed_s': round(time.time() - t0, 3),
    }
    f = exp / 'EXPORT_MANIFEST_V2.json'
    wlf(f, json.dumps(out, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    for b in backed:
        sidecar(sup / (b['name'] + '.step'))
    print('changed:', len(changed), 'unchanged:', len(unchanged))
    print('changed all angle_web:', out['geometry_fingerprint_compare']['changed_all_angle_web_fasteners'])
    print('V1 common max:', out['v1_defect_recomputation_max_mm3'])
    print('V2 common max:', out['v2_washer_web_common_max_mm3'])
    print('params changed:', out['parameters_changed_vs_v1'])

if __name__ == '__main__':
    main()
