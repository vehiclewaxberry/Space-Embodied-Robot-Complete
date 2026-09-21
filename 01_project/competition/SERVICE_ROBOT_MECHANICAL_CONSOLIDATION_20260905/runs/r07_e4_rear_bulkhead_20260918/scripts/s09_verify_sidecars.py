# -*- coding: utf-8 -*-
# 全量边车校验：0 缺失 / 0 哈希不符 / 0 相对路径异常 / 0 绝对路径
import hashlib, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ['inputs', 'scripts', 'exports', 'evidence', 'logs']
targets = []
for d in DIRS:
    for dp, _, fns in os.walk(os.path.join(RUN, d)):
        for fn in fns:
            targets.append(os.path.join(dp, fn))
for fn in ['PATCH_NOTES.md', 'ACCEPTANCE_SUMMARY.json']:
    targets.append(os.path.join(RUN, fn))

missing, mismatch, abspath, badrel = [], [], [], []
checked = 0
for p in sorted(targets):
    if p.endswith('.sha256'):
        continue
    sc = p + '.sha256'
    if not os.path.exists(sc):
        missing.append(os.path.relpath(p, RUN))
        continue
    checked += 1
    content = open(sc, 'rb').read().decode('utf-8')
    if not content.endswith('\n'):
        badrel.append(os.path.relpath(p, RUN) + ' (no trailing LF)')
    line = content.rstrip('\n')
    h, sep, rel = line.partition('  ')
    if not sep:
        badrel.append(os.path.relpath(p, RUN) + ' (no separator)')
        continue
    actual = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if h != actual:
        mismatch.append(os.path.relpath(p, RUN))
    expected_rel = os.path.relpath(p, RUN).replace(chr(92), '/')
    if rel != expected_rel:
        badrel.append(os.path.relpath(p, RUN) + ' rel=%r expected=%r' % (rel, expected_rel))
    if ':' in rel or rel.startswith('/') or chr(92) in rel:
        abspath.append(os.path.relpath(p, RUN))

print('checked', checked, 'missing', len(missing), 'hash_mismatch', len(mismatch),
      'bad_rel', len(badrel), 'abs_path', len(abspath))
for l in (missing, mismatch, badrel, abspath):
    for x in l:
        print(' !!', x)
