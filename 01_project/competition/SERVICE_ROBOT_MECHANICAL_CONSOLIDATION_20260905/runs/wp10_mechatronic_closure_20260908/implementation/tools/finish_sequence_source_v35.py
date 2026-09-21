"""Repair MCP hierarchy and presentation; preserve the V34 parent verbatim."""
from pathlib import Path
import json,uuid,math,copy
from erc_source_contract import parse,enc,children,val,properties,node_uuid
A=Path(__file__).resolve().parents[1]; D=A/'ecad/revisions/v35'; R=A/'results/aux_v35'
def uid():return json.dumps(str(uuid.uuid4()))
def at(n,x,y,angle=0):children(n,'at')[0][1:]=[str(round(x,5)),str(round(y,5)),str(angle)]
def prop(s,name,value,hidden=True):
    old=[p for p in children(s,'property') if val(p[1])==name]
    if old:old[0][2]=json.dumps(value);return
    s.append(['property',json.dumps(name),json.dumps(value),['at','0','0','0'],['effects',['font',['size','1','1']],*([['hide','yes']] if hidden else [])]])
def pin_xy(tree,ref,pn):
    s=next(s for s in children(tree,'symbol') if properties(s)['Reference']==ref)
    lib=next(s1 for lib in children(tree,'lib_symbols') for s1 in children(lib,'symbol') if val(s1[1])==val(children(s,'lib_id')[0][1]))
    p=next(p for sub in children(lib,'symbol') for p in children(sub,'pin') if val(children(p,'number')[0][1])==str(pn))
    x,y,ang=map(float,children(s,'at')[0][1:]);assert ang==0
    px,py=map(float,children(p,'at')[0][1:3]);return x+px,y-py
