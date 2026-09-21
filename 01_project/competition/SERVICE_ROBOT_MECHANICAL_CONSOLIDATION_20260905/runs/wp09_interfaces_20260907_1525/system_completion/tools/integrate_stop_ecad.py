"""Versioned system wiring + actual stop subpage. No frozen source mutation."""
from pathlib import Path
import ast,csv,json,re,uuid,hashlib,collections,shutil,subprocess,os
C=Path(__file__).resolve().parents[1];N=C.parent/'reuse_closure';E=C/'ecad';S=C/'electrical_delta'
E.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def q(s):return json.dumps(str(s),ensure_ascii=False)
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp09-resume-system:'+s))
def parse(text):
    toks=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text)
    stack=[];root=None
    for t in toks:
        if t=='(':
            a=[]
            if stack:stack[-1].append(a)
            stack.append(a)
        elif t==')':
            a=stack.pop()
            if not stack:root=a
        else:stack[-1].append(t)
    assert not stack
    return root
def enc(n):return '('+' '.join(enc(x) if isinstance(x,list) else x for x in n)+')'
def val(x):return json.loads(x) if x.startswith('"') else x
def children(n,key):return [x for x in n if isinstance(x,list) and x and x[0]==key]
def walk(n):
    yield n
    for x in n:
        if isinstance(x,list):yield from walk(x)

parent_rows=list(csv.DictReader((N/'ecad/MASTER_FROM_TO.csv').open(encoding='utf-8-sig')))
rows=[dict(x) for x in parent_rows]
changes={'K1_COILP':('STOPBOARD.J104.1','K1.X1(+)','COIL24'),
 'K1_COILR':('K1.X2(-)','STOPBOARD.J104.2','COIL_SWITCHED_RETURN'),
 'K1_FB1':('K1.T1','STOPBOARD.J105.2','AUX_RETURN'),
 'K1_FB2':('STOPBOARD.J105.1','K1.T2','AUX_FEED')}
lineage=[]
for r in rows:
    before=dict(r)
    if r['wire_id'] in changes:
        r['from_endpoint'],r['to_endpoint'],r['signal']=changes[r['wire_id']]
        r['status']='ACTUAL_STOP_SUBPAGE_TERMINAL_ASSIGNMENT; connector_MPN_and_harness_unbound'
        r['source']+='; electrical_delta/STOP_PIN_NET_MAP.csv'
    lineage.append({'wire_id':r['wire_id'],'change':'STOP_BOUNDARY_REPLACED' if before!=r else 'UNCHANGED','old_from':before['from_endpoint'],'old_to':before['to_endpoint'],'new_from':r['from_endpoint'],'new_to':r['to_endpoint']})
for k,a,b,sig in [('SC_PWR24','Q1.2','STOPBOARD.J101.3','STOP_UPSTREAM_24V'),('SC_RET','PS1.TB2.1','STOPBOARD.J101.4','STOP_GND')]:
    r={k:'' for k in rows[0]};r.update(wire_id=k,from_endpoint=a,to_endpoint=b,signal=sig,wire_or_mate='New GSE branch; physical protection/terminal/wire sizing not released',status='DESIGN_CONNECTION_TO_UPSTREAM_PROTECTED_SOURCE; total_Q1_budget_open',source='N MASTER_FROM_TO A02/A04; stop J101 local pin contract',build_approved='False',physical_test='NOT_EXECUTED');rows.append(r)
    lineage.append({'wire_id':k,'change':'ADDED_GSE_CONTROL_SOURCE_BRANCH','old_from':'','old_to':'','new_from':a,'new_to':b})
pinrows=list(csv.DictReader((S/'STOP_PIN_NET_MAP.csv').open(encoding='utf-8-sig')))
pins={r['reference']+'.'+r['pin']:r for r in pinrows}
assert all(p in pins for p in ['J104.1','J104.2','J105.1','J105.2','J101.3','J101.4'])
internal=[]
for r in csv.DictReader((S/'STOP_FROM_TO_DELTA.csv').open(encoding='utf-8-sig')):
    internal.append({'from_endpoint':'STOPBOARD.'+r['from_endpoint'],'to_endpoint':'STOPBOARD.'+r['to_endpoint']})
