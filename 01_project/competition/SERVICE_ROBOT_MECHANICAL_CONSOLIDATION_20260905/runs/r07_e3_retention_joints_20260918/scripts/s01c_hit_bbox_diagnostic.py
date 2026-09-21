# -*- coding: utf-8 -*-
"""R07-E3 探针 HIT 诊断（非裁决）：打印碰撞双方与邻域构件 bbox，定位 x 向冲突。"""
import sys
from pathlib import Path
sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
ROOT = Path(__file__).resolve().parents[6]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

def bbox(s):
    b = s.bounding_box()
    return tuple(round(v, 3) for v in (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z))

model, shapes, receipt = sm.build('service', include_arm=False)
names = [n for n in sorted(shapes) if (
    n.startswith('e3_clamp_bolt_J0') or n.startswith('e3_foot_')
    or n.startswith('hold_roof_lug') or n.startswith('hold_crossbeam')
    or n.startswith('hold_pivot_clevis') or 'mast' in n or 'pivot_pin' in n)]
for n in names:
    print(n, bbox(shapes[n]))
