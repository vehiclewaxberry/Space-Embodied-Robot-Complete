"""Independent small-displacement beam-frame compliance of the WP01 GSE root coupon.

Units inside assembly: N, mm, radians. No CAD kernel, stress allowable, or
flight-fixed boundary is used. The JSON keeps raw/SI/engineering matrix units.
"""
from pathlib import Path
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import numpy as np

HERE = Path(__file__).resolve().parent
WP01 = HERE.parent / 'service_robot_wp01_20260905'
ROOT = HERE.parents[1]
URDF = ROOT / '20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
P = json.loads((WP01 / 'design_parameters.json').read_text(encoding='utf-8'))
ROOT_POINT = np.array([*P['root_xy_mm'], P['bus_mm'][2]/2 + P['m3r_B_thickness_mm']])
LO = -P['bus_mm'][2]/2 + P['longeron_outer_mm'] + 3
HI = P['bus_mm'][2]/2 - 18
BEAM_Z = P['bus_mm'][2]/2 - 12
REFERENCE_LENGTH_M = 0.1


def skew(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def rigid_offset(r):
    """u_slave = u_master + theta_master cross r; same rotation."""
    h = np.eye(6)
    h[:3, 3:] = -skew(r)
    return h


def sections(wall=2.):
    b = 14.
    area = b*b - (b-2*wall)**2
    inertia = (b**4 - (b-2*wall)**4)/12
    # Bredt closed-cell median-line approximation; not exact thick-wall torsion.
    j_tube = wall * (b-wall)**3
    w, h = 14., 12.
    j_beam = w*h**3/3 * (1-.63*h/w+.052*(h/w)**5)
    return {'column': dict(A=area, Iy=inertia, Iz=inertia, J=j_tube),
            'crossbeam': dict(A=w*h, Iy=w*h**3/12, Iz=h*w**3/12, J=j_beam)}


def local_stiffness(length, sec, e, nu):
    l = length
    g = e/(2*(1+nu))
    k = np.zeros((12, 12))
    for indices, value in [([0, 6], e*sec['A']/l), ([3, 9], g*sec['J']/l)]:
        k[np.ix_(indices, indices)] += value*np.array([[1, -1], [-1, 1]])
    bending = np.array([[12, 6*l, -12, 6*l],
                        [6*l, 4*l*l, -6*l, 2*l*l],
                        [-12, -6*l, 12, -6*l],
                        [6*l, 2*l*l, -6*l, 4*l*l]])
    k[np.ix_([1, 5, 7, 11], [1, 5, 7, 11])] += e*sec['Iz']/l**3*bending
    signs = np.diag([1, -1, 1, -1])
    k[np.ix_([2, 4, 8, 10], [2, 4, 8, 10])] += e*sec['Iy']/l**3*(signs@bending@signs)
    return k


def element_stiffness(a, b, sec, e, nu):
    ex = (b-a)/np.linalg.norm(b-a)
    reference = np.array([1., 0., 0.])
    if abs(ex@reference) > .9:
        reference = np.array([0., 1., 0.])
    ey = reference-ex*(reference@ex)
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    rotation = np.vstack([ex, ey, ez])
    t = np.zeros((12, 12))
    for start in [0, 3, 6, 9]:
        t[start:start+3, start:start+3] = rotation
    return t.T@local_stiffness(np.linalg.norm(b-a), sec, e, nu)@t


def solve_frame(e=69000., nu=.33, wall=2., subdivisions=1):
    sec = sections(wall)
    # Independent blocks: root, four beam-end stations, then internal mesh nodes.
    free_blocks = 5
    endpoints = []
    bases = []
    for ix, x in enumerate([ROOT_POINT[0]-70, ROOT_POINT[0]+70]):
        center = np.array([x, 0., BEAM_Z])
        center_map = (0, rigid_offset(center-ROOT_POINT))
        for iy, y in enumerate([-94.15, 94.15]):
            block = 1+ix*2+iy
            low, high, beam_end = [np.array([x, y, z]) for z in [LO, HI, BEAM_Z]]
            bases.append(low)
            endpoints.append(dict(a=low, b=high, map_a=None,
                                  map_b=(block, rigid_offset(high-beam_end)), section='column', base=ix*2+iy))
            endpoints.append(dict(a=beam_end, b=center, map_a=(block, np.eye(6)),
                                  map_b=center_map, section='crossbeam', base=None))
    elements = []
    for item in endpoints:
        nodes = [(item['a'], item['map_a'])]
        for n in range(1, subdivisions):
            point = item['a']+(item['b']-item['a'])*n/subdivisions
            nodes.append((point, (free_blocks, np.eye(6))))
            free_blocks += 1
        nodes.append((item['b'], item['map_b']))
        for n in range(subdivisions):
            elements.append(dict(a=nodes[n][0], b=nodes[n+1][0],
                                 map_a=nodes[n][1], map_b=nodes[n+1][1], section=item['section'],
                                 base=item['base'] if n == 0 else None))
    ndof = free_blocks*6
    stiffness = np.zeros((ndof, ndof))
    for element in elements:
        transform = np.zeros((12, ndof))
        for offset, mapping in [(0, element['map_a']), (6, element['map_b'])]:
            if mapping is not None:
                block, matrix = mapping
                transform[offset:offset+6, block*6:block*6+6] = matrix
        ke = element_stiffness(element['a'], element['b'], sec[element['section']], e, nu)
        stiffness += transform.T@ke@transform
        element.update(ke=ke, transform=transform)
    loads = np.zeros((ndof, 6))
    loads[:6, :] = np.eye(6)  # 1 N or 1 N mm in internal units.
    displacement = np.linalg.solve(stiffness, loads)
    c_raw = displacement[:6, :]
    load_to_nmm = np.diag([1, 1, 1, 1000, 1000, 1000])
    out_to_si = np.diag([.001, .001, .001, 1, 1, 1])
    c_si = out_to_si@c_raw@load_to_nmm
    reactions = np.zeros((4, 6, 6))
    for element in elements:
        if element['base'] is not None:
            f = element['ke']@element['transform']@displacement@load_to_nmm
            reactions[element['base'], :, :] = f[:6, :]
    balance = np.zeros((6, 6))
    for i, point in enumerate(bases):
        balance[:3] += reactions[i, :3]
        balance[3:] += reactions[i, 3:] + skew(point-ROOT_POINT)@reactions[i, :3]
    balance += load_to_nmm
    balance[3:] /= 1000
    reactions[:, 3:, :] /= 1000
    scale = np.diag([1, 1, 1, REFERENCE_LENGTH_M, REFERENCE_LENGTH_M, REFERENCE_LENGTH_M])
    c_normalized = scale@c_si@scale
    eigenvalues = np.linalg.eigvalsh((c_normalized+c_normalized.T)/2)
    return dict(C_raw_mm_N_Nmm=c_raw, C_SI=c_si,
                C_engineering_mm_rad_per_N_Nm=c_raw@load_to_nmm,
                normalized_eigenvalues_m_per_N=eigenvalues,
                max_reciprocity_absolute_SI=np.max(np.abs(c_si-c_si.T)),
                normalized_symmetry_relative=np.linalg.norm(c_normalized-c_normalized.T)/np.linalg.norm(c_normalized),
                positive_definite=bool(np.all(eigenvalues>0)),
                support_reactions_N_Nm=reactions, reaction_balance_residual_N_Nm=balance,
                max_force_balance_error_N=np.max(np.abs(balance[:3])),
                max_moment_balance_error_Nm=np.max(np.abs(balance[3:])),
                number_elements=len(elements), independent_dof=ndof,
                support_points_S_mm=bases, section_properties=sec,
                E_N_per_mm2=e, nu=nu, wall_mm=wall, subdivisions_per_member=subdivisions)


def analytical_column_check():
    l = HI-LO
    sec = sections()['column']
    e, nu = 69000., .33
    g = e/(2*(1+nu))
    computed = np.linalg.inv(local_stiffness(l, sec, e, nu)[6:, 6:])
    target = np.diag([l/(e*sec['A']), l**3/(3*e*sec['Iz']), l**3/(3*e*sec['Iy']),
                      l/(g*sec['J']), l/(e*sec['Iy']), l/(e*sec['Iz'])])
    target[1, 5] = target[5, 1] = l*l/(2*e*sec['Iz'])
    target[2, 4] = target[4, 2] = -l*l/(2*e*sec['Iy'])
    return dict(description='Isolated cantilever with free tip: exact axial/torsion/two bending planes',
                computed_raw=computed, closed_form_raw=target,
                relative_Frobenius_error=np.linalg.norm(computed-target)/np.linalg.norm(target),
                max_absolute_error=np.max(np.abs(computed-target)))


def rotation_rpy(rpy):
    r, p, y = rpy
    cx, sx, cy, sy, cz, sz = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])


