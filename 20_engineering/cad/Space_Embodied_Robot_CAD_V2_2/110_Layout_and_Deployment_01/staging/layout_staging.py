"""Isolated V22 layout/deployment staging assembly.

This source composes read-only accepted/proposal sources in CS_S and applies
only the explicitly registered staging revisions:

* bilateral shallow cassette pockets in a copied primary-structure model;
* V22_TOP_LAYOUT_FRAME -> CS_S transform T=[0, 0, 119.15] mm;
* independent left/right solar angles;
* read-only accepted-URDF q0 conservative boxes where state policy permits.

It does not edit the canonical SolidWorks top assembly.  STEP outputs have no
native configuration, mate, BOM, or mass authority.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any

from build123d import Align, Box, Color, Compound, Location


MODEL_KIND = "assembly"
MODEL_NAME = "V22_LAYOUT_AND_DEPLOYMENT_01_ISOLATED_STAGING"
ROOT = Path(__file__).resolve().parent
TASK_ROOT = ROOT.parent
V22_ROOT = TASK_ROOT.parent
CAD_ROOT = V22_ROOT.parent
PRIOR_SOURCE = (
    V22_ROOT / "100_Mechanical_Continuation" / "v22_mechanical_continuation.py"
)
SOLAR_SOURCE = TASK_ROOT / "solar" / "solar_deployment_test_rig.py"
ARM_SOURCE = TASK_ROOT / "arm_stow" / "arm_stow_layout.py"
STATE_POLICY_PATH = TASK_ROOT / "design" / "state_policy.json"
Q0_BOX_PATH = (
    CAD_ROOT
    / "Space_Embodied_Robot_CAD_V2_0"
    / "evidence"
    / "b3_06"
    / "b601_q0_boxes.json"
)

CS_S_TOP_EXTERIOR_Z_MM = 113.15
TOP_LAYOUT_TO_CS_S_Z_MM = 119.15
POCKET_X_BOUNDS_MM = (-175.0, 53.0)
POCKET_LEFT_Y_BOUNDS_MM = (106.5, 113.15)
POCKET_RIGHT_Y_BOUNDS_MM = (-113.15, -106.5)
POCKET_Z_BOUNDS_MM = (-111.65, 94.35)

CLAIM_LIMIT = (
    "ISOLATED_LAYOUT_STAGING_ONLY;CANONICAL_TOP_WRITE_NO;"
    "STEP_HAS_NO_NATIVE_CONFIGURATION_MATE_BOM_OR_MASS_AUTHORITY;"
    "NO_STRENGTH_STIFFNESS_RELEASE_RELIABILITY_MANUFACTURING_OR_FLIGHT_CLAIM"
)
POCKET_MATERIAL = (
    "PRIMARY_STRUCTURE_POCKET_DESIGN_PROPOSAL;"
    "RESIDUAL_SECTION_STRENGTH_AND_JOINTS_HOLD;"
    + CLAIM_LIMIT
)
Q0_MATERIAL = (
    "ACCEPTED_URDF_Q0_TRANSFORM_READ_ONLY;"
    "CONSERVATIVE_AXIS_ALIGNED_PROXY;MASS_EXCLUDED_FROM_STEP;"
    + CLAIM_LIMIT
)
REFERENCE_MATERIAL = "REFERENCE_NON_PHYSICAL;" + CLAIM_LIMIT

COLOR_Q0 = Color(0.58, 0.62, 0.68, 0.72)
COLOR_POCKET_DATUM = Color(0.96, 0.16, 0.18, 0.28)
COLOR_LEGACY_CONFLICT = Color(0.92, 0.08, 0.08, 0.42)


STATE_DEFS = {
    "STOWED": {
        "left_deg": 0.0,
        "right_deg": 0.0,
        "q0": False,
        "label": "STOWED_LAYOUT_CANDIDATE_HOLD_B601_HIFI_ABSENT",
    },
    "DEPLOYED_NOMINAL": {
        "left_deg": 90.0,
        "right_deg": 90.0,
        "q0": True,
        "label": "DEPLOYED_NOMINAL_Q0_DIAGNOSTIC_ONLY",
    },
    "DEPLOY_FAILED_BOTH": {
        "left_deg": 0.0,
        "right_deg": 0.0,
        "q0": True,
        "label": "DEPLOY_FAILED_BOTH_Q0_DIAGNOSTIC_ONLY",
    },
    "L_FAIL": {
        "left_deg": 0.0,
        "right_deg": 90.0,
        "q0": True,
        "label": "L_FAIL_Q0_DIAGNOSTIC_ONLY",
    },
    "R_FAIL": {
        "left_deg": 90.0,
        "right_deg": 0.0,
        "q0": True,
        "label": "R_FAIL_Q0_DIAGNOSTIC_ONLY",
    },
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load source module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bbox_tuple(shape) -> tuple[float, float, float, float, float, float]:
    bb = shape.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z)


def _bbox_overlap(
    left: tuple[float, float, float, float, float, float],
    right: tuple[float, float, float, float, float, float],
) -> bool:
    return all(
        min(left[index + 3], right[index + 3])
        - max(left[index], right[index])
        > 1.0e-9
        for index in range(3)
    )


def _named(shape, label: str, color=None, material: str = CLAIM_LIMIT):
    shape.label = label
    if color is not None:
        shape.color = color
    shape.material = material
    return shape


def _box_bounds(
    x: tuple[float, float],
    y: tuple[float, float],
    z: tuple[float, float],
    label: str,
    color,
    material: str,
):
    shape = Box(
        x[1] - x[0],
        y[1] - y[0],
        z[1] - z[0],
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(
        Location(
            (
                (x[0] + x[1]) / 2.0,
                (y[0] + y[1]) / 2.0,
                (z[0] + z[1]) / 2.0,
            )
        )
    )
    return _named(shape, label, color, material)


def _pocket_tools():
    return [
        _box_bounds(
            POCKET_X_BOUNDS_MM,
            POCKET_LEFT_Y_BOUNDS_MM,
            POCKET_Z_BOUNDS_MM,
            "CUT_TOOL_LEFT_RECESSED_CASSETTE_POCKET_NON_OUTPUT",
            COLOR_POCKET_DATUM,
            REFERENCE_MATERIAL,
        ),
        _box_bounds(
            POCKET_X_BOUNDS_MM,
            POCKET_RIGHT_Y_BOUNDS_MM,
            POCKET_Z_BOUNDS_MM,
            "CUT_TOOL_RIGHT_RECESSED_CASSETTE_POCKET_NON_OUTPUT",
            COLOR_POCKET_DATUM,
            REFERENCE_MATERIAL,
        ),
    ]


def build_revised_primary_structure():
    """Copy prior primary geometry and subtract the bilateral staging pockets."""

    prior = _load_module("v22_prior_for_staging", PRIOR_SOURCE)
    source_module = prior._build_primary_structure()
    tools = _pocket_tools()
    tool_bounds = [_bbox_tuple(tool) for tool in tools]
    revised_children = []

    for source_shape in list(source_module.children):
        source_label = str(getattr(source_shape, "label", "UNLABELLED_PRIMARY"))
        source_color = getattr(source_shape, "color", None)
        source_material = str(getattr(source_shape, "material", ""))
        revised = source_shape
        was_cut = False
        for tool, tool_bbox in zip(tools, tool_bounds):
            if _bbox_overlap(_bbox_tuple(revised), tool_bbox):
                revised = revised - tool
                was_cut = True
        if not revised.solids():
            raise RuntimeError(
                f"Cassette pocket removed an entire primary member: {source_label}"
            )
        suffix = "_CASSETTE_POCKET_REVISED" if was_cut else ""
        material = (
            POCKET_MATERIAL
            if was_cut
            else source_material + ";" + CLAIM_LIMIT
        )
        revised_children.append(
            _named(
                revised,
                source_label + suffix,
                source_color,
                material,
            )
        )

    # Thin datum witnesses mark the inboard pocket boundary without filling
    # the removed volume.
    witness_thickness = 0.20
    revised_children.extend(
        [
            _box_bounds(
                POCKET_X_BOUNDS_MM,
                (
                    POCKET_LEFT_Y_BOUNDS_MM[0] - witness_thickness,
                    POCKET_LEFT_Y_BOUNDS_MM[0],
                ),
                POCKET_Z_BOUNDS_MM,
                "REFERENCE_NON_PHYSICAL_LEFT_POCKET_INBOARD_DATUM_Y106_5",
                COLOR_POCKET_DATUM,
                REFERENCE_MATERIAL,
            ),
            _box_bounds(
                POCKET_X_BOUNDS_MM,
                (
                    POCKET_RIGHT_Y_BOUNDS_MM[1],
                    POCKET_RIGHT_Y_BOUNDS_MM[1] + witness_thickness,
                ),
                POCKET_Z_BOUNDS_MM,
                "REFERENCE_NON_PHYSICAL_RIGHT_POCKET_INBOARD_DATUM_YM106_5",
                COLOR_POCKET_DATUM,
                REFERENCE_MATERIAL,
            ),
        ]
    )

    return Compound(
        children=revised_children,
        label="MOD_PLATFORM_10_PRIMARY_STRUCTURE_WITH_BILATERAL_CASSETTE_POCKETS",
        material=POCKET_MATERIAL,
    )


def build_platform_and_mount():
    prior = _load_module("v22_prior_mount_for_staging", PRIOR_SOURCE)
    return Compound(
        children=[
            build_revised_primary_structure(),
            prior._build_b601_mount(),
            build_legacy_device_references(),
        ],
        label="PLATFORM_MOUNT_AND_LEGACY_DEVICE_REFERENCES",
        material=CLAIM_LIMIT,
    )


def build_legacy_device_references():
    """Retain prior display interfaces and expose the star-tracker clash.

    The original top-centre star-tracker envelope intersects the revised aft
    crossbeam.  It remains visible as a red NON_PHYSICAL conflict witness while
    the Gate-4 side-band sensor reservation carries the relocation intent.
    """

    prior = _load_module("v22_prior_devices_for_staging", PRIOR_SOURCE)
    source = prior._build_platform_fidelity_interfaces()
    children = []
    for item in list(source.children):
        label = str(getattr(item, "label", "UNLABELLED_LEGACY_DEVICE"))
        if label == "FIDELITY_STAR_TRACKER_ENVELOPE_AXIS_PLUS_Z":
            item.label = (
                "REFERENCE_NON_PHYSICAL_LEGACY_STAR_TRACKER_"
                "AFT_CROSSBEAM_CONFLICT_RELOCATION_HOLD"
            )
            item.color = COLOR_LEGACY_CONFLICT
            item.material = (
                "REFERENCE_NON_PHYSICAL;PRESERVED_5625_MM3_PRE_RELOCATION_"
                "INTERSECTION_WITNESS;FOV_MOUNT_AND_HARNESS_HOLD;"
                + CLAIM_LIMIT
            )
        else:
            item.material = str(getattr(item, "material", "")) + ";" + CLAIM_LIMIT
        children.append(item)
    return Compound(
        children=children,
        label="MOD_LEGACY_EXTERNAL_INTERFACES_WITH_STAR_TRACKER_CONFLICT_WITNESS",
        material=CLAIM_LIMIT,
    )


def build_arm_stow_in_cs_s():
    arm = _load_module("arm_stow_for_staging", ARM_SOURCE)
    spec = arm.load_spec()
    entities = arm.make_entities()
    transform = Location((0.0, 0.0, TOP_LAYOUT_TO_CS_S_Z_MM))
    grouped: dict[str, list] = {group_id: [] for group_id in spec["groups"]}
    for item in spec["entities"]:
        placed = entities[item["id"]].moved(transform)
        placed.label = item["label"] + "_IN_CS_S"
        placed.material = (
            str(getattr(placed, "material", ""))
            + ";T_CS_S_FROM_TOP_LAYOUT_0_0_119_15;"
            + CLAIM_LIMIT
        )
        grouped[item["group"]].append(placed)
    groups = [
        Compound(
            children=grouped[group_id],
            label=group_label + "_IN_CS_S",
            material=CLAIM_LIMIT,
        )
        for group_id, group_label in spec["groups"].items()
    ]
    return Compound(
        children=groups,
        label="MOD_ARM_STOW_LAYOUT_IN_CS_S_TZ119_15",
        material=CLAIM_LIMIT,
    )


def build_solar(left_deg: float, right_deg: float, state_label: str):
    solar = _load_module("solar_for_staging", SOLAR_SOURCE)
    return Compound(
        children=[
            solar._fixed_cassette(1),
            solar._fixed_cassette(-1),
            solar._moving_panel(1, left_deg, state_label),
            solar._moving_panel(-1, right_deg, state_label),
        ],
        label=(
            f"MOD_SOLAR_RECESSED_BOOK_FOLD_L{left_deg:06.2f}_"
            f"R{right_deg:06.2f}_{state_label}"
        ),
        material=CLAIM_LIMIT,
    )


def build_q0_proxy():
    data = json.loads(Q0_BOX_PATH.read_text(encoding="utf-8"))
    children = []
    for link_name, link_data in data["links"].items():
        lower, upper = link_data["s_box_mm"]
        children.append(
            _box_bounds(
                (lower[0], upper[0]),
                (lower[1], upper[1]),
                (lower[2], upper[2]),
                f"B601_{link_name}_Q0_CONSERVATIVE_AABB_PROXY",
                COLOR_Q0,
                Q0_MATERIAL,
            )
        )
    return Compound(
        children=children,
        label="MOD_B601_ACCEPTED_URDF_Q0_CONSERVATIVE_PROXY",
        material=Q0_MATERIAL,
    )


def load_state_policy() -> dict[str, Any]:
    return json.loads(STATE_POLICY_PATH.read_text(encoding="utf-8"))


def build_state(state_id: str):
    state_id = state_id.strip().upper()
    if state_id in {"PARTIAL", "SERVICE"}:
        raise ValueError(
            f"{state_id} has no geometry binding by fail-closed state policy"
        )
    if state_id not in STATE_DEFS:
        raise ValueError(
            f"STAGING_STATE must be one of {sorted(STATE_DEFS)}; got {state_id}"
        )
    state = STATE_DEFS[state_id]
    children = [
        build_platform_and_mount(),
        build_arm_stow_in_cs_s(),
        build_solar(
            state["left_deg"],
            state["right_deg"],
            state["label"],
        ),
    ]
    if state["q0"]:
        children.append(build_q0_proxy())
    return Compound(
        children=children,
        label=f"{MODEL_NAME}_{state['label']}",
        material=CLAIM_LIMIT,
    )


def design_contract() -> dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "frame": "CS_S",
        "top_layout_to_cs_s_translation_mm": [
            0.0,
            0.0,
            TOP_LAYOUT_TO_CS_S_Z_MM,
        ],
        "cassette_pockets": {
            "x_bounds_mm": list(POCKET_X_BOUNDS_MM),
            "left_y_bounds_mm": list(POCKET_LEFT_Y_BOUNDS_MM),
            "right_y_bounds_mm": list(POCKET_RIGHT_Y_BOUNDS_MM),
            "z_bounds_mm": list(POCKET_Z_BOUNDS_MM),
            "structural_status": "HOLD",
        },
        "states_with_step_geometry": sorted(STATE_DEFS),
        "states_without_geometry_binding": ["PARTIAL", "SERVICE"],
        "q0_proxy_source": str(Q0_BOX_PATH),
        "canonical_top_write": False,
        "authority": CLAIM_LIMIT,
    }


def gen_step():
    return build_state(os.environ.get("STAGING_STATE", "DEPLOYED_NOMINAL"))


if __name__ == "__main__":
    state_id = os.environ.get("STAGING_STATE", "DEPLOYED_NOMINAL")
    model = build_state(state_id)
    print(MODEL_NAME)
    print(f"state={state_id}")
    print(f"solids={len(model.solids())}")
    print(f"bbox={model.bounding_box().size}")
