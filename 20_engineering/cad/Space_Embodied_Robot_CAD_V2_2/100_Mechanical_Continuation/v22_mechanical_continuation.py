"""STEP-first V2.2 mechanical-continuation integration assembly.

This source is intentionally self-contained.  It copies only the frozen
V22_B601_CONTINUE_01 dimensions and current B5 source values needed to rebuild
the isolated STEP.  It never opens or writes the canonical SolidWorks top.

Authority:
    geometry: mechanical-integration proposal, with per-label provenance
    kinematics: NONE
    mass: EXCLUDED
    structural: LOAD_PATH_INTENT_ONLY
"""

from __future__ import annotations

from build123d import (
    Align,
    Box,
    Color,
    Compound,
    Cone,
    Cylinder,
    Face,
    Location,
    Torus,
    Vector,
    Wire,
    extrude,
)


# ---------------------------------------------------------------------------
# Source identity and global claim limit
# ---------------------------------------------------------------------------

SOURCE_DECISION = "V22_B601_CONTINUE_01"
SOURCE_B5_SPEC = "../automation/b5_build_spec.yaml"
CLAIM_LIMIT = (
    "DISPLAY_AND_LOAD_PATH_INTENT_ONLY;"
    "NO_STRENGTH_STIFFNESS_RELEASE_RELIABILITY_OR_MANUFACTURING_CLAIM;"
    "KINEMATIC_AUTHORITY_NONE;MASS_AUTHORITY_EXCLUDED"
)


# ---------------------------------------------------------------------------
# Frozen decision values
# ---------------------------------------------------------------------------

FROZEN_B601_MOUNT_PLATE_X = (171.0, 183.0)
FROZEN_B601_MOUNT_PLATE_SIZE = 160.0
FROZEN_B601_MOUNT_PLATE_THICKNESS = 12.0
FROZEN_B601_CENTRAL_INTERFACE_DIAMETER = 100.0

# Stable names intentionally exposed for machine validators and downstream
# staging scripts.  They duplicate the authority-classified values above.
MOUNT_PLATE_WIDTH_MM = 160.0
MOUNT_PLATE_HEIGHT_MM = 160.0
MOUNT_PLATE_THICKNESS_MM = 12.0
CENTRAL_INTERFACE_DIAMETER_MM = 100.0
C5_REQUIRED_MM = 238.3
C5_AVAILABLE_MM = 226.3
SERVICE_STATUS = "PENDING_RATIFICATION"
CAPTURE_SAFE_STATUS = "UNKNOWN_CANDIDATE_NOT_UPGRADED"


# ---------------------------------------------------------------------------
# Current B5 source values.
# Values under SOURCE_B5_DISPLAY_* remain display proposals, not signed ICD.
# ---------------------------------------------------------------------------

SOURCE_B5_BUS_X = (-183.0, 183.0)
SOURCE_B5_BUS_HALF_YZ = 113.15
SOURCE_B5_INNER_HALF_YZ = 98.15
SOURCE_B5_LONGERON_CENTER = 105.65
SOURCE_B5_MID1_X = 61.0
SOURCE_B5_MID2_X = -61.0
SOURCE_B5_FRAMES = {
    "FRONT": ((171.0, 183.0), 113.15),
    "MID1": ((55.0, 67.0), 110.15),
    "MID2": ((-67.0, -55.0), 110.15),
    "REAR": ((-183.0, -171.0), 113.15),
}
SOURCE_B5_DECKS = {
    "MID1": (61.0, 8.0),
    "MID2": (-61.0, 8.0),
}
SOURCE_B5_DECK_PASSAGE_DIAMETER = 30.0
SOURCE_B5_DECK_PASSAGE_CENTER_YZ = (0.0, -60.0)

SOURCE_B5_DISPLAY_ADAPTER_X = (183.0, 198.0)
SOURCE_B5_DISPLAY_ADAPTER_OD = 180.0
SOURCE_B5_DISPLAY_ADAPTER_ID = 100.0
SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_DIAMETER = 18.0
SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_YZ = (70.0, 0.0)
SOURCE_B5_DISPLAY_HARNESS_PASSAGE_DIAMETER = 30.0
SOURCE_B5_DISPLAY_HARNESS_PASSAGE_YZ = (55.0, 0.0)
SOURCE_B5_DISPLAY_FRONT_BOSS_X = (156.0, 171.0)
SOURCE_B5_DISPLAY_FRONT_BOSS_SIZE = 100.0

SOURCE_B5_DISPLAY_MAIN_SADDLE = {
    "x": (40.0, 90.0),
    "y": (-30.0, 30.0),
    "z": (88.0, 110.15),
}
SOURCE_B5_DISPLAY_WRIST_SUPPORT = {
    "x": (-150.0, -110.0),
    "y": (-30.0, 30.0),
    "z": (88.0, 110.15),
}

SOURCE_B5_DISPLAY_WING_X = (-174.5, 52.5)
SOURCE_B5_DISPLAY_WING_Y_ABS = (113.15, 119.15)
SOURCE_B5_DISPLAY_WING_Z = (-200.0, 0.0)
SOURCE_B5_DISPLAY_WING_BORDER = 6.0
SOURCE_B5_DISPLAY_CELL_INSET = 10.0

SOURCE_B5_DISPLAY_ROOT_BASE_X = (-79.0, -43.0)
SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD = 8.0
SOURCE_B5_DISPLAY_ROOT_BASE_Z = (-40.0, 40.0)
SOURCE_B5_DISPLAY_ROOT_EARS_X = ((-75.0, -65.0), (-57.0, -47.0))
SOURCE_B5_DISPLAY_ROOT_EAR_HEIGHT = 30.0
SOURCE_B5_DISPLAY_ROOT_EAR_THICKNESS = 10.0
SOURCE_B5_DISPLAY_HINGE_PIN_DIAMETER = 8.0
SOURCE_B5_DISPLAY_HINGE_PIN_LENGTH = 24.0
SOURCE_B5_DISPLAY_SPRING_DIAMETER = 16.0
SOURCE_B5_DISPLAY_SPRING_LENGTH = 18.0
SOURCE_B5_DISPLAY_HDRM_BASE_SQUARE = 24.0
SOURCE_B5_DISPLAY_HDRM_BASE_THICKNESS = 8.0
SOURCE_B5_DISPLAY_HDRM_ROD_DIAMETER = 10.0
SOURCE_B5_DISPLAY_HDRM_ROD_LENGTH = 20.0
SOURCE_B5_DISPLAY_HDRM_STATIONS_X = (-160.0, 40.0)
SOURCE_B5_DISPLAY_HARD_STOP_SQUARE = 14.0
SOURCE_B5_DISPLAY_HARD_STOP_THICKNESS = 8.0

SOURCE_B5_DISPLAY_NAV_CAM_AT = (175.0, 60.0, 105.0)
SOURCE_B5_DISPLAY_NAV_CAM_BODY = (40.0, 40.0, 60.0)
SOURCE_B5_DISPLAY_RANGE_AT = (175.0, -60.0, 105.0)
SOURCE_B5_DISPLAY_RANGE_BODY = (35.0, 35.0, 50.0)
SOURCE_B5_DISPLAY_STAR_TRACKER_AT = (-100.0, 0.0, 105.0)
SOURCE_B5_DISPLAY_STAR_TRACKER_BODY = (45.0, 45.0, 70.0)
SOURCE_B5_DISPLAY_SBAND_AT = (-183.0, 40.0, -40.0)
SOURCE_B5_DISPLAY_SBAND_SQUARE = 60.0
SOURCE_B5_DISPLAY_SBAND_THICKNESS = 6.0
SOURCE_B5_DISPLAY_GNSS_AT = (100.0, 0.0, 113.15)
SOURCE_B5_DISPLAY_GNSS_SQUARE = 40.0
SOURCE_B5_DISPLAY_GNSS_THICKNESS = 6.0
SOURCE_B5_DISPLAY_RADIATOR_X = (-60.0, 60.0)
SOURCE_B5_DISPLAY_RADIATOR_HALF_WIDTH = 80.0
SOURCE_B5_DISPLAY_RADIATOR_THICKNESS = 2.0

