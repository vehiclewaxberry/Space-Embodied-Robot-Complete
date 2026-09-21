"""STEP-first bilateral recessed book-deployment solar-array test rig.

Authority:
    layout: Gate 1 baseline geometry
    kinematics: discrete rigid-body diagnostic poses
    mass: EXCLUDED
    strength/stiffness/reliability/manufacturing: NOT_EVALUATED

The exported pose samples never define the formal PARTIAL configuration.
PARTIAL remains UNKNOWN.  No purchased component or native SolidWorks
assembly is represented.

Generation controls:
    SOLAR_OUTPUT_MODE=pose|sweep
    SOLAR_POSE_DEG=0..90 (pose mode; verification outputs use 0/5/15/30/60/90)
"""

from __future__ import annotations

import math
import os

from build123d import Align, Axis, Box, Color, Compound, Cylinder, Location


# ---------------------------------------------------------------------------
# Frozen task inputs
# ---------------------------------------------------------------------------

PANEL_X_MIN_MM = -174.5
PANEL_X_MAX_MM = 52.5
PANEL_X_LENGTH_MM = PANEL_X_MAX_MM - PANEL_X_MIN_MM
PANEL_X_CENTER_MM = (PANEL_X_MIN_MM + PANEL_X_MAX_MM) / 2.0
PANEL_RADIAL_LENGTH_MM = 200.0
PANEL_THICKNESS_MM = 6.0

PLATFORM_HALF_WIDTH_MM = 113.15
LOWER_LONGERON_ABS_Y_MM = 105.65
LOWER_LONGERON_Z_MM = -105.65
MID2_X_MM = -61.0

POSE_SAMPLES_DEG = (0.0, 5.0, 15.0, 30.0, 60.0, 90.0)
PARTIAL_STATE_ANGLE_DEG = None


# ---------------------------------------------------------------------------
# Explicit design proposals - no sizing, load, or purchased-part authority
# ---------------------------------------------------------------------------

DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM = 110.0
DESIGN_PROPOSAL_HINGE_AXIS_Z_MM = -105.65
DESIGN_PROPOSAL_HINGE_STATION_RATIO = 0.66
DESIGN_PROPOSAL_HINGE_STATION_SEPARATION_MM = (
    PANEL_X_LENGTH_MM * DESIGN_PROPOSAL_HINGE_STATION_RATIO
)
DESIGN_PROPOSAL_HINGE_STATIONS_X_MM = (
    PANEL_X_CENTER_MM - DESIGN_PROPOSAL_HINGE_STATION_SEPARATION_MM / 2.0,
    PANEL_X_CENTER_MM + DESIGN_PROPOSAL_HINGE_STATION_SEPARATION_MM / 2.0,
)
DESIGN_PROPOSAL_HDRM_STATIONS_X_MM = (-160.0, 40.0)

DESIGN_PROPOSAL_CELL_SKIN_MM = 0.4
DESIGN_PROPOSAL_CELL_EDGE_INSET_MM = 8.0
DESIGN_PROPOSAL_BACKPLANE_THICKNESS_MM = 2.0
DESIGN_PROPOSAL_CASSETTE_GAP_MM = 2.0
DESIGN_PROPOSAL_CASSETTE_RAIL_MM = 6.0
DESIGN_PROPOSAL_LONGERON_REFERENCE_SECTION_MM = 6.0
DESIGN_PROPOSAL_MID2_REFERENCE_THICKNESS_MM = 6.0
DESIGN_PROPOSAL_HINGE_PIN_DIAMETER_MM = 6.0
DESIGN_PROPOSAL_HINGE_PIN_LENGTH_MM = 26.0
DESIGN_PROPOSAL_HINGE_EAR_X_MM = 5.0
DESIGN_PROPOSAL_HINGE_EAR_Y_INBOARD_MM = 3.0
DESIGN_PROPOSAL_HINGE_EAR_Y_OUTBOARD_MM = 3.0
DESIGN_PROPOSAL_HINGE_EAR_Z_MIN_MM = -6.0
DESIGN_PROPOSAL_HINGE_EAR_Z_MAX_MM = 12.0
DESIGN_PROPOSAL_MOVING_DOUBLER_X_MM = 28.0
DESIGN_PROPOSAL_MOVING_DOUBLER_HEIGHT_MM = 24.0
DESIGN_PROPOSAL_MOVING_DOUBLER_INBOARD_MM = 0.5
DESIGN_PROPOSAL_HDRM_FIXED_Y_MM = 7.5
DESIGN_PROPOSAL_HDRM_PAD_Y_MM = 0.5
DESIGN_PROPOSAL_HDRM_X_MM = 14.0
DESIGN_PROPOSAL_HDRM_Z_MM = 14.0
DESIGN_PROPOSAL_HDRM_Z_CENTER_MM = 40.0
DESIGN_PROPOSAL_STOP_X_MM = 10.0
DESIGN_PROPOSAL_STOP_Y_MM = 5.0
DESIGN_PROPOSAL_STOP_Z_MM = 8.0

