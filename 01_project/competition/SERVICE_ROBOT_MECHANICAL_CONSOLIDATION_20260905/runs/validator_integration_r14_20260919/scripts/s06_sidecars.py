# -*- coding: utf-8 -*-
"""s06_sidecars：为 run 目录下所有缺少边车的文件补写 sha256 边车（wb 二进制，run 根相对路径）。"""
import hashlib, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


created = []
for dirpath, _, files in os.walk(RUN):
    for f in sorted(files):
        if f.endswith('.sha256'):
            continue
        p = os.path.join(dirpath, f)
        sc = p + '.sha256'
        if not os.path.exists(sc):
            rel = os.path.relpath(p, RUN).replace('\\', '/')
            open(sc, 'wb').write((sha(p) + '  ' + rel + '\n').encode('utf-8'))
            created.append(rel)
print('created', len(created))
for c in created:
    print(' ', c)
