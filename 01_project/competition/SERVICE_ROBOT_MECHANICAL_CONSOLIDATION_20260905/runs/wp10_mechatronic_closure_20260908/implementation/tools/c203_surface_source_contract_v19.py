"""Pure extraction of the supported C203 PCB primitives; no native imports."""
from pathlib import Path
import json
from erc_source_contract import parse,children,val,properties
from c203_cam_contract_v20 import current
A=Path(__file__).resolve().parents[1]
def xy(n,key='at'):return [float(v) for v in children(n,key)[0][1:3]]
def canonical(items):return sorted(json.dumps(x,sort_keys=True) for x in items)
def walk(n):
 if isinstance(n,list):
  yield n
  for q in n:yield from walk(q)
def extract():
 cam,native,_=current()
 d=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text())
 assert d['board']=='ecad/wp10_c203_terminal.kicad_pcb','Definition and native CAM source differ'
 tree=parse((A/d['board']).read_text());origin=d['pcb_origin_xy_mm']
 assert not any(children(tree,k) for k in ['zone','via','arc'])
 for n in walk(tree):
  if not n:continue
  if n[0] in ['solder_mask_margin','pad_to_mask_clearance','solder_mask_min_width']:
   assert len(n)==2 and float(n[1])==0,'Nonzero mask override is unsupported'
  if str(n[0]).startswith(('gr_','fp_')) and children(n,'layer'):
   assert val(children(n,'layer')[0][1]) not in ['F.Cu','B.Cu','F.Mask','B.Mask'],'Unsupported graphic material primitive'
 stack=children(children(tree,'setup')[0],'stackup')[0]
 layers={val(q[1]):float(children(q,'thickness')[0][1]) for q in children(stack,'layer') if children(q,'thickness')}
 pads=[];holes=[]
 for fp in children(tree,'footprint'):
  at=children(fp,'at')[0];assert len(at)==3 or float(at[3])==0
  pos=xy(fp)
  assert val(children(fp,'layer')[0][1])=='F.Cu'
  for p in children(fp,'pad'):
   at=children(p,'at')[0];assert len(at)==3 or float(at[3])==0
   size=[float(x) for x in children(p,'size')[0][1:3]];assert p[3]=='circle' and size[0]==size[1]>0
   local=[xy(p)[i]+pos[i]-origin[i] for i in [0,1]]
   item=dict(ref=properties(fp)['Reference'],pin=val(p[1]),type=p[2],local_xy_mm=local,diameter_mm=size[0],layers=[val(x) for x in children(p,'layers')[0][1:]])
   matches=[q for q in native['pads'] if q['ref']==item['ref'] and q['number']==item['pin'] and q['xy_mm']==[local[i]+origin[i] for i in [0,1]]]
   assert len(matches)==1
   resolved=matches[0]
   item['declared_layers']=item['layers']
   item['remove_unused_layers']=children(p,'remove_unused_layers')==[['remove_unused_layers','yes']]
   item['keep_end_layers']=children(p,'keep_end_layers')==[['keep_end_layers','yes']]
   assert item['remove_unused_layers']==resolved['remove_unconnected'] and item['keep_end_layers']==resolved['keep_top_bottom']
   item['layers']=resolved['copper_layers'][:]
   for mask in ['F.Mask','B.Mask']:
    apertures=[q for q in cam[mask]['flashes'] if q['xy_mm']==resolved['xy_mm']]
    assert len(apertures)==1 and apertures[0]['diameter_mm']==item['diameter_mm']
    item['layers'].append(mask)
   assert p[2] in ['np_thru_hole','thru_hole','smd'] and not children(p,'padstack') and not children(p,'primitives')
   if p[2]=='np_thru_hole':assert not item['pin']
   drill=children(p,'drill')
   if drill:
    assert len(drill[0])==2 and float(drill[0][1])>0
    item['finished_drill_mm']=float(drill[0][1])
    holes.append(dict(local_xy_mm=local,finished_drill_mm=item['finished_drill_mm'],type=p[2]))
   pads.append(item)
 tracks=[]
 for t in children(tree,'segment'):
  assert val(children(t,'layer')[0][1])=='B.Cu'
  tracks.append(dict(start_local_mm=[float(q)-origin[i] for i,q in enumerate(children(t,'start')[0][1:3])],end_local_mm=[float(q)-origin[i] for i,q in enumerate(children(t,'end')[0][1:3])],width_mm=float(children(t,'width')[0][1])))
 edges=[]
 for n in [x for x in tree[1:] if isinstance(x,list)]:
  if children(n,'layer') and val(children(n,'layer')[0][1])=='Edge.Cuts':
   assert n[0]=='gr_line','Only rectangular straight board outline is supported'
   edges.append(tuple(sorted([tuple(xy(n,k)[i]-origin[i] for i in [0,1]) for k in ['start','end']])))
 assert len(edges)==4
 pts={q for e in edges for q in e};xs=sorted({p[0] for p in pts});ys=sorted({p[1] for p in pts})
 assert len(xs)==len(ys)==2 and pts=={(x,y) for x in xs for y in ys}
 expected={tuple(sorted(e)) for e in [((xs[0],ys[0]),(xs[1],ys[0])),((xs[1],ys[0]),(xs[1],ys[1])),((xs[1],ys[1]),(xs[0],ys[1])),((xs[0],ys[1]),(xs[0],ys[0]))]}
 assert set(edges)==expected
 assert len(pads)==8 and len(holes)==8 and len(tracks)==6
 assert sum(p['type']=='thru_hole' for p in pads)==4 and sum(p['type']=='np_thru_hole' for p in pads)==4
 return dict(layers_mm=layers,pads=pads,holes=holes,back_tracks=tracks,board_y_mm=xs,board_z_mm=[-50-ys[1],-50-ys[0]],
  mount_holes_yz_mm=sorted([[p['local_xy_mm'][0],-50-p['local_xy_mm'][1]] for p in pads if p['ref']=='H_C203']))
def validate_profile(c):
 expected=extract()
 for key,value in expected.items():
  assert (canonical(c[key])==canonical(value) if key in ['pads','holes','back_tracks'] else sorted(c[key])==sorted(value) if key=='mount_holes_yz_mm' else c[key]==value),'Native PCB/profile mismatch: '+key
 return True
