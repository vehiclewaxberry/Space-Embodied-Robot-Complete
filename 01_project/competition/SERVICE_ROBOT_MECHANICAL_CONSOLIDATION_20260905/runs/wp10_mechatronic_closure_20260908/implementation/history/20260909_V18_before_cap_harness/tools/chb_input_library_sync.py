"""Repair library/placed footprint type mismatch without editing PCB copper."""
from pathlib import Path
import pcbnew as k,json,hashlib
A=Path(__file__).resolve().parents[1];L=A/'ecad/WP10_PASSIVES.pretty';N='CHB_Input_124_Terminal_V18';P=L/(N+'.kicad_mod');B=A/'ecad/wp10_chb_input.kicad_pcb'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def geometry(f):return sorted((p.GetNumber(),p.GetPosition().x,p.GetPosition().y,p.GetSize().x,p.GetSize().y,p.GetDrillSize().x,p.GetDrillSize().y,int(p.GetAttribute()),p.GetLayerSet().FmtHex()) for p in f.Pads())
io=k.PCB_IO_KICAD_SEXPR();f=io.FootprintLoad(str(L),N);before=sha(P);board_before=sha(B);before_geometry=geometry(f);before_type=f.GetAttributes()
f.SetAttributes(k.FP_THROUGH_HOLE);io.FootprintSave(str(L),f);f=io.FootprintLoad(str(L),N)
assert geometry(f)==before_geometry and sha(B)==board_before
out=dict(library_before_sha256=before,library_after_sha256=sha(P),before_attributes=int(before_type),after_attributes=int(f.GetAttributes()),geometry_unchanged=True,board_unchanged=True,board_sha256=sha(B),note='MCP footprint generator omitted through-hole placement type; native supported library API sets the same type already on U203. No DRC severity/exclusion changed.')
(A/'results/CHB_INPUT_LIBRARY_SYNC_V18.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
