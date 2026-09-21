from pathlib import Path
import shutil
from erc_source_contract import parse,enc,children,val
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V25_before_layout_clearance_fix';assert not H.exists();H.mkdir()
for rel in ['ecad/wp10_main_input.kicad_pcb','results/MAIN_INPUT_BOARD_DRC_V25.json','results/MAIN_INPUT_BOARD_COMMANDS_V25.json','power/MAIN_INPUT_BOARD_DEFINITION_V25.json']:
 dst=H/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/rel,dst)
# Move a verified generated candidate only; never delete a user board.
p=(A/'ecad/wp10_main_input.kicad_pcb').resolve();assert p.parent==(A/'ecad').resolve();p.unlink()
for name in ['SMBJ30A_A1K2','STPS3H100U_A1K2']:
 p=A/'ecad/WP10_INPUT.pretty'/(name+'.kicad_mod');tree=parse(p.read_text())
 for s in children(tree,'fp_line'):
  if val(children(s,'layer')[0][1])=='F.SilkS':
   s[s.index(children(s,'start')[0])]=['start','1.4','-2.25']
   s[s.index(children(s,'end')[0])]=['end','1.4','-2.85']
 p.write_text(enc(tree)+'\n',encoding='utf-8')
print('Original short/clearance evidence archived; prototype regenerated next')
