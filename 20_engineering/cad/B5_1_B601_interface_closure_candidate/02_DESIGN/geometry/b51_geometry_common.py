"""B5.1 bridge-adapter and stow-saddle engineering-candidate geometry.

Coordinate convention
---------------------
All geometry is authored in the spacecraft frame ``CS_S`` in millimetres.
``+X`` points outboard through the B601 task-face interface.  The spacecraft
primary-structure task face terminates at ``X = 183.0``.  Every physical
candidate in this module starts at or above that plane so it cannot overlap
the admitted primary frame volume ``X <= 183.0``.

Authority boundary
------------------
Only values explicitly listed in ``ADMITTED`` are frozen/admitted inputs.
Every other section or feature size is an ``ENGINEERING_CANDIDATE_HOLD``.
The generated bodies are therefore geometry candidates, not released
hardware, mass truth, manufacturing definition, or structural qualification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from build123d import Box, Color, Compound, Cylinder, Plane, Pos, Rot, Vector


CLAIM_LIMIT = (
    "ENGINEERING_CANDIDATE_HOLD;NO_MANUFACTURING_AUTHORITY;"
    "NO_FLIGHT_AUTHORITY;NO_MASS_AUTHORITY;NO_STRENGTH_AUTHORITY"
)

ADMITTED = {
    "task_face_x_mm": 183.0,
    "mount_plane_x_mm": 198.0,
    "installation_reference_yz_mm": (160.0, 160.0),
    "central_passage_diameter_mm": 100.0,
    "longeron_center_abs_yz_mm": 105.65,
    "clocking_candidate_deg": 25.0,
    "main_contact_x_window_mm": (10.0, 60.0),
    "main_contact_z_bottom_mm": 234.77,
    "main_contact_y_window_mm": (-66.48, 92.89),
    "grip_contact_x_window_mm": (-100.0, -40.0),
    "grip_contact_z_bottom_mm": 253.80,
    "grip_contact_y_window_mm": (-27.25, 104.24),
}

# These are deliberately centralized and carry no qualification beyond being a
# coherent first engineering candidate.  They are not inferred requirements.
CANDIDATE_HOLD = {
    "adapter_top_flange_outer_diameter_mm": 140.0,
    "adapter_top_flange_thickness_mm": 2.0,
    "adapter_pedestal_outer_diameter_mm": 130.0,
    "adapter_pedestal_length_mm": 5.0,
    "adapter_crossmember_outer_span_mm": 160.0,
    "adapter_crossmember_inner_opening_mm": 116.0,
    "adapter_aft_frame_thickness_x_mm": 3.0,
    "adapter_forward_frame_thickness_x_mm": 3.0,
    "adapter_interface_web_thickness_x_mm": 2.0,
    "adapter_interface_shoe_yz_mm": 15.0,
    "adapter_diagonal_web_width_mm": 10.0,
    "clocking_witness_tab_radial_center_mm": 70.0,
    "clocking_witness_tab_tangential_mm": 18.0,
    "clocking_witness_tab_radial_mm": 10.0,
    "saddle_base_tie_height_mm": 4.0,
    "saddle_triangle_frame_thickness_x_mm": 6.0,
    "saddle_triangle_strut_width_mm": 10.0,
    "saddle_triangle_node_height_mm": 8.0,
    "saddle_top_cap_height_mm": 6.0,
    "saddle_contact_pad_thickness_mm": 3.0,
    "saddle_contact_pad_y_allowance_each_side_mm": 1.0,
    "saddle_guide_clearance_y_mm": 2.0,
    "saddle_guide_nominal_thickness_y_mm": 8.0,
    "saddle_guide_height_mm": 24.0,
    "saddle_hdrm_envelope_diameter_mm": 16.0,
    "saddle_hdrm_envelope_length_mm": 36.0,
}


COL_STRUCTURE = Color(0.27, 0.34, 0.44, 1.0)
COL_STRUCTURE_ALT = Color(0.18, 0.48, 0.62, 1.0)
COL_PAD = Color(0.18, 0.68, 0.38, 1.0)
COL_GUIDE = Color(0.88, 0.49, 0.14, 1.0)
COL_HOLD = Color(0.78, 0.16, 0.20, 0.42)


def _label(shape, label: str, color: Color, material: str = CLAIM_LIMIT):
    """Attach user-facing traceability metadata to one exported body."""

    shape.label = label
    shape.color = color
    shape.material = material
    return shape


def _x_cylinder(x_min: float, x_max: float, radius: float):
    """Create a cylinder whose axis is +X and whose end faces are exact X planes."""

    return (
        Plane(
            origin=Vector((x_min + x_max) / 2.0, 0.0, 0.0),
            z_dir=Vector(1.0, 0.0, 0.0),
            x_dir=Vector(0.0, 1.0, 0.0),
        ).location
        * Cylinder(radius, x_max - x_min)
    )


def _annulus_x(x_min: float, x_max: float, outer_radius: float, inner_radius: float):
    """Create an X-axis annulus with an overshooting inner cutting tool."""

    outer = _x_cylinder(x_min, x_max, outer_radius)
    inner = _x_cylinder(x_min - 1.0, x_max + 1.0, inner_radius)
    return outer - inner


def _rectangular_frame_x(
    x_min: float,
    x_max: float,
    outer_span: float,
    inner_opening: float,
):
    """Closed YZ rectangular frame, fused as one candidate member."""

    member = (outer_span - inner_opening) / 2.0
    offset = (outer_span + inner_opening) / 4.0
    x_center = (x_min + x_max) / 2.0
    x_size = x_max - x_min

    top = Pos(x_center, 0.0, offset) * Box(x_size, outer_span, member)
    bottom = Pos(x_center, 0.0, -offset) * Box(x_size, outer_span, member)
    left = Pos(x_center, offset, 0.0) * Box(x_size, member, inner_opening)
    right = Pos(x_center, -offset, 0.0) * Box(x_size, member, inner_opening)
    return top + bottom + left + right


def _beam_yz(
    x_center: float,
    p0_yz: tuple[float, float],
    p1_yz: tuple[float, float],
    x_width: float,
    transverse_width: float,
    overlap_mm: float = 1.0,
):
    """Rectangular beam between two YZ points, with +X as local width axis."""

    y0, z0 = p0_yz
    y1, z1 = p1_yz
    dy, dz = y1 - y0, z1 - z0
    length = math.hypot(dy, dz)
    if length <= 0.0:
        raise ValueError("beam endpoints must be distinct")
    uy, uz = dy / length, dz / length
    center = Vector(x_center, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
    plane = Plane(
        origin=center,
        z_dir=Vector(0.0, uy, uz),
        x_dir=Vector(1.0, 0.0, 0.0),
    )
    return plane.location * Box(
        x_width,
        transverse_width,
        length + 2.0 * overlap_mm,
    )


def build_bridge_adapter() -> Compound:
    """Build the interface-closed bridge-adapter candidate.

    Axial segmentation prevents inter-part volume overlap:

    ``interface webs [183,185] -> aft frame [185,188] -> pedestal [188,193]
    -> forward frame [193,196] -> top flange [196,198]``.

    The four interface-web minimum-X faces are exactly ``X=183`` and therefore
    touch, but do not enter, the admitted spacecraft frame volume.
    """

    task_x = ADMITTED["task_face_x_mm"]
    mount_x = ADMITTED["mount_plane_x_mm"]
    longeron = ADMITTED["longeron_center_abs_yz_mm"]
    bore_r = ADMITTED["central_passage_diameter_mm"] / 2.0
    outer_span = CANDIDATE_HOLD["adapter_crossmember_outer_span_mm"]
    inner_opening = CANDIDATE_HOLD["adapter_crossmember_inner_opening_mm"]

    x_web = (task_x, task_x + CANDIDATE_HOLD["adapter_interface_web_thickness_x_mm"])
    x_aft = (
        x_web[1],
        x_web[1] + CANDIDATE_HOLD["adapter_aft_frame_thickness_x_mm"],
    )
    x_ped = (x_aft[1], x_aft[1] + CANDIDATE_HOLD["adapter_pedestal_length_mm"])
    x_fwd = (
        x_ped[1],
        x_ped[1] + CANDIDATE_HOLD["adapter_forward_frame_thickness_x_mm"],
    )
    x_flange = (
        mount_x - CANDIDATE_HOLD["adapter_top_flange_thickness_mm"],
        mount_x,
    )
    if abs(x_fwd[1] - x_flange[0]) > 1.0e-9:
        raise ValueError("candidate axial stack no longer closes at the mount plane")

    children = []

    # Four independently traceable shoes/webs.  Each stays outside the D100
    # reserve and terminates on the known longeron-reference corner region.
    shoe_yz = CANDIDATE_HOLD["adapter_interface_shoe_yz_mm"]
    web_width = CANDIDATE_HOLD["adapter_diagonal_web_width_mm"]
    for sy in (-1, 1):
        for sz in (-1, 1):
            x_center = sum(x_web) / 2.0
            shoe = Pos(x_center, sy * longeron, sz * longeron) * Box(
                x_web[1] - x_web[0],
                shoe_yz,
                shoe_yz,
            )
            diagonal = _beam_yz(
                x_center,
                (sy * longeron, sz * longeron),
                (sy * 78.0, sz * 78.0),
                x_web[1] - x_web[0],
                web_width,
                overlap_mm=1.0,
            )
            web = shoe + diagonal
            quadrant = f"{'P' if sy > 0 else 'N'}Y_{'P' if sz > 0 else 'N'}Z"
            children.append(
                _label(
                    web,
                    f"B51_INTERFACE_SHOE_AND_WEB_{quadrant}_CANDIDATE_HOLD",
                    COL_STRUCTURE_ALT,
                )
            )

    aft_frame = _rectangular_frame_x(*x_aft, outer_span, inner_opening)
    children.append(
        _label(
            aft_frame,
            "B51_AFT_CROSSMEMBER_FRAME_CANDIDATE_HOLD",
            COL_STRUCTURE,
        )
    )

    pedestal = _annulus_x(
        *x_ped,
        CANDIDATE_HOLD["adapter_pedestal_outer_diameter_mm"] / 2.0,
        bore_r,
    )
    children.append(
        _label(
            pedestal,
            "B51_SHORT_CENTER_PEDESTAL_D130_D100_CANDIDATE_HOLD",
            COL_STRUCTURE_ALT,
        )
    )

    forward_frame = _rectangular_frame_x(*x_fwd, outer_span, inner_opening)
    children.append(
        _label(
            forward_frame,
            "B51_FORWARD_CROSSMEMBER_FRAME_CANDIDATE_HOLD",
            COL_STRUCTURE,
        )
    )

    flange = _annulus_x(
        *x_flange,
        CANDIDATE_HOLD["adapter_top_flange_outer_diameter_mm"] / 2.0,
        bore_r,
    )
    # Four integral witness tabs make the 25-degree installation clock visible.
    # They are not bolt pads and do not encode a released hole pattern.
    clock = ADMITTED["clocking_candidate_deg"]
    r_tab = CANDIDATE_HOLD["clocking_witness_tab_radial_center_mm"]
    tab_t = CANDIDATE_HOLD["clocking_witness_tab_tangential_mm"]
    tab_r = CANDIDATE_HOLD["clocking_witness_tab_radial_mm"]
    x_mid = sum(x_flange) / 2.0
    for k in range(4):
        angle = clock + 90.0 * k
        tab = (
            Pos(x_mid, 0.0, 0.0)
            * Rot(angle, 0.0, 0.0)
            * Pos(0.0, r_tab, 0.0)
            * Box(x_flange[1] - x_flange[0], tab_t, tab_r)
        )
        flange = flange + tab
    children.append(
        _label(
            flange,
            "B51_TOP_FLANGE_D140_D100_CLOCK25_WITNESS_CANDIDATE_HOLD",
            COL_STRUCTURE_ALT,
        )
    )

    assembly = Compound(
        children=children,
        label="B51_BRIDGE_ADAPTER_ENGINEERING_CANDIDATE_HOLD",
    )
    assembly.material = CLAIM_LIMIT
    return assembly


@dataclass(frozen=True)
class SaddleContract:
    tag: str
    x_window: tuple[float, float]
    y_window: tuple[float, float]
    z_bottom: float
    source_status: str


MAIN_SADDLE = SaddleContract(
    tag="G07_MAIN",
    x_window=ADMITTED["main_contact_x_window_mm"],
    y_window=ADMITTED["main_contact_y_window_mm"],
    z_bottom=ADMITTED["main_contact_z_bottom_mm"],
    source_status="CONTACT_QUALIFICATION_HOLD",
)

GRIP_SADDLE = SaddleContract(
    tag="G08_GRIP",
    x_window=ADMITTED["grip_contact_x_window_mm"],
    y_window=ADMITTED["grip_contact_y_window_mm"],
    z_bottom=ADMITTED["grip_contact_z_bottom_mm"],
    source_status="CHAIN_DERIVED_AND_CONTACT_QUALIFICATION_HOLD",
)


def _triangle_frame(contract: SaddleContract, x_station: float):
    """One open triangular frame, exported as one fused body."""

    longeron = ADMITTED["longeron_center_abs_yz_mm"]
    base_z = 113.15 + CANDIDATE_HOLD["saddle_base_tie_height_mm"]
    pad_t = CANDIDATE_HOLD["saddle_contact_pad_thickness_mm"]
    pad_bottom = contract.z_bottom - pad_t
    frame_x = CANDIDATE_HOLD["saddle_triangle_frame_thickness_x_mm"]
    strut_w = CANDIDATE_HOLD["saddle_triangle_strut_width_mm"]
    node_h = CANDIDATE_HOLD["saddle_triangle_node_height_mm"]
    top_h = CANDIDATE_HOLD["saddle_top_cap_height_mm"]
    y_lo, y_hi = contract.y_window
    allowance = CANDIDATE_HOLD["saddle_contact_pad_y_allowance_each_side_mm"]
    cap_lo, cap_hi = y_lo - allowance, y_hi + allowance
    cap_center_y = (cap_lo + cap_hi) / 2.0

    # Bottom nodes start exactly on the base-tie top face.
    left_node = Pos(x_station, -longeron, base_z + node_h / 2.0) * Box(
        frame_x,
        15.0,
        node_h,
    )
    right_node = Pos(x_station, longeron, base_z + node_h / 2.0) * Box(
        frame_x,
        15.0,
        node_h,
    )

    top_cap = Pos(
        x_station,
        cap_center_y,
        pad_bottom - top_h / 2.0,
    ) * Box(frame_x, cap_hi - cap_lo, top_h)

    left_strut = _beam_yz(
        x_station,
        (-longeron, base_z + node_h - 1.0),
        (cap_lo + 12.0, pad_bottom - top_h + 1.0),
        frame_x,
        strut_w,
        overlap_mm=2.0,
    )
    right_strut = _beam_yz(
        x_station,
        (longeron, base_z + node_h - 1.0),
        (cap_hi - 12.0, pad_bottom - top_h + 1.0),
        frame_x,
        strut_w,
        overlap_mm=2.0,
    )
    return left_node + right_node + top_cap + left_strut + right_strut


def build_saddle(contract: SaddleContract) -> Compound:
    """Build one independent two-frame triangular stow saddle.

    Only two narrow base-tie shoes contact the longeron reference strips.
    No central deck, equipment plate, or skin is assigned as a primary load
    path.  Contact-pad shape, guide clearances, HDRM envelope, preload, and
    material all remain HOLD.
    """

    x_lo, x_hi = contract.x_window
    y_lo, y_hi = contract.y_window
    longeron = ADMITTED["longeron_center_abs_yz_mm"]
    base_h = CANDIDATE_HOLD["saddle_base_tie_height_mm"]
    pad_t = CANDIDATE_HOLD["saddle_contact_pad_thickness_mm"]
    allowance = CANDIDATE_HOLD["saddle_contact_pad_y_allowance_each_side_mm"]
    guide_gap = CANDIDATE_HOLD["saddle_guide_clearance_y_mm"]
    guide_t_nom = CANDIDATE_HOLD["saddle_guide_nominal_thickness_y_mm"]
    guide_h = CANDIDATE_HOLD["saddle_guide_height_mm"]
    base_z0 = 113.15

    children = []
    x_center = (x_lo + x_hi) / 2.0
    x_span = x_hi - x_lo

    # Two named load-introduction shoes; the entire central deck span is open.
    for sy in (-1, 1):
        shoe = Pos(
            x_center,
            sy * longeron,
            base_z0 + base_h / 2.0,
        ) * Box(x_span, 15.0, base_h)
        children.append(
            _label(
                shoe,
                f"B51_{contract.tag}_LONGERON_SHOE_{'P' if sy > 0 else 'N'}Y_CANDIDATE_HOLD",
                COL_STRUCTURE,
            )
        )

    # Ten millimetres keeps both the 6 mm structural frame and the nominal
    # radius-8 HDRM reservation fully inside the admitted X contact window.
    frame_margin = 10.0
    frame_stations = (x_lo + frame_margin, x_hi - frame_margin)
    for station, station_tag in zip(frame_stations, ("AFT", "FORWARD")):
        frame = _triangle_frame(contract, station)
        children.append(
            _label(
                frame,
                f"B51_{contract.tag}_{station_tag}_TRIANGULAR_FRAME_CANDIDATE_HOLD",
                COL_STRUCTURE_ALT,
            )
        )

    pad_lo, pad_hi = y_lo - allowance, y_hi + allowance
    pad = Pos(
        x_center,
        (pad_lo + pad_hi) / 2.0,
        contract.z_bottom - pad_t / 2.0,
    ) * Box(x_span, pad_hi - pad_lo, pad_t)
    children.append(
        _label(
            pad,
            f"B51_{contract.tag}_REPLACEABLE_CONTACT_PAD_QUALIFICATION_HOLD",
            COL_PAD,
        )
    )

    # Low guides remain outside the measured Y window and within the known
    # +/-113.15 outer envelope.  Their interaction with the moving arm remains
    # a collision and tolerance HOLD.
    envelope_y = 113.15
    guide_ranges = (
        (max(-envelope_y, y_lo - guide_gap - guide_t_nom), y_lo - guide_gap, "N"),
        (y_hi + guide_gap, min(envelope_y, y_hi + guide_gap + guide_t_nom), "P"),
    )
    for g_lo, g_hi, side in guide_ranges:
        if g_hi - g_lo < 3.0:
            continue
        guide = Pos(
            x_center,
            (g_lo + g_hi) / 2.0,
            contract.z_bottom + guide_h / 2.0,
        ) * Box(x_span, g_hi - g_lo, guide_h)
        children.append(
            _label(
                guide,
                f"B51_{contract.tag}_LOW_GUIDE_{side}Y_CLEARANCE_HOLD",
                COL_GUIDE,
            )
        )

    # One non-physical HDRM reservation envelope is centred between the two
    # triangular frames and terminates on the pad lower face.  The visual-review
    # repair from the first candidate removed two frame-coincident cylinders:
    # a keepout may not silently occupy candidate structure.  This establishes
    # only a packaging/interface question, not a selected release mechanism.
    hdrm_d = CANDIDATE_HOLD["saddle_hdrm_envelope_diameter_mm"]
    hdrm_l = CANDIDATE_HOLD["saddle_hdrm_envelope_length_mm"]
    yc = (y_lo + y_hi) / 2.0
    envelope = (
        Plane(
            origin=Vector(
                x_center,
                yc,
                contract.z_bottom - pad_t - hdrm_l / 2.0,
            ),
            z_dir=Vector(0.0, 0.0, 1.0),
        ).location
        * Cylinder(hdrm_d / 2.0, hdrm_l)
    )
    children.append(
        _label(
            envelope,
            f"B51_{contract.tag}_HDRM_CENTER_ENVELOPE_NON_PHYSICAL_HOLD",
            COL_HOLD,
            material="NON_PHYSICAL_KEEP_OUT;HDRM_TYPE_PRELOAD_RELEASE_HOLD",
        )
    )

    assembly = Compound(
        children=children,
        label=f"B51_{contract.tag}_DOUBLE_TRIANGLE_SADDLE_ENGINEERING_CANDIDATE_HOLD",
    )
    assembly.material = f"{CLAIM_LIMIT};SOURCE_STATUS={contract.source_status}"
    return assembly


def assert_central_passage_clear(shape, diameter_mm: float = 100.0) -> None:
    """BREP-check that the X-axis D100 probe has zero common volume.

    The probe deliberately spans beyond the adapter's axial limits.  A volume
    above numerical tolerance would mean the reserved cable passage is blocked.
    """

    probe = _x_cylinder(
        ADMITTED["task_face_x_mm"] - 1.0,
        ADMITTED["mount_plane_x_mm"] + 1.0,
        diameter_mm / 2.0,
    )
    overlap = shape & probe
    if overlap.volume > 1.0e-6:
        raise ValueError(
            f"central passage blocked by {overlap.volume:.9f} mm^3"
        )


def assert_pairwise_no_volume_overlap(shape, tolerance_mm3: float = 1.0e-6) -> None:
    """Require zero common volume between every exported occurrence body."""

    children = list(shape.children)
    violations = []
    for i, left in enumerate(children):
        for j in range(i + 1, len(children)):
            right = children[j]
            common = left & right
            if common is None:
                common_volume = 0.0
            elif hasattr(common, "volume"):
                common_volume = common.volume
            else:
                common_volume = sum(item.volume for item in common)
            if common_volume > tolerance_mm3:
                violations.append(
                    {
                        "left": left.label,
                        "right": right.label,
                        "common_volume_mm3": common_volume,
                    }
                )
    if violations:
        raise ValueError(f"unexpected candidate body overlap: {violations}")


def assert_bounds_and_validity(shape, expected_x: tuple[float, float]) -> None:
    """Fail generation when a body is invalid or crosses its admitted X planes."""

    if not shape.is_valid:
        raise ValueError("generated BREP is invalid")
    bbox = shape.bounding_box()
    if bbox.min.X < expected_x[0] - 1.0e-7:
        raise ValueError(
            f"candidate crosses minimum X plane: {bbox.min.X} < {expected_x[0]}"
        )
    if bbox.max.X > expected_x[1] + 1.0e-7:
        raise ValueError(
            f"candidate crosses maximum X plane: {bbox.max.X} > {expected_x[1]}"
        )
