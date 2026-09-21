"""WP03 independent 3D beam skeleton screen; not a full-structure FE analysis.

Reuses only WP02 Euler beam element/rigid-offset formulas, not its coupon mesh,
constraints or compliance result. Reads no CAD geometry and runs no dynamics.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FORMULAS = HERE.parent / 'service_robot_wp02_20260905/root_compliance.py'
spec = importlib.util.spec_from_file_location('wp02_beam_formulas_only', FORMULAS)
beam = importlib.util.module_from_spec(spec); spec.loader.exec_module(beam)
ROOT = np.array([90., 0., 125.15])
CASES = ('REAR_X_MINUS_180_FOUR_CORNERS_IDEAL_CLAMP', 'GROUND_FOUR_LOWER_CORNERS_IDEAL_CLAMP')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def square_tube(outer, wall):
    if wall <= 0 or 2 * wall >= outer:
        raise ValueError('Bad square tube wall')
    return {'A': outer**2 - (outer - 2*wall)**2,
            'Iy': (outer**4 - (outer - 2*wall)**4)/12,
            'Iz': (outer**4 - (outer - 2*wall)**4)/12,
            'J': wall * (outer-wall)**3,
            'torsion_basis': 'BREDT_MEDIAN_LINE_CLOSED_CELL_APPROXIMATION_NOT_EXACT_THICK_WALL'}


def rectangle(width_local_y, height_local_z):
    w, h = width_local_y, height_local_z
    long, short = max(w, h), min(w, h)
    return {'A': w*h, 'Iy': w*h**3/12, 'Iz': h*w**3/12,
            'J': long*short**3/3 * (1 - .63*short/long + .052*(short/long)**5),
            'torsion_basis': 'SAINT_VENANT_RECTANGULAR_SECTION_ENGINEERING_APPROXIMATION'}


def sections(longeron_wall=2., pillar_wall=2., end_thickness=6., upper_height=12.):
    # Local x is member axis, local y is global X for Y/Z members.
    return {'longeron': square_tube(12., longeron_wall), 'pillar': square_tube(14., pillar_wall),
            'end_frame': rectangle(end_thickness, 12.),
            'upper_crossbeam': rectangle(14., upper_height),
            'lower_crossbeam': rectangle(14., 6.)}


def build_mesh(subdivisions=1):
    points = [ROOT.copy()]
    names = ['arm_root_rigid_distributor']
    lookup = {}
    members = []

    def node(point, name):
        point = np.asarray(point, dtype=float)
        key = tuple(np.round(point, 8))
        if key not in lookup:
            lookup[key] = len(points); points.append(point); names.append(name)
        return lookup[key]

    def mapping(block, physical_point=None):
        return block, np.eye(6) if physical_point is None else beam.rigid_offset(np.asarray(physical_point)-points[block])

    def member(a, b, section, ma, mb, name):
        a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        members.append({'a': a, 'b': b, 'section': section, 'map_a': ma, 'map_b': mb, 'name': name})

    # Ring neutral lines represent the two 6 mm thick end frames, not panels.
    corner = {}
    for x in (-180., 180.):
        for y in (-107.15, 107.15):
            for z in (-107.15, 107.15):
                corner[x, y, z] = node([x, y, z], f'end_corner_{x}_{y}_{z}')
        for z in (-107.15, 107.15):
            a, b = [x, -107.15, z], [x, 107.15, z]
            member(a, b, 'end_frame', mapping(corner[x, -107.15, z]), mapping(corner[x, 107.15, z]), f'end_frame_horizontal_{x}_{z}')
        for y in (-107.15, 107.15):
            a, b = [x, y, -107.15], [x, y, 107.15]
            member(a, b, 'end_frame', mapping(corner[x, y, -107.15]), mapping(corner[x, y, 107.15]), f'end_frame_vertical_{x}_{y}')

    # Physical longeron endpoints x=+-177 connect to end-frame neutral x=+-180
    # through rigid 3 mm offsets. Holes/end plugs/bolts are not beam sections.
    rail_nodes = {}
    for y in (-107.15, 107.15):
        for z in (-107.15, 107.15):
            stations = []
            for x in (-177., 20., 160., 177.):
                point = np.array([x, y, z])
                if abs(x) == 177:
                    block = corner[np.sign(x)*180., y, z]
                else:
                    block = node(point, f'rail_root_station_{x}_{y}_{z}')
                    rail_nodes[x, y, z] = block
                stations.append((point, mapping(block, point)))
            for i in range(3):
                member(stations[i][0], stations[i+1][0], 'longeron', stations[i][1], stations[i+1][1], f'longeron_{y}_{z}_segment_{i}')

    # The root's six components are distributed rigidly to the upper crossbeam
    # centers. Actual bridge/M3R compliance is deliberately not represented.
    for x in (20., 160.):
        column_maps = {}
        for tag, z, rail_z, section in [('upper', 101.15, 107.15, 'upper_crossbeam'),
                                       ('lower', -104.15, -107.15, 'lower_crossbeam')]:
            stations = []
            for y in (-101.15, -94.15, 0., 94.15, 101.15):
                point = np.array([x, y, z])
                if abs(y) == 101.15:
                    block = rail_nodes[x, np.sign(y)*107.15, rail_z]
                elif y == 0 and tag == 'upper':
                    block = 0
                else:
                    block = node(point, f'{tag}_crossbeam_station_{x}_{y}')
                mapped = mapping(block, point)
                stations.append((point, mapped))
                if abs(y) == 94.15:
                    column_maps[tag, y] = block
            for i in range(4):
                member(stations[i][0], stations[i+1][0], section, stations[i][1], stations[i+1][1], f'{tag}_crossbeam_{x}_segment_{i}')
        for y in (-94.15, 94.15):
            a, b = np.array([x, y, -98.15]), np.array([x, y, 95.15])
            member(a, b, 'pillar', mapping(column_maps['lower', y], a), mapping(column_maps['upper', y], b), f'root_pillar_{x}_{y}')

    elements = []
    for item in members:
        stations = [(item['a'], item['map_a'])]
        for i in range(1, subdivisions):
            point = item['a']+(item['b']-item['a'])*i/subdivisions
            block = len(points); points.append(point); names.append(f'{item["name"]}_mesh_{i}')
            stations.append((point, mapping(block)))
        stations.append((item['b'], item['map_b']))
        for i in range(subdivisions):
            elements.append({'a': stations[i][0], 'b': stations[i+1][0], 'map_a': stations[i][1],
                             'map_b': stations[i+1][1], 'section': item['section'], 'name': item['name']})
    supports = {CASES[0]: [corner[-180., y, z] for y in (-107.15, 107.15) for z in (-107.15, 107.15)],
                CASES[1]: [corner[x, y, -107.15] for x in (-180., 180.) for y in (-107.15, 107.15)]}
    return {'points': np.asarray(points), 'names': names, 'elements': elements, 'members': members,
            'supports': supports, 'subdivisions': subdivisions}


def assemble(mesh, e=69000., nu=.33, **section_options):
    sec = sections(**section_options)
    rr, cc, vv = [], [], []
    for element in mesh['elements']:
        ke = beam.element_stiffness(element['a'], element['b'], sec[element['section']], e, nu)
        blocks = [element['map_a'], element['map_b']]
        for i, (ni, hi) in enumerate(blocks):
            for j, (nj, hj) in enumerate(blocks):
                value = hi.T @ ke[i*6:i*6+6, j*6:j*6+6] @ hj
                rows, cols = np.meshgrid(np.arange(ni*6, ni*6+6), np.arange(nj*6, nj*6+6), indexing='ij')
                rr.extend(rows.ravel()); cc.extend(cols.ravel()); vv.extend(value.ravel())
    n = len(mesh['points'])*6
    k = coo_matrix((vv, (rr, cc)), shape=(n, n)).tocsc()
    k.sum_duplicates()
    return k, sec


def solve_case(mesh, k, case):
    ndof = k.shape[0]
    fixed = np.array([node*6+i for node in mesh['supports'][case] for i in range(6)])
    free = np.setdiff1d(np.arange(ndof), fixed)
    applied = np.zeros((ndof, 6)); applied[:6] = np.diag([1., 1., 1., 1000., 1000., 1000.])
    displacement = np.zeros((ndof, 6))
    displacement[free] = splu(k[free][:, free]).solve(applied[free])
    c_engineering = displacement[:6]
    c_si = np.diag([.001, .001, .001, 1., 1., 1.]) @ c_engineering
    reaction = k @ displacement-applied
    support = []; balance = applied[:6].copy()
    for node in mesh['supports'][case]:
        f = reaction[node*6:node*6+6].copy()
        balance[:3] += f[:3]
        balance[3:] += f[3:] + beam.skew(mesh['points'][node]-ROOT) @ f[:3]
        f[3:] *= .001
        support.append({'node': mesh['names'][node], 'point_S_mm': mesh['points'][node],
                        'reaction_matrix_N_Nm': f})
    balance[3:] *= .001
    # The same reference length scales angular generalized coordinates and loads
    # for a dimensionally homogeneous reciprocity/positive-definiteness check.
    scale = np.diag([1., 1., 1., .1, .1, .1])
    normalized = scale @ c_si @ scale
    eigen = np.linalg.eigvalsh((normalized+normalized.T)/2)
    return {'case': case, 'C_SI': c_si, 'C_engineering_mm_rad_per_N_Nm': c_engineering,
            'root_condensed_K_SI': np.linalg.inv(c_si),
            'normalized_compliance_eigenvalues_m_per_N': eigen,
            'compliance_positive_definite': bool(eigen.min() > 0),
            'normalized_reciprocity_relative_error': np.linalg.norm(normalized-normalized.T)/np.linalg.norm(normalized),
            'reciprocity_max_absolute_SI': np.max(np.abs(c_si-c_si.T)),
            'support_reactions': support, 'reaction_balance_N_Nm': balance,
            'max_force_balance_error_N': np.max(np.abs(balance[:3])),
            'max_moment_balance_error_Nm': np.max(np.abs(balance[3:])),
            'max_free_dof_residual_N_or_Nmm': np.max(np.abs(reaction[free])),
            'node_count': len(mesh['points']), 'element_count': len(mesh['elements']), 'free_dof_count': len(free)}


def free_body_check(mesh, k):
    modes = np.vstack([beam.rigid_offset(p-ROOT) for p in mesh['points']])
    residual = np.asarray(k @ modes)
    dense = k.toarray()
    scale = np.tile([1., 1., 1., .01, .01, .01], len(mesh['points']))
    normalized_k = scale[:, None]*dense*scale[None, :]
    eigen = np.linalg.eigvalsh((normalized_k+normalized_k.T)/2)
    tolerance = float(np.max(np.abs(eigen))*1e-9)
    return {'statically_inverted': False, 'reason': 'FREE_BODY_HAS_SIX_RIGID_BODY_MODES_NO_UNIQUE_ABSOLUTE_STATIC_ROOT_COMPLIANCE',
            'rigid_mode_count_at_relative_tolerance_1e_minus_9': int(np.count_nonzero(np.abs(eigen) <= tolerance)),
            'stiffness_eigenvalue_threshold_N_per_mm': tolerance,
            'first_10_scaled_stiffness_eigenvalues_N_per_mm': eigen[:10],
            'rigid_mode_residual_relative': np.linalg.norm(residual)/(np.linalg.norm(dense)*np.linalg.norm(modes)),
            'static_equilibrium_requirements': ['sum external forces = 0', 'sum external moments about one common point = 0'],
            'future_load_solution': 'For in-orbit acceleration use a free-body/multibody dynamic model or documented inertia relief; do not fix arbitrary spacecraft points and call that free flight.'}


def analytic_cantilever_check():
    length, e, nu = 354., 69000., .33
    sec = square_tube(12., 2.)
    computed = np.linalg.inv(beam.local_stiffness(length, sec, e, nu)[6:, 6:])
    g = e/(2*(1+nu))
    expected = np.diag([length/(e*sec['A']), length**3/(3*e*sec['Iz']), length**3/(3*e*sec['Iy']),
                        length/(g*sec['J']), length/(e*sec['Iy']), length/(e*sec['Iz'])])
    expected[1, 5] = expected[5, 1] = length**2/(2*e*sec['Iz'])
    expected[2, 4] = expected[4, 2] = -length**2/(2*e*sec['Iy'])
    return {'section': '12x12x2 mm longeron', 'length_mm': length,
            'relative_error': np.linalg.norm(computed-expected)/np.linalg.norm(expected),
            'covers': 'axial, approximate Saint-Venant torsion, both Euler bending planes and translation-rotation coupling'}


def main():
    start = time.monotonic()
    files = [FORMULAS, HERE/'root_structure.py', HERE/'spacecraft_model.py', HERE/'design_parameters.json']
    hashes = {str(p.resolve()): sha(p) for p in files}
    mesh = build_mesh()
    k, sec = assemble(mesh)
    baseline = {case: solve_case(mesh, k, case) for case in CASES}
    refinement = []
    for divisions in (1, 2, 4):
        current_mesh = mesh if divisions == 1 else build_mesh(divisions)
        current_k = k if divisions == 1 else assemble(current_mesh)[0]
        for case in CASES:
            result = baseline[case] if divisions == 1 else solve_case(current_mesh, current_k, case)
            relative = np.linalg.norm(result['C_SI']-baseline[case]['C_SI'])/np.linalg.norm(baseline[case]['C_SI'])
            refinement.append({'case': case, 'subdivisions_per_segment': divisions,
                               'element_count': result['element_count'], 'relative_compliance_difference_to_n1': relative,
                               'C_SI': result['C_SI']})
    sensitivity = []
    options = [('E_N_per_mm2', value, {'e': value}) for value in (62100., 69000., 75900.)]
    options += [('longeron_wall_mm', value, {'longeron_wall': value}) for value in (1.5, 2., 2.5)]
    options += [('pillar_wall_mm', value, {'pillar_wall': value}) for value in (1.5, 2., 2.5)]
    options += [('end_frame_thickness_mm', value, {'end_thickness': value}) for value in (5., 6., 8.)]
    for parameter, value, kwargs in options:
        varied_k, _ = assemble(mesh, **kwargs)
        for case in CASES:
            result = solve_case(mesh, varied_k, case)
            sensitivity.append({'case': case, 'parameter': parameter, 'value': value,
                                'C_engineering_diagonal': np.diag(result['C_engineering_mm_rad_per_N_Nm']),
                                'diagonal_ratio_to_baseline': np.diag(result['C_SI'])/np.diag(baseline[case]['C_SI'])})
    free = free_body_check(mesh, k)
    analytical = analytic_cantilever_check()
    verified = analytical['relative_error'] < 1e-10 and free['rigid_mode_count_at_relative_tolerance_1e_minus_9'] == 6
    verified &= all(r['compliance_positive_definite'] and r['normalized_reciprocity_relative_error'] < 1e-8
                    and r['max_force_balance_error_N'] < 1e-6 and r['max_moment_balance_error_Nm'] < 1e-6 for r in baseline.values())
    verified &= max(row['relative_compliance_difference_to_n1'] for row in refinement) < 1e-7
    out = {'model': 'WP03_LONGERON_END_RING_AND_ROOT_COLUMN_EULER_FRAME',
           'status': 'CANDIDATE_LINEAR_SKELETON_SCREEN_NOT_STRENGTH_OR_FLIGHT_VERIFICATION',
           'root_point_S_mm': ROOT, 'bearing_point_S_mm': ROOT + [0, 0, 2.405],
           'material': {'E_GPa': 69., 'nu': .33, 'source': 'CANDIDATE_ALUMINUM_ASSUMPTION_NOT_MEASURED'},
           'load_order': ['Fx_N', 'Fy_N', 'Fz_N', 'Mx_Nm', 'My_Nm', 'Mz_Nm'],
           'response_order_engineering': ['ux_mm', 'uy_mm', 'uz_mm', 'theta_x_rad', 'theta_y_rad', 'theta_z_rad'],
           'matrix_units': {'C_SI': 'row [m,m,m,rad,rad,rad] / column [N,N,N,Nm,Nm,Nm]',
                            'C_engineering_mm_rad_per_N_Nm': 'row [mm,mm,mm,rad,rad,rad] / column [N,N,N,Nm,Nm,Nm]',
                            'root_condensed_K_SI': 'row [N,N,N,Nm,Nm,Nm] / column [m,m,m,rad,rad,rad]',
                            'reaction_matrices': 'rows [Fx,Fy,Fz,Mx,My,Mz] in N/Nm; columns correspond to the six root unit loads',
                            'note': 'C_SI is reciprocal; the mixed mm/rad engineering matrix is not numerically symmetric.'},
           'geometry': {'four_longerons': {'actual_length_mm': 354., 'section_mm': [12., 12., 2.], 'center_y_z_mm': [-107.15, 107.15]},
                        'two_end_ring_x_mm': [-180., 180.], 'end_ring_neutral_side_mm': 214.3,
                        'end_ring_rectangular_section_mm': [6., 12.],
                        'root_upper_crossbeam': {'x_mm': [20., 160.], 'center_z_mm': 101.15, 'length_mm': 202.3, 'section_mm': [14., 12.]},
                        'root_lower_crossbeam': {'x_mm': [20., 160.], 'center_z_mm': -104.15, 'length_mm': 202.3, 'section_mm': [14., 6.]},
                        'four_pillars': {'x_mm': [20., 160.], 'y_mm': [-94.15, 94.15], 'z_range_mm': [-98.15, 95.15], 'section_mm': [14., 14., 2.]},
                        'rigid_offsets': '3 mm rail/end-frame; upper beam endpoint to upper rail [dy=+-6,dz=6]; lower beam endpoint to lower rail [dy=+-6,dz=-3]; pillar end to crossbeam center +-6 mm; root to two upper-crossbeam centers',
                        'independent_node_points_S_mm': mesh['points'],
                        'section_properties_mm2_mm4': sec,
                        'centerline_segments': [{key: row[key] for key in ('name', 'a', 'b', 'section')} for row in mesh['members']]},
           'boundary_cases': baseline, 'free_body': free, 'analytical_check': analytical,
           'mesh_refinement': refinement, 'parameter_sensitivity': sensitivity,
           'boundary_comparison': {'diagonal_C_rear_divided_by_C_ground': np.diag(baseline[CASES[0]]['C_SI'])/np.diag(baseline[CASES[1]]['C_SI'])},
           'unknown_root_series_interface_compliance_SI': None,
           'assumptions_and_omissions': [
               'Root/M3R/170x202.3x6 bridge represented by a rigid distributor; its bending/shear/contact compliance is omitted.',
               'End-frame/longeron and crossbeam/longeron joints are ideal rigid joints with geometric eccentricities; bolt, plug, insert, friction and preload compliance omitted.',
               'WP03 shear webs, decks, covers, equipment, solar brackets and retainers do not contribute stiffness to this skeleton model.',
               'No translational shear deformation, local plate bending, hole reductions, stress concentration, ovalization, warping restraint, material nonlinearities, contact opening or buckling.',
               'Short crossbeam end segments are centerline discretization near ideal junctions, not evidence that Euler theory resolves local joint stresses.',
               'Section sensitivity holds neutral-axis geometry fixed; it is not a regenerated CAD variant.',
               'No physical allowable load, bolt preload, launch-provider boundary compliance or stress margin was specified.',
               'Omitting stiffening plates and omitting interface compliance act in different directions; these results are not claimed rigorous upper/lower bounds on real-assembly stiffness.',
               'Element subdivision agreement verifies this beam formulation and mesh, not beam-model adequacy or hardware correlation.',
               'Rear clamps are a candidate load-introduction idealization, not an approved separation interface. Ground clamps are an independent AIT comparison.',
               'Free-flight has rigid-body modes; no absolute free-body static inverse was computed.'],
           'input_source_sha256': hashes, 'source_files_unchanged_during_run': all(sha(p) == value for p, value in hashes.items()),
           'numerical_implementation_checks_satisfied': bool(verified),
           'scientific_gate_modified': False, 'strength_margin': None, 'hardware_qualified': False,
           'elapsed_s': time.monotonic()-start}
    if not verified:
        raise RuntimeError('Beam numerical check failed; output not issued')
    output = HERE/'results/FRAME_STIFFNESS_SCREEN.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(beam.serialize(out), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(beam.serialize({'output': str(output), 'elapsed_s': out['elapsed_s'],
                                    'diagonal_compliances': {case: np.diag(value['C_engineering_mm_rad_per_N_Nm']) for case, value in baseline.items()},
                                    'free_body_modes': free['rigid_mode_count_at_relative_tolerance_1e_minus_9'],
                                    'numerical_checks': bool(verified)}), indent=2))


if __name__ == '__main__':
    main()
