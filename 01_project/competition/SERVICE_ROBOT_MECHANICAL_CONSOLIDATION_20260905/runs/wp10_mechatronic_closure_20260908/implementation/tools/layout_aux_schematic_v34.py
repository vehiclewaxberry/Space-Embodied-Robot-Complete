"""Presentation repair of existing MCP schematic; preserve all nets and symbol UUIDs."""
from pathlib import Path
import json,uuid,math
from erc_source_contract import parse,enc,children,val,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34'
def main():
    p=D/'wp10_aux_protection.kicad_sch';t=parse(p.read_text(encoding='utf-8-sig'))
    assert not children(t,'wire'),'One-time layout of MCP direct-label source'
    cs={properties(s)['Reference']:s for s in children(t,'symbol')}
    old={r:tuple(float(v) for v in children(s,'at')[0][1:3]) for r,s in cs.items()}
    pos={'U207':(132.08,63.5),'J208':(50.8,25.4),'J209':(228.6,25.4),
      'C214':(50.8,55.88),'D207':(50.8,83.82),'C215':(228.6,55.88),'D208':(228.6,83.82),
      'R224':(73.66,119.38),'C216':(147.32,119.38),'R223':(220.98,119.38),'J210':(81.28,144.78)}
    def at(node,x,y,angle=0):children(node,'at')[0][1:]=[str(round(x,5)),str(round(y,5)),str(angle)]
    def wire(a,b):
        t.append(['wire',['pts',['xy',str(round(a[0],5)),str(round(a[1],5))],['xy',str(round(b[0],5)),str(round(b[1],5))]],
          ['stroke',['width','0'],['type','default']],['uuid',json.dumps(str(uuid.uuid4()))]])
    for g in list(children(t,'global_label')):
        x,y=map(float,children(g,'at')[0][1:3]);r=min(old,key=lambda r:(old[r][0]-x)**2+(old[r][1]-y)**2)
        nx,ny=pos[r];ox,oy=old[r];pin=(x+nx-ox,y+ny-oy)
        if r=='U207' and abs(x-ox)<.1:
            end=(pin[0]+5.08,pin[1]+7.62);wire(pin,(pin[0],end[1]));wire((pin[0],end[1]),end);angle=0
        elif r=='U207':
            direction=-1 if x<ox else 1;end=(pin[0]+direction*5.08,pin[1]);wire(pin,end);angle=180 if direction<0 else 0
        elif r.startswith('J'):
            end=(pin[0]-5.08,pin[1]);wire(pin,end);angle=180
        else:
            direction=-1 if y<oy else 1;end=(pin[0]-5.08,pin[1]+direction*3.81)
            corner=(pin[0],end[1]);wire(pin,corner);wire(corner,end);angle=180
        at(g,*end,angle)
        eff=children(g,'effects')[0]
        for q in list(children(eff,'justify')):eff.remove(q)
        eff.append(['justify','right' if angle==180 else 'left'])
        children(children(eff,'font')[0],'size')[0][1:]=['1','1']
        for prop in children(g,'property'):at(prop,*end,0)
    for nc in children(t,'no_connect'):
        q=children(nc,'at')[0];x,y=map(float,q[1:3]);r=min(old,key=lambda r:(old[r][0]-x)**2+(old[r][1]-y)**2)
        q[1:]=[str(round(x+pos[r][0]-old[r][0],5)),str(round(y+pos[r][1]-old[r][1],5))]
    for r,s in cs.items():
        x,y=pos[r];angle=float(children(s,'at')[0][3]);at(s,x,y,angle)
        for prop in children(s,'property'):
            name=val(prop[1])
            if name=='Reference':xy=(x,y-20.32) if r=='U207' else (x+5.08,y-1.905) if not r.startswith('J') else (x,y-6.35)
            elif name=='Value':xy=(x,y-16.51) if r=='U207' else (x+5.08,y+1.905) if not r.startswith('J') else (x,y+6.35)
            else:continue
            at(prop,*xy,0);eff=children(prop,'effects')[0]
            for q in list(children(eff,'justify')):eff.remove(q)
            if not r.startswith('J') and r!='U207':eff.append(['justify','left'])
    for text in children(t,'text'):
        q=children(text,'at')[0];q[1:3]=['25.4','163.83']
        eff=children(text,'effects')[0]
        for q in list(children(eff,'justify')):eff.remove(q)
        eff.append(['justify','left','top'])
    p.write_text(enc(t)+'\n',encoding='utf-8')
    # Normalize MCP library registration to preserve package relocation.
    p=D/'sym-lib-table';t=parse(p.read_text(encoding='utf-8-sig'))
    for lib in children(t,'lib'):
        name=val(children(lib,'name')[0][1]);uri=children(lib,'uri')[0]
        if (D/(name+'.kicad_sym')).exists():uri[1]=json.dumps('${KIPRJMOD}/'+name+'.kicad_sym')
    p.write_text(enc(t)+'\n',encoding='utf-8')
    print('Moved 11 symbols; labels face outward on short wires. Pin/net identity will be verified by native export.')
if __name__=='__main__':main()
