"""Native padstack probes on copies; never change the active PCB or its rules."""
from pathlib import Path
import sys,subprocess,json,hashlib,shutil,collections
A=Path(__file__).resolve().parents[1]
KPY=Path('G:/Windows_program_file/Kicad/bin/python.exe')
ROOT=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists())
CLI=ROOT/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if sys.argv[1:]!=['--native']:
  raise SystemExit(subprocess.run([str(KPY),'-B','-X','utf8',str(Path(__file__)),'--native'],cwd=A).returncode)
 import pcbnew as k
 source=A/'ecad/wp10_c203_terminal.kicad_pcb';before=sha(source)
 outdir=A/'results/CAP_PADSTACK_PROBE_V20';assert not outdir.exists(),'Preserve probe history'
 outdir.mkdir();records=[]
 for variant in ['REMOVE_UNUSED_FRONT','BACK_ONLY_LAYERSET']:
  board=k.LoadBoard(str(source));fp=next(f for f in board.GetFootprints() if f.GetReference()=='C203')
  for pin,x in [('1',95),('2',105)]:
   group=[p for p in fp.Pads() if abs(k.ToMM(p.GetPosition().x)-x)<1e-8 and abs(k.ToMM(p.GetPosition().y)-100)<1e-8]
   assert len(group)==2
   hole=next(p for p in group if p.GetAttribute()==k.PAD_ATTRIB_NPTH);land=next(p for p in group if p.GetAttribute()==k.PAD_ATTRIB_SMD)
   assert land.GetNumber()==pin and k.ToMM(hole.GetDrillSize().x)==2
   fp.Remove(hole);land.SetAttribute(k.PAD_ATTRIB_PTH);land.SetDrillSize(k.VECTOR2I(k.FromMM(2),k.FromMM(2)))
   layers=k.LSET()
   for layer in ([k.F_Cu,k.B_Cu,k.F_Mask,k.B_Mask] if variant=='REMOVE_UNUSED_FRONT' else [k.B_Cu,k.F_Mask,k.B_Mask]):layers.AddLayer(layer)
   land.SetLayerSet(layers)
   if variant=='REMOVE_UNUSED_FRONT':land.SetRemoveUnconnected(True);land.SetKeepTopBottom(False)
  board.BuildConnectivity()
  dest=outdir/(variant+'.kicad_pcb');assert k.SaveBoard(str(dest),board)
  shutil.copy2(A/'ecad/wp10_c203_terminal.kicad_pro',dest.with_suffix('.kicad_pro'))
  board=k.LoadBoard(str(dest));board.BuildConnectivity();pads=[]
  for f in board.GetFootprints():
   for p in f.Pads():
    if not p.GetNumber():continue
    detail=dict(number=p.GetNumber(),xy_mm=[k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y)],attribute=int(p.GetAttribute()),drill_mm=k.ToMM(p.GetDrillSize().x),remove_unconnected=p.GetRemoveUnconnected(),keep_top_bottom=p.GetKeepTopBottom(),net=p.GetNetname(),layers={})
    for name,layer in [('F.Cu',k.F_Cu),('B.Cu',k.B_Cu),('F.Mask',k.F_Mask),('B.Mask',k.B_Mask)]:
     shape=p.GetEffectiveShape(layer);bb=shape.BBox()
     detail['layers'][name]=dict(declared_on_layer=p.IsOnLayer(layer),flash=p.FlashLayer(layer),effective_shape_bbox_size_mm=[k.ToMM(bb.GetWidth()),k.ToMM(bb.GetHeight())])
    pads.append(detail)
  drc=outdir/(variant+'_DRC.json')
  command=[str(CLI),'pcb','drc','--format','json','--severity-all','--exit-code-violations','-o',str(drc),str(dest)]
  q=subprocess.run(command,cwd=A,capture_output=True,text=True,encoding='utf-8');assert q.returncode in [0,5],q.stderr
  report=json.loads(drc.read_text())
  records.append(dict(variant=variant,board=dest.relative_to(A).as_posix(),board_sha256=sha(dest),pads=pads,DRC=drc.relative_to(A).as_posix(),DRC_sha256=sha(drc),violation_count=len(report['violations']),violations_by_type=dict(collections.Counter(v['type'] for v in report['violations'])),unconnected_items=len(report['unconnected_items']),ignored_checks=report['ignored_checks'],command=command,returncode=q.returncode))
  print(json.dumps(dict(variant=variant,violations=len(report['violations']),types=records[-1]['violations_by_type'],pads=pads)),flush=True)
 assert sha(source)==before
 result=dict(schema='WP10_C203_CAP_PADSTACK_PROBE_V20',KiCad_version=k.GetBuildVersion(),source=source.relative_to(A).as_posix(),source_sha256=before,active_board_unchanged=True,variants=records,design_candidate_selected=False,manufacturing_release=False,whole_design_complete=False,probe_code_sha256=sha(__file__))
 (A/'results/CAP_PADSTACK_PROBE_V20.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
