"""Activate separately probed no-front-land CAP PTH in the same board and libraries."""
from pathlib import Path
import json,hashlib,copy,shutil,datetime,re
from erc_source_contract import parse,enc,children,val,properties
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V19_before_CAP_PTH'
N='C203_SingleFace_Terminal_D30_P10_W18'
TARGET={(-5.,0.):'1',(5.,0.):'2'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def xy(p):return tuple(float(v) for v in children(p,'at')[0][1:3])
def edit(fp):
 old=copy.deepcopy(fp)
 for pos,pin in TARGET.items():
  group=[p for p in children(fp,'pad') if xy(p)==pos];assert len(group)==2
  h=next(p for p in group if p[2]=='np_thru_hole');p=next(p for p in group if p[2]=='smd')
  assert children(h,'drill')[0]==['drill','2'] and val(p[1])==pin
  fp.remove(h);p[2]='thru_hole';p.insert(5,['drill','2'])
  children(p,'layers')[0][:]=['layers','"*.Cu"','"*.Mask"']
  p.extend([['remove_unused_layers','yes'],['keep_end_layers','no']])
 assert [p for p in children(old,'pad') if xy(p) not in TARGET]==[p for p in children(fp,'pad') if xy(p) not in TARGET]
 children(fp,'descr')[0][1]=json.dumps('C203 V20: four electrical PTH. CAP +/- use 2mm holes with B.Cu land only in the connected board (remove unused layers, keep end layers no). WIRE PTH unchanged. CAP front mask opening3.5mm verified by KiCad10.0.6 CAM probe; landless barrel, solder and fabrication qualification remain open.')
def main():
 assert not H.exists()
 probe=json.loads((A/'results/CAP_PADSTACK_PROBE_V20.json').read_text())
 assert probe['KiCad_version']=='10.0.6' and probe['active_board_unchanged']
 paths=set()
 for folder in ['power','mechanical','results','tools','thermal','review']:
  for p in (A/folder).iterdir():
   if p.is_file() and re.search('cap|c203',p.name,re.I):paths.add(p.relative_to(A).as_posix())
 paths.update(['ecad/wp10_c203_terminal.kicad_pcb','ecad/wp10_c203_terminal.kicad_pro',f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod',f'power/cap_terminal_sources/{N}.kicad_mod','WORKING_V19.md','WORKING_V19.html','docs/hardware/CAP_HARNESS_BRIEF_V19.md'])
 for rel in sorted(paths):
  dest=H/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/rel,dest)
 dump(H/'ARCHIVE_SHA256.json',{p:sha(H/p) for p in sorted(paths)})
 boardpath=A/'ecad/wp10_c203_terminal.kicad_pcb';board=parse(boardpath.read_text());old=copy.deepcopy(board)
 fp=next(f for f in children(board,'footprint') if properties(f).get('Reference')=='C203');edit(fp)
 for tag in ['segment','arc','zone','general','gr_line','setup']:assert children(old,tag)==children(board,tag),tag
 for path in [f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod',f'power/cap_terminal_sources/{N}.kicad_mod']:
  fp=parse((A/path).read_text());edit(fp);(A/path).write_text(enc(fp)+'\n',encoding='utf-8')
 for t in children(board,'gr_text'):
  if 'V17 SINGLE PRINTED COPPER FACE' in val(t[1]):t[1]=json.dumps('V20 CAP PTH / FRONT LANDS REMOVED BY CONNECTIVITY\nC203 CAPACITOR BRANCH ONLY\nCAM REVIEW ONLY / NO MANUFACTURING RELEASE')
 boardpath.write_text(enc(board)+'\n',encoding='utf-8')
 d=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text())
 for t in d['terminal_features']:
  if t['id'].startswith('CAP_'):t.update(drill_type='PTH',front_pad_outer_D_mm=0,back_pad_outer_D_mm=3.5,front_mask_opening_D_mm=3.5,back_mask_opening_D_mm=3.5,remove_unused_layers=True,keep_end_layers=False,finished_hole_tolerance_mm=None,barrel_plating_min_mm=None)
 d.update(schema='WP10_C203_TERMINAL_DEFINITION_V20_CAP_PTH',manufacturing_definition='All four electrical holes PTH: CAP2mm and WIRE1.8mm; four3.4mm mounting NPTH. CAP has no F.Cu land, B.Cu3.5mm land and both mask openings3.5mm. Conditional pad flashing depends on actual B-only tracks. Plating, finished-hole tolerance, solder wicking and laminate/process remain unqualified.',DRC_current_revision_executed=False,DRC_local_process_issues_open=True,surface_profile_native_verified=False,finished_copper_thickness_native_bound=False,whole_design_complete=False)
 dump(A/'power/CAP_TERMINAL_DEFINITION.json',d)
 m=json.loads((A/'mechanical/INPUT_CAP_MOUNT_DESIGN.json').read_text())
 m['source_files'].update({q:sha(A/q) for q in ['power/CAP_TERMINAL_DEFINITION.json',f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod']})
 m['materials']['pcb']='FR4 nominal surface candidate, electrical4PTH/mount4NPTH. CAP front lands removed; actual CAM front mask3.5mm. Barrel and tolerances unqualified.'
 dump(A/'mechanical/INPUT_CAP_MOUNT_DESIGN.json',m)
 paths=['ecad/wp10_c203_terminal.kicad_pcb',f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod',f'power/cap_terminal_sources/{N}.kicad_mod','power/CAP_TERMINAL_DEFINITION.json','mechanical/INPUT_CAP_MOUNT_DESIGN.json']
 dump(A/'results/CAP_PTH_SOURCE_CHANGE_V20.json',dict(status='ACTIVE_SOURCE_CHANGED__NATIVE_AND_CAD_REBIND_PENDING',source_files={p:sha(A/p) for p in paths},archived_files=len(paths),history=H.relative_to(A).as_posix(),active_source_changed=True,CAP_holes_plated=True,actual_active_DRC_errors=None,manufacturing_release=False,whole_design_complete=False))
 print('Same active PCB and both footprint sources changed:4PTH/4NPTH; native and surface rebinding required')
if __name__=='__main__':main()
