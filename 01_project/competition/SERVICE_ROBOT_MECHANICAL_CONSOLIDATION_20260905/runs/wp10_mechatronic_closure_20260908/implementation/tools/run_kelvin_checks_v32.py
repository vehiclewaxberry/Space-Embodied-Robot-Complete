"""Run serial native ERC, netlist and PCB DRC on the same V32 sources."""
from pathlib import Path
import json, subprocess

A=Path(__file__).resolve().parents[1]
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
D=A/'ecad/revisions/v32'
R=A/'results/kelvin_v32'

def main():
    jobs=[['sch','export','netlist','--format','kicadxml','-o',str(D/'wp10_system.xml'),str(D/'wp10_system.kicad_sch')],
          ['sch','export','netlist','--format','kicadsexpr','-o',str(D/'wp10_system.net'),str(D/'wp10_system.kicad_sch')],
          ['sch','erc','--format','json','--severity-all','-o',str(R/'SYSTEM_ERC.json'),str(D/'wp10_system.kicad_sch')],
          ['pcb','drc','--format','json','--severity-all','-o',str(R/'MAIN_INPUT_DRC.json'),str(D/'wp10_main_input.kicad_pcb')],
          ['pcb','export','svg','--mode-single','--page-size-mode','2','--exclude-drawing-sheet',
           '--layers','F.Cu,F.Silkscreen,Edge.Cuts','-o',str(R/'MAIN_INPUT_TOP.svg'),str(D/'wp10_main_input.kicad_pcb')]]
    results=[]
    for args in jobs:
        q=subprocess.run([str(CLI),*args],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
        results.append(dict(command=[str(CLI),*args],returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
        (R/'NATIVE_COMMANDS.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        if q.returncode!=0: raise RuntimeError(q.stderr or q.stdout)
    print(json.dumps(results))

if __name__=='__main__':main()
