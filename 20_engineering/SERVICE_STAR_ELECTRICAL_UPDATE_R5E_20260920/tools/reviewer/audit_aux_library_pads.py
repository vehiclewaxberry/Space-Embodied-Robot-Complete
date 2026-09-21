"""Read-only geometry check for AUX's 11 embedded footprints without library nicknames."""
from pathlib import Path
import hashlib
import json
import pcbnew as k

ROOT=Path(__file__).resolve().parents[4]
D=ROOT/'20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
I=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
E=I/'ecad/revisions/v36'
R=D/'results/reviewer'
source=R/'LOCKED_249_XML_BOARD_AUDIT.json'
audit=json.loads(source.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
board_path=ROOT/audit['boards']['AUX']['path']
assert sha(board_path)==audit['boards']['AUX']['sha256']
board=k.LoadBoard(str(board_path))
fps={f.GetReference():f for f in board.GetFootprints()}
def vec(v):return [v.x,v.y]
def signature(fp):
    # Only the in-memory loaded object is normalized; never saved to source.
    assert not fp.IsFlipped()
    fp.SetOrientationDegrees(0)
    fp.SetPosition(k.VECTOR2I(0,0))
    rows=[]
    for p in fp.Pads():
        rows.append({'pin':p.GetNumber(),'position_nm':vec(p.GetPosition()),
            'size_nm':vec(p.GetSize()),'drill_nm':vec(p.GetDrillSize()),
            'shape':int(p.GetShape()),'attribute':int(p.GetAttribute()),
            'layers':str(p.GetLayerSet().FmtHex()),
            'orientation_deg':round(p.GetOrientationDegrees()%360,6),
            'round_rect_ratio':round(p.GetRoundRectRadiusRatio(),9),
            'offset_nm':vec(p.GetOffset())})
    return sorted(rows,key=lambda x:json.dumps(x,sort_keys=True))
rows=[]
for item in audit['boards']['AUX']['footprint_library_nickname_missing']:
    ref=item['ref']; lib,name=item['xml'].split(':',1)
    lp=E/(lib+'.pretty')/(name+'.kicad_mod')
    if not lp.is_file():
        rows.append({'ref':ref,'library_path':str(lp),'status':'MISSING_LIBRARY'})
        continue
    library=k.FootprintLoad(str(lp.parent),name)
    assert library is not None
    embedded_signature=signature(fps[ref]); library_signature=signature(library)
    rows.append({'ref':ref,'library_path':lp.relative_to(ROOT).as_posix(),
        'library_sha256':sha(lp),'embedded_pads':len(embedded_signature),'library_pads':len(library_signature),
        'embedded_signature':embedded_signature,'library_signature':library_signature,
        'pad_geometry_equal':embedded_signature==library_signature,
        'status':'PAD_GEOMETRY_EQUAL' if embedded_signature==library_signature else 'PAD_GEOMETRY_DIFFERENT'})
assert sha(board_path)==audit['boards']['AUX']['sha256']
out={'schema':'R5E_AUX_EMBEDDED_LIBRARY_PADS_REVIEW_V1',
    'source_audit':source.relative_to(ROOT).as_posix(),'source_audit_sha256':sha(source),
    'board_path':board_path.relative_to(ROOT).as_posix(),'board_sha256':sha(board_path),
    'footprints_compared':len(rows),'rows':rows,
    'all_pad_geometry_equal':all(x.get('pad_geometry_equal',False) for x in rows),
    'scope':'Pads only: location, dimensions, drill, shape, layers, attribute, angle, roundrect ratio, offset. No courtyard, mask, paste, custom primitive, whole-footprint, or manufacturing release equivalence claim.',
    'source_board_unchanged':True,'engineering_release':False}
(R/'AUX_EMBEDDED_LIBRARY_PADS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'all_pad_geometry_equal':out['all_pad_geometry_equal'],'rows':[{'ref':x['ref'],'pads':x.get('embedded_pads'),'status':x['status']} for x in rows]},indent=2))