SOURCE_B5_DISPLAY_MAIN_THRUSTER_AT_X = -183.0
SOURCE_B5_DISPLAY_MAIN_THRUSTER_DIAMETER = 40.0
SOURCE_B5_DISPLAY_MAIN_THRUSTER_LENGTH = 30.0
SOURCE_B5_DISPLAY_MAIN_THRUSTER_YZ = (0.0, -60.0)
SOURCE_B5_DISPLAY_CORNER_MODULE_X = (-183.0, -143.0)
SOURCE_B5_DISPLAY_CORNER_MODULE_HALF = 16.0
SOURCE_B5_DISPLAY_CORNER_CENTERS_YZ = (
    (95.0, 95.0),
    (95.0, -95.0),
    (-95.0, 95.0),
    (-95.0, -95.0),
)

SOURCE_B5_DISPLAY_CAPTURE_STACK_X0 = 480.0
SOURCE_B5_DISPLAY_CAPTURE_STACK = (
    ("WRIST", 60.0, 25.0),
    ("FT_SENSOR", 70.0, 30.0),
    ("CAM_RING", 80.0, 20.0),
    ("COMPLIANT", 55.0, 25.0),
)


# ---------------------------------------------------------------------------
# Explicit proposal-only values.
# None of these are frozen, signed ICD, or analysis-qualified.
# ---------------------------------------------------------------------------

DESIGN_PROPOSAL_FRAME_RAIL_OVERLAP = 0.0
DESIGN_PROPOSAL_LONGERON_SECTION = 15.0
DESIGN_PROPOSAL_PANEL_THICKNESS = 2.0
DESIGN_PROPOSAL_PANEL_SEAM_GAP = 1.0
DESIGN_PROPOSAL_ACCESS_COVER_X = (-45.0, 25.0)
DESIGN_PROPOSAL_ACCESS_COVER_Y = (-25.0, 25.0)
DESIGN_PROPOSAL_ACCESS_COVER_THICKNESS = 1.0
DESIGN_PROPOSAL_FASTENER_DIAMETER = 3.0
DESIGN_PROPOSAL_FASTENER_HEIGHT = 1.0

DESIGN_PROPOSAL_SPREADER_RIB_X = (156.0, 183.0)
DESIGN_PROPOSAL_GUSSET_INNER_CORNER = 72.0
DESIGN_PROPOSAL_GUSSET_OUTER_A = 98.0
DESIGN_PROPOSAL_GUSSET_OUTER_B = 105.65
DESIGN_PROPOSAL_FRONT_GUSSET_HALF = 7.575
DESIGN_PROPOSAL_LOAD_PATH_WEB_HALF_WIDTH = 7.5

DESIGN_PROPOSAL_CRADLE_BASE_THICKNESS = 6.0
DESIGN_PROPOSAL_CRADLE_SIDE_THICKNESS = 6.0
DESIGN_PROPOSAL_SOFT_PAD_THICKNESS = 3.0
DESIGN_PROPOSAL_SOFT_PAD_EDGE_CLEARANCE = 5.0
DESIGN_PROPOSAL_ARM_HDRM_BLOCK_X = 12.0
DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Y = 8.0
DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Z = 12.0
DESIGN_PROPOSAL_ARM_HDRM_OUTBOARD_GAP = 2.0

DESIGN_PROPOSAL_TOOL_AXIS_DIAMETER = 8.0
DESIGN_PROPOSAL_TOOL_AXIS_LENGTH = 60.0
DESIGN_PROPOSAL_ROOT_KEEP_OUT_DIAMETER = 200.0
DESIGN_PROPOSAL_ROOT_KEEP_OUT_LENGTH = 40.0
DESIGN_PROPOSAL_KEEP_OUT_WALL = 1.0

DESIGN_PROPOSAL_CELL_ZONE_COUNT = 3
DESIGN_PROPOSAL_CELL_ZONE_GAP = 3.0
DESIGN_PROPOSAL_CELL_RECESS = 1.0
DESIGN_PROPOSAL_HARNESS_LOOP_MAJOR_RADIUS = 18.0
DESIGN_PROPOSAL_HARNESS_LOOP_TUBE_RADIUS = 2.0
DESIGN_PROPOSAL_HARNESS_LOOP_X = -61.0
DESIGN_PROPOSAL_HARNESS_LOOP_Z = -25.0

DESIGN_PROPOSAL_CAMERA_WINDOW_DEPTH = 2.0
DESIGN_PROPOSAL_CAPTURE_WINDOW_DIAMETER = 60.0
DESIGN_PROPOSAL_THRUSTER_EXIT_DIAMETER = 56.0


# ---------------------------------------------------------------------------
# Colors are review aids only.
# ---------------------------------------------------------------------------

COLOR_STRUCTURE = Color(0.42, 0.47, 0.52)
COLOR_MOUNT = Color(0.92, 0.55, 0.16)
COLOR_STOW = Color(0.65, 0.40, 0.20)
COLOR_SOFT = Color(0.25, 0.72, 0.35)
COLOR_SOLAR_FRAME = Color(0.74, 0.74, 0.78)
COLOR_SOLAR_CELL = Color(0.05, 0.18, 0.42)
COLOR_SENSOR = Color(0.26, 0.64, 0.72)
COLOR_THERMAL = Color(0.82, 0.34, 0.28)
COLOR_PROPULSION = Color(0.36, 0.36, 0.40)
COLOR_REFERENCE = Color(0.95, 0.18, 0.12, 0.28)
COLOR_UNKNOWN = Color(0.70, 0.30, 0.78)


def _named(shape, label: str, color: Color, material: str):
    """Apply a traceable native label, review color, and authority tag."""

    shape.label = label
    shape.color = color
    shape.material = material
    return shape


def _module(label: str, children: list):
    return Compound(children=children, label=label, material=CLAIM_LIMIT)


def _box_bounds(
    x: tuple[float, float],
    y: tuple[float, float],
    z: tuple[float, float],
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = x
    y0, y1 = y
    z0, z1 = z
    body = Box(
        x1 - x0,
        y1 - y0,
        z1 - z0,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)))
    return _named(body, label, color, material)


def _cylinder_x(
    x: tuple[float, float],
    yz: tuple[float, float],
    diameter: float,
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = x
    body = Cylinder(
        diameter / 2,
        x1 - x0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2, yz[0], yz[1])))
    return _named(body, label, color, material)


def _cylinder_y(
    y: tuple[float, float],
    xz: tuple[float, float],
    diameter: float,
    label: str,
    color: Color,
    material: str,
):
    y0, y1 = y
    body = Cylinder(
        diameter / 2,
        y1 - y0,
        rotation=(90, 0, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((xz[0], (y0 + y1) / 2, xz[1])))
    return _named(body, label, color, material)


def _cylinder_z(
    z: tuple[float, float],
    xy: tuple[float, float],
    diameter: float,
    label: str,
    color: Color,
    material: str,
):
    z0, z1 = z
    body = Cylinder(
        diameter / 2,
        z1 - z0,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((xy[0], xy[1], (z0 + z1) / 2)))
    return _named(body, label, color, material)


def _ring_x(
    x: tuple[float, float],
    yz: tuple[float, float],
    outer_diameter: float,
    inner_diameter: float,
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = x
    outer = Cylinder(
        outer_diameter / 2,
        x1 - x0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2, yz[0], yz[1])))
    cutter = Cylinder(
        inner_diameter / 2,
        x1 - x0 + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(((x0 + x1) / 2, yz[0], yz[1])))
    return _named(outer - cutter, label, color, material)


def _triangular_prism_x(
    x: tuple[float, float],
    points_yz: tuple[tuple[float, float], ...],
    label: str,
    color: Color,
    material: str,
):
    x0, x1 = x
    wire = Wire.make_polygon(
        [Vector(x0, y, z) for y, z in points_yz],
        close=True,
    )
    body = extrude(Face(wire), amount=x1 - x0, dir=(1, 0, 0))
    return _named(body, label, color, material)


