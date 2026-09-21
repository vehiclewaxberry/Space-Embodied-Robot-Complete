"""Validate the process-local font fix with real geometry and a normal font."""
from pathlib import Path
import json,hashlib,os,sys,glob
from build123d import Box,Text,FontStyle,extrude
A=Path(__file__).resolve().parents[1]
p=Path('C:/Windows/Fonts/mstmc.ttf')
box=Box(2,3,4)
glyph=extrude(Text('C203',font_size=4,font='Arial',font_style=FontStyle.REGULAR),amount=.25)
out=dict(schema='WP10_CAD_RUNTIME_FONT_FILTER_V17',enabled=os.environ.get('WP10_FONT_SANITY')=='1',
    bad_font_path=str(p),bad_font_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    ordinary_glob_preserves_bad_font=any(Path(v).resolve()==p.resolve() for v in glob.glob('C:/Windows/Fonts/*ttf')),
    box_volume_mm3=box.volume,text_volume_mm3=glyph.volume,
    geometry_valid=box.is_valid and glyph.is_valid,system_fonts_modified=False,installed_skills_modified=False,
    inputs={'tools/cad_runtime/sitecustomize.py':hashlib.sha256((A/'tools/cad_runtime/sitecustomize.py').read_bytes()).hexdigest()})
out['passed']=out['enabled'] and out['ordinary_glob_preserves_bad_font'] and out['geometry_valid'] and abs(box.volume-24)<1e-9 and glyph.volume>0
(A/'results/CAD_RUNTIME_FONT_FILTER.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out));assert out['passed']