# Reuse only pure source definitions from the proven parent generator. Its top-level
# writes/imports are never executed; E points only to the new child directory.
tree=ast.parse((N/'tools/build_ecad.py').read_text(encoding='utf-8'))
defs=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in ['DSU','graph','pin_type','symbol_def','schematic']]
scope={'__name__':'wp09_derived_ecad','E':E,'uid':uid,'q':q,'dump':dump,'collections':collections}
exec(compile(ast.Module(body=defs,type_ignores=[]),'parent_pure_ecad_definitions','exec'),scope)
all_nets=scope['graph'](rows+internal)
external_eps=sorted({r[k] for r in rows for k in ['from_endpoint','to_endpoint']})
nets={k:all_nets[k] for k in external_eps}
modules=collections.OrderedDict()
for ep in external_eps:
    dev,pin=ep.split('.',1);modules.setdefault(dev,[]).append(pin)
mapping=scope['schematic']('wp09_system',modules,nets,'WP09 actual stop subpage integration; GSE branch; flight energy/propulsion unbound','A2')
root_path=E/'wp09_system.kicad_sch';root=parse(root_path.read_text(encoding='utf-8'))
rootid=val(children(root,'uuid')[0][1]);sheetid=uid('STOP_DETAIL_SHEET')
child=parse((S/'wp09_stop_circuit.kicad_sch').read_text(encoding='utf-8'))
net_global={}
for ep in external_eps:
    if ep.startswith('STOPBOARD.'):
        sub=ep[len('STOPBOARD.'):];boardnet=pins[sub]['net'];g='SC_SYSTEM_'+nets[ep]
        assert boardnet not in net_global or net_global[boardnet]==g
        net_global[boardnet]=g
def globalize(tree,names):
    for x in walk(tree):
        if len(x)>1 and x[0]=='label' and val(x[1]) in names:
            x[0]='global_label';x[1]=q(names[val(x[1])]);x.insert(2,['shape','bidirectional'])
globalize(root,{x[len('SC_SYSTEM_'):]:x for x in net_global.values()})
globalize(child,net_global)
for sym in children(child,'symbol'):
    inst=children(sym,'instances')
    if inst:
        for project in children(inst[0],'project'):
            project[1]=q('wp09_system')
            for path in children(project,'path'):path[1]=q('/'+rootid+'/'+sheetid)
for si in children(child,'sheet_instances'):child.remove(si)
root.append(parse(f'(sheet (at 25.4 267.97) (size 160 20) (stroke (width 0) (type default)) (fill (color 0 0 0 0)) (uuid {q(sheetid)}) (property "Sheetname" "Actual watchdog and contactor driver" (at 25.4 266.97 0) (effects (font (size 1.27 1.27)) (justify left bottom))) (property "Sheetfile" "wp09_stop_detail.kicad_sch" (at 25.4 288.97 0) (effects (font (size 1.27 1.27)) (justify left top))) (instances (project "wp09_system" (path {q("/"+rootid)} (page "2")))))'))
root_path.write_text(enc(root),encoding='utf-8')
(E/'wp09_stop_detail.kicad_sch').write_text(enc(child),encoding='utf-8')
(E/'wp09_system.kicad_pro').write_text('{}',encoding='utf-8')
shutil.copy2(S/'WP09STOP.kicad_sym',E/'WP09STOP.kicad_sym')
(E/'sym-lib-table').write_text('(sym_lib_table (version 7) '+''.join(f'(lib (name "{l}") (type "KiCad") (uri "'+chr(36)+f'{{KIPRJMOD}}/{l}.kicad_sym") (options "") (descr "Versioned candidate source"))' for l in ['WP09','WP09STOP'])+')',encoding='utf-8')
csvout(E/'MASTER_FROM_TO.csv',rows);csvout(E/'MASTER_LINEAGE.csv',lineage)
dump(E/'SYSTEM_ENDPOINT_MAP.json',mapping)
dump(E/'STOP_INTEGRATION_BINDING.json',{'parent_master':{'path':str(N/'ecad/MASTER_FROM_TO.csv'),'sha256':sha(N/'ecad/MASTER_FROM_TO.csv')},'child_master_sha256':sha(E/'MASTER_FROM_TO.csv'),'child_subpage_source_sha256':sha(S/'wp09_stop_circuit.kicad_sch'),'child_pinmap_sha256':sha(S/'STOP_PIN_NET_MAP.csv'),'root_generator_source_sha256':sha(N/'tools/build_ecad.py'),'source_board_net_to_system_global_net':net_global,'old_wire_ids_preserved':70,'wiring_rows':len(rows),'board_internal_edges_separate_but_source_bound':len(internal),'no_wire_length_or_manufacturing_credit':True,'3V3_and_5V1_sources_bound':False,'whole_flight_power_closed':False})
print(json.dumps({'status':'SYSTEM_AND_ACTUAL_STOP_HIERARCHY_GENERATED_NOT_YET_VERIFIED','wiring_rows':len(rows),'subpage_parts':len(children(child,'symbol')),'globals':net_global}))
