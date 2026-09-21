from pathlib import Path
import subprocess,json,hashlib
A=Path(__file__).resolve().parents[1]
exe=A.parents[5]/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
out=A/'review/input_passive_footprint';out.mkdir(exist_ok=True)
cmd=[str(exe),'fp','export','svg','--output',str(out),'--layers','F.Cu,F.Fab,F.CrtYd','--sketch-pads-on-fab-layers',str(A/'ecad/WP10_PASSIVES.pretty')]
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
svg=list(out.glob('*.svg'))
result=dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,SVGs=[p.relative_to(A).as_posix() for p in svg],footprint_parse_and_export_pass=r.returncode==0 and len(svg)==1,PCB_DRC_or_assembly_verified=False)
(A/'results/INPUT_PASSIVE_FOOTPRINT_NATIVE.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result));assert result['footprint_parse_and_export_pass']