def _build_primary_structure():
    children = []
    rail_material = "SOURCE_B5_LOAD_PATH_INTENT;" + CLAIM_LIMIT

    for frame_name, (x_bounds, radial_out) in SOURCE_B5_FRAMES.items():
        rail = radial_out - SOURCE_B5_INNER_HALF_YZ
        for side in (-1, 1):
            y_bounds = (
                -SOURCE_B5_INNER_HALF_YZ,
                SOURCE_B5_INNER_HALF_YZ,
            )
            z_bounds = (
                side * SOURCE_B5_INNER_HALF_YZ,
                side * radial_out,
            )
            z_bounds = (min(z_bounds), max(z_bounds))
            children.append(
                _box_bounds(
                    x_bounds,
                    y_bounds,
                    z_bounds,
                    f"STRUCT_FRAME_{frame_name}_{'PZ' if side > 0 else 'NZ'}",
                    COLOR_STRUCTURE,
                    rail_material,
                )
            )

            y_side_bounds = (
                side * SOURCE_B5_INNER_HALF_YZ,
                side * radial_out,
            )
            y_side_bounds = (min(y_side_bounds), max(y_side_bounds))
            children.append(
                _box_bounds(
                    x_bounds,
                    y_side_bounds,
                    (
                        -SOURCE_B5_INNER_HALF_YZ,
                        SOURCE_B5_INNER_HALF_YZ,
                    ),
                    f"STRUCT_FRAME_{frame_name}_{'PY' if side > 0 else 'NY'}",
                    COLOR_STRUCTURE,
                    rail_material,
                )
            )

    half_lng = DESIGN_PROPOSAL_LONGERON_SECTION / 2
    for sy in (-1, 1):
        for sz in (-1, 1):
            children.append(
                _box_bounds(
                    SOURCE_B5_BUS_X,
                    (
                        sy * SOURCE_B5_LONGERON_CENTER - half_lng,
                        sy * SOURCE_B5_LONGERON_CENTER + half_lng,
                    ),
                    (
                        sz * SOURCE_B5_LONGERON_CENTER - half_lng,
                        sz * SOURCE_B5_LONGERON_CENTER + half_lng,
                    ),
                    f"STRUCT_LONGERON_{'PY' if sy > 0 else 'NY'}_"
                    f"{'PZ' if sz > 0 else 'NZ'}",
                    COLOR_STRUCTURE,
                    "SOURCE_B5_CENTER;"
                    "DESIGN_PROPOSAL_LONGERON_SECTION;"
                    + CLAIM_LIMIT,
                )
            )

    for deck_name, (xc, thickness) in SOURCE_B5_DECKS.items():
        deck = Box(
            thickness,
            2 * SOURCE_B5_INNER_HALF_YZ,
            2 * SOURCE_B5_INNER_HALF_YZ,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).located(Location((xc, 0, 0)))
        hole = Cylinder(
            SOURCE_B5_DECK_PASSAGE_DIAMETER / 2,
            thickness + 2.0,
            rotation=(0, 90, 0),
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).located(
            Location(
                (
                    xc,
                    SOURCE_B5_DECK_PASSAGE_CENTER_YZ[0],
                    SOURCE_B5_DECK_PASSAGE_CENTER_YZ[1],
                )
            )
        )
        children.append(
            _named(
                deck - hole,
                f"STRUCT_DECK_{deck_name}_WITH_D30_PASSAGE",
                COLOR_STRUCTURE,
                "SOURCE_B5_REAL_OPENING;LOAD_PATH_INTENT;" + CLAIM_LIMIT,
            )
        )

    # Exterior panels are deliberately split so the seam is an actual gap.
    t = DESIGN_PROPOSAL_PANEL_THICKNESS
    g = DESIGN_PROPOSAL_PANEL_SEAM_GAP / 2
    panel_mat = "DESIGN_PROPOSAL_PANEL_THICKNESS_AND_SEAM;" + CLAIM_LIMIT
    children.extend(
        [
            _box_bounds(
                (-171.0, -g),
                (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                (SOURCE_B5_BUS_HALF_YZ - t, SOURCE_B5_BUS_HALF_YZ),
                "FIDELITY_PANEL_TOP_AFT",
                COLOR_STRUCTURE,
                panel_mat,
            ),
            _box_bounds(
                (g, 171.0),
                (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                (SOURCE_B5_BUS_HALF_YZ - t, SOURCE_B5_BUS_HALF_YZ),
                "FIDELITY_PANEL_TOP_FWD",
                COLOR_STRUCTURE,
                panel_mat,
            ),
            _box_bounds(
                (-171.0, -g),
                (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                (-SOURCE_B5_BUS_HALF_YZ, -SOURCE_B5_BUS_HALF_YZ + t),
                "FIDELITY_PANEL_BOTTOM_AFT",
                COLOR_STRUCTURE,
                panel_mat,
            ),
            _box_bounds(
                (g, 171.0),
                (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                (-SOURCE_B5_BUS_HALF_YZ, -SOURCE_B5_BUS_HALF_YZ + t),
                "FIDELITY_PANEL_BOTTOM_FWD",
                COLOR_STRUCTURE,
                panel_mat,
            ),
        ]
    )
    for sy in (-1, 1):
        y_bounds = (
            sy * (SOURCE_B5_BUS_HALF_YZ - t),
            sy * SOURCE_B5_BUS_HALF_YZ,
        )
        y_bounds = (min(y_bounds), max(y_bounds))
        side_name = "LEFT" if sy > 0 else "RIGHT"
        children.extend(
            [
                _box_bounds(
                    (-171.0, SOURCE_B5_MID1_X - g),
                    y_bounds,
                    (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                    f"FIDELITY_PANEL_{side_name}_AFT",
                    COLOR_STRUCTURE,
                    panel_mat,
                ),
                _box_bounds(
                    (SOURCE_B5_MID1_X + g, 171.0),
                    y_bounds,
                    (-SOURCE_B5_BUS_HALF_YZ, SOURCE_B5_BUS_HALF_YZ),
                    f"FIDELITY_PANEL_{side_name}_FWD",
                    COLOR_STRUCTURE,
                    panel_mat,
                ),
            ]
        )

    # Top access cover and fastener markers are deliberately proposal geometry.
    cx = DESIGN_PROPOSAL_ACCESS_COVER_X
    cy = DESIGN_PROPOSAL_ACCESS_COVER_Y
    children.append(
        _box_bounds(
            cx,
            cy,
            (
                SOURCE_B5_BUS_HALF_YZ,
                SOURCE_B5_BUS_HALF_YZ
                + DESIGN_PROPOSAL_ACCESS_COVER_THICKNESS,
            ),
            "FIDELITY_ACCESS_COVER_TOP_DESIGN_PROPOSAL",
            COLOR_MOUNT,
            "DESIGN_PROPOSAL_ACCESS_COVER;" + CLAIM_LIMIT,
        )
    )
    for x in (cx[0] + 6.0, cx[1] - 6.0):
        for y in (cy[0] + 6.0, cy[1] - 6.0):
            children.append(
                _cylinder_z(
                    (
                        SOURCE_B5_BUS_HALF_YZ
                        + DESIGN_PROPOSAL_ACCESS_COVER_THICKNESS,
                        SOURCE_B5_BUS_HALF_YZ
                        + DESIGN_PROPOSAL_ACCESS_COVER_THICKNESS
                        + DESIGN_PROPOSAL_FASTENER_HEIGHT,
                    ),
                    (x, y),
                    DESIGN_PROPOSAL_FASTENER_DIAMETER,
                    f"FIDELITY_FASTENER_MARKER_X{x:+.0f}_Y{y:+.0f}",
                    COLOR_UNKNOWN,
                    "DESIGN_PROPOSAL_FASTENER_MARKER_NOT_HARDWARE;"
                    + CLAIM_LIMIT,
                )
            )

    return _module("MOD_PLATFORM_10_PRIMARY_STRUCTURE_FIDELITY_01A", children)


def _build_b601_mount():
    children = []
    mount_material = (
        "B601_ICD_01_FROZEN_160X160X12_AND_D100_ONLY;"
        "BOLT_PIN_PATTERN_TBD_HOLD;"
        + CLAIM_LIMIT
    )
    plate = Box(
        FROZEN_B601_MOUNT_PLATE_THICKNESS,
        FROZEN_B601_MOUNT_PLATE_SIZE,
        FROZEN_B601_MOUNT_PLATE_SIZE,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                sum(FROZEN_B601_MOUNT_PLATE_X) / 2,
                0,
                0,
            )
        )
    )
    central = Cylinder(
        FROZEN_B601_CENTRAL_INTERFACE_DIAMETER / 2,
        FROZEN_B601_MOUNT_PLATE_THICKNESS + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location((sum(FROZEN_B601_MOUNT_PLATE_X) / 2, 0, 0)))
    harness = Cylinder(
        SOURCE_B5_DISPLAY_HARNESS_PASSAGE_DIAMETER / 2,
        FROZEN_B601_MOUNT_PLATE_THICKNESS + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                sum(FROZEN_B601_MOUNT_PLATE_X) / 2,
                SOURCE_B5_DISPLAY_HARNESS_PASSAGE_YZ[0],
                SOURCE_B5_DISPLAY_HARNESS_PASSAGE_YZ[1],
            )
        )
    )
    children.append(
        _named(
            plate - central - harness,
            "B601_MOUNT_PLATE_WITH_B601_CENTRAL_INTERFACE_D100_"
            "FROZEN_160X160X12_AND_SOURCE_D30_HARNESS",
            COLOR_MOUNT,
            mount_material,
        )
    )

    adapter = _ring_x(
        SOURCE_B5_DISPLAY_ADAPTER_X,
        (0.0, 0.0),
        SOURCE_B5_DISPLAY_ADAPTER_OD,
        SOURCE_B5_DISPLAY_ADAPTER_ID,
        "B601_BASE_ADAPTER_RING_SOURCE_DISPLAY_PROPOSAL_OD180_ID100",
        COLOR_MOUNT,
        "SOURCE_B5_DISPLAY_PROPOSAL;BOLT_CIRCLE_AND_PINS_TBD_HOLD;"
        + CLAIM_LIMIT,
    )
    connector_cut = Cylinder(
        SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_DIAMETER / 2,
        SOURCE_B5_DISPLAY_ADAPTER_X[1]
        - SOURCE_B5_DISPLAY_ADAPTER_X[0]
        + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                sum(SOURCE_B5_DISPLAY_ADAPTER_X) / 2,
                SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_YZ[0],
                SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_YZ[1],
            )
        )
    )
    adapter = _named(
        adapter - connector_cut,
        "B601_BASE_ADAPTER_RING_WITH_SOURCE_D18_CONNECTOR_RESERVATION",
        COLOR_MOUNT,
        "SOURCE_B5_DISPLAY_PROPOSAL;CONNECTOR_MODEL_UNKNOWN;" + CLAIM_LIMIT,
    )
    children.append(adapter)

    children.append(
        _cylinder_x(
            SOURCE_B5_DISPLAY_FRONT_BOSS_X,
            (0.0, 0.0),
            SOURCE_B5_DISPLAY_FRONT_BOSS_SIZE,
            "B601_FRONT_LOCAL_BOSS_D100_SOURCE_DISPLAY_PROPOSAL",
            COLOR_MOUNT,
            "SOURCE_B5_DISPLAY_PROPOSAL;LOAD_PATH_INTENT;" + CLAIM_LIMIT,
        )
    )

    for sy in (-1, 1):
        for sz in (-1, 1):
            points = (
                (
                    sy * DESIGN_PROPOSAL_GUSSET_INNER_CORNER,
                    sz * DESIGN_PROPOSAL_GUSSET_INNER_CORNER,
                ),
                (
                    sy * DESIGN_PROPOSAL_GUSSET_OUTER_B,
                    sz * DESIGN_PROPOSAL_GUSSET_OUTER_A,
                ),
                (
                    sy * DESIGN_PROPOSAL_GUSSET_OUTER_A,
                    sz * DESIGN_PROPOSAL_GUSSET_OUTER_B,
                ),
            )
            children.append(
                _triangular_prism_x(
                    DESIGN_PROPOSAL_SPREADER_RIB_X,
                    points,
                    f"B601_FOUR_WAY_SPREADER_RIB_{'PY' if sy > 0 else 'NY'}_"
                    f"{'PZ' if sz > 0 else 'NZ'}_DESIGN_PROPOSAL",
                    COLOR_MOUNT,
                    "DESIGN_PROPOSAL_SPREADER_RIB_SECTION;"
                    "LOAD_PATH_TO_LONGERON_INTENT;"
                    + CLAIM_LIMIT,
                )
            )
            gc = 90.575
            gh = DESIGN_PROPOSAL_FRONT_GUSSET_HALF
            children.append(
                _box_bounds(
                    FROZEN_B601_MOUNT_PLATE_X,
                    (sy * gc - gh, sy * gc + gh),
                    (sz * gc - gh, sz * gc + gh),
                    f"B601_FRONT_GUSSET_CELL_{'PY' if sy > 0 else 'NY'}_"
                    f"{'PZ' if sz > 0 else 'NZ'}",
                    COLOR_MOUNT,
                    "SOURCE_B5_GUSSET_CELL;LOAD_PATH_INTENT;" + CLAIM_LIMIT,
                )
            )

    # Staging-only four-way closure from the 160 mm plate edges to the inner
    # boundary of the front task frame.  Fastener/joint definition is TBD.
    web_half = DESIGN_PROPOSAL_LOAD_PATH_WEB_HALF_WIDTH
    for sy in (-1, 1):
        y_web = (
            sy * FROZEN_B601_MOUNT_PLATE_SIZE / 2,
            sy * SOURCE_B5_INNER_HALF_YZ,
        )
        children.append(
            _box_bounds(
                FROZEN_B601_MOUNT_PLATE_X,
                (min(y_web), max(y_web)),
                (-web_half, web_half),
                f"B601_LOAD_PATH_WEB_{'PY' if sy > 0 else 'NY'}_"
                "STAGING_DESIGN_PROPOSAL",
                COLOR_MOUNT,
                "DESIGN_PROPOSAL_FOUR_WAY_RIB_CLOSURE;"
                "FASTENERS_AND_JOINTS_TBD_HOLD;"
                + CLAIM_LIMIT,
            )
        )
    for sz in (-1, 1):
        z_web = (
            sz * FROZEN_B601_MOUNT_PLATE_SIZE / 2,
            sz * SOURCE_B5_INNER_HALF_YZ,
        )
        children.append(
            _box_bounds(
                FROZEN_B601_MOUNT_PLATE_X,
                (-web_half, web_half),
                (min(z_web), max(z_web)),
                f"B601_LOAD_PATH_WEB_{'PZ' if sz > 0 else 'NZ'}_"
                "STAGING_DESIGN_PROPOSAL",
                COLOR_MOUNT,
                "DESIGN_PROPOSAL_FOUR_WAY_RIB_CLOSURE;"
                "FASTENERS_AND_JOINTS_TBD_HOLD;"
                + CLAIM_LIMIT,
            )
        )

    # Non-physical reference solids make the reserved directions explicit.
    tool_axis = _cylinder_x(
        (
            SOURCE_B5_DISPLAY_ADAPTER_X[1],
            SOURCE_B5_DISPLAY_ADAPTER_X[1]
            + DESIGN_PROPOSAL_TOOL_AXIS_LENGTH,
        ),
        (0.0, 0.0),
        DESIGN_PROPOSAL_TOOL_AXIS_DIAMETER,
        "REFERENCE_NON_PHYSICAL_TOOL_APPROACH_AXIS_PLUS_X_DESIGN_PROPOSAL",
        COLOR_REFERENCE,
        "REFERENCE_NON_PHYSICAL;DESIGN_PROPOSAL_TOOL_AXIS;" + CLAIM_LIMIT,
    )
    children.append(tool_axis)

    keepout_outer = _cylinder_x(
        (
            SOURCE_B5_DISPLAY_ADAPTER_X[1],
            SOURCE_B5_DISPLAY_ADAPTER_X[1]
            + DESIGN_PROPOSAL_ROOT_KEEP_OUT_LENGTH,
        ),
        (0.0, 0.0),
        DESIGN_PROPOSAL_ROOT_KEEP_OUT_DIAMETER,
        "REFERENCE_NON_PHYSICAL_B601_ROOT_KEEP_OUT_OUTER_DESIGN_PROPOSAL",
        COLOR_REFERENCE,
        "REFERENCE_NON_PHYSICAL;DESIGN_PROPOSAL_ROOT_KEEP_OUT;" + CLAIM_LIMIT,
    )
    keepout_inner = Cylinder(
        DESIGN_PROPOSAL_ROOT_KEEP_OUT_DIAMETER / 2
        - DESIGN_PROPOSAL_KEEP_OUT_WALL,
        DESIGN_PROPOSAL_ROOT_KEEP_OUT_LENGTH + 2.0,
        rotation=(0, 90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                SOURCE_B5_DISPLAY_ADAPTER_X[1]
                + DESIGN_PROPOSAL_ROOT_KEEP_OUT_LENGTH / 2,
                0,
                0,
            )
        )
    )
    children.append(
        _named(
            keepout_outer - keepout_inner,
            "REFERENCE_NON_PHYSICAL_B601_ROOT_KEEP_OUT_SHELL_DESIGN_PROPOSAL",
            COLOR_REFERENCE,
            "REFERENCE_NON_PHYSICAL;DESIGN_PROPOSAL_ROOT_KEEP_OUT;" + CLAIM_LIMIT,
        )
    )

    return _module("MOD_20_B601_ICD_AND_MOUNT_01", children)


