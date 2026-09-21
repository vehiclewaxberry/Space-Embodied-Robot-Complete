import csv, os

base = r'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/PL1_MAINLINE_20260808'

# --- PL1-A discovery CSV coverage vs actual F:\ top level ---
with open(os.path.join(base, 'PL1-A/PL1_PROJECT_ASSET_DISCOVERY.csv'), newline='', encoding='utf-8-sig') as f:
    rows = list(csv.reader(f))
paths = [r[0] for r in rows[1:]]
actual = sorted(os.listdir('F:/'))
print('PL1-A CSV data rows:', len(paths))
print('Actual F:\\ top-level entries:', len(actual))
norm = lambda p: p.replace('/', '\\').rstrip('\\')
csvn = [norm(p) for p in paths]
missing = [a for a in actual if not any(p.endswith('\\' + a) or p == 'F:\\' + a for p in csvn)]
print('Top-level entries NOT covered by CSV:', missing)
# duplicate coverage?
from collections import Counter
c = Counter(csvn)
dups = {k: v for k, v in c.items() if v > 1}
print('Duplicated CSV path rows:', dups)
# rows that are NOT top-level (sub-paths)
subs = [p for p in paths if norm(p).count('\\') > 2]
print('Sub-path rows (not top-level):', len(subs))
for s in subs[:20]:
    print('   ', s)

# --- PL1-G matrix structure ---
with open(os.path.join(base, 'PL1-G/TWO_ROOT_CONSOLIDATION_MATRIX.csv'), newline='', encoding='utf-8-sig') as f:
    mrows = list(csv.reader(f))
print()
print('PL1-G matrix data rows:', len(mrows) - 1)
cls = Counter(r[2] for r in mrows[1:])
print('classification counts:', dict(cls))
act = Counter(r[4] for r in mrows[1:])
print('action counts:', dict(act))
tgt = Counter(r[3] for r in mrows[1:])
print('target_root counts:', dict(tgt))