def digital_gravity(c_si):
    tree = ET.parse(URDF).getroot()
    rows = []
    for state in ['stowed', 'work']:
        frames = {'base_link': np.eye(4)}
        frames['base_link'][:3, 3] = ROOT_POINT/1000
        count = 0
        for joint in tree.findall('joint'):
            origin = joint.find('origin')
            t = np.eye(4)
            t[:3, :3] = rotation_rpy([float(x) for x in origin.get('rpy').split()])
            t[:3, 3] = [float(x) for x in origin.get('xyz').split()]
            motion = np.eye(4)
            if joint.get('type') == 'revolute':
                axis = np.array([float(x) for x in joint.find('axis').get('xyz').split()])
                angle = np.deg2rad(P['states'][state]['q_deg'][count]); count += 1
                a = skew(axis)
                motion[:3, :3] = np.eye(3)+math.sin(angle)*a+(1-math.cos(angle))*(a@a)
            elif joint.get('type') == 'prismatic':
                axis = np.array([float(x) for x in joint.find('axis').get('xyz').split()])
                motion[:3, 3] = axis*P['states'][state]['finger_mm']/1000
            frames[joint.find('child').get('link')] = frames[joint.find('parent').get('link')]@t@motion
        mass = 0.; weighted = np.zeros(3)
        for link in tree.findall('link'):
            inertial = link.find('inertial')
            m = float(inertial.find('mass').get('value'))
            local = np.r_[[float(x) for x in inertial.find('origin').get('xyz').split()], 1.]
            weighted += m*(frames[link.get('name')]@local)[:3]
            mass += m
        center = weighted/mass
        force = np.array([0., 0., -mass*9.80665])
        moment = np.cross(center-ROOT_POINT/1000, force)
        wrench = np.r_[force, moment]
        rows.append(dict(state=state, digital_arm_mass_kg=mass, digital_COM_S_m=center,
                         force_N=force, moment_about_root_Nm=moment,
                         root_wrench_N_Nm=wrench, root_displacement_m_rad=c_si@wrench,
                         load_assumption='EARTH_1G_ALONG_MINUS_S_Z_ARM_ONLY_STATIC_NO_SADDLE_CONTACT',
                         status='ILLUSTRATIVE_DIGITAL_WEIGHT_CASE_NOT_ALLOWED_DESIGN_LOAD'))
    return rows


