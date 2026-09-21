"""Export actual native B.Cu layout and render its PDF without editing the PCB."""
from pathlib import Path
import subprocess,sys,hashlib,json
A=Path(__file__).resolve().parents[1]
# Resolve project ownership explicitly instead of guessing a parent count.
root=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
cli=root/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
board='ecad/wp10_c203_terminal.kicad_pcb';pdf='review/C203_TERMINAL_LAYOUT_V17.pdf';png='review/C203_TERMINAL_LAYOUT_V17.png'
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
before=sha(board)
subprocess.run([str(cli),'pcb','export','pdf','--mode-single','--mirror','--scale','0','-l','B.Cu,B.SilkS,Edge.Cuts','-o',pdf,board],cwd=A,check=True)
for form,path in [('report','results/CAP_TERMINAL_DRC_V17.rpt'),('json','results/CAP_TERMINAL_DRC_NATIVE_V17.json')]:
    subprocess.run([str(cli),'pcb','drc','--format',form,'-o',path,board],cwd=A,check=True)
runtime='C:/Users/stude/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
code="import pypdfium2 as p; d=p.PdfDocument('"+pdf+"'); assert len(d)==1; im=d[0].render(scale=2).to_pil(); im.save('"+png+"')"
subprocess.run([runtime,'-B','-X','utf8','-c',code],cwd=A,check=True)
assert sha(board)==before
(A/'results/CAP_TERMINAL_LAYOUT_EXPORT_V17.json').write_text(json.dumps(dict(board=board,board_sha256=before,outputs={p:sha(p) for p in [pdf,png,'results/CAP_TERMINAL_DRC_V17.rpt','results/CAP_TERMINAL_DRC_NATIVE_V17.json']},native_export=True,edited_board=False),indent=2),encoding='utf-8')
print('Native B.Cu PDF and PNG exported')
