"""Only planned source deltas: four source-bound terminals and one diode relocation."""
from pathlib import Path
import json,hashlib,copy
from erc_source_contract import parse,enc,children,properties,val
A=Path(__file__).resolve().parents[1];H=A/'history/20260910_V29_before_terminals'
FP='WP10_TERMINALS:MP_Wurth_WP-THRSH_74651195R'
ROWS=[('J204','PORT_BAT_PLUS',(7,15),'WP10_BAT_PROTECTED_PLUS'),('J205','PORT_BAT_RETURN',(7,28),'WP10_INPUT_RETURN'),('J206','PORT_CHB_PLUS',(93,15),'WP10_PRECHARGED_PLUS'),('J207','PORT_CHB_RETURN',(93,28),'WP10_INPUT_RETURN')]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def normalize_instances():
 p=A/'ecad/wp10_power_1.kicad_sch';t=parse(p.read_text());syms={properties(s)['Reference']:s for s in children(t,'symbol')}
 template=children(syms['J200'],'instances')[0];records=[]
 for ref,_,_,_ in ROWS:
  s=syms[ref];old=children(s,'instances')[0];new=copy.deepcopy(template)
  for project in children(new,'project'):
   for path in children(project,'path'):children(path,'reference')[0][1]=json.dumps(ref)
  records.append(dict(reference=ref,old=old,new=new));s[s.index(old)]=new
 p.write_text(enc(t)+'\n',encoding='utf-8');dump(A/'results/TERMINAL_INSTANCE_REPAIR_V29.json',records)
 # The MCP selected another .kicad_pro in a multi-project directory. Only the
 # four new instance paths are corrected to the actual root hierarchy.
def prepare_board_ast():
 p=H/'ecad/wp10_main_input.kicad_pcb';t=parse(p.read_text());ports={r[1] for r in ROWS};out=[];changes=[]
 for n in t:
  if not isinstance(n,list):out.append(n);continue
  if n[0]=='footprint':
   ref=properties(n)['Reference']
   if ref in ports:changes.append(dict(removed_port=ref));continue
   if ref=='D202':
    at=children(n,'at')[0];assert [float(x) for x in at[1:3]]==[84,25];at[1]='82';changes.append(dict(ref=ref,from_mm=[84,25],to_mm=[82,25]))
   if ref=='F201':
    at=children(n,'at')[0];assert [float(x) for x in at[1:3]]==[18,15];at[1]='20';changes.append(dict(ref=ref,from_mm=[18,15],to_mm=[20,15]))
  if n[0]=='segment':
   net=val(children(n,'net')[0][-1]);layer=val(children(n,'layer')[0][1]);w=float(children(n,'width')[0][1]);s=children(n,'start')[0];e=children(n,'end')[0];xy=lambda v:tuple(float(x) for x in v[1:3])
   if net in ['WP10_BAT_PROTECTED_PLUS','WP10_MAIN_FUSED'] and layer=='F.Cu':
    for v in (s,e):
     if xy(v) in [(13.325,15),(22.675,15)]:v[1]=str(float(v[1])+2)
   if net=='WP10_INPUT_RETURN' and layer=='B.Cu' and w==8:
    for v in (s,e):
     if float(v[1]) in [17,83]:v[1]=str(18 if float(v[1])==17 else 82)
   if net=='WP10_PRECHARGED_PLUS' and layer=='F.Cu' and w==1.5 and (xy(s),xy(e)) in [((86.11,25),(88,25)),((88,25),(88,17)),((88,17),(93,15))]:
    changes.append(dict(removed_old_D202_clamp=[xy(s),xy(e)]));continue
   if net=='WP10_INPUT_RETURN' and layer=='F.Cu' and w==1.5 and (xy(s),xy(e))==((81.89,25),(81.89,29)):
    changes.append(dict(removed_old_D202_return=[xy(s),xy(e)]));continue
  out.append(n)
 dst=A/'ecad/wp10_main_input_v29_prepared.kicad_pcb';dst.write_text(enc(out)+'\n',encoding='utf-8')
 dump(A/'results/TERMINAL_PLANNED_DELTA_V29.json',dict(parent_sha256=sha(p),changes=changes,return_corridor_delta_x_mm={'left':1,'right':-1},qualified=False))
if __name__=='__main__':normalize_instances();prepare_board_ast()
