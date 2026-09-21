"""B51R1 Master Skeleton V2 neutral STEP construction witness.

This file deliberately creates small positive-volume witness bodies so the
datum contract can be inspected in ordinary STEP tooling.  The bodies are not
physical spacecraft hardware and carry no mass, stiffness, load-path, mate,
manufacturing, qualification, or flight credit.
"""

from math import cos, radians, sin

from build123d import Align, Box, Compound, Cylinder, Location


# Authoritative dimensions in millimetres.
BUS_LENGTH = 366.0
TASK_FACE_X = 183.0
DYNAMICS_RAIL_X = 185.25
DISPLAY_RAIL_X = 198.0
MOUNT_SIDE = 160.0
CENTRAL_KEEP_OUT_D = 100.0
LONGERON_AXIS = 101.65
PRIMARY_OUTER = 110.15
PANEL_OUTER = 113.15
A0_CLOCK_DEG = 25.0

# Visual witness sizes only; never physical design dimensions.
AXIS_R = 0.80
FRAME_BAR = 1.20
PLANE_THICKNESS = 0.60
TRIAD_LENGTH = 26.0
TRIAD_R = 0.95


def label(shape, name):
    shape.label = name
    return shape


def rod_x(length, y, z, radius, name, x=0.0):
    shape = Cylinder(
        radius,
        length,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).moved(Location((x, y, z), (0.0, 90.0, 0.0)))
    return label(shape, name)


def rod_y(length, x, z, radius, name, y=0.0):
    shape = Cylinder(
        radius,
        length,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).moved(Location((x, y, z), (90.0, 0.0, 0.0)))
    return label(shape, name)


def rod_z(length, x, y, radius, name, z=0.0):
    shape = Cylinder(
        radius,
        length,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).moved(Location((x, y, z)))
    return label(shape, name)


def yz_square_frame(x, half_span, name):
    bars = [
        Box(
            FRAME_BAR,
            2.0 * half_span,
            FRAME_BAR,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).moved(Location((x, 0.0, +half_span))),
        Box(
            FRAME_BAR,
            2.0 * half_span,
            FRAME_BAR,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).moved(Location((x, 0.0, -half_span))),
        Box(
            FRAME_BAR,
            FRAME_BAR,
            2.0 * half_span,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).moved(Location((x, +half_span, 0.0))),
        Box(
            FRAME_BAR,
            FRAME_BAR,
            2.0 * half_span,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        ).moved(Location((x, -half_span, 0.0))),
    ]
    return label(Compound(children=bars), name)


def triad(x, name, angle_x_deg=0.0):
    # +X remains the clock axis. +Y/+Z are rotated about +X.
    a = radians(angle_x_deg)
    y_dir = (0.0, cos(a), sin(a))
    z_dir = (0.0, -sin(a), cos(a))
    x_axis = rod_x(TRIAD_LENGTH, 0.0, 0.0, TRIAD_R, f"{name}_X", x + TRIAD_LENGTH / 2.0)
    y_axis = Cylinder(
        TRIAD_R,
        TRIAD_LENGTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    ).moved(Location((x, 0.0, 0.0), (90.0 - angle_x_deg, 0.0, 0.0)))
    y_axis = label(y_axis, f"{name}_Y")
    # Build +Z then rotate about X. Explicit direction constants document intent.
    z_axis = Cylinder(
        TRIAD_R,
        TRIAD_LENGTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    ).moved(Location((x, 0.0, 0.0), (angle_x_deg, 0.0, 0.0)))
    z_axis = label(z_axis, f"{name}_Z")
    result = label(Compound(children=[x_axis, y_axis, z_axis]), name)
    result.metadata = {
        "x_axis": (1.0, 0.0, 0.0),
        "y_axis": y_dir,
        "z_axis": z_dir,
    }
    return result


def interface_plane_witness():
    plate = Box(
        PLANE_THICKNESS,
        MOUNT_SIDE,
        MOUNT_SIDE,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).moved(Location((DYNAMICS_RAIL_X, 0.0, 0.0)))
    keepout = Cylinder(
        CENTRAL_KEEP_OUT_D / 2.0,
        PLANE_THICKNESS + 2.0,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).moved(Location((DYNAMICS_RAIL_X, 0.0, 0.0), (0.0, 90.0, 0.0)))
    return label(
        plate - keepout,
        "IF_B601_MOUNT_160_SQUARE_KEEP_OUT_D100_DATUM_WITNESS_ONLY",
    )


def gen_step():
    children = []

    for y_sign, y_name in ((+1, "PY"), (-1, "NY")):
        for z_sign, z_name in ((+1, "PZ"), (-1, "NZ")):
            children.append(
                rod_x(
                    BUS_LENGTH,
                    y_sign * LONGERON_AXIS,
                    z_sign * LONGERON_AXIS,
                    AXIS_R,
                    f"AX_LONGERON_{y_name}_{z_name}_DATUM_WITNESS_ONLY",
                )
            )

    children.extend(
        [
            yz_square_frame(TASK_FACE_X, PRIMARY_OUTER, "PLN_TASK_FACE_X183_FRAME_WITNESS"),
            yz_square_frame(
                DYNAMICS_RAIL_X,
                PRIMARY_OUTER,
                "PLN_M_DYNAMICS_X185_25_FRAME_WITNESS",
            ),
            yz_square_frame(DISPLAY_RAIL_X, PANEL_OUTER, "PLN_M_DISPLAY_X198_FRAME_WITNESS"),
            interface_plane_witness(),
            triad(0.0, "CS_S"),
            triad(DYNAMICS_RAIL_X, "CS_M_DYNAMICS_X185_25"),
            triad(DISPLAY_RAIL_X, "CS_M_DISPLAY_X198"),
            triad(DYNAMICS_RAIL_X, "CS_A0_CLOCKED_25_DEG", A0_CLOCK_DEG),
        ]
    )

    root = Compound(children=children)
    root.label = "B51R1_MASTER_SKELETON_V2_STEP_WITNESS_DATUM_ONLY"
    return root