def _build_one_stow_support(name: str, envelope: dict, role: str):
    x0, x1 = envelope["x"]
    y0, y1 = envelope["y"]
    z0, z1 = envelope["z"]
    base_top = z0 + DESIGN_PROPOSAL_CRADLE_BASE_THICKNESS
    side_t = DESIGN_PROPOSAL_CRADLE_SIDE_THICKNESS
    pad_clear = DESIGN_PROPOSAL_SOFT_PAD_EDGE_CLEARANCE
    items = [
        _box_bounds(
            (x0, x1),
            (y0, y1),
            (z0, base_top),
            f"ARM_STOW_{name}_BASE_SOURCE_ENVELOPE_DESIGN_PROPOSAL_SECTION",
            COLOR_STOW,
            "SOURCE_B5_ENVELOPE;DESIGN_PROPOSAL_CRADLE_SECTION;"
            "CONTACT_CANDIDATE_PENDING_B601_LOD1;"
            + CLAIM_LIMIT,
        ),
        _box_bounds(
            (x0, x1),
            (y0, y0 + side_t),
            (base_top, z1),
            f"ARM_STOW_{name}_SIDE_NY",
            COLOR_STOW,
            "SOURCE_B5_ENVELOPE;DESIGN_PROPOSAL_CRADLE_SECTION;"
            "CONTACT_CANDIDATE_PENDING_B601_LOD1;"
            + CLAIM_LIMIT,
        ),
        _box_bounds(
            (x0, x1),
            (y1 - side_t, y1),
            (base_top, z1),
            f"ARM_STOW_{name}_SIDE_PY",
            COLOR_STOW,
            "SOURCE_B5_ENVELOPE;DESIGN_PROPOSAL_CRADLE_SECTION;"
            "CONTACT_CANDIDATE_PENDING_B601_LOD1;"
            + CLAIM_LIMIT,
        ),
        _box_bounds(
            (x0 + pad_clear, x1 - pad_clear),
            (y0 + side_t, y1 - side_t),
            (base_top, base_top + DESIGN_PROPOSAL_SOFT_PAD_THICKNESS),
            f"ARM_STOW_{name}_SOFT_PAD_CONTACT_CANDIDATE",
            COLOR_SOFT,
            "DESIGN_PROPOSAL_SOFT_PAD;"
            "LOCAL_PRESSURE_AND_MATERIAL_UNKNOWN;"
            "CONTACT_CANDIDATE_PENDING_B601_LOD1;"
            + CLAIM_LIMIT,
        ),
    ]

    for sy in (-1, 1):
        yc = (
            y1
            + DESIGN_PROPOSAL_ARM_HDRM_OUTBOARD_GAP
            + DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Y / 2
        ) * sy
        items.append(
            _box_bounds(
                (
                    (x0 + x1) / 2 - DESIGN_PROPOSAL_ARM_HDRM_BLOCK_X / 2,
                    (x0 + x1) / 2 + DESIGN_PROPOSAL_ARM_HDRM_BLOCK_X / 2,
                ),
                (
                    yc - DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Y / 2,
                    yc + DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Y / 2,
                ),
                (
                    z1 - DESIGN_PROPOSAL_ARM_HDRM_BLOCK_Z,
                    z1,
                ),
                f"ARM_STOW_{name}_HDRM_RESERVATION_{'PY' if sy > 0 else 'NY'}",
                COLOR_UNKNOWN,
                "DESIGN_PROPOSAL_HDRM_RESERVATION;"
                "RELEASE_DIRECTION_SHOCK_PATH_UNKNOWN;"
                + CLAIM_LIMIT,
            )
        )
    return _module(f"ARM_STOW_{name}_{role}", items)


