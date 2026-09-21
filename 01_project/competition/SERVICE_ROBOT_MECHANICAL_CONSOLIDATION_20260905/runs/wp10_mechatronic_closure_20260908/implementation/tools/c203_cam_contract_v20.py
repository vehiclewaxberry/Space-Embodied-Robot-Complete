"""Strict reader for the native C203 circular-flash/straight-track CAM subset."""
from pathlib import Path
import re,json,hashlib,copy
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def role(text,key):
 lines=text.splitlines()
 if key in ['PTH','NPTH']:
  actual=[s for s in lines if 'TF.FileFunction,' in s]
  expected='; #@! TF.FileFunction,'+('Plated,1,2,PTH' if key=='PTH' else 'NonPlated,1,2,NPTH')
  assert actual==[expected],'Drill FileFunction mismatch or ambiguity'
 else:
  fn={'F.Cu':'Copper,L1,Top','B.Cu':'Copper,L2,Bot','F.Mask':'Soldermask,Top','B.Mask':'Soldermask,Bot'}[key]
  assert [s for s in lines if s.startswith('%TF.FileFunction,')]==['%TF.FileFunction,'+fn+'*%']
  assert [s for s in lines if s.startswith('%TF.FilePolarity,')]==['%TF.FilePolarity,'+('Negative' if key.endswith('Mask') else 'Positive')+'*%']
 return True
def gerber(text):
 assert '%FSLAX46Y46*%' in text and '%MOMM*%' in text and '%LPD*%' in text
 lines=[line for line in text.splitlines() if line]
 assert lines[-1]=='M02*' and lines.count('M02*')==1,'Missing or premature Gerber termination'
 tools={};tool=None;point=None;net=None;flashes=[];tracks=[]
 for line in text.splitlines():
  if not line:continue
  m=re.fullmatch(r'%ADD(\d+)C,([\d.]+)\*%',line)
  if m:tools[m[1]]=float(m[2]);continue
  m=re.fullmatch(r'D(\d+)\*',line)
  if m:tool=m[1];assert tool in tools;continue
  m=re.fullmatch(r'%TO.N,([^*]+)\*%',line)
  if m:net=m[1];continue
  if line=='%TD*%':net=None;continue
  m=re.fullmatch(r'X(-?\d+)Y(-?\d+)D0([123])\*',line)
  if m:
   assert tool in tools
   q=[int(m[1])/1e6,-int(m[2])/1e6];mode=m[3]
   if mode=='3':flashes.append(dict(xy_mm=q,diameter_mm=tools[tool],net=net))
   if mode=='1':
    assert point is not None
    tracks.append(dict(start_mm=point,end_mm=q,width_mm=tools[tool],net=net))
   point=q;continue
  assert line in ['%FSLAX46Y46*%','%MOMM*%','%LPD*%','G01*','M02*'] or line.startswith(('G04 ','%TF.','%TA.','%TO.P,','%TO.C,')), 'Unsupported CAM command: '+line
 return dict(flashes=flashes,tracks=tracks)
def drill(text):
 assert '\nMETRIC\n' in text and '\nG90\n' in text
 lines=[line for line in text.splitlines() if line]
 assert lines[0]=='M48' and lines[-1]=='M30' and lines.count('M30')==1,'Missing or premature drill termination'
 kind='PTH' if 'TF.FileFunction,Plated,' in text else 'NPTH' if 'TF.FileFunction,NonPlated,' in text else None
 assert kind
 tools={};tool=None;holes=[]
 for line in text.splitlines():
  m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
  if m:tools[m[1]]=float(m[2]);continue
  m=re.fullmatch(r'T(\d+)',line)
  if m:tool=m[1];assert tool in tools;continue
  m=re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
  if m:
   assert tool in tools
   holes.append(dict(xy_mm=[float(m[1]),-float(m[2])],diameter_mm=tools[tool]));continue
  assert not line or line.startswith(';') or line in ['M48','FMAT,2','METRIC','%','G90','G05','M30'],line
 return dict(kind=kind,holes=holes)
