"""Run geometry-only producers with Windows font discovery disabled for import.

build123d eagerly reads a malformed installed font on this host. These producers
do not create text geometry; exclude only system/user font discovery during the
initial import, without changing installed fonts or CAD library files.
"""
import sys, glob, runpy, json
from pathlib import Path
sys.dont_write_bytecode=True
original=glob.glob
skipped=[]
def geometry_glob(pattern,*a,**kw):
    normalized=str(pattern).replace('\\','/').casefold()
    if '/windows/fonts/' in normalized:
        skipped.append(str(pattern));return []
    return original(pattern,*a,**kw)
try:
    glob.glob=geometry_glob
    import build123d
finally:
    glob.glob=original
print(json.dumps({'font_discovery_skipped_only_for_text_free_geometry':skipped,'installed_files_modified':False}),flush=True)
target=Path(sys.argv[1]).resolve();sys.argv=sys.argv[1:]
runpy.run_path(str(target),run_name='__main__')
