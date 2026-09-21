# -*- coding: utf-8 -*-
"""_work 探针：归因 r32 复算差（build123d intersect vs OCP BRepAlgoAPI_Common）。
对 A 对与 B 的 H01/H03 分别用两条布尔路径复算，验证登记值是否由 build123d 路径复现。"""
import sys
from e2_common import (RUN, RUN_E1, common_volume, import_step,
                       m4_screw_envelope, plug_rebuild)

E1_SCRIPTS = RUN.parent / 'r07_e1_anchoring_review_20260918' / 'scripts'
sys.path.insert(0, str(E1_SCRIPTS))
from rev_common import unmodified_upper_beam, shear_web_screw_envelope  # noqa: E402


def b123d_common(a, b):
    """被审方原始路径（仅对 build123d 原生件有效；import 件会触发 None 陷阱）。"""
    c = a.intersect(b)
    if c is None:
        return None
    return float(sum(s.volume for s in c.solids()))


def main():
    # A 对
    beam = unmodified_upper_beam(160)
    for side in (-1, 1):
        env = shear_web_screw_envelope(side)
        v_b = b123d_common(beam, env)
        v_o = common_volume(beam, env)
        print(f'A side={side}: build123d={v_b!r}  OCC={v_o!r}')
    # B 对 H01/H03（参数重建塞 = build123d 原生件，可两路径对照）
    for sid, sx, sy, sz, reg in (('H01', -1, -1, 1, 49.71566494430083),
                                 ('H03', 1, -1, 1, 49.71343670159784)):
        plug = plug_rebuild(sx, sy, sz)
        env = m4_screw_envelope(sx, sy, sz)
        v_b = b123d_common(plug, env)
        v_o = common_volume(plug, env)
        print(f'B {sid}: build123d={v_b!r}  OCC={v_o!r}  registered={reg!r}')
        # exports 读回件走 build123d 路径（预期 None 陷阱）
        plug_imp = import_step(str(RUN / 'exports' / f'RB_end_plug_{sx}_{sy}_{sz}.step'))
        v_bi = b123d_common(plug_imp, env)
        v_bi2 = b123d_common(env, plug_imp)
        print(f'B {sid} exports-plug build123d(plug,env)={v_bi!r}  build123d(env,plug)={v_bi2!r}')


if __name__ == '__main__':
    main()
