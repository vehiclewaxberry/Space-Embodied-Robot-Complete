"""Build the AUX and STOP PCBA bodies in board-local coordinates.

Three geometry classes, all recorded per reference, none zero-filled:

  KICAD_NATIVE_MODEL   the solid KiCad itself exported for that footprint
  PREVIOUS_CATALOGUE_OR_OEM_BODY_REFERENCE
                       a body already in the mechanical model for the identical
                       MPN (the two WIMA MKS2 boxes AUX shares with MAIN)
  FOOTPRINT_XY_PLUS_ASSUMED_HEIGHT_RESERVATION
                       footprint XY from KiCad plus a declared project reservation
                       height; manufacturer_max_height_mm stays null until the OEM
                       drawing is filed

Board bodies export at the KiCad dielectric thickness and are Z-scaled to the
nominal total stack, the same correction R6H applied to MAIN. Components keep
their KiCad datum at z=1.595 and are not moved.
"""
from geometry import *
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.gp import gp_GTrsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.BRepCheck import BRepCheck_Analyzer

DIELECTRIC_MM = 1.51
COMPONENT_DATUM_MM = 1.595

# Reservation heights are conservative project values: a reservation only makes
# the installed envelope larger, so a later OEM maximum that is smaller does not
# invalidate a clearance result obtained with these.
RESERVATION = {
    'SMD_IC_OR_DIODE': 6.0,
    'MOLEX_MICROFIT_3_0_HORIZONTAL': 12.0,
    'THT_AXIAL_RESISTOR': 6.0,
    'TEST_PADS': 2.0,
}

# refs with no usable 3D solid, and the class each is reserved under
RESERVE = {
    'AUX': {
        'C219': 'V30_REUSE:V30_007', 'C220': 'V30_REUSE:V30_008',
        'D207': 'SMD_IC_OR_DIODE', 'D208': 'SMD_IC_OR_DIODE',
        'D209': 'SMD_IC_OR_DIODE', 'D210': 'SMD_IC_OR_DIODE',
        'U207': 'SMD_IC_OR_DIODE', 'U208': 'SMD_IC_OR_DIODE', 'U209': 'SMD_IC_OR_DIODE',
        'J208': 'MOLEX_MICROFIT_3_0_HORIZONTAL', 'J209': 'MOLEX_MICROFIT_3_0_HORIZONTAL',
        'J211': 'MOLEX_MICROFIT_3_0_HORIZONTAL', 'J210': 'TEST_PADS',
    },
    'STOP': {
        'J101': 'MOLEX_MICROFIT_3_0_HORIZONTAL', 'J102': 'MOLEX_MICROFIT_3_0_HORIZONTAL',
        'J103': 'MOLEX_MICROFIT_3_0_HORIZONTAL', 'J104': 'MOLEX_MICROFIT_3_0_HORIZONTAL',
        'J105': 'MOLEX_MICROFIT_3_0_HORIZONTAL',
        'R124': 'THT_AXIAL_RESISTOR', 'R125': 'THT_AXIAL_RESISTOR',
        'U101': 'SMD_IC_OR_DIODE',
    },
}
MOUNT_PREFIX = ('MH', 'HSTOP')


def board_body_index(rows):
    """The one exported solid that is the bare board: z from 0 to the dielectric."""
    hits = [i for i, r in enumerate(rows)
            if abs(r['expected_local_bbox_mm']['min_mm'][2]) < 1e-6
            and abs(r['expected_local_bbox_mm']['max_mm'][2] - DIELECTRIC_MM) < 1e-6]
    assert len(hits) == 1, hits
    return hits[0]


def recentre(shape, target_xy, bottom_z):
    """Place a reused catalogue body at a footprint centre, sitting on the board."""
    lo, hi = g.precise_bounds(shape)
    T = np.eye(4)
    T[0, 3] = target_xy[0] - (lo[0] + hi[0]) / 2
    T[1, 3] = target_xy[1] - (lo[1] + hi[1]) / 2
    T[2, 3] = bottom_z - lo[2]
    return moved(shape, T)