def canonical(rows):return sorted(json.dumps(x,sort_keys=True) for x in rows)
def validate_manifest(manifest):
 root=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file())
 cli=root/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
 source=A/'ecad/wp10_c203_terminal.kicad_pcb';out=A/'results/CAP_CAM_ACTIVE_V20'
 required={f'results/CAP_CAM_ACTIVE_V20/wp10_c203_terminal{x}' for x in ['-F_Cu.gtl','-B_Cu.gbl','-F_Mask.gts','-B_Mask.gbs','-PTH.drl','-NPTH.drl']}
 required.add('results/CAP_CAM_ACTIVE_V20/commands.json')
 assert required<=set(manifest['files']),'Incomplete native CAM file manifest'
 assert all((A/p).resolve().is_relative_to(out.resolve()) for p in manifest['files'])
 expected=[[str(cli),'pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask','--output',str(out)+'/',str(source)],
 [str(cli),'pcb','export','drill','--format','excellon','--excellon-separate-th','--output',str(out)+'/',str(source)]]
 assert len(manifest['commands'])==2 and [c['command'] for c in manifest['commands']]==expected
 assert all(c['returncode']==0 for c in manifest['commands'])
 assert manifest['commands']==read('results/CAP_CAM_ACTIVE_V20/commands.json')
 assert manifest['source']=='ecad/wp10_c203_terminal.kicad_pcb'
 return True
def validate(data,g):
 assert len(g['pads'])==8 and len(g['tracks'])==6 and not g['zone_count'] and not g['copper_drawing_count']
 for side in ['F','B']:
  expected=[dict(xy_mm=p['xy_mm'],diameter_mm=p['size_mm'][0],net=p['net']) for p in g['pads'] if p['number'] and side+'.Cu' in p['copper_layers']]
  assert canonical(data[side+'.Cu']['flashes'])==canonical(expected),side+' copper pads'
  expected=[{k:t[k] for k in ['start_mm','end_mm','width_mm','net']} for t in g['tracks'] if t['layer']==side+'.Cu']
  assert canonical(data[side+'.Cu']['tracks'])==canonical(expected),side+' copper tracks'
  expected=[dict(xy_mm=p['xy_mm'],diameter_mm=p['size_mm'][0],net=None) for p in g['pads']]
  assert canonical(data[side+'.Mask']['flashes'])==canonical(expected) and not data[side+'.Mask']['tracks'],side+' mask apertures'
 for kind in ['PTH','NPTH']:
  expected=[dict(xy_mm=p['xy_mm'],diameter_mm=p['drill_mm'][0]) for p in g['pads'] if p['type']==g['pad_type_values'][kind]]
  assert len(expected)==4 and data[kind]['kind']==kind and canonical(data[kind]['holes'])==canonical(expected),kind+' drill class'
 cap=[p for p in g['pads'] if p['xy_mm'] in [[95,100],[105,100]]]
 assert len(cap)==2 and all(p['copper_layers']==['B.Cu'] and p['remove_unconnected'] and not p['keep_top_bottom'] and p['drill_mm']==[2,2] for p in cap)
 assert len(data['F.Cu']['flashes'])==2 and len(data['B.Cu']['flashes'])==4
 return True
def current():
 manifest=read('results/CAP_CAM_ACTIVE_V20.json');g=read('results/CAP_TERMINAL_NATIVE_GEOMETRY.json')
 validate_manifest(manifest)
 assert g['native_C203_binding_sha256']==sha('results/CAP_TERMINAL_NATIVE_BINDING.json')
 assert manifest['mode']=='active' and manifest['source_sha256']==sha(manifest['source'])==g['board_sha256']
 assert g['extractor_sha256']==sha('tools/cap_terminal_native.py')
 assert all(sha(p)==h for p,h in manifest['files'].items())
 assert all(c['returncode']==0 for c in manifest['commands'])
 data={};base='results/CAP_CAM_ACTIVE_V20/wp10_c203_terminal'
 for key,suffix in [('F.Cu','-F_Cu.gtl'),('B.Cu','-B_Cu.gbl'),('F.Mask','-F_Mask.gts'),('B.Mask','-B_Mask.gbs')]:
  text=(A/(base+suffix)).read_text();role(text,key)
  data[key]=gerber(text)
 for key in ['PTH','NPTH']:
  text=(A/(base+'-'+key+'.drl')).read_text();role(text,key);data[key]=drill(text)
 validate(data,g);return data,g,manifest
