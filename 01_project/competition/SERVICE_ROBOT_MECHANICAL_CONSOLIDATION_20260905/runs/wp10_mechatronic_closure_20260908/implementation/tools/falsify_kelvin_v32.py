"""Negative native PCB fixtures: omitted terminal model and physically broken sense trace."""
from pathlib import Path
import hashlib,json,shutil,subprocess
import pcbnew as k

A=Path(__file__).resolve().parents[1]
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
D=A/'ecad/revisions/v32'; R=A/'results/kelvin_v32'
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'

def run_case(name, edit):
    b=k.LoadBoard(str(D/'wp10_main_input.kicad_pcb'))
    detail=edit(b)
    path=D/(name+'.kicad_pcb')
    k.SaveBoard(str(path),b)
    shutil.copy2(D/'wp10_main_input.kicad_pro',path.with_suffix('.kicad_pro'))
    report=R/(name+'_DRC.json')
    cmd=[str(CLI),'pcb','drc','--format','json','--severity-all','-o',str(report),str(path)]
    q=subprocess.run(cmd,cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert q.returncode==0,(name,q.stderr)
    result=json.loads(report.read_text())
    count=len(result['unconnected_items'])
    assert count>0,(name,'Failure hidden by internal-terminal model')
    return dict(case=name,edit=detail,unconnected_items=count,rule_violations=len(result['violations']),
                detection_passed=True,command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr,
                fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def disable(b):
    f=next(f for f in b.GetFootprints() if f.GetReference()=='R201')
    f.SetDuplicatePadNumbersAreJumpers(False)
    return dict(ref='R201',duplicate_pad_numbers_are_jumpers=False,copper_changed=False)

def break_sense(b):
    f=next(f for f in b.GetFootprints() if f.GetReference()=='R201')
    p=min((p for p in f.Pads() if p.GetNumber()=='1'),key=lambda p:p.GetSize().y)
    pos=p.GetPosition()
    ts=[t for t in b.GetTracks() if not isinstance(t,k.PCB_VIA) and t.GetNetname()==p.GetNetname()
        and t.GetWidth()==200000 and (t.GetStart()==pos or t.GetEnd()==pos)]
    assert len(ts)==1,len(ts)
    t=ts[0]
    info=dict(uuid=t.m_Uuid.AsString(),start_mm=[t.GetStart().x/1e6,t.GetStart().y/1e6],
              end_mm=[t.GetEnd().x/1e6,t.GetEnd().y/1e6],net=t.GetNetname(),width_mm=t.GetWidth()/1e6)
    b.Remove(t)
    assert all(f.GetDuplicatePadNumbersAreJumpers() for f in b.GetFootprints() if f.GetReference() in ['R201','R202'])
    return dict(removed_sense_segment=info,internal_terminal_attributes_still_enabled=True)

def main():
    nominal_sha=hashlib.sha256((D/'wp10_main_input.kicad_pcb').read_bytes()).hexdigest()
    cases=[run_case('negative_missing_internal_R201',disable),run_case('negative_broken_VIN_sense',break_sense)]
    assert hashlib.sha256((D/'wp10_main_input.kicad_pcb').read_bytes()).hexdigest()==nominal_sha
    result=dict(passed=True,cases=cases,nominal_board_unchanged=True,hardware_tests=0)
    (R/'COUNTEREXAMPLES.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