def main():
    rootp=D/'wp10_system.kicad_sch';root=parse(rootp.read_text(encoding='utf-8-sig'))
    sheet=next(s for s in children(root,'sheet') if 'wp10_aux_sequence.kicad_sch' in properties(s).values())
    for p in children(sheet,'property'):
        if val(p[1]) in ['Sheet name','Sheetname']:p[1]=json.dumps('Sheetname')
        if val(p[1]) in ['Sheet file','Sheetfile']:p[1]=json.dumps('Sheetfile')
    rootp.write_text(enc(root)+'\n',encoding='utf-8')
    p=D/'wp10_aux_sequence.kicad_sch';t=parse(p.read_text(encoding='utf-8-sig'));assert not children(t,'wire')
    refs={properties(s)['Reference']:s for s in children(t,'symbol')};assert len(refs)==13
    full='/'+node_uuid(root)+'/'+node_uuid(sheet)
    import main_board_selection_v25 as m
    selected={}
    for new,old in [('U209','U205'),('R229','R211'),('R230','R212'),('R231','R213'),('C219','C211'),('C220','C212')]:selected[new]=copy.deepcopy(m.PARTS[old])
    for ref,ohm,code in [('R225',200000,'200K'),('R226',10000,'10K0'),('R227',2000,'2K00')]:
        d=copy.deepcopy(m.PARTS['R212']);d.update(MPN='TNPW0603'+code+'BEEA',resistance_ohm=ohm);selected[ref]=d
    for ref in ['C217','C218']:selected[ref]=dict(MPN='C1210C104J1GACTU',manufacturer='KEMET',source_url='https://search.kemet.com/component-documentation/download/specsheet/C1210C104J1GACTU',C_nominal_F=1e-7,initial_tolerance_fraction=.05,TCR_ppm_per_K=30,rated_DC_V=100,footprint='Capacitor_SMD:C_1210_3225Metric')
    selected['U208']=dict(MPN='TPS3760A015DYYR',manufacturer='Texas Instruments',source_url='https://www.ti.com/lit/ds/symlink/tps3760.pdf',source_revision='SBVS420A September2023 DYY0014A July2024',footprint='WP10_AUX:TPS3760_DYY14',availability='Active manufacturer product; TI stock page unavailable/out-of-stock at check; no procurement claim')
    selected['J211']=dict(MPN='430450200',manufacturer='Molex',source_url='https://www.molex.com/en-us/products/part-detail/0430450200',footprint='WP10_AUX:Molex_430450200_2pin_RA')
    for ref,s in refs.items():
        for n in list(children(s,'instances')):s.remove(n)
        s.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps(ref)],['unit','1']]]])
        for key,k in [('MPN','MPN'),('Manufacturer','manufacturer'),('Datasheet','source_url'),('Footprint','footprint')]:prop(s,key,str(selected[ref].get(k,'')))
        prop(s,'Selection_Revision','V35')
        x,y=map(float,children(s,'at')[0][1:3])
        for q in children(s,'property'):
            name=val(q[1])
            if name=='Reference':at(q,x,y-24 if ref=='U209' else y-20 if ref=='U208' else y-8 if ref=='J211' else y-6.35)
            elif name=='Value':at(q,x,y-20 if ref=='U209' else y-16 if ref=='U208' else y+8 if ref=='J211' else y-3.81)
    # Labels drawn away from ICs / passive bodies on explicit wire stubs.
    for g in children(t,'global_label'):
        x,y=map(float,children(g,'at')[0][1:3])
        ref=min(refs,key=lambda r:sum((v-w)**2 for v,w in zip((x,y),map(float,children(refs[r],'at')[0][1:3]))))
        cx,cy=map(float,children(refs[ref],'at')[0][1:3]);left=x<cx or (abs(x-cx)<.01 and y<cy)
        end=(x-3.81 if left else x+3.81,y);ang=180 if left else 0
        t.append(['wire',['pts',['xy',str(x),str(y)],['xy',str(end[0]),str(end[1])]],['stroke',['width','0'],['type','default']],['uuid',uid()]])
        at(g,*end,ang);eff=children(g,'effects')[0]
        for j in list(children(eff,'justify')):eff.remove(j)
        eff.append(['justify','right' if left else 'left']);children(children(eff,'font')[0],'size')[0][1:]=['.8','.8']
        for q in children(g,'property'):at(q,*end,0)
    t.append(['text',json.dumps('PRIMARY DOMAIN ONLY. U208 qualifies AUX_LIMITED; U209 supplies remote pull-up.\nU202 remote harness open can bypass sequencing. Not a safety-rated STOP gate.\nNominal UV falling16.8V / rising17.64V; C218 cold delay~127ms.\nWarm restart, input capacitance, THN inrush and STOP brownout remain unverified.'),['at','25.4','180.34','0'],['effects',['font',['size','1','1']],['justify','left','top']],['uuid',uid()]])
    p.write_text(enc(t)+'\n',encoding='utf-8')
    # Exactly one old electrical endpoint changes: replace U202 pin3 NC.
    p=D/'wp10_power_3.kicad_sch';t=parse(p.read_text(encoding='utf-8-sig'));xy=pin_xy(t,'U202',3)
    nc=[n for n in children(t,'no_connect') if all(abs(float(c)-v)<1e-5 for c,v in zip(children(n,'at')[0][1:3],xy))];assert len(nc)==1
    t.remove(nc[0]);g=copy.deepcopy(children(t,'global_label')[0]);g[1]=json.dumps('WP10_THN_REMOTE');at(g,*xy,0);children(g,'uuid')[0][1]=uid()
    for q in children(g,'property'):at(q,*xy,0)
    t.append(g);p.write_text(enc(t)+'\n',encoding='utf-8')
    # Portable project registration, retaining existing parent libraries.
    p=D/'sym-lib-table';t=parse(p.read_text())
    for lib in children(t,'lib'):
        name=val(children(lib,'name')[0][1]);children(lib,'uri')[0][1]=json.dumps('${KIPRJMOD}/'+name+'.kicad_sym')
    p.write_text(enc(t)+'\n',encoding='utf-8')
    (R/'SELECTED_PARTS.json').write_text(json.dumps(selected,indent=2)+'\n',encoding='utf-8')
    print('V35: 13 new components; U202 remote connected; parent V34 untouched')
if __name__=='__main__':main()
