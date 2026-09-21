# -*- coding: utf-8 -*-
"""R07-E4 角区实读探针（非裁决）：后端框/隔框/角区螺钉/端塞/肋/保留体积 bbox 与贴合关系。"""
import sys
from pathlib import Path
sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

ROOT = Path(__file__).resolve().parents[6]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

def bbox(s):
    b = s.bounding_box()
    return tuple(round(v, 3) for v in (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z))

def cv(a, b):
    op = BRepAlgoAPI_Common(a.wrapped, b.wrapped); op.Build()
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(op.Shape(), g)
    return g.Mass()

model, shapes, receipt = sm.build('service', include_arm=False)
print('instances', len(receipt['instances']))
names = ['rear_launch_bulkhead', 'RB_end_frame_-1', 'RB_end_screw_-1_1_1', 'RB_end_screw_-1_-1_-1',
         'RB_end_plug_-1_1_1', 'rear_vertical_rib_-86', 'rear_vertical_rib_86',
         'rear_horizontal_rib_-86', 'rear_horizontal_rib_86', 'launch_interface_reserved_volume',
         'front_service_cover', 'RB_end_frame_1', 'RB_end_screw_1_1_1']
for n in names:
    if n in shapes:
        print(n, bbox(shapes[n]))
print('--- common volumes ---')
print('bulkhead ∩ end_frame_-1:', cv(shapes['rear_launch_bulkhead'], shapes['RB_end_frame_-1']))
print('bulkhead ∩ end_screw_-1_1_1:', cv(shapes['rear_launch_bulkhead'], shapes['RB_end_screw_-1_1_1']))
print('bulkhead ∩ ribs v86:', cv(shapes['rear_launch_bulkhead'], shapes['rear_vertical_rib_86']))
print('end_screw_-1_1_1 ∩ end_frame_-1:', cv(shapes['RB_end_screw_-1_1_1'], shapes['RB_end_frame_-1']))
print('end_screw_-1_1_1 ∩ end_plug_-1_1_1 (thread conv):', cv(shapes['RB_end_screw_-1_1_1'], shapes['RB_end_plug_-1_1_1']))
