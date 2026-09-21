# -*- coding: utf-8 -*-
"""由 s05_readback.py 生成 s05b_readback.py（V2 判据修正）。"""
import io
from pathlib import Path

d = Path(__file__).resolve().parent
src = io.open(d / 's05_readback.py', encoding='utf-8').read()

old = """            import math as _m
            bad = [a for a in ro3 if min(abs(a), abs(a - _m.pi), abs(a - 2*_m.pi)) > 0.6]
            hrec['center_plane_out_angles_off_bore'] = bad"""
new = """            import math as _m
            sin_max = 1.65 / (rr + 0.05)  # X 向 Ø3.3 导孔在塞心平面的合法遮盖带 |sin a|<=r_bore/(r+dr)
            bad = [a for a in ro3 if abs(_m.sin(a)) > sin_max + 1e-9]
            hrec['center_plane_out_angles_off_bore'] = bad
            hrec['center_plane_criterion'] = '环外点合法带 |sin a| <= 1.65/2.3 (Ø3.3 X 向导孔遮盖带); 带外出现外点即 FAIL'"""
assert old in src, 'pattern not found'
src = src.replace(old, new)
src = src.replace('"""R07-E2 STEP 读回机器验证',
                  '"""R07-E2 STEP 读回机器验证（s05b：V2 判据修正版——V1 判据 FAIL 保留于 acc_readback_holes_coaxial_V1_CRITERION_FAIL.json）')
with open(d / 's05b_readback.py', 'wb') as f:
    f.write(src.encode('utf-8'))
print('s05b written')