LEGACY_DEPLOYED_TIP_ABS_Y_MM = 313.15
ACTUAL_DEPLOYED_TIP_ABS_Y_MM = (
    DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM + PANEL_RADIAL_LENGTH_MM
)
LEGACY_TIP_DELTA_MM = (
    ACTUAL_DEPLOYED_TIP_ABS_Y_MM - LEGACY_DEPLOYED_TIP_ABS_Y_MM
)


# ---------------------------------------------------------------------------
# Claim limits and review appearance
# ---------------------------------------------------------------------------

CLAIM_LIMIT = (
    "LAYOUT_AND_DISCRETE_KINEMATIC_DIAGNOSTIC_ONLY;"
    "MASS_EXCLUDED;NO_STRENGTH_STIFFNESS_RELEASE_RELIABILITY_"
    "MANUFACTURING_OR_FLIGHT_CLAIM"
)
REFERENCE_ONLY = (
    "REFERENCE_ENVELOPE_ONLY;NOT_AS_BUILT_GEOMETRY;" + CLAIM_LIMIT
)
DESIGN_PROPOSAL_ONLY = (
    "DESIGN_PROPOSAL_ONLY;NO_PURCHASED_PART_REPRESENTATION;" + CLAIM_LIMIT
)
PANEL_DISPLAY_BASELINE = (
    "PANEL_DISPLAY_BASELINE;CELL_AND_SANDWICH_CONSTRUCTION_UNSPECIFIED;"
    + CLAIM_LIMIT
)
CELL_ORIENTATION_WITNESS = (
    "CELL_FACE_ORIENTATION_WITNESS_ONLY;NO_ELECTRICAL_OR_THERMAL_CLAIM;"
    + CLAIM_LIMIT
)

COLOR_REFERENCE = Color(0.75, 0.78, 0.82, 0.35)
COLOR_LOADPATH = Color(0.95, 0.48, 0.12)
COLOR_CASSETTE = Color(0.40, 0.48, 0.56)
COLOR_HINGE_FIXED = Color(0.84, 0.58, 0.18)
COLOR_HINGE_MOVING = Color(0.92, 0.74, 0.24)
COLOR_PANEL = Color(0.18, 0.26, 0.38)
COLOR_CELL = Color(0.05, 0.22, 0.56)
COLOR_HDRM = Color(0.72, 0.22, 0.20)
COLOR_STOP = Color(0.55, 0.30, 0.16)


def _named(shape, label: str, color: Color, material: str):
    """Apply traceable STEP label, review colour, and claim classification."""

    shape.label = label
    shape.color = color
    shape.material = material
    return shape


def _module(label: str, children: list, material: str = CLAIM_LIMIT):
    return Compound(children=children, label=label, material=material)