def build(tag):
    smap = read(D / 'inputs' / ('%s_SOURCE_MAP.json' % tag))
    pop = read(D / 'inputs' / ('%s_POPULATION_READBACK.json' % tag))
    v30 = {r['id']: r for r in read(R5 / 'inputs/V30_SOURCE_MAP.json')['rows']}
    fps = {r['ref']: r for r in pop['footprints']}
    stack = pop['thickness_mm']
    rows = smap['rows']

    shapes = []
    coverage = {}

    # 1. KiCad's own solids, board body rescaled to the nominal total stack.
    bi = board_body_index(rows)
    for i, r in enumerate(rows):
        s = source(r)
        if i == bi:
            ex = TopExp_Explorer(s, TopAbs_SOLID)
            solids = []
            while ex.More():
                solids.append(ex.Current())
                ex.Next()
            assert len(solids) == 1
            gt = gp_GTrsf()
            gt.SetValue(3, 3, stack / DIELECTRIC_MM)
            s = BRepBuilderAPI_GTransform(solids[0], gt, True).Shape()
            assert BRepCheck_Analyzer(s).IsValid()
            coverage['__BOARD__'] = dict(
                ref='__BOARD__', MPN=None, geometry_class='KICAD_BOARD_BODY_Z_SCALED_TO_NOMINAL_STACK',
                source_rows=[r['id']], exported_dielectric_mm=DIELECTRIC_MM,
                nominal_total_stack_mm=stack,
                note='Z scaling of the board body only; copper and mask are not separately materialised')
        else:
            lo = r['expected_local_bbox_mm']['min_mm']
            hi = r['expected_local_bbox_mm']['max_mm']
            mid = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
            ref = min((k for k in fps if fps[k]['models']),
                      key=lambda k: (fps[k]['xy_mm'][0] - mid[0]) ** 2 + (-fps[k]['xy_mm'][1] - mid[1]) ** 2)
            # A 3D model's centroid can sit off the footprint origin (THT modules
            # with asymmetric bodies); the binding check that matters is the
            # bijection asserted below, not this radius.
            d = ((fps[ref]['xy_mm'][0] - mid[0]) ** 2 + (-fps[ref]['xy_mm'][1] - mid[1]) ** 2) ** 0.5
            assert d < 6.0, (tag, r['id'], ref, d)
            e = coverage.setdefault(ref, dict(ref=ref, MPN=fps[ref]['value'],
                                              geometry_class='KICAD_NATIVE_MODEL', source_rows=[],
                                              model_files=fps[ref]['models'],
                                              match_distance_mm=d, local_z_mm=[lo[2], hi[2]]))
            e['source_rows'].append(r['id'])
            e['match_distance_mm'] = max(e['match_distance_mm'], d)
            e['local_z_mm'] = [min(e['local_z_mm'][0], lo[2]), max(e['local_z_mm'][1], hi[2])]
        shapes.append(s)

    # Every footprint KiCad could actually place must have received exactly the
    # solids it exported, and nothing else: refs with a model file, minus the ones
    # whose model file was missing on disk, must equal the refs matched above.
    placeable = {k for k in fps if fps[k]['models']} - set(RESERVE[tag])
    matched = {k for k, v in coverage.items()
               if k != '__BOARD__' and v['geometry_class'] == 'KICAD_NATIVE_MODEL'}
    assert matched == placeable, (tag, sorted(matched ^ placeable))
    assert sum(len(coverage[k]['source_rows']) for k in matched) == len(rows) - 1

    # 2. Reservations and reused catalogue bodies for everything KiCad could not place.
    for ref, kind in RESERVE[tag].items():
        f = fps[ref]
        xy = (f['xy_mm'][0], -f['xy_mm'][1])
        if kind.startswith('V30_REUSE:'):
            ident = kind.split(':', 1)[1]
            body = recentre(source(v30[ident]), xy, COMPONENT_DATUM_MM)
            lo, hi = g.precise_bounds(body)
            shapes.append(body)
            coverage[ref] = dict(ref=ref, MPN=f['value'],
                                 geometry_class='PREVIOUS_CATALOGUE_OR_OEM_BODY_REFERENCE',
                                 source_row=ident, source_sha256=v30[ident]['source_sha256'],
                                 reused_because='identical MPN already bodied in the MAIN board model',
                                 local_z_mm=[lo[2], hi[2]], leads_below_board_modelled=False,
                                 mounting_pose_qualified=False)
        else:
            h = RESERVATION[kind]
            x0, y0, x1, y1 = f['bbox_mm']
            shapes.append(box(x0, -y1, COMPONENT_DATUM_MM, x1, -y0, COMPONENT_DATUM_MM + h))
            coverage[ref] = dict(ref=ref, MPN=f['value'],
                                 geometry_class='FOOTPRINT_XY_PLUS_ASSUMED_HEIGHT_RESERVATION',
                                 reservation_class=kind, reserved_height_mm=h,
                                 manufacturer_max_height_mm=None,
                                 local_z_mm=[COMPONENT_DATUM_MM, COMPONENT_DATUM_MM + h],
                                 assumption='Space reservation only; OEM 3D and real installed height '
                                            'must replace this before clearance qualification')

    real = {r['ref'] for r in pop['footprints'] if not r['ref'].startswith(MOUNT_PREFIX)}
    covered = {k for k in coverage if k != '__BOARD__'}
    assert covered == real, (tag, sorted(real ^ covered))

    s = compound(shapes)
    lo, hi = g.precise_bounds(s)
    row = emit('R7_%s_PCBA_LOCAL' % tag, s, 'SOURCE_BOUND_MIXED_PCBA_GEOMETRY_NOT_RELEASED',
               board=tag, kicad_pcb_sha256=smap['kicad_pcb_sha256'],
               export_sha256=smap['source_sha256'], footprints_total=pop['footprints_total'],
               real_component_refs=len(real), mounting_holes=len(pop['footprints']) - len(real),
               all_geometry_OEM=False)
    write(D / 'inputs' / ('%s_GEOMETRY_COVERAGE.json' % tag), dict(
        board=row, tag=tag,
        local_frame='KiCad XY mirrored in Y; board base z=0; component datum z=%.3f mm' % COMPONENT_DATUM_MM,
        coverage=sorted(coverage.values(), key=lambda r: r['ref']),
        footprints_total=pop['footprints_total'], real_component_refs=len(real),
        covered_refs=len(covered),
        kicad_native_refs=sum(1 for v in coverage.values() if v['geometry_class'] == 'KICAD_NATIVE_MODEL'),
        reservation_refs=sorted(k for k, v in coverage.items()
                                if v['geometry_class'] == 'FOOTPRINT_XY_PLUS_ASSUMED_HEIGHT_RESERVATION'),
        reused_body_refs=sorted(k for k, v in coverage.items()
                                if v['geometry_class'] == 'PREVIOUS_CATALOGUE_OR_OEM_BODY_REFERENCE'),
        reservation_heights_mm=RESERVATION,
        board_size_mm=pop['board_size_mm'], nominal_total_stack_mm=stack,
        installed_local_bbox_mm={'min_mm': list(lo), 'max_mm': list(hi)},
        below_board_extent_mm=-lo[2], above_board_extent_mm=hi[2] - stack,
        mounting_hole_xy_mm=[[r['ref'], r['xy_mm'][0], -r['xy_mm'][1]]
                             for r in pop['footprints'] if r['ref'].startswith(MOUNT_PREFIX)],
        solder_and_termination_installation_qualified=False,
        whole_PCBA_clearance_qualified=False))
    print('%-5s %d solids  bbox z %.3f..%.3f  below %.3f  above-stack %.3f  reservations %d' % (
        tag, row['expected_solids'], lo[2], hi[2], -lo[2], hi[2] - stack,
        sum(1 for v in coverage.values() if v['geometry_class'].startswith('FOOTPRINT_XY'))), flush=True)
    return row


if __name__ == '__main__':
    out = {t: build(t) for t in ('AUX', 'STOP')}
    write(D / 'inputs/BOARD_LOCAL_BODIES.json', dict(
        schema='R7_BOARD_LOCAL_BODIES_V1', boards=out,
        component_datum_mm=COMPONENT_DATUM_MM, exported_dielectric_mm=DIELECTRIC_MM,
        reservation_heights_mm=RESERVATION,
        all_geometry_OEM=False, whole_PCBA_clearance_qualified=False))
