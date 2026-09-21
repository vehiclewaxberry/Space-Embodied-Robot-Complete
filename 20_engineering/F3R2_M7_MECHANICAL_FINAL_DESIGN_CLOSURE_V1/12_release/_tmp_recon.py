import os, re, sys, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TOKENS = ['185.25','198.0','208.0','210.405','210.41','215.0','4.695555949342986',
          '0.7619','0.3483933','22.927194215348','0.376019184652','702.195458',
          '90.509642','0.101015357','0.206','0.207','1.8909','71.5','82.23','50.50',
          '0.0601233','0.360622','0.274973','0.677633','0.130197','0.113705',
          '1.05961','0.59965','19.20','1.0005','POST_CAPTURE','C3D8R','C3D8I',
          '2.1','6.7','10.75','0.227','0.200','0.006','64','160']
ART = {'.inp','.dat','.msg','.odb','.prt','.sta','.com','.runlog','.env','.fcstd'}
hits = collections.defaultdict(collections.Counter)
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in ('__pycache__', 'wp13_embodied_mechanical_contract')]
    for f in fn:
        ext = os.path.splitext(f)[1].lower()
        if ext in ART:
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        if rel.startswith('12_release/_tmp'):
            continue
        if os.path.basename(rel).startswith('GEOM_'):
            continue
        try:
            t = open(p, 'r', encoding='utf-8', errors='replace').read()
        except Exception as e:
            print('READFAIL', rel, e); continue
        for tok in TOKENS:
            n = t.count(tok)
            if n:
                hits[tok][rel] = n
for tok in TOKENS:
    fs = hits[tok]
    print('### %-20s files=%d total=%d' % (tok, len(fs), sum(fs.values())))
    for k, v in sorted(fs.items()):
        print('      %4d  %s' % (v, k))
