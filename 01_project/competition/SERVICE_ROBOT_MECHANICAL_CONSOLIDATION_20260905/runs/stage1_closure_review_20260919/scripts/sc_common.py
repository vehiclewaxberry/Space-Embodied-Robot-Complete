# -*- coding: utf-8 -*-
"""阶段一收口两包独立复验公共模块（审阅侧工具；只读候选，不改任何被审文件，不执行 git 提交）。
本组任务无 build123d/CAD 布尔需求（R17 为软件溯源链、验证器为 stdlib+vtk 链），
如需 CAD 导入须先 sys.path.insert cadgen 守卫（E 组先例）。
约定：输出写二进制 LF；边车 = sha256 + '  ' + 相对 review run 根正斜杠路径。"""
import json, hashlib
from pathlib import Path

REV = Path(__file__).resolve().parents[1]            # stage1_closure_review_20260919/
RUN_A = REV.parent / 'r17_export_chain_20260919'
RUN_B = REV.parent / 'validator_integration_r14_20260919'
ROOT = REV.parents[4]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
WP01 = ROOT / '20_engineering/service_robot_wp01_20260905'
WP02 = ROOT / '20_engineering/service_robot_wp02_20260905'
URDF = ROOT / '20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'

# 钉固期望值（被审登记，逐位复核用）
E4_SOURCE_SHA = 'a888cda0a2c0ead7d3d985b5d3218ee1f8f6721059420dec593e1bdefcf1d81e'
PARAMS_SHA = '324b49c712f3b499dda0feb963527e4e7f4b25bfc151c4f83ab57bf382108ea8'
BASELINE_STRUCTURE_RECEIPT_SHA = 'd220c70274ab3bc27b306b253a4f6ac96057494de05a50c05955f04a450ef9a3'
R17_AFTER = {
    'BOM.csv': 'a6ce5bffd57a2232e5f55e0d6ed4166216405427f9d5f3f980d70329794624f9',
    'INTERFACES.csv': 'f432955d50c78bcdeab1eaef8926a207a77f6002c067a76e0c70f38365b7fd60',
    'DYNAMICS_HANDOFF.json': '5390292aa363d830e9eb55ca0780ee835b2cf47a3602739aec97a6dee71ac47f',
    'DYNAMICS_SUMMARY_ZH.md': 'cb199620a9f53cb6ac0a2fb555632df72b4a49625b1191470a8e1f2fbbf48a8b',
    'parking_instances.json': '2d9efa228fbb2b8ca575e3dfe8cfb6eed5f33cd7292842e9fe25a702dae8cb5f',
    'released_instances.json': 'a50459daaa89e8bdaf3345551f51680330eec0bd5e03e4f7577847a8c0c0b937',
    'service_instances.json': '25e12ac96f9afbb759d3d4d4305f638999a4fe9a08cc802c2e3ae3ae0c53b043',
    'parking_ground_instances.json': 'b35c99d9dac9a0e7d16007f2ee22e3fa410ef91b35464eb4e12902958411fa41',
}
R17_BEFORE_BOM = 'cfb4df9a60b7246cdeb77a8dc36dfef2847c3cba276d5668203f808776fb1b44'
POSE_SCREEN_V2_SHA = '07670f67879b88950c6a320b7e8e2695e15049254d2a14d9f8e557bef386c57f'


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))


def sidecar(p):
    h = sha256_file(p)
    rel = Path(p).resolve().relative_to(REV).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h


def write_json(p, obj):
    wlf(p, json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    return sidecar(p)
