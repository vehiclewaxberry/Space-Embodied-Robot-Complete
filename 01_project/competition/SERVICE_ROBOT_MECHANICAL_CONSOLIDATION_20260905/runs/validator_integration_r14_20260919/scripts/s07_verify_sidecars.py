# -*- coding: utf-8 -*-
"""s07_verify_sidecars：全量边车校验——0 缺失 / 0 不符 / 0 异常才 PASS。"""
import hashlib, os, sys

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


missing, mismatch, malformed, checked = [], [], [], 0
for dirpath, _, files in os.walk(RUN):
    for f in sorted(files):
        p = os.path.join(dirpath, f)
        if f.endswith('.sha256'):
            continue
        sc = p + '.sha256'
        if not os.path.exists(sc):
            missing.append(os.path.relpath(p, RUN))
            continue
        raw = open(sc, 'rb').read().decode('utf-8')
        if not raw.endswith('\n') or '  ' not in raw:
            malformed.append(f)
            continue
        h, rel = raw.rstrip('\n').split('  ', 1)
        if rel != os.path.relpath(p, RUN).replace('\\', '/') or h != sha(p):
            mismatch.append(f)
        checked += 1
print({'checked': checked, 'missing': len(missing), 'mismatch': len(mismatch), 'malformed': len(malformed)})
if missing or mismatch or malformed:
    print('MISSING:', missing); print('MISMATCH:', mismatch); print('MALFORMED:', malformed)
    sys.exit(1)
print('SIDECARS_ALL_VALID')