def _build_arm_stow():
    return _module(
        "MOD_30_ARM_STOW_01",
        [
            _build_one_stow_support(
                "MAIN_SADDLE",
                SOURCE_B5_DISPLAY_MAIN_SADDLE,
                "PRIMARY_ARM_SUPPORT",
            ),
            _build_one_stow_support(
                "WRIST_SOFT_SUPPORT",
                SOURCE_B5_DISPLAY_WRIST_SUPPORT,
                "WRIST_GRIPPER_SUPPORT",
            ),
        ],
    )


def _build_one_solar_side(side: int):
    side_name = "LEFT_PY" if side > 0 else "RIGHT_NY"
    children = []
    y_bus = side * SOURCE_B5_BUS_HALF_YZ
    y_outer_base = side * (
        SOURCE_B5_BUS_HALF_YZ + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
    )
    root_y = (min(y_bus, y_outer_base), max(y_bus, y_outer_base))
    children.append(
        _box_bounds(
            SOURCE_B5_DISPLAY_ROOT_BASE_X,
            root_y,
            SOURCE_B5_DISPLAY_ROOT_BASE_Z,
            f"SOLAR_ROOT_{side_name}_BASE_SOURCE_DISPLAY_PROPOSAL",
            COLOR_MOUNT,
            "SOURCE_B5_DISPLAY_PROPOSAL;C2_MID2_NODE_ATTACH_INTENT;"
            + CLAIM_LIMIT,
        )
    )

    # Embedded staging spine closes the currently visible 5 mm X/Y gap between
    # the root bracket proposal and the signed-node-location context.  It is a
    # proposal plate, not an assertion of joint or fastener definition.
    spine_y = (
        side * 110.15,
        side
        * (
            SOURCE_B5_BUS_HALF_YZ
            + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
        ),
    )
    children.append(
        _box_bounds(
            (-67.0, -55.0),
            (min(spine_y), max(spine_y)),
            (-75.0, 75.0),
            f"SOLAR_ROOT_NODE_SPINE_{'L' if side > 0 else 'R'}_"
            "STAGING_DESIGN_PROPOSAL",
            COLOR_MOUNT,
            "DESIGN_PROPOSAL_ROOT_NODE_SPINE_EMBEDDED_STAGING_ONLY;"
            "FASTENERS_AND_JOINTS_TBD_HOLD;"
            + CLAIM_LIMIT,
        )
    )

    hinge_y = side * (
        SOURCE_B5_BUS_HALF_YZ
        + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
        + SOURCE_B5_DISPLAY_ROOT_EAR_HEIGHT
        - SOURCE_B5_DISPLAY_HINGE_PIN_DIAMETER
    )
    for index, ear_x in enumerate(SOURCE_B5_DISPLAY_ROOT_EARS_X, start=1):
        ear_y_end = side * (
            SOURCE_B5_BUS_HALF_YZ
            + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
            + SOURCE_B5_DISPLAY_ROOT_EAR_HEIGHT
        )
        ear_y = (min(y_outer_base, ear_y_end), max(y_outer_base, ear_y_end))
        children.append(
            _box_bounds(
                ear_x,
                ear_y,
                (
                    -SOURCE_B5_DISPLAY_ROOT_EAR_THICKNESS / 2,
                    SOURCE_B5_DISPLAY_ROOT_EAR_THICKNESS / 2,
                ),
                f"SOLAR_ROOT_{side_name}_HINGE_EAR_{index}_SOURCE_DISPLAY_PROPOSAL",
                COLOR_MOUNT,
                "SOURCE_B5_DISPLAY_PROPOSAL;DUAL_EAR_ANTITORSION_INTENT;"
                + CLAIM_LIMIT,
            )
        )
        xc = sum(ear_x) / 2
        pin_x = (
            xc - SOURCE_B5_DISPLAY_HINGE_PIN_LENGTH / 2,
            xc + SOURCE_B5_DISPLAY_HINGE_PIN_LENGTH / 2,
        )
        children.append(
            _cylinder_x(
                pin_x,
                (hinge_y, 0.0),
                SOURCE_B5_DISPLAY_HINGE_PIN_DIAMETER,
                f"SOLAR_ROOT_{side_name}_HINGE_PIN_{index}_SOURCE_DISPLAY_PROPOSAL",
                COLOR_UNKNOWN,
                "SOURCE_B5_DISPLAY_PROPOSAL;PIN_SPEC_ICD_PENDING;" + CLAIM_LIMIT,
            )
        )
        spring_x0 = pin_x[1]
        children.append(
            _cylinder_x(
                (
                    spring_x0,
                    spring_x0 + SOURCE_B5_DISPLAY_SPRING_LENGTH,
                ),
                (hinge_y, 0.0),
                SOURCE_B5_DISPLAY_SPRING_DIAMETER,
                f"SOLAR_ROOT_{side_name}_TORSION_SPRING_{index}_ENVELOPE",
                COLOR_UNKNOWN,
                "SOURCE_B5_DISPLAY_PROPOSAL;SPRING_STIFFNESS_UNKNOWN;"
                + CLAIM_LIMIT,
            )
        )

    for index, xc in enumerate(SOURCE_B5_DISPLAY_HDRM_STATIONS_X, start=1):
        y_outer = side * (
            SOURCE_B5_BUS_HALF_YZ + SOURCE_B5_DISPLAY_HDRM_BASE_THICKNESS
        )
        y_base = (min(y_bus, y_outer), max(y_bus, y_outer))
        children.append(
            _box_bounds(
                (
                    xc - SOURCE_B5_DISPLAY_HDRM_BASE_SQUARE / 2,
                    xc + SOURCE_B5_DISPLAY_HDRM_BASE_SQUARE / 2,
                ),
                y_base,
                (
                    -100.0 - SOURCE_B5_DISPLAY_HDRM_BASE_SQUARE / 2,
                    -100.0 + SOURCE_B5_DISPLAY_HDRM_BASE_SQUARE / 2,
                ),
                f"SOLAR_ROOT_{side_name}_HDRM_BASE_{index}_SOURCE_DISPLAY_PROPOSAL",
                COLOR_UNKNOWN,
                "SOURCE_B5_DISPLAY_PROPOSAL;DUAL_HDRM_STAGGERED_C5;"
                "RELEASE_MECHANISM_ICD_PENDING;"
                + CLAIM_LIMIT,
            )
        )
        rod_y0 = y_outer
        rod_y1 = side * (
            SOURCE_B5_BUS_HALF_YZ
            + SOURCE_B5_DISPLAY_HDRM_BASE_THICKNESS
            + SOURCE_B5_DISPLAY_HDRM_ROD_LENGTH
        )
        children.append(
            _cylinder_y(
                (min(rod_y0, rod_y1), max(rod_y0, rod_y1)),
                (xc, -100.0),
                SOURCE_B5_DISPLAY_HDRM_ROD_DIAMETER,
                f"SOLAR_ROOT_{side_name}_HDRM_ROD_{index}_SOURCE_DISPLAY_PROPOSAL",
                COLOR_UNKNOWN,
                "SOURCE_B5_DISPLAY_PROPOSAL;RELEASE_RELIABILITY_UNKNOWN;"
                + CLAIM_LIMIT,
            )
        )

    hard_stop_yc = side * (
        SOURCE_B5_BUS_HALF_YZ
        + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
        + SOURCE_B5_DISPLAY_HARD_STOP_THICKNESS / 2
    )
    children.append(
        _box_bounds(
            (-64.0, -58.0),
            (
                hard_stop_yc - SOURCE_B5_DISPLAY_HARD_STOP_THICKNESS / 2,
                hard_stop_yc + SOURCE_B5_DISPLAY_HARD_STOP_THICKNESS / 2,
            ),
            (
                30.0 - SOURCE_B5_DISPLAY_HARD_STOP_SQUARE / 2,
                30.0 + SOURCE_B5_DISPLAY_HARD_STOP_SQUARE / 2,
            ),
            f"SOLAR_ROOT_{side_name}_HARD_STOP_SOURCE_DISPLAY_PROPOSAL",
            COLOR_MOUNT,
            "SOURCE_B5_DISPLAY_PROPOSAL;DEPLOY_STOP_INTENT;"
            "STOP_LOAD_UNKNOWN;"
            + CLAIM_LIMIT,
        )
    )

    harness = Torus(
        DESIGN_PROPOSAL_HARNESS_LOOP_MAJOR_RADIUS,
        DESIGN_PROPOSAL_HARNESS_LOOP_TUBE_RADIUS,
        rotation=(90, 0, 0),
    ).located(
        Location(
            (
                DESIGN_PROPOSAL_HARNESS_LOOP_X,
                side
                * (
                    SOURCE_B5_BUS_HALF_YZ
                    + SOURCE_B5_DISPLAY_ROOT_BASE_OUTBOARD
                    + 14.0
                ),
                DESIGN_PROPOSAL_HARNESS_LOOP_Z,
            )
        )
    )
    children.append(
        _named(
            harness,
            f"SOLAR_ROOT_{side_name}_HARNESS_BEND_ENVELOPE_DESIGN_PROPOSAL",
            COLOR_REFERENCE,
            "REFERENCE_NON_PHYSICAL;DESIGN_PROPOSAL_HARNESS_BEND_RADIUS;"
            "HARNESS_SLACK_UNKNOWN;"
            + CLAIM_LIMIT,
        )
    )

    # Stowed wing border retains the full current B5 envelope.
    x0, x1 = SOURCE_B5_DISPLAY_WING_X
    z0, z1 = SOURCE_B5_DISPLAY_WING_Z
    y0 = side * SOURCE_B5_DISPLAY_WING_Y_ABS[0]
    y1 = side * SOURCE_B5_DISPLAY_WING_Y_ABS[1]
    wing_y = (min(y0, y1), max(y0, y1))
    b = SOURCE_B5_DISPLAY_WING_BORDER
    frame_material = "SOURCE_B5_STOWED_WING_ENVELOPE_AND_BORDER;" + CLAIM_LIMIT
    children.extend(
        [
            _box_bounds(
                (x0, x0 + b),
                wing_y,
                (z0, z1),
                f"SOLAR_WING_{side_name}_FRAME_XMIN",
                COLOR_SOLAR_FRAME,
                frame_material,
            ),
            _box_bounds(
                (x1 - b, x1),
                wing_y,
                (z0, z1),
                f"SOLAR_WING_{side_name}_FRAME_XMAX",
                COLOR_SOLAR_FRAME,
                frame_material,
            ),
            _box_bounds(
                (x0 + b, x1 - b),
                wing_y,
                (z0, z0 + b),
                f"SOLAR_WING_{side_name}_FRAME_ZMIN",
                COLOR_SOLAR_FRAME,
                frame_material,
            ),
            _box_bounds(
                (x0 + b, x1 - b),
                wing_y,
                (z1 - b, z1),
                f"SOLAR_WING_{side_name}_FRAME_ZMAX",
                COLOR_SOLAR_FRAME,
                frame_material,
            ),
        ]
    )

    cell_x0 = x0 + SOURCE_B5_DISPLAY_CELL_INSET
    cell_x1 = x1 - SOURCE_B5_DISPLAY_CELL_INSET
    cell_z = (
        z0 + SOURCE_B5_DISPLAY_CELL_INSET,
        z1 - SOURCE_B5_DISPLAY_CELL_INSET,
    )
    total_gap = DESIGN_PROPOSAL_CELL_ZONE_GAP * (
        DESIGN_PROPOSAL_CELL_ZONE_COUNT - 1
    )
    zone_width = (
        cell_x1 - cell_x0 - total_gap
    ) / DESIGN_PROPOSAL_CELL_ZONE_COUNT
    if side > 0:
        cell_y = (
            SOURCE_B5_DISPLAY_WING_Y_ABS[0] + DESIGN_PROPOSAL_CELL_RECESS,
            SOURCE_B5_DISPLAY_WING_Y_ABS[1] - DESIGN_PROPOSAL_CELL_RECESS,
        )
    else:
        cell_y = (
            -SOURCE_B5_DISPLAY_WING_Y_ABS[1] + DESIGN_PROPOSAL_CELL_RECESS,
            -SOURCE_B5_DISPLAY_WING_Y_ABS[0] - DESIGN_PROPOSAL_CELL_RECESS,
        )
    for index in range(DESIGN_PROPOSAL_CELL_ZONE_COUNT):
        zx0 = cell_x0 + index * (
            zone_width + DESIGN_PROPOSAL_CELL_ZONE_GAP
        )
        children.append(
            _box_bounds(
                (zx0, zx0 + zone_width),
                cell_y,
                cell_z,
                f"SOLAR_WING_{side_name}_CELL_ZONE_{index + 1}",
                COLOR_SOLAR_CELL,
                "SOURCE_B5_CELL_INSET;"
                "DESIGN_PROPOSAL_CELL_ZONE_COUNT_GAP_AND_RECESS;"
                + CLAIM_LIMIT,
            )
        )

    return _module(f"MOD_SOLAR_ROOT_AND_STOWED_WING_{side_name}", children)


