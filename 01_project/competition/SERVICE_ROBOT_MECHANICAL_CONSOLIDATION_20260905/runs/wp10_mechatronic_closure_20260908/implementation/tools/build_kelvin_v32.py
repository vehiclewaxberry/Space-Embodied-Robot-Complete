"""Apply KiCad 10 component-internal pad connections via the native API."""
from pathlib import Path
import hashlib, json
import pcbnew as k

A=Path(__file__).resolve().parents[1]
E=A/'ecad'
D=E/'revisions/v32'
R=A/'results/kelvin_v32'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def geometry(b):
    footprints=[]
    for f in b.GetFootprints():
        pads=[]
        for p in f.Pads():
            pads.append(dict(uuid=p.m_Uuid.AsString(),pin=p.GetNumber(),net=p.GetNetname(),
                xy=[p.GetPosition().x,p.GetPosition().y],size=[p.GetSize().x,p.GetSize().y],
                drill=[p.GetDrillSize().x,p.GetDrillSize().y],shape=int(p.GetShape()),
                layers=list(p.GetLayerSet().Seq()),angle=p.GetOrientationDegrees()))
        footprints.append(dict(uuid=f.m_Uuid.AsString(),ref=f.GetReference(),value=f.GetValue(),
            fp=str(f.GetFPID().GetLibItemName()),xy=[f.GetPosition().x,f.GetPosition().y],angle=f.GetOrientationDegrees(),
            pads=sorted(pads,key=lambda p:p['uuid'])))
    tracks=[]
    for t in b.GetTracks():
        d=dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),start=[t.GetStart().x,t.GetStart().y],
               end=[t.GetEnd().x,t.GetEnd().y],layer=int(t.GetLayer()))
        if isinstance(t,k.PCB_VIA): d.update(type='via',width=t.GetWidth(k.F_Cu),drill=t.GetDrillValue())
        else: d.update(type='track',width=t.GetWidth(),length=t.GetLength())
        tracks.append(d)
    return dict(footprints=sorted(footprints,key=lambda x:x['ref']),tracks=sorted(tracks,key=lambda x:x['uuid']),
                zones=b.GetAreaCount())

def relocate_models(f):
    changes=[]
    models=f.Models()
    for i in range(len(models)):
        m=models[i]
        old=m.m_Filename
        if old.startswith('${KIPRJMOD}/'):
            m.m_Filename=old.replace('${KIPRJMOD}/','${KIPRJMOD}/../../',1)
            models[i]=m
            assert f.Models()[i].m_Filename==m.m_Filename
            changes.append({'before':old,'after':m.m_Filename})
    return changes

def main():
    board=k.LoadBoard(str(E/'wp10_main_input.kicad_pcb'))
    before=geometry(board)
    modified=[]; models=[]
    for f in board.GetFootprints():
        models.extend(relocate_models(f))
        if f.GetReference() in ['R201','R202']:
            assert not f.GetDuplicatePadNumbersAreJumpers()
            ps=list(f.Pads())
            assert sorted(p.GetNumber() for p in ps)==['1','1','2','2']
            assert len({p.GetNetname() for p in ps})==2
            for pin in ['1','2']:
                pp=[p for p in ps if p.GetNumber()==pin]
                assert len({p.GetNetname() for p in pp})==1
            f.SetDuplicatePadNumbersAreJumpers(True)
            modified.append(f.GetReference())
    assert sorted(modified)==['R201','R202']
    assert geometry(board)==before
    k.SaveBoard(str(D/'wp10_main_input.kicad_pcb'),board)
    # Preserve the same attribute through footprint updates and file reloads.
    lib=D/'WP10_INPUT.pretty'
    fp=k.FootprintLoad(str(E/'WP10_INPUT.pretty'),'WSLP2726_KelvinSplit_TwoTerminals')
    fp.SetDuplicatePadNumbersAreJumpers(True)
    relocate_models(fp)
    k.FootprintSave(str(lib),fp)
    saved=k.FootprintLoad(str(lib),'WSLP2726_KelvinSplit_TwoTerminals')
    assert saved is not None and saved.GetDuplicatePadNumbersAreJumpers()
    # Library refresh must not restore model paths relative to the parent directory.
    library_relocations=[]
    for source in E.glob('*.pretty/*.kicad_mod'):
        if source.name=='WSLP2726_KelvinSplit_TwoTerminals.kicad_mod': continue
        f=k.FootprintLoad(str(source.parent),source.stem)
        changes=relocate_models(f)
        if changes:
            target=D/source.parent.name
            k.FootprintSave(str(target),f)
            readback=k.FootprintLoad(str(target),source.stem)
            actual=[m.m_Filename for m in readback.Models()]
            assert all(c['after'] in actual for c in changes)
            library_relocations.append(dict(footprint=source.name,changes=changes))
    check=k.LoadBoard(str(D/'wp10_main_input.kicad_pcb'))
    assert geometry(check)==before
    assert all(f.GetDuplicatePadNumbersAreJumpers() for f in check.GetFootprints() if f.GetReference() in modified)
    actual_models=[]
    for f in check.GetFootprints():
        for m in f.Models():
            if m.m_Filename.startswith('${KIPRJMOD}/'):
                p=(D/m.m_Filename.split('${KIPRJMOD}/',1)[1]).resolve()
                assert p.is_file(),str(p)
                actual_models.append(dict(ref=f.GetReference(),path=m.m_Filename,resolved_path=str(p),sha256=sha(p)))
    assert len(actual_models)==len(models)
    receipt=dict(passed=True,KiCad_version=k.Version(),modified_refs=modified,
        original_board_sha256=sha(E/'wp10_main_input.kicad_pcb'),board_sha256=sha(D/'wp10_main_input.kicad_pcb'),
        copper_pad_drill_and_placement_fingerprint_unchanged=True,
        geometry_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
        model_path_relocations=models,model_paths_verified_after_reload=actual_models,
        library_model_relocations=library_relocations,tracks=len(before['tracks']),footprints=len(before['footprints']),
        copper_added=0,copper_removed=0,net_or_pin_reassignment=0,explicit_cross_terminal_groups=0,
        scope='EDA representation of two same-number split lands per physical terminal; no fabricated component connection')
    (R/'NATIVE_BUILD.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (R/'GEOMETRY_FINGERPRINT.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':main()
