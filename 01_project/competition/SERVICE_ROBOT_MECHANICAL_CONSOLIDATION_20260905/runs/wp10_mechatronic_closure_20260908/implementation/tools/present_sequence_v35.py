"""Correct the new symbols' visual pin labels without changing electrical pins."""
from pathlib import Path
import json,copy
from erc_source_contract import parse,enc,children,val,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35'
lp=D/'WP10SEQ.kicad_sym';sp=D/'wp10_aux_sequence.kicad_sch';lib=parse(lp.read_text());sch=parse(sp.read_text())
names={'TPS3760A015DYYR':{'1':'VDD','3':'SENSE','6':'OUT_N','9':'CTR','10':'CTS'},'LT3013_DE12':{'7':'CT','6':'PG','13':'GND'},'REMOTE_PORT2':{'2':'RET'}}
for sym in children(lib,'symbol'):
    name=val(sym[1])
    for sub in children(sym,'symbol'):
        for pin in children(sub,'pin'):
            n=val(children(pin,'number')[0][1])
            if n in names.get(name,{}):children(pin,'name')[0][1]=json.dumps(names[name][n])
            if name=='TPS3760A015DYYR' and n in ['2','4','5','7','11','12','14']:
                at=children(pin,'at')[0];oldx=float(at[1]);newx=-7.62+['2','4','5','7','11','12','14'].index(n)*2.54
                for nc in children(sch,'no_connect'):
                    a=children(nc,'at')[0]
                    if abs(float(a[1])-(76.2+oldx))<1e-5 and abs(float(a[2])-(66.04+15.24))<1e-5:a[1]=str(76.2+newx);break
                at[1]=str(newx)
        if name=='TPS3760A015DYYR':
            for r in children(sub,'rectangle'):children(r,'end')[0][1]='7.62'
block=children(sch,'lib_symbols')[0]
for sym in list(children(block,'symbol')):
    name=val(sym[1])
    if name.startswith('WP10SEQ:'):
        c=copy.deepcopy(next(s for s in children(lib,'symbol') if val(s[1])==name.split(':')[1]));c[1]=json.dumps(name);block[block.index(sym)]=c
for g in children(sch,'global_label'):
    a=children(g,'at')[0]
    if abs(float(a[1])-231.14)<1e-5 and abs(float(a[2])-91.44)<1e-5:
        a[3]='0';e=children(g,'effects')[0]
        for j in list(children(e,'justify')):e.remove(j)
        e.append(['justify','left']);children(children(e,'font')[0],'size')[0][1:]=['.8','.8']
for s in children(sch,'symbol'):
    if properties(s)['Reference']=='#FLG03501':
        p=next(p for p in children(s,'property') if val(p[1])=='Reference');children(p,'effects')[0].append(['hide','yes'])
lp.write_text(enc(lib)+'\n');sp.write_text(enc(sch)+'\n')
print('Shortened pin names and corrected symbol body/NC spacing; electrical pin numbers unchanged')
