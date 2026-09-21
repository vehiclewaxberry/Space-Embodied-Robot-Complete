"""Independent native pad/net/source audit and retained power-trace coverage."""
from pathlib import Path
import json,math,hashlib,collections,xml.etree.ElementTree as E
import pcbnew as k
from erc_source_contract import physical_netlist,source_inventory,parse,children,properties,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35';P=D.parent/'v34'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def vec(v):return (k.ToMM(v.x),k.ToMM(v.y))
def records(b):
    return [dict(net=t.GetNetname(),layer=t.GetLayerName(),start=vec(t.GetStart()),end=vec(t.GetEnd()),width=k.ToMM(t.GetWidth())) for t in b.GetTracks() if not isinstance(t,k.PCB_VIA)]
def covered(a,new):
    x,y=a['start'];dx,dy=a['end'][0]-x,a['end'][1]-y;norm=dx*dx+dy*dy
    if norm<1e-12:return True
    spans=[]
    for z in new:
        if z['net']!=a['net'] or z['layer']!=a['layer'] or z['width']+1e-5<a['width']:continue
        q=[(p[0]-x,p[1]-y) for p in [z['start'],z['end']]]
        if max(abs(i*dy-j*dx)/math.sqrt(norm) for i,j in q)>1e-4:continue
        spans.append(sorted((i*dx+j*dy)/norm for i,j in q))
    end=0.
    for lo,hi in sorted(spans):
        if hi<end:continue
        if lo>end+1e-4:return False
        end=max(end,hi)
        if end>=1-1e-4:return True
    return False
def main():
    oldc,oldp=physical_netlist(P/'wp10_system.xml');cs,pins=physical_netlist(D/'wp10_system.xml')
    change={str(key):(oldp[key],pins.get(key)) for key in oldp if oldp[key]!=pins.get(key)}
    assert set(change)=={str(('U202','3'))},change
    assert all(cs[ref]==v for ref,v in oldc.items())
    expected_new=set(json.loads((R/'SELECTED_PARTS.json').read_text()));assert set(cs)-set(oldc)==expected_new
    b=k.LoadBoard(str(D/'wp10_aux_protection.kicad_pcb'));parent=k.LoadBoard(str(P/'wp10_aux_protection.kicad_pcb'))
    refs=set();pad_count=0
    for f in b.GetFootprints():
        if f.GetAttributes()&k.FP_BOARD_ONLY:continue
        ref=f.GetReference();assert ref not in refs;refs.add(ref);assert f.GetValue()==cs[ref][0],(ref,f.GetValue(),cs[ref])
        for p in f.Pads():
            if not p.GetNumber():continue
            assert p.GetNetname()==pins[ref,p.GetNumber()][0],(ref,p.GetNumber(),p.GetNetname(),pins.get((ref,p.GetNumber())))
            pad_count+=1
    oldtr=records(parent);newtr=records(b)
    retained=[covered(t,newtr) for t in oldtr]
    power=[(t,covered(t,newtr)) for t in oldtr if t['net'] in ['WP10_AUX_FUSED','WP10_AUX_LIMITED','WP10_INPUT_RETURN']]
    oldvias=[(v.GetNetname(),vec(v.GetPosition()),k.ToMM(v.GetWidth(k.F_Cu)),k.ToMM(v.GetDrillValue())) for v in parent.GetTracks() if isinstance(v,k.PCB_VIA)]
    newvias=[(v.GetNetname(),vec(v.GetPosition()),k.ToMM(v.GetWidth(k.F_Cu)),k.ToMM(v.GetDrillValue())) for v in b.GetTracks() if isinstance(v,k.PCB_VIA)]
    missingvias=[v for v in oldvias if v not in newvias]
    flags,pages,_=source_inventory(D/'wp10_system.kicad_sch')
    f=next(f for f in flags if f['reference']=='#FLG03501');assert f['nets']==['WP10_AUX_SEQ_VDD'] and f['on_board']=='no' and f['in_bom']=='no'
    assert pins['U208','1'][0]==pins['D209','1'][0]==pins['D210','1'][0]==pins['C217','1'][0]=='WP10_AUX_SEQ_VDD'
    assert pins['D209','2'][0]=='WP10_AUX_LIMITED' and pins['D210','2'][0]=='WP10_AUX_REMOTE_BIAS'
    assert pins['U208','6'][0]==pins['J211','1'][0]==pins['U202','3'][0]=='WP10_THN_REMOTE'
    assert pins['U207','8'][0]!=pins['U207','9'][0] and pins['U202','2'][0]!=pins['U202','6'][0]
    lock=json.loads((R/'PARENT_SOURCE_LOCK.json').read_text());parent_ok=all(sha(p)==h for p,h in lock.items());assert parent_ok
    result=dict(native_components=len(cs),native_pin_net_records=len(pins),source_pages=len(pages),new_refs=sorted(expected_new),changed_old_pins=change,
        aux_electrical_footprints=len(refs),aux_numbered_pads=pad_count,all_aux_pads_net_and_values_match=True,
        original_power_segments_covered=all(v for t,v in power),power_segments=len(power),uncovered_power_segments=[t for t,v in power if not v],
        all_original_segments_covered=all(retained),old_vias_preserved=not missingvias,missing_old_vias=missingvias,
        primary_internal_RTN_and_secondary_domains_separate=True,conditional_power_declaration=f,
        original_parent_files_unchanged=parent_ok,parent_files_locked=len(lock),
        main_board_byte_identical_to_V34=sha(D/'wp10_main_input.kicad_pcb')==sha(P/'wp10_main_input.kicad_pcb'),
        board_R_scope='V34 serial power-trace model can be reused only if original power segments and vias retained. New30mA branch loss not extracted; allocation scenario only.',
        source_bindings={str(p):sha(p) for p in pages+[D/'wp10_system.xml',D/'wp10_aux_protection.kicad_pcb',D/'wp10_main_input.kicad_pcb']})
    (R/'NATIVE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:v for key,v in result.items() if key not in ['source_bindings','conditional_power_declaration']}))
if __name__=='__main__':main()
