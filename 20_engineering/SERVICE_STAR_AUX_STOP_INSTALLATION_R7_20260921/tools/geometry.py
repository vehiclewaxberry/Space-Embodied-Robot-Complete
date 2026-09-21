"""R7 installs AUX and STOP on top of the sealed R6H horizontal result.

The host for every R7 clearance question is the spacecraft *after* R6H: the R4
canonical rows with the R6H replacements and pose changes applied, plus the 23
R6H parts (horizontal MAIN PCBA, its four M3 standoff stacks, the thermal bridge
and the top isolation pad). Nothing from R6H or earlier is modified here.
"""
from pathlib import Path
import importlib.util, json, numpy as np

D = Path(__file__).resolve().parents[1]
ROOT = D.parents[1]
R6H = D.parent / 'SERVICE_STAR_CORE_INSTALLATION_R6H_20260920'
R6 = D.parent / 'SERVICE_STAR_CORE_INSTALLATION_R6_20260920'
R5 = D.parent / 'SERVICE_STAR_POWER_THERMAL_LAYOUT_R5_20260920'
R4 = D.parent / 'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
E = D.parent / 'SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
V36 = ROOT / ('01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/'
              'wp10_mechatronic_closure_20260908/implementation/ecad/revisions/v36')

_sp = importlib.util.spec_from_file_location('r6h_geometry', R6H / 'tools/geometry.py')
c = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(c)

g = c.g
read, write, sha, load, moved = c.read, c.write, c.sha, c.load, c.moved
box, cyl, cut, union, common, distance = c.box, c.cyl, c.cut, c.union, c.common, c.distance
compound, source, world_bounds, candidates = c.compound, c.source, c.world_bounds, c.candidates
I = np.eye(4).tolist()

for p in ['inputs', 'results', 'cad', 'native', 'views', 'docs', 'sources']:
    (D / p).mkdir(exist_ok=True, parents=True)


def emit(ident, s, role, sub='', **kw):
    p = D / 'cad' / sub / (ident + '.step') if sub else D / 'cad' / (ident + '.step')
    p.parent.mkdir(exist_ok=True, parents=True)
    fact = g.dump(s, p)
    return dict(id=ident, step_path=str(p), source_sha256=fact['sha256'],
                native_path=str(D / 'native' / (ident + '.SLDPRT')), T_S_local=I,
                expected_solids=fact['solids'], expected_sheets=0,
                expected_volume_mm3=fact['volume_mm3'],
                expected_local_bbox_mm={'min_mm': fact['bounds_mm'][0], 'max_mm': fact['bounds_mm'][1]},
                representation_role=role, **kw)


def host_rows():
    """The three fixed states as they stand after the R6H horizontal installation."""
    lay = read(R6H / 'inputs/INSTALLATION_LAYOUT.json')
    mods = {r['id']: r for r in lay['replacements'] + lay['pose_changes']}
    added = lay['parts']
    out = {}
    for st, rows in c.state_rows().items():
        out[st] = [mods.get(r['id'], r) for r in rows] + list(added)
    # The R6H service top that this package builds on must still be the file on disk.
    resume = read(R6H / 'results/NATIVE_SERVICE_TOP_RESUME.json')
    assert resume['status'] == 'PASS_R6H_SERVICE_TOP_RESUMED_AND_COLD_VERIFIED'
    assert sha(resume['service']['saved']['path']) == resume['service']['saved']['sha256']
    return out
