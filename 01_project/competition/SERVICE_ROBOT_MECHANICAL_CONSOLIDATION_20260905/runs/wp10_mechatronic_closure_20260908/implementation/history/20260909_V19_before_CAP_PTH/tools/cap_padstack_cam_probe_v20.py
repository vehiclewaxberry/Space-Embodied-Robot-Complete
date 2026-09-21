"""Review-only Gerber/Excellon exports; no fabrication release or transmission."""
from pathlib import Path
import sys,subprocess,json,hashlib
A=Path(__file__).resolve().parents[1];ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 mode=sys.argv[1];assert mode in ['probe','active']
 source=A/('results/CAP_PADSTACK_PROBE_V20/REMOVE_UNUSED_FRONT.kicad_pcb' if mode=='probe' else 'ecad/wp10_c203_terminal.kicad_pcb')
 out=A/f'results/CAP_CAM_{mode.upper()}_V20';assert not out.exists();out.mkdir()
 commands=[
 [str(CLI),'pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask','--output',str(out)+'/',str(source)],
 [str(CLI),'pcb','export','drill','--format','excellon','--excellon-separate-th','--output',str(out)+'/',str(source)]]
 records=[]
 for cmd in commands:
  q=subprocess.run(cmd,cwd=A,capture_output=True,text=True,encoding='utf-8')
  records.append(dict(command=cmd,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
  (out/'commands.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
  assert q.returncode==0,q.stderr
 files={p.relative_to(A).as_posix():sha(p) for p in out.iterdir() if p.is_file()}
 result=dict(status='REVIEW_ONLY_NATIVE_CAM_EXPORT__NOT_MANUFACTURING_RELEASE',mode=mode,source=source.relative_to(A).as_posix(),source_sha256=sha(source),commands=records,files=files,manufacturing_release=False,transmitted_to_fabricator=False,whole_design_complete=False)
 (A/f'results/CAP_CAM_{mode.upper()}_V20.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(dict(mode=mode,files=list(files))))
if __name__=='__main__':main()