def _build_solar_roots_and_c5():
    return _module(
        "MOD_50_51_SOLAR_ROOT_01_AND_C5_NEGATIVE_PACKAGE",
        [
            _build_one_solar_side(1),
            _build_one_solar_side(-1),
        ],
    )


def _build_platform_fidelity_interfaces():
    children = []
    display_mat = "SOURCE_B5_DISPLAY_PROPOSAL;" + CLAIM_LIMIT

    # Camera and tracker envelopes.  Axis directions are recorded in labels.
    nav_len = SOURCE_B5_DISPLAY_NAV_CAM_BODY[2]
    nav_cross = SOURCE_B5_DISPLAY_NAV_CAM_BODY[0]
    children.append(
        _box_bounds(
            (
                SOURCE_B5_DISPLAY_NAV_CAM_AT[0] - nav_len / 2,
                SOURCE_B5_DISPLAY_NAV_CAM_AT[0] + nav_len / 2,
            ),
            (
                SOURCE_B5_DISPLAY_NAV_CAM_AT[1] - nav_cross / 2,
                SOURCE_B5_DISPLAY_NAV_CAM_AT[1] + nav_cross / 2,
            ),
            (
                SOURCE_B5_DISPLAY_NAV_CAM_AT[2] - nav_cross / 2,
                SOURCE_B5_DISPLAY_NAV_CAM_AT[2] + nav_cross / 2,
            ),
            "FIDELITY_NAV_CAMERA_ENVELOPE_AXIS_PLUS_X",
            COLOR_SENSOR,
            display_mat + ";FOV_AND_BORESIGHT_UNKNOWN",
        )
    )
    range_len = SOURCE_B5_DISPLAY_RANGE_BODY[2]
    range_cross = SOURCE_B5_DISPLAY_RANGE_BODY[0]
    children.append(
        _box_bounds(
            (
                SOURCE_B5_DISPLAY_RANGE_AT[0] - range_len / 2,
                SOURCE_B5_DISPLAY_RANGE_AT[0] + range_len / 2,
            ),
            (
                SOURCE_B5_DISPLAY_RANGE_AT[1] - range_cross / 2,
                SOURCE_B5_DISPLAY_RANGE_AT[1] + range_cross / 2,
            ),
            (
                SOURCE_B5_DISPLAY_RANGE_AT[2] - range_cross / 2,
                SOURCE_B5_DISPLAY_RANGE_AT[2] + range_cross / 2,
            ),
            "FIDELITY_RANGE_SENSOR_ENVELOPE_AXIS_PLUS_X",
            COLOR_SENSOR,
            display_mat + ";FOV_AND_BORESIGHT_UNKNOWN",
        )
    )
    st_xy = SOURCE_B5_DISPLAY_STAR_TRACKER_BODY[0]
    st_z = SOURCE_B5_DISPLAY_STAR_TRACKER_BODY[2]
    children.append(
        _box_bounds(
            (
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[0] - st_xy / 2,
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[0] + st_xy / 2,
            ),
            (
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[1] - st_xy / 2,
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[1] + st_xy / 2,
            ),
            (
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[2] - st_z / 2,
                SOURCE_B5_DISPLAY_STAR_TRACKER_AT[2] + st_z / 2,
            ),
            "FIDELITY_STAR_TRACKER_ENVELOPE_AXIS_PLUS_Z",
            COLOR_SENSOR,
            display_mat + ";FOV_AND_BORESIGHT_UNKNOWN",
        )
    )

    # External communication and thermal interfaces.
    children.append(
        _box_bounds(
            (
                SOURCE_B5_DISPLAY_SBAND_AT[0]
                - SOURCE_B5_DISPLAY_SBAND_THICKNESS,
                SOURCE_B5_DISPLAY_SBAND_AT[0],
            ),
            (
                SOURCE_B5_DISPLAY_SBAND_AT[1]
                - SOURCE_B5_DISPLAY_SBAND_SQUARE / 2,
                SOURCE_B5_DISPLAY_SBAND_AT[1]
                + SOURCE_B5_DISPLAY_SBAND_SQUARE / 2,
            ),
            (
                SOURCE_B5_DISPLAY_SBAND_AT[2]
                - SOURCE_B5_DISPLAY_SBAND_SQUARE / 2,
                SOURCE_B5_DISPLAY_SBAND_AT[2]
                + SOURCE_B5_DISPLAY_SBAND_SQUARE / 2,
            ),
            "FIDELITY_SBAND_PATCH_INTERFACE_FACE_NEGATIVE_X",
            COLOR_SENSOR,
            display_mat + ";RF_MODEL_UNKNOWN",
        )
    )
    children.append(
        _box_bounds(
            (
                SOURCE_B5_DISPLAY_GNSS_AT[0]
                - SOURCE_B5_DISPLAY_GNSS_SQUARE / 2,
                SOURCE_B5_DISPLAY_GNSS_AT[0]
                + SOURCE_B5_DISPLAY_GNSS_SQUARE / 2,
            ),
            (
                SOURCE_B5_DISPLAY_GNSS_AT[1]
                - SOURCE_B5_DISPLAY_GNSS_SQUARE / 2,
                SOURCE_B5_DISPLAY_GNSS_AT[1]
                + SOURCE_B5_DISPLAY_GNSS_SQUARE / 2,
            ),
            (
                SOURCE_B5_DISPLAY_GNSS_AT[2],
                SOURCE_B5_DISPLAY_GNSS_AT[2]
                + SOURCE_B5_DISPLAY_GNSS_THICKNESS,
            ),
            "FIDELITY_GNSS_PATCH_INTERFACE_FACE_PLUS_Z",
            COLOR_SENSOR,
            display_mat + ";RF_MODEL_UNKNOWN",
        )
    )
    children.append(
        _box_bounds(
            SOURCE_B5_DISPLAY_RADIATOR_X,
            (
                -SOURCE_B5_DISPLAY_RADIATOR_HALF_WIDTH,
                SOURCE_B5_DISPLAY_RADIATOR_HALF_WIDTH,
            ),
            (
                SOURCE_B5_BUS_HALF_YZ,
                SOURCE_B5_BUS_HALF_YZ
                + SOURCE_B5_DISPLAY_RADIATOR_THICKNESS,
            ),
            "FIDELITY_RADIATOR_PLUS_Z_FUNCTIONAL_SURFACE",
            COLOR_THERMAL,
            display_mat + ";THERMAL_PERFORMANCE_UNKNOWN",
        )
    )

    # Rear propulsion module envelopes and one bell-shaped main nozzle.
    for index, (yc, zc) in enumerate(
        SOURCE_B5_DISPLAY_CORNER_CENTERS_YZ,
        start=1,
    ):
        h = SOURCE_B5_DISPLAY_CORNER_MODULE_HALF
        children.append(
            _box_bounds(
                SOURCE_B5_DISPLAY_CORNER_MODULE_X,
                (yc - h, yc + h),
                (zc - h, zc + h),
                f"FIDELITY_REAR_PROPULSION_CORNER_MODULE_{index}",
                COLOR_PROPULSION,
                display_mat + ";THRUST_AND_PLUME_UNKNOWN",
            )
        )

    thruster = Cone(
        DESIGN_PROPOSAL_THRUSTER_EXIT_DIAMETER / 2,
        SOURCE_B5_DISPLAY_MAIN_THRUSTER_DIAMETER / 2,
        SOURCE_B5_DISPLAY_MAIN_THRUSTER_LENGTH,
        rotation=(0, -90, 0),
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                SOURCE_B5_DISPLAY_MAIN_THRUSTER_AT_X
                - SOURCE_B5_DISPLAY_MAIN_THRUSTER_LENGTH / 2,
                SOURCE_B5_DISPLAY_MAIN_THRUSTER_YZ[0],
                SOURCE_B5_DISPLAY_MAIN_THRUSTER_YZ[1],
            )
        )
    )
    children.append(
        _named(
            thruster,
            "FIDELITY_MAIN_THRUSTER_BELL_DISPLAY_PROPOSAL_EXIT",
            COLOR_PROPULSION,
            "SOURCE_B5_INLET_D40_AND_LENGTH30;"
            "DESIGN_PROPOSAL_THRUSTER_EXIT_DIAMETER;"
            "THRUST_AND_PLUME_UNKNOWN;"
            + CLAIM_LIMIT,
        )
    )

    # Detached B5 display anchor: not a kinematic pose and not B601 geometry.
    stack_x = SOURCE_B5_DISPLAY_CAPTURE_STACK_X0
    for name, diameter, length in SOURCE_B5_DISPLAY_CAPTURE_STACK:
        if name == "CAM_RING":
            element = _ring_x(
                (stack_x, stack_x + length),
                (0.0, 0.0),
                diameter,
                DESIGN_PROPOSAL_CAPTURE_WINDOW_DIAMETER,
                "FIDELITY_CAPTURE_CAM_RING_WITH_VISUAL_WINDOW_REFERENCE",
                COLOR_SENSOR,
                "SOURCE_B5_DISPLAY_PROPOSAL;"
                "DESIGN_PROPOSAL_CAPTURE_WINDOW_DIAMETER;"
                "DETACHED_DISPLAY_ANCHOR_NOT_KINEMATICS;"
                + CLAIM_LIMIT,
            )
            window = _cylinder_x(
                (
                    stack_x + length - DESIGN_PROPOSAL_CAMERA_WINDOW_DEPTH,
                    stack_x + length,
                ),
                (0.0, 0.0),
                DESIGN_PROPOSAL_CAPTURE_WINDOW_DIAMETER,
                "FIDELITY_CAPTURE_VISUAL_WINDOW_DESIGN_PROPOSAL",
                COLOR_SENSOR,
                "DESIGN_PROPOSAL_CAMERA_WINDOW_DEPTH;"
                "DETACHED_DISPLAY_ANCHOR_NOT_KINEMATICS;"
                + CLAIM_LIMIT,
            )
            children.extend([element, window])
        else:
            children.append(
                _cylinder_x(
                    (stack_x, stack_x + length),
                    (0.0, 0.0),
                    diameter,
                    f"FIDELITY_CAPTURE_{name}_DISPLAY_ENVELOPE",
                    COLOR_MOUNT,
                    "SOURCE_B5_DISPLAY_PROPOSAL;"
                    "DETACHED_DISPLAY_ANCHOR_NOT_KINEMATICS;"
                    + CLAIM_LIMIT,
                )
            )
        stack_x += length

    return _module("MOD_60_90_FIDELITY_01A_EXTERNAL_INTERFACES", children)


