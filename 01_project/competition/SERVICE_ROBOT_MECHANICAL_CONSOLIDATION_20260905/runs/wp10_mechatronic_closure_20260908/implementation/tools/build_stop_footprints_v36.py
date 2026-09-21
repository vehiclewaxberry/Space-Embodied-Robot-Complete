"""Native KiCad footprint construction from archived OEM drawings, V36.

Does not create or route the STOP board. PR02 lead forming is a project choice.
"""
from pathlib import Path
import hashlib, json
import pcbnew as k

A=Path(__file__).resolve().parents[1]
D=A/'ecad/revisions/v36'
R=A/'results/stop_v36/pcb'
LIB=D/'WP10_STOP.pretty'

def mm(x,y): return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def layers(*ids):
    z=k.LSET()
    for i in ids: z.AddLayer(i)
    return z
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def segment(f,a,b,layer,width=.05):
    z=k.PCB_SHAPE(f); z.SetShape(k.SHAPE_T_SEGMENT)
    z.SetStart(mm(*a)); z.SetEnd(mm(*b)); z.SetLayer(layer)
    z.SetWidth(k.FromMM(width)); f.Add(z)
def box(f,x0,y0,x1,y1,layer,width=.05):
    q=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
    for a,b in zip(q,q[1:]):segment(f,a,b,layer,width)
def smd(f,n,x,y,w,h,lays,radius=.05):
    p=k.PAD(f);p.SetNumber(str(n));p.SetAttribute(k.PAD_ATTRIB_SMD)
    p.SetShape(k.PAD_SHAPE_ROUNDRECT);p.SetRoundRectRadiusRatio(radius/min(w,h))
    p.SetSize(mm(w,h));p.SetPosition(mm(x,y));p.SetLayerSet(layers(*lays));f.Add(p)
    return p
def new(name,desc,smd_attr):
    f=k.FOOTPRINT(None);f.SetFPID(k.LIB_ID('WP10_STOP',name))
    f.SetReference('REF**');f.SetValue(name);f.SetLibDescription(desc)
    f.SetAttributes(k.FP_SMD if smd_attr else k.FP_THROUGH_HOLE)
    f.Reference().SetPosition(mm(0,-2.6));f.Reference().SetTextSize(mm(.8,.8))
    f.Value().SetVisible(False)
    return f
def tps3431():
    f=new('TPS3431_DRB0008A','TI drawing 4218875/A 01/2018; TPS3431 PDF pp29-30. EP=pin9 GND. Optional thermal vias deferred to PCB.',True)
    for n in range(1,9):
        x=-1.4 if n<=4 else 1.4
        y=-.975+(n-1)*.65 if n<=4 else -.975+(8-n)*.65
        p=smd(f,n,x,y,.6,.31,[k.F_Cu,k.F_Mask,k.F_Paste])
        p.SetLocalSolderMaskMargin(k.FromMM(.05))
    # Main exposed pad and four connected copper fingers. No unfilled via-in-pad.
    p=smd(f,9,0,0,1.5,1.75,[k.F_Cu,k.F_Mask]);p.SetLocalSolderMaskMargin(k.FromMM(.05))
    for x in [-.325,.325]:
        for s in [-1,1]:
            # .825 mm extension plus .05 mm copper overlap into the main pad.
            p=smd(f,9,x,s*1.2625,.23,.875,[k.F_Cu,k.F_Mask]);p.SetLocalSolderMaskMargin(k.FromMM(.05))
            smd(f,'',x,s*1.337,.23,.725,[k.F_Paste])
    smd(f,'',0,0,1.34,1.55,[k.F_Paste])
    box(f,-1.5,-1.5,1.5,1.5,k.F_Fab,.1)
    box(f,-2,-2,2,2,k.F_CrtYd,.05)
    segment(f,(-1.65,-1.75),(-1.1,-1.75),k.F_SilkS,.12)
    segment(f,(-1.65,-1.75),(-1.65,-1.4),k.F_SilkS,.12)
    return f
