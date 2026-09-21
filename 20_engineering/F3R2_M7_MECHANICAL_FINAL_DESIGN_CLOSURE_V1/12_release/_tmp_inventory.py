import os, sys
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KEEP = ('.yaml', '.yml', '.json', '.csv', '.md', '.svg', '.py')
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d != '__pycache__']
    rel = os.path.relpath(dp, root).replace(os.sep, '/')
    keep = [f for f in fn if os.path.splitext(f)[1].lower() in KEEP]
    if keep:
        print('== %s  (%d files total in dir)' % (rel, len(fn)))
        for f in sorted(keep):
            sz = os.path.getsize(os.path.join(dp, f))
            print('   %10d  %s' % (sz, f))
