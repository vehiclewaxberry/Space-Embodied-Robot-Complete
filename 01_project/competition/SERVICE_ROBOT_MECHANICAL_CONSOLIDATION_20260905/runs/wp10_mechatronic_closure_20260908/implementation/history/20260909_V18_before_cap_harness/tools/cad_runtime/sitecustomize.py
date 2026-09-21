"""Opt-in, process-local workaround for one invalid Windows font file.

Only build123d.text font discovery is affected. No OS/font/package writes.
Set WP10_FONT_SANITY=1 and add this directory to PYTHONPATH for CAD workers.
"""
import os
if os.environ.get('WP10_FONT_SANITY') == '1':
    import glob, hashlib, sys
    from pathlib import Path
    _glob=glob.glob
    _bad=Path('C:/Windows/Fonts/mstmc.ttf')
    _sha='31561c81e3fd1710926605578ef8210222191de5aa9304cef24d620165a78db6'
    _reported=False
    def _font_glob(pathname, *args, **kwargs):
        global _reported
        values=_glob(pathname,*args,**kwargs)
        caller=sys._getframe(1).f_globals.get('__name__','')
        if caller!='build123d.text':return values
        result=[]
        for v in values:
            if Path(v).resolve()==_bad.resolve():
                raw=Path(v).read_bytes()
                if hashlib.sha256(raw).hexdigest()==_sha and raw[:4] not in (b'\x00\x01\x00\x00',b'OTTO',b'ttcf',b'true',b'typ1'):
                    if not _reported:
                        print('WP10 CAD font filter: skipped hash-bound non-SFNT mstmc.ttf; system file unchanged',file=sys.stderr)
                        _reported=True
                    continue
            result.append(v)
        return result
    glob.glob=_font_glob