def pr02():
    f=new('Vishay_PR02_P15_24','Vishay 28729 Rev08Jul2025 p16 PR02. ENGINEERING formed P15.24; Dmax3.9 L1max10 L2max12 leadmax0.83. >=1mm body stand-off. Finished drill1.1 is project choice.',False)
    for n,x in [(1,0),(2,15.24)]:
        p=k.PAD(f);p.SetNumber(str(n));p.SetAttribute(k.PAD_ATTRIB_PTH)
        p.SetShape(k.PAD_SHAPE_RECT if n==1 else k.PAD_SHAPE_CIRCLE)
        p.SetSize(mm(2.2,2.2));p.SetDrillSize(mm(1.1,1.1));p.SetPosition(mm(x,0))
        ls=k.LSET.AllCuMask();ls.AddLayer(k.F_Mask);ls.AddLayer(k.B_Mask)
        p.SetLayerSet(ls);f.Add(p)
    box(f,2.62,-1.95,12.62,1.95,k.F_Fab,.1)
    for a,b in [((0,0),(2.62,0)),((12.62,0),(15.24,0))]:segment(f,a,b,k.F_Fab,.1)
    box(f,2.52,-2.05,12.72,2.05,k.F_SilkS,.12)
    box(f,-1.35,-2.5,16.6,2.5,k.F_CrtYd,.05)
    f.Reference().SetPosition(mm(7.62,-3.1))
    return f
def pads(f):
    return [dict(number=p.GetNumber(),xy=[k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y)],size=[k.ToMM(p.GetSize().x),k.ToMM(p.GetSize().y)],drill=[k.ToMM(p.GetDrillSize().x),k.ToMM(p.GetDrillSize().y)],copper=p.IsOnLayer(k.F_Cu),paste=p.IsOnLayer(k.F_Paste)) for p in f.Pads()]
def main():
    LIB.mkdir(exist_ok=True)
    # Explicit native writer also supports a newly-created empty .pretty library.
    io=k.PCB_IO_KICAD_SEXPR()
    names=[]
    for f in [tps3431(),pr02()]:
        io.FootprintSave(str(LIB),f)
        names.append(str(f.GetFPID().GetLibItemName()))
    loaded={name:io.FootprintLoad(str(LIB),name) for name in names}
    assert all(f is not None for f in loaded.values())
    data={name:pads(f) for name,f in loaded.items()}
    t=data[names[0]]
    signal={p['number']:p for p in t if p['number'] not in ['','9']}
    assert set(signal)==set(map(str,range(1,9)))
    for n,p in signal.items():
        assert abs(abs(p['xy'][0])-1.4)<1e-6 and p['size']==[.6,.31]
    assert signal['1']['xy']==[-1.4,-.975] and signal['8']['xy']==[1.4,-.975]
    assert any(p['number']=='9' and p['size']==[1.5,1.75] and p['xy']==[0,0] for p in t)
    assert len([p for p in t if p['number']=='' and p['paste']])==5
    r=data[names[1]];assert len(r)==2 and {p['number'] for p in r}=={'1','2'}
    assert all(p['drill']==[1.1,1.1] for p in r)
    assert abs(r[1]['xy'][0]-r[0]['xy'][0])==15.24
    report=dict(schema='WP10_V36_STOP_NATIVE_FOOTPRINT_CHECK',native_load_and_dimensional_checks_passed=True,
        footprint_files={str(LIB/(n+'.kicad_mod')):sha(LIB/(n+'.kicad_mod')) for n in names},pads=data,
        primary_sources={str(R/'sources'/p):sha(R/'sources'/p) for p in ['tps3431.pdf','pr010203.pdf']},
        decisions=['DRB signal columns are +/-1.4mm, NOT +/-1.1mm; exposed pad main rectangle1.5x1.75mm.',
          'DRB connected fingers and paste aperture dimensions follow example drawing4218875/A; no optional vias authored.',
          'PR02 15.24mm lead forming,1.1mm finished drill,2.2mm lands and >=1mm stand-off are engineering selections, not OEM fixed formed dimensions.'],
        limitations=['No STOP PCB placement/routing/DRC yet.','Solder process, lead forming and assembly fit not executed.','PR02 worst screening loss1.23008W combined excludes regulator loss; installation thermal test absent.'],
        whole_design_complete=False)
    (R/'FOOTPRINT_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(footprints=names,native_load_checks=True,STOP_PCB_complete=False)))
if __name__=='__main__':main()
