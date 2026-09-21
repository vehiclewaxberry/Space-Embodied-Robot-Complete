"""Native footprint load and export-sheet visual inspection, under serial guard."""
from pathlib import Path
import json,subprocess,sys,shutil
from pypdf import PdfReader
A=Path(__file__).resolve().parents[1]
code="""import pcbnew,json
p=pcbnew.FootprintLoad('ecad/WP10_TIMING.pretty','C201_MKP2_1uF_P5_Slot2')
assert p is not None
rows=[dict(pin=x.GetNumber(),drill_mm=[x.GetDrillSize().x/1e6,x.GetDrillSize().y/1e6],position_mm=[x.GetPosition().x/1e6,x.GetPosition().y/1e6]) for x in p.Pads()]
rows.sort(key=lambda r:r['pin'])
assert rows[0]['drill_mm']==[.9,.9] and rows[1]['drill_mm']==[2,.9]
assert rows[0]['position_mm']==[0,0] and rows[1]['position_mm']==[5,0]
print(json.dumps(dict(passed=True,pads=rows,model_count=len(p.Models()))))
"""
q=subprocess.run(['G:/Windows_program_file/Kicad/bin/python.exe','-B','-c',code],cwd=A,capture_output=True,text=True)
assert q.returncode==0,q.stderr
r=dict(native_footprint=json.loads(q.stdout),images=[])
pdf=A/'ecad/wp10_system_v24.pdf';reader=PdfReader(pdf)
for ref in ['R203','C201']:
 pages=[i+1 for i,p in enumerate(reader.pages) if ref in p.extract_text()]
 assert len(pages)==1,(ref,pages)
 output=A/'review'/('TIMER_'+ref+'_SCHEMATIC_V24')
 cmd=[shutil.which('pdftoppm'),'-f',str(pages[0]),'-singlefile','-scale-to','2200','-png',str(pdf),str(output)]
 p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,p.stderr
 r['images'].append(dict(reference=ref,page=pages[0],path=str(output)+'.png'))
(A/'results/TIMER_NATIVE_VISUAL_V24.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))