def main():
 data,g,m=current();faults=[]
 def reject(name,mutation):
  q=copy.deepcopy(data);mutation(q)
  try:validate(q,g)
  except AssertionError:faults.append(dict(name=name,rejected=True));return
  raise AssertionError(name)
 reject('CAP_front_copper_restored',lambda q:q['F.Cu']['flashes'].append(dict(xy_mm=[95,100],diameter_mm=3.5,net='WP10_PRECHARGED_PLUS')))
 reject('CAP_front_mask_aperture_closed',lambda q:q['F.Mask']['flashes'].__setitem__(5,dict(xy_mm=[95,100],diameter_mm=2,net=None)))
 reject('CAP_nonplated_drill_class',lambda q:q['PTH'].update(kind='NPTH'))
 reject('wrong_finished_hole',lambda q:q['PTH']['holes'][2].update(diameter_mm=1.8))
 reject('back_trace_removed',lambda q:q['B.Cu']['tracks'].pop())
 reject('polarity_swapped',lambda q:q['B.Cu']['flashes'][0].update(net='WP10_INPUT_RETURN'))
 def reject_call(name,fn):
  try:fn()
  except AssertionError:faults.append(dict(name=name,rejected=True));return
  raise AssertionError(name)
 gt=(A/'results/CAP_CAM_ACTIVE_V20/wp10_c203_terminal-F_Cu.gtl').read_text()
 dt=(A/'results/CAP_CAM_ACTIVE_V20/wp10_c203_terminal-PTH.drl').read_text()
 reject_call('premature_Gerber_end',lambda:gerber(gt.replace('G01*','M02*\nG01*')))
 reject_call('missing_Gerber_end',lambda:gerber(gt.replace('M02*','')))
 reject_call('premature_drill_end',lambda:drill(dt.replace('G05','M30\nG05')))
 reject_call('missing_drill_end',lambda:drill(dt.replace('M30','')))
 bad=copy.deepcopy(m);bad['files']={};reject_call('empty_CAM_manifest',lambda:validate_manifest(bad))
 bad=copy.deepcopy(m);bad['commands']=[];reject_call('empty_export_commands',lambda:validate_manifest(bad))
 bad=copy.deepcopy(m);bad['commands'][0]['command'][-1]='other.kicad_pcb';reject_call('wrong_export_source',lambda:validate_manifest(bad))
 mask=(A/'results/CAP_CAM_ACTIVE_V20/wp10_c203_terminal-F_Mask.gts').read_text()
 reject_call('mask_file_falsely_declared_copper',lambda:role(mask.replace('Soldermask,Top','Copper,L1,Top'),'F.Mask'))
 reject_call('contradictory_mask_polarity',lambda:role(mask+'\n%TF.FilePolarity,Positive*%\n','F.Mask'))
 reject_call('contradictory_drill_role',lambda:role(dt+'\n; #@! TF.FileFunction,NonPlated,1,2,NPTH\n','PTH'))
 inputs=['tools/c203_cam_contract_v20.py','tools/cap_terminal_native.py','results/CAP_CAM_ACTIVE_V20.json','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_TERMINAL_NATIVE_BINDING.json',m['source'],*m['files']]
 out=dict(schema='C203_NATIVE_CAM_CHECK_V20',passed=True,data=data,faults=faults,inputs={p:sha(p) for p in inputs},scope='Native CAM agrees with effective copper and four PTH/four NPTH; no fabrication or process qualification',manufacturing_release=False,whole_design_complete=False)
 (A/'results/C203_CAM_CHECK_V20.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print('Native CAM verified; '+str(len(faults))+' material/net/drill/termination/manifest counterexamples rejected')
if __name__=='__main__':main()