def serialize(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k:serialize(v) for k,v in value.items()}
    if isinstance(value, list): return [serialize(v) for v in value]
    return value


def main():
    baseline = solve_frame()
    refinements = []
    for n in [1, 2, 4]:
        value = baseline if n == 1 else solve_frame(subdivisions=n)
        refinements.append(dict(subdivisions=n, elements=value['number_elements'],
                                C_SI=value['C_SI'],
                                relative_Frobenius_difference=np.linalg.norm(value['C_SI']-baseline['C_SI'])/np.linalg.norm(baseline['C_SI'])))
    sensitivities = []
    for factor in [.9, 1., 1.1]:
        value = solve_frame(e=69000*factor)
        sensitivities.append(dict(parameter='E', E_GPa=69*factor, C_engineering_diagonal=np.diag(value['C_engineering_mm_rad_per_N_Nm']),
                                  diagonal_ratio_to_baseline=np.diag(value['C_SI'])/np.diag(baseline['C_SI'])))
    for wall in [1.5, 2., 2.5]:
        value = solve_frame(wall=wall)
        sensitivities.append(dict(parameter='column_wall_mm', value=wall, C_engineering_diagonal=np.diag(value['C_engineering_mm_rad_per_N_Nm']),
                                  diagonal_ratio_to_baseline=np.diag(value['C_SI'])/np.diag(baseline['C_SI'])))
    connection = []
    for alpha in [0., .1, 1., 10.]:
        added = alpha*np.diag(np.diag(baseline['C_SI']))
        total = baseline['C_SI']+added
        connection.append(dict(alpha=alpha, C_connection_SI=added, C_total_SI=total,
                               meaning='HYPOTHETICAL_SERIES_DIAGONAL_COMPLIANCE_ALPHA_TIMES_BASELINE_DIAGONAL; NOT_MEASURED_OR_SELECTED_CONNECTION'))
    bearing_offset = np.array([0., 0., P['nominal_base_bearing_local_z_mm']/1000])
    h = rigid_offset(bearing_offset)
    transformed = h@baseline['C_SI']@h.T
    out = dict(model='FOUR_COLUMN_TWO_CROSSBEAM_EULER_BERNOULLI_GSE_COUPON',
               root_point_S_mm=ROOT_POINT, bearing_point_S_mm=ROOT_POINT+np.array([0.,0.,2.405]),
               load_order=['Fx_N','Fy_N','Fz_N','Mx_Nm','My_Nm','Mz_Nm'],
               response_order=['ux_mm','uy_mm','uz_mm','theta_x_rad','theta_y_rad','theta_z_rad'],
               matrix_units=dict(C_SI_rows=['m','m','m','rad','rad','rad'], C_SI_columns=['N','N','N','N*m','N*m','N*m'],
                                 C_engineering_rows=['mm','mm','mm','rad','rad','rad'], C_engineering_columns=['N','N','N','N*m','N*m','N*m'],
                                 note='Each entry has row displacement unit divided by column applied-load unit. Engineering matrix is not numerically symmetric; canonical SI matrix is.'),
               material=dict(E_GPa=69., nu=.33, classification='CANDIDATE_ALUMINUM_ASSUMPTION_NOT_MEASURED'),
               geometry=dict(column_top_z_mm=HI,column_bottom_z_mm=LO,column_length_mm=HI-LO,
                             beam_neutral_axis_z_mm=BEAM_Z,column_top_to_beam_axis_rigid_offset_mm=BEAM_Z-HI,
                             root_plate_size_mm=[170.,202.3,6.],beam_section_mm=[14.,12.],
                             beam_effective_support_span_mm=188.3,beam_full_length_mm=202.3,
                             no_load_overhang_each_end_mm=7., column_outer_mm=14.,column_wall_mm=2.),
               baseline=baseline, analytical_column_check=analytical_column_check(), mesh_refinement=refinements,
               parameter_sensitivity=sensitivities, unknown_series_connection_sensitivity=connection,
               conditional_bearing_transfer=dict(r_root_to_bearing_m=bearing_offset,
                                                 H_displacement=h, wrench_rule='w_root = H.T @ w_bearing: M_root=M_bearing+r_cross_F',
                                                 compliance_rule='C_bearing=H@C_root@H.T', C_bearing_SI=transformed,
                                                 condition='RIGID_ROOT_TO_BEARING_ONLY; M3R_AND_PLATE_FLEXIBILITY_NOT_INCLUDED'),
               digital_1g_examples=digital_gravity(baseline['C_SI']),
               unknown_physical_series_compliance_SI=None, saddle_reactions=None,
               scope='LINEAR_BEAM_STIFFNESS_SCREEN_ONLY; FOUR_BOTTOM_ENDS_IDEALLY_CLAMPED_GSE_COUPON; NOT_FLIGHT_BOUNDARY; NO_STRESS_OR_STRENGTH_MARGIN',
               omitted=['M3R and six-mm root-plate bending','plate/beam joints and fastener/contact/preload compliance','lower crossbeam/longeron/end-frame and GSE fixture flexibility','beam transverse shear and torsion warping','M6 hole/local bearing/net-section flexibility','local buckling, geometric nonlinearity, material nonlinearity','thermal-vacuum and dynamic response','hardware metrology and root as-installed state'],
               source_files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [WP01/'design_parameters.json',WP01/'service_robot_common.py',URDF]},
               references=[dict(title='TU Delft: Local stiffness matrix Euler-Bernoulli element',url='https://oit.tudelft.nl/CIEM5000/2026/lecture1/other_elements.html'),
                           dict(title='OpenSees: Elastic Beam Column Element',url='https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/elasticBeamColumn.html')])
    (HERE/'results').mkdir(exist_ok=True)
    (HERE/'results/ROOT_COMPLIANCE.json').write_text(json.dumps(serialize(out),indent=2),encoding='utf-8')
    print(json.dumps(serialize(dict(C_engineering=baseline['C_engineering_mm_rad_per_N_Nm'],
                                    symmetry_relative=baseline['normalized_symmetry_relative'],
                                    positive_definite=baseline['positive_definite'],force_balance_N=baseline['max_force_balance_error_N'],
                                    moment_balance_Nm=baseline['max_moment_balance_error_Nm'],analytic=out['analytical_column_check']['relative_Frobenius_error'],
                                    refinement4=refinements[-1]['relative_Frobenius_difference'],gravity=out['digital_1g_examples'])),indent=2))


if __name__ == '__main__': main()