def _box_bounds(
    x: tuple[float, float],
    y: tuple[float, float],
    z: tuple[float, float],
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = sorted(x)
    y0, y1 = sorted(y)
    z0, z1 = sorted(z)
    body = Box(
        x1 - x0,
        y1 - y0,
        z1 - z0,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)))
    return _named(body, label, color, material)


def _cylinder_x(
    x: tuple[float, float],
    yz: tuple[float, float],
    diameter: float,
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = sorted(x)
    body = Cylinder(
        diameter / 2.0,
        x1 - x0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2.0, yz[0], yz[1])))
    return _named(body, label, color, material)


def _side_y_bounds(side: int, abs_inner: float, abs_outer: float):
    return tuple(sorted((side * abs_inner, side * abs_outer)))


def _hinge_axis(side: int):
    return Axis(
        (0.0, side * DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM, DESIGN_PROPOSAL_HINGE_AXIS_Z_MM),
        (1.0, 0.0, 0.0),
    )


def _rotated(shape, side: int, angle_deg: float):
    # +Y/left rotates -theta; -Y/right rotates +theta.
    return shape.rotate(_hinge_axis(side), -side * angle_deg)


def _platform_loadpath_references():
    """Fixed references only; these are not a replacement platform model."""

    section = DESIGN_PROPOSAL_LONGERON_REFERENCE_SECTION_MM
    children = [
        _box_bounds(
            (-183.0, 183.0),
            (
                LOWER_LONGERON_ABS_Y_MM - section / 2.0,
                LOWER_LONGERON_ABS_Y_MM + section / 2.0,
            ),
            (
                LOWER_LONGERON_Z_MM - section / 2.0,
                LOWER_LONGERON_Z_MM + section / 2.0,
            ),
            "LOWER_LONGERON_LEFT_REFERENCE",
            COLOR_LOADPATH,
            REFERENCE_ONLY,
        ),
        _box_bounds(
            (-183.0, 183.0),
            (
                -LOWER_LONGERON_ABS_Y_MM - section / 2.0,
                -LOWER_LONGERON_ABS_Y_MM + section / 2.0,
            ),
            (
                LOWER_LONGERON_Z_MM - section / 2.0,
                LOWER_LONGERON_Z_MM + section / 2.0,
            ),
            "LOWER_LONGERON_RIGHT_REFERENCE",
            COLOR_LOADPATH,
            REFERENCE_ONLY,
        ),
        _box_bounds(
            (
                MID2_X_MM - DESIGN_PROPOSAL_MID2_REFERENCE_THICKNESS_MM / 2.0,
                MID2_X_MM + DESIGN_PROPOSAL_MID2_REFERENCE_THICKNESS_MM / 2.0,
            ),
            (
                -LOWER_LONGERON_ABS_Y_MM - section / 2.0,
                LOWER_LONGERON_ABS_Y_MM + section / 2.0,
            ),
            (
                LOWER_LONGERON_Z_MM - section / 2.0,
                LOWER_LONGERON_Z_MM + section / 2.0,
            ),
            "MID2_LOWER_CROSSMEMBER_REFERENCE",
            COLOR_LOADPATH,
            REFERENCE_ONLY,
        ),
    ]

    # Thin external-side datum witnesses end exactly at |Y|=113.15.
    for side, side_name in ((1, "LEFT"), (-1, "RIGHT")):
        children.append(
            _box_bounds(
                (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
                _side_y_bounds(side, PLATFORM_HALF_WIDTH_MM - 0.15, PLATFORM_HALF_WIDTH_MM),
                (-113.15, 113.15),
                f"PLATFORM_SIDE_LIMIT_{side_name}_ABS_Y_113_15_REFERENCE",
                COLOR_REFERENCE,
                REFERENCE_ONLY,
            )
        )

    return _module("PLATFORM_LOADPATH_AND_ENVELOPE_REFERENCES", children, REFERENCE_ONLY)


def _fixed_hinge_ear(side: int, station_x: float, x_bounds: tuple[float, float], label: str):
    axis_y = side * DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
    y_bounds = _side_y_bounds(
        side,
        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
        - DESIGN_PROPOSAL_HINGE_EAR_Y_INBOARD_MM,
        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
        + DESIGN_PROPOSAL_HINGE_EAR_Y_OUTBOARD_MM,
    )
    z_bounds = (
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM + DESIGN_PROPOSAL_HINGE_EAR_Z_MIN_MM,
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM + DESIGN_PROPOSAL_HINGE_EAR_Z_MAX_MM,
    )
    ear = _box_bounds(
        x_bounds,
        y_bounds,
        z_bounds,
        label,
        COLOR_HINGE_FIXED,
        DESIGN_PROPOSAL_ONLY,
    )
    cutter = Cylinder(
        DESIGN_PROPOSAL_HINGE_PIN_DIAMETER_MM / 2.0 + 0.25,
        max(x_bounds) - min(x_bounds) + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((station_x, axis_y, DESIGN_PROPOSAL_HINGE_AXIS_Z_MM)))
    return _named(ear - cutter, label, COLOR_HINGE_FIXED, DESIGN_PROPOSAL_ONLY)


def _fixed_cassette(side: int):
    side_name = "LEFT" if side > 0 else "RIGHT"
    axis_abs_y = DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
    backplane_outer_abs_y = (
        axis_abs_y
        - PANEL_THICKNESS_MM / 2.0
        - DESIGN_PROPOSAL_CASSETTE_GAP_MM
    )
    backplane_inner_abs_y = (
        backplane_outer_abs_y - DESIGN_PROPOSAL_BACKPLANE_THICKNESS_MM
    )
    backplane_y = _side_y_bounds(
        side, backplane_inner_abs_y, backplane_outer_abs_y
    )
    cassette_rail_y = _side_y_bounds(side, 98.0, LOWER_LONGERON_ABS_Y_MM)
    z_bottom = DESIGN_PROPOSAL_HINGE_AXIS_Z_MM
    z_top = z_bottom + PANEL_RADIAL_LENGTH_MM

    children = [
        _box_bounds(
            (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
            backplane_y,
            (z_bottom, z_top),
            f"{side_name}_RECESSED_CASSETTE_BACKPLANE_REFERENCE",
            COLOR_CASSETTE,
            DESIGN_PROPOSAL_ONLY,
        ),
        _box_bounds(
            (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
            cassette_rail_y,
            (z_bottom - 6.0, z_bottom + 6.0),
            f"{side_name}_CASSETTE_LOWER_SPINE_TO_LONGERON_REFERENCE",
            COLOR_LOADPATH,
            DESIGN_PROPOSAL_ONLY,
        ),
        _box_bounds(
            (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
            cassette_rail_y,
            (z_top - 3.0, z_top + 3.0),
            f"{side_name}_CASSETTE_UPPER_RAIL_REFERENCE",
            COLOR_CASSETTE,
            DESIGN_PROPOSAL_ONLY,
        ),
        _box_bounds(
            (MID2_X_MM - 6.0, MID2_X_MM + 6.0),
            _side_y_bounds(side, 98.0, LOWER_LONGERON_ABS_Y_MM + 1.5),
            (z_bottom - 6.0, z_bottom + 6.0),
            f"{side_name}_MID2_TO_CASSETTE_LOAD_BRACKET_REFERENCE",
            COLOR_LOADPATH,
            DESIGN_PROPOSAL_ONLY,
        ),
    ]

    for edge_name, edge_x in (
        ("AFT", PANEL_X_MIN_MM),
        ("FWD", PANEL_X_MAX_MM),
    ):
        children.append(
            _box_bounds(
                (edge_x - 3.0, edge_x + 3.0),
                cassette_rail_y,
                (z_bottom, z_top),
                f"{side_name}_CASSETTE_{edge_name}_PERIMETER_RAIL_REFERENCE",
                COLOR_CASSETTE,
                DESIGN_PROPOSAL_ONLY,
            )
        )

    for index, station_x in enumerate(DESIGN_PROPOSAL_HINGE_STATIONS_X_MM, start=1):
        fixed_left_x = (
            station_x - DESIGN_PROPOSAL_HINGE_PIN_LENGTH_MM / 2.0 + 1.0,
            station_x - 7.0,
        )
        fixed_right_x = (
            station_x + 7.0,
            station_x + DESIGN_PROPOSAL_HINGE_PIN_LENGTH_MM / 2.0 - 1.0,
        )
        children.extend(
            [
                _fixed_hinge_ear(
                    side,
                    station_x,
                    fixed_left_x,
                    f"{side_name}_HINGE_{index}_FIXED_EAR_A_PROPOSAL",
                ),
                _fixed_hinge_ear(
                    side,
                    station_x,
                    fixed_right_x,
                    f"{side_name}_HINGE_{index}_FIXED_EAR_B_PROPOSAL",
                ),
                _cylinder_x(
                    (
                        station_x - DESIGN_PROPOSAL_HINGE_PIN_LENGTH_MM / 2.0,
                        station_x + DESIGN_PROPOSAL_HINGE_PIN_LENGTH_MM / 2.0,
                    ),
                    (
                        side * DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM,
                        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM,
                    ),
                    DESIGN_PROPOSAL_HINGE_PIN_DIAMETER_MM,
                    f"{side_name}_HINGE_{index}_PIN_X_AXIS_PROPOSAL",
                    COLOR_HINGE_FIXED,
                    DESIGN_PROPOSAL_ONLY,
                ),
                _box_bounds(
                    (
                        station_x - DESIGN_PROPOSAL_STOP_X_MM / 2.0,
                        station_x + DESIGN_PROPOSAL_STOP_X_MM / 2.0,
                    ),
                    _side_y_bounds(
                        side,
                        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM - 9.0,
                        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM - 4.0,
                    ),
                    (
                        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM
                        - DESIGN_PROPOSAL_STOP_Z_MM / 2.0,
                        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM
                        + DESIGN_PROPOSAL_STOP_Z_MM / 2.0,
                    ),
                    f"{side_name}_HINGE_{index}_NOMINAL_90_STOP_PROPOSAL",
                    COLOR_STOP,
                    DESIGN_PROPOSAL_ONLY,
                ),
            ]
        )

    for index, station_x in enumerate(DESIGN_PROPOSAL_HDRM_STATIONS_X_MM, start=1):
        children.append(
            _box_bounds(
                (
                    station_x - DESIGN_PROPOSAL_HDRM_X_MM / 2.0,
                    station_x + DESIGN_PROPOSAL_HDRM_X_MM / 2.0,
                ),
                _side_y_bounds(side, 99.0, 99.0 + DESIGN_PROPOSAL_HDRM_FIXED_Y_MM),
                (
                    DESIGN_PROPOSAL_HDRM_Z_CENTER_MM
                    - DESIGN_PROPOSAL_HDRM_Z_MM / 2.0,
                    DESIGN_PROPOSAL_HDRM_Z_CENTER_MM
                    + DESIGN_PROPOSAL_HDRM_Z_MM / 2.0,
                ),
                f"{side_name}_HDRM_{index}_FIXED_INTERFACE_RESERVATION",
                COLOR_HDRM,
                DESIGN_PROPOSAL_ONLY,
            )
        )

    return _module(
        f"{side_name}_FIXED_RECESSED_ROOT_CASSETTE",
        children,
        DESIGN_PROPOSAL_ONLY,
    )


def _moving_hinge_lug(side: int, station_x: float, index: int):
    side_name = "LEFT" if side > 0 else "RIGHT"
    axis_y = side * DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
    x_bounds = (station_x - 6.0, station_x + 6.0)
    y_bounds = _side_y_bounds(
        side,
        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
        - DESIGN_PROPOSAL_HINGE_EAR_Y_INBOARD_MM,
        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
        + DESIGN_PROPOSAL_HINGE_EAR_Y_OUTBOARD_MM,
    )
    z_bounds = (
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM + DESIGN_PROPOSAL_HINGE_EAR_Z_MIN_MM,
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM + DESIGN_PROPOSAL_HINGE_EAR_Z_MAX_MM,
    )
    label = f"{side_name}_HINGE_{index}_MOVING_EAR_PROPOSAL"
    lug = _box_bounds(
        x_bounds,
        y_bounds,
        z_bounds,
        label,
        COLOR_HINGE_MOVING,
        DESIGN_PROPOSAL_ONLY,
    )
    cutter = Cylinder(
        DESIGN_PROPOSAL_HINGE_PIN_DIAMETER_MM / 2.0 + 0.25,
        14.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((station_x, axis_y, DESIGN_PROPOSAL_HINGE_AXIS_Z_MM)))
    return _named(lug - cutter, label, COLOR_HINGE_MOVING, DESIGN_PROPOSAL_ONLY)


def _moving_panel_stowed(side: int):
    side_name = "LEFT" if side > 0 else "RIGHT"
    axis_abs_y = DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM
    panel_y = _side_y_bounds(
        side,
        axis_abs_y - PANEL_THICKNESS_MM / 2.0,
        axis_abs_y + PANEL_THICKNESS_MM / 2.0,
    )
    z_bounds = (
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM,
        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM + PANEL_RADIAL_LENGTH_MM,
    )
    inward_surface_abs_y = axis_abs_y - PANEL_THICKNESS_MM / 2.0
    cell_y = _side_y_bounds(
        side,
        inward_surface_abs_y - DESIGN_PROPOSAL_CELL_SKIN_MM,
        inward_surface_abs_y,
    )
    cell_inset = DESIGN_PROPOSAL_CELL_EDGE_INSET_MM

    children = [
        _box_bounds(
            (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
            panel_y,
            z_bounds,
            f"{side_name}_SOLAR_PANEL_SANDWICH_BASELINE",
            COLOR_PANEL,
            PANEL_DISPLAY_BASELINE,
        ),
        _box_bounds(
            (PANEL_X_MIN_MM + cell_inset, PANEL_X_MAX_MM - cell_inset),
            cell_y,
            (z_bounds[0] + cell_inset, z_bounds[1] - cell_inset),
            f"{side_name}_CELL_FACE_INWARD_AT_0_PLUS_Z_AT_90_WITNESS",
            COLOR_CELL,
            CELL_ORIENTATION_WITNESS,
        ),
    ]

    # Back-face perimeter witnesses stay within the 6 mm panel thickness.
    back_face_abs_y = axis_abs_y + PANEL_THICKNESS_MM / 2.0
    back_skin_y = _side_y_bounds(side, back_face_abs_y - 0.4, back_face_abs_y)
    frame_width = 6.0
    children.extend(
        [
            _box_bounds(
                (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
                back_skin_y,
                (z_bounds[0], z_bounds[0] + frame_width),
                f"{side_name}_PANEL_BACK_FRAME_LOWER_WITNESS",
                COLOR_HINGE_MOVING,
                PANEL_DISPLAY_BASELINE,
            ),
            _box_bounds(
                (PANEL_X_MIN_MM, PANEL_X_MAX_MM),
                back_skin_y,
                (z_bounds[1] - frame_width, z_bounds[1]),
                f"{side_name}_PANEL_BACK_FRAME_UPPER_WITNESS",
                COLOR_HINGE_MOVING,
                PANEL_DISPLAY_BASELINE,
            ),
            _box_bounds(
                (PANEL_X_MIN_MM, PANEL_X_MIN_MM + frame_width),
                back_skin_y,
                z_bounds,
                f"{side_name}_PANEL_BACK_FRAME_AFT_WITNESS",
                COLOR_HINGE_MOVING,
                PANEL_DISPLAY_BASELINE,
            ),
            _box_bounds(
                (PANEL_X_MAX_MM - frame_width, PANEL_X_MAX_MM),
                back_skin_y,
                z_bounds,
                f"{side_name}_PANEL_BACK_FRAME_FWD_WITNESS",
                COLOR_HINGE_MOVING,
                PANEL_DISPLAY_BASELINE,
            ),
        ]
    )

    for index, station_x in enumerate(DESIGN_PROPOSAL_HINGE_STATIONS_X_MM, start=1):
        children.extend(
            [
                _moving_hinge_lug(side, station_x, index),
                _box_bounds(
                    (
                        station_x - DESIGN_PROPOSAL_MOVING_DOUBLER_X_MM / 2.0,
                        station_x + DESIGN_PROPOSAL_MOVING_DOUBLER_X_MM / 2.0,
                    ),
                    _side_y_bounds(
                        side,
                        inward_surface_abs_y
                        - DESIGN_PROPOSAL_MOVING_DOUBLER_INBOARD_MM,
                        inward_surface_abs_y,
                    ),
                    (
                        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM,
                        DESIGN_PROPOSAL_HINGE_AXIS_Z_MM
                        + DESIGN_PROPOSAL_MOVING_DOUBLER_HEIGHT_MM,
                    ),
                    f"{side_name}_HINGE_{index}_LOCAL_PANEL_DOUBLER_PROPOSAL",
                    COLOR_HINGE_MOVING,
                    DESIGN_PROPOSAL_ONLY,
                ),
            ]
        )

    for index, station_x in enumerate(DESIGN_PROPOSAL_HDRM_STATIONS_X_MM, start=1):
        children.append(
            _box_bounds(
                (
                    station_x - DESIGN_PROPOSAL_HDRM_X_MM / 2.0,
                    station_x + DESIGN_PROPOSAL_HDRM_X_MM / 2.0,
                ),
                _side_y_bounds(
                    side,
                    inward_surface_abs_y - DESIGN_PROPOSAL_HDRM_PAD_Y_MM,
                    inward_surface_abs_y,
                ),
                (
                    DESIGN_PROPOSAL_HDRM_Z_CENTER_MM
                    - DESIGN_PROPOSAL_HDRM_Z_MM / 2.0,
                    DESIGN_PROPOSAL_HDRM_Z_CENTER_MM
                    + DESIGN_PROPOSAL_HDRM_Z_MM / 2.0,
                ),
                f"{side_name}_HDRM_{index}_MOVING_PAD_RESERVATION",
                COLOR_HDRM,
                DESIGN_PROPOSAL_ONLY,
            )
        )

    return children


def _moving_panel(side: int, angle_deg: float, sample_prefix: str = ""):
    side_name = "LEFT" if side > 0 else "RIGHT"
    rotated_children = [
        _rotated(shape, side, angle_deg) for shape in _moving_panel_stowed(side)
    ]
    label_prefix = f"{sample_prefix}_" if sample_prefix else ""
    return _module(
        f"{label_prefix}{side_name}_MOVING_PANEL_{angle_deg:06.2f}DEG_NOT_PARTIAL",
        rotated_children,
        CLAIM_LIMIT,
    )


def _validate_source_contract():
    assert math.isclose(PANEL_X_LENGTH_MM, 227.0, abs_tol=1e-9)
    assert 0.60 <= DESIGN_PROPOSAL_HINGE_STATION_RATIO <= 0.75
    assert math.isclose(
        DESIGN_PROPOSAL_HINGE_STATION_SEPARATION_MM,
        DESIGN_PROPOSAL_HINGE_STATIONS_X_MM[1]
        - DESIGN_PROPOSAL_HINGE_STATIONS_X_MM[0],
        abs_tol=1e-9,
    )
    stowed_outer_abs_y = (
        DESIGN_PROPOSAL_HINGE_AXIS_ABS_Y_MM + PANEL_THICKNESS_MM / 2.0
    )
    assert stowed_outer_abs_y <= PLATFORM_HALF_WIDTH_MM
    assert math.isclose(stowed_outer_abs_y, 113.0, abs_tol=1e-9)
    assert math.isclose(ACTUAL_DEPLOYED_TIP_ABS_Y_MM, 310.0, abs_tol=1e-9)
    assert not math.isclose(
        ACTUAL_DEPLOYED_TIP_ABS_Y_MM,
        LEGACY_DEPLOYED_TIP_ABS_Y_MM,
        abs_tol=1e-9,
    )
    assert PARTIAL_STATE_ANGLE_DEG is None


def _checked_angle(angle_deg: float, name: str) -> float:
    """Return one bounded diagnostic angle without assigning PARTIAL."""

    angle_deg = float(angle_deg)
    if not 0.0 <= angle_deg <= 90.0:
        raise ValueError(f"{name} must remain in the 0..90 degree test range")
    return angle_deg


def build_bilateral_pose(
    left_angle_deg: float,
    right_angle_deg: float,
    state_label: str = "ASYMMETRIC_DIAGNOSTIC",
):
    """Build a bilateral pose with independently traceable left/right angles."""

    _validate_source_contract()
    left_angle_deg = _checked_angle(left_angle_deg, "SOLAR_LEFT_POSE_DEG")
    right_angle_deg = _checked_angle(right_angle_deg, "SOLAR_RIGHT_POSE_DEG")

    children = [
        _platform_loadpath_references(),
        _fixed_cassette(1),
        _fixed_cassette(-1),
        _moving_panel(1, left_angle_deg),
        _moving_panel(-1, right_angle_deg),
    ]
    return _module(
        "SOLAR_DEPLOYMENT_TEST_RIG_"
        f"L{left_angle_deg:06.2f}_R{right_angle_deg:06.2f}_"
        f"{state_label}_NOT_PARTIAL",
        children,
        CLAIM_LIMIT,
    )


def build_pose(angle_deg: float):
    """Build one symmetric static sample around fixed world-X hinge axes."""

    angle_deg = _checked_angle(angle_deg, "SOLAR_POSE_DEG")
    model = build_bilateral_pose(angle_deg, angle_deg, "SYMMETRIC_SAMPLE")
    model.label = (
        f"SOLAR_DEPLOYMENT_TEST_RIG_{angle_deg:06.2f}DEG_SAMPLE_NOT_PARTIAL"
    )
    return model


def build_sweep_samples():
    """Build a labelled multi-pose diagnostic; not a fused continuous envelope."""

    _validate_source_contract()
    children = [
        _platform_loadpath_references(),
        _fixed_cassette(1),
        _fixed_cassette(-1),
    ]
    for angle_deg in POSE_SAMPLES_DEG:
        sample_prefix = f"SWEEP_SAMPLE_{int(angle_deg):03d}DEG"
        children.extend(
            [
                _moving_panel(1, angle_deg, sample_prefix),
                _moving_panel(-1, angle_deg, sample_prefix),
            ]
        )
    return _module(
        "SOLAR_SWEEP_SAMPLED_MULTI_POSE_DIAGNOSTIC_NOT_PARTIAL",
        children,
        CLAIM_LIMIT,
    )


def gen_step():
    output_mode = os.environ.get("SOLAR_OUTPUT_MODE", "pose").strip().lower()
    if output_mode == "sweep":
        return build_sweep_samples()
    if output_mode == "bilateral":
        left_deg = float(os.environ.get("SOLAR_LEFT_POSE_DEG", "0"))
        right_deg = float(os.environ.get("SOLAR_RIGHT_POSE_DEG", "0"))
        state_label = os.environ.get(
            "SOLAR_STATE_LABEL", "ASYMMETRIC_DIAGNOSTIC"
        ).strip()
        return build_bilateral_pose(left_deg, right_deg, state_label)
    if output_mode != "pose":
        raise ValueError(
            "SOLAR_OUTPUT_MODE must be 'pose', 'bilateral', or 'sweep'"
        )
    pose_deg = float(os.environ.get("SOLAR_POSE_DEG", "0"))
    return build_pose(pose_deg)