def design_contract():
    """Deterministic numeric contract consumed by the local validator."""

    bus_width = 2 * SOURCE_B5_BUS_HALF_YZ
    stowed_package_width = 2 * SOURCE_B5_DISPLAY_WING_Y_ABS[1]
    return {
        "source_decision": SOURCE_DECISION,
        "source_b5_spec": SOURCE_B5_SPEC,
        "authority": {
            "geometry": "MECHANICAL_INTEGRATION_PROPOSAL",
            "kinematic": "NONE",
            "mass": "EXCLUDED",
            "structural": "LOAD_PATH_INTENT_ONLY",
        },
        "frozen": {
            "mount_plate_mm": [
                FROZEN_B601_MOUNT_PLATE_SIZE,
                FROZEN_B601_MOUNT_PLATE_SIZE,
                FROZEN_B601_MOUNT_PLATE_THICKNESS,
            ],
            "central_interface_diameter_mm": (
                FROZEN_B601_CENTRAL_INTERFACE_DIAMETER
            ),
        },
        "source_b5": {
            "bus_length_x_mm": SOURCE_B5_BUS_X[1] - SOURCE_B5_BUS_X[0],
            "bus_width_y_mm": bus_width,
            "bus_height_z_mm": bus_width,
            "mount_outer_face_x_mm": SOURCE_B5_DISPLAY_ADAPTER_X[1],
            "mid1_x_mm": SOURCE_B5_MID1_X,
            "mid2_x_mm": SOURCE_B5_MID2_X,
            "longeron_center_abs_yz_mm": SOURCE_B5_LONGERON_CENTER,
            "connector_reservation_diameter_mm": (
                SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_DIAMETER
            ),
            "harness_passage_diameter_mm": (
                SOURCE_B5_DISPLAY_HARNESS_PASSAGE_DIAMETER
            ),
        },
        "c5_negative": {
            "available_bus_width_mm": C5_AVAILABLE_MM,
            "stowed_package_width_mm": C5_REQUIRED_MM,
            "overage_mm": stowed_package_width - bus_width,
            "relation": "238.3 mm > 226.3 mm",
            "status": "NEGATIVE_PRESERVED_NOT_CLOSED",
            "solar_root_mechanism_lower_bound_width_mm": 302.3,
        },
        "holds": [
            "B601 bolt count/spec",
            "B601 bolt circle",
            "B601 locating-pin diameter/tolerance",
            "launch loads",
            "interface stiffness",
            "grounding and thermal interface",
            "connector model",
            "arm stow contact-face qualification",
            "arm HDRM/release/shock design",
            "solar deployment clearance and reliability",
            "C5 package closure",
        ],
    }


def gen_step():
    """Return one native-labeled assembly compound for CAD CLI export."""

    return Compound(
        children=[
            _build_primary_structure(),
            _build_b601_mount(),
            _build_arm_stow(),
            _build_solar_roots_and_c5(),
            _build_platform_fidelity_interfaces(),
        ],
        label="V22_MECHANICAL_CONTINUATION_ISOLATED",
        material=(
            "DECISION_V22_B601_CONTINUE_01;"
            "CANONICAL_TOP_WRITE_NO;"
            + CLAIM_LIMIT
        ),
    )
