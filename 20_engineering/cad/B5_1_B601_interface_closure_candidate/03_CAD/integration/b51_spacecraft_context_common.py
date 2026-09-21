"""B5.1 full-spacecraft static visualization in the existing CS_S frame.

This module composes read-only V2.2/VENDOR-CAD-03 inputs with the B5.1
bridge-adapter and saddle candidates.  It creates an engineering review
context only.  It does not alter donor files, close H9/H10, verify continuous
motion, or assign CAD mass authority.
"""

from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path

from build123d import Align, Box, Color, Compound, Location, import_step


MODEL_KIND = "assembly"
MODEL_NAME = "B51_SPACECRAFT_B601_STOW_INTEGRATION"

HERE = Path(__file__).resolve().parent
CANDIDATE_ROOT = HERE.parent.parent


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "20_engineering").is_dir():
            return candidate
    raise RuntimeError("Cannot resolve repository root from integration source")


REPO_ROOT = _find_repo_root(HERE)
V22_ROOT = (
    REPO_ROOT
    / "20_engineering"
    / "cad"
    / "Space_Embodied_Robot_CAD_V2_2"
)
VENDOR_ROOT = V22_ROOT / "130_B601_Vendor_CAD_Direct_Integration_03"
LAYOUT_SOURCE = (
    V22_ROOT
    / "110_Layout_and_Deployment_01"
    / "staging"
    / "layout_staging.py"
)
ARM_STEP = VENDOR_ROOT / "cad" / "B601_VENDOR_STOW.step"
REGISTRATION_JSON = VENDOR_ROOT / "design" / "group_link_transforms.json"

BRIDGE_STEP = CANDIDATE_ROOT / "03_CAD" / "step" / "B51_BRIDGE_ADAPTER.step"
MAIN_SADDLE_STEP = (
    CANDIDATE_ROOT / "03_CAD" / "step" / "B51_G07_MAIN_SADDLE.step"
)
GRIP_SADDLE_STEP = (
    CANDIDATE_ROOT / "03_CAD" / "step" / "B51_G08_GRIP_SADDLE.step"
)

CLAIM_LIMIT = (
    "ENGINEERING_CANDIDATE_HOLD;H9_HUMAN_DECISION_REQUIRED;"
    "H10_NOT_CLOSED;CONTINUOUS_MOTION_NOT_VERIFIED;"
    "NO_MANUFACTURING_FLIGHT_STRENGTH_CONTACT_OR_MASS_AUTHORITY"
)
MASS_AUTHORITY = (
    "ACCEPTED_URDF_ONLY_4.695555949342986_KG;"
    "CAD_AUTOMATIC_MASS_EXCLUDED"
)

MODE_A_BOUNDS_MM = (
    (-183.0, -113.15, -113.15),
    (183.0, 113.15, 115.15),
)
MODE_B_BOUNDS_MM = (
    (-213.0, -113.15, -115.0),
    (412.47, 113.15, 361.34),
)

GROUP_ORDER = [f"G{index:02d}" for index in range(1, 9)]
GROUP_NAMES = {
    "G01": "LINK1_DIRECT_NN",
    "G02": "LINK2_DIRECT_NN",
    "G03": "LINK3_DIRECT_NN",
    "G04": "LINK4_DIRECT_NN",
    "G05": "LINK6_CHAIN_DERIVED_HOLD",
    "G06": "BASE_DIRECT_NN",
    "G07": "LINK5_DIRECT_NN",
    "G08": "GRIPPER_CHAIN_DERIVED_HOLD",
}
GROUP_COLORS = {
    "G01": Color(0.66, 0.70, 0.74, 1.0),
    "G02": Color(0.93, 0.49, 0.12, 1.0),
    "G03": Color(0.16, 0.43, 0.78, 1.0),
    "G04": Color(0.08, 0.58, 0.58, 1.0),
    "G05": Color(0.86, 0.66, 0.10, 1.0),
    "G06": Color(0.18, 0.24, 0.34, 1.0),
    "G07": Color(0.70, 0.25, 0.58, 1.0),
    "G08": Color(0.24, 0.66, 0.32, 1.0),
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load source module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def layout_module():
    return _load_module("b51_v22_layout_read_only", LAYOUT_SOURCE)


def _tag(shape, label: str, material: str, color: Color | None = None):
    shape.label = label
    shape.material = material
    if color is not None:
        shape.color = color
    return shape


def _paint_solids(shape, color: Color, material: str) -> None:
    shape.color = color
    shape.material = material
    for solid in shape.solids():
        solid.color = color
        solid.material = material


def build_primary_structure():
    shape = layout_module().build_revised_primary_structure()
    return _tag(
        shape,
        "V22_REVISED_PRIMARY_STRUCTURE_READ_ONLY_CS_S",
        "V22_DONOR_READ_ONLY;" + CLAIM_LIMIT,
    )


def build_legacy_external_references_filtered():
    source = layout_module().build_legacy_device_references()
    kept = []
    for item in list(source.children):
        label = str(getattr(item, "label", "UNLABELLED_V22_REFERENCE"))
        if "FIDELITY_CAPTURE_" in label:
            continue
        item.material = (
            str(getattr(item, "material", ""))
            + ";V22_DONOR_READ_ONLY;"
            + CLAIM_LIMIT
        )
        kept.append(item)
    return Compound(
        children=kept,
        label="V22_EXTERNAL_INTERFACE_REFERENCES_FILTERED_READ_ONLY",
        material="V22_DONOR_READ_ONLY;" + CLAIM_LIMIT,
    )


def build_solar_stow_reference():
    shape = layout_module().build_solar(
        0.0,
        0.0,
        "B51_STOW_STATIC_REFERENCE_ENGINEERING_CANDIDATE_HOLD",
    )
    return _tag(
        shape,
        "V22_SOLAR_STOW_0_0_STATIC_REFERENCE_READ_ONLY",
        "STATIC_ENDPOINT_ONLY;NO_CONTINUOUS_SWEEP_EVIDENCE;"
        "V22_DONOR_READ_ONLY;"
        + CLAIM_LIMIT,
    )


def build_solar_deployed_moving_panel_reference():
    deployed = layout_module().build_solar(
        90.0,
        90.0,
        "B51_DEPLOYED_ENDPOINT_DIAGNOSTIC_HOLD",
    )
    moving = list(deployed.children)[2:]
    ghost_color = Color(0.18, 0.55, 0.92, 0.24)
    for index, item in enumerate(moving, start=1):
        label = str(getattr(item, "label", f"MOVING_PANEL_{index}"))
        _tag(
            item,
            label + "_TRANSPARENT_ENDPOINT_REFERENCE",
            "REFERENCE_NON_PHYSICAL;STATIC_90_DEG_ENDPOINT_ONLY;"
            "NO_CONTINUOUS_SWEEP_EVIDENCE;"
            + CLAIM_LIMIT,
            ghost_color,
        )
        _paint_solids(
            item,
            ghost_color,
            "REFERENCE_NON_PHYSICAL;STATIC_90_DEG_ENDPOINT_ONLY;"
            + CLAIM_LIMIT,
        )
    return Compound(
        children=moving,
        label="V22_SOLAR_DEPLOYED_90_90_TRANSPARENT_ENDPOINT_REFERENCE_HOLD",
        material="REFERENCE_NON_PHYSICAL;STATIC_ENDPOINT_ONLY;" + CLAIM_LIMIT,
    )


def _import_candidate_step(path: Path, label: str):
    shape = import_step(path)
    return _tag(
        shape,
        label,
        "IDENTITY_PLACEMENT_IN_CS_S;B51_CANDIDATE_SOURCE_READ_ONLY;"
        + CLAIM_LIMIT,
    )


def build_bridge_adapter():
    return _import_candidate_step(
        BRIDGE_STEP,
        "B51_BRIDGE_ADAPTER_IDENTITY_IN_CS_S_ENGINEERING_CANDIDATE_HOLD",
    )


def build_main_saddle():
    return _import_candidate_step(
        MAIN_SADDLE_STEP,
        "B51_G07_MAIN_DOUBLE_TRIANGLE_SADDLE_IDENTITY_IN_CS_S_HOLD",
    )


def build_grip_saddle():
    return _import_candidate_step(
        GRIP_SADDLE_STEP,
        "B51_G08_GRIP_DOUBLE_TRIANGLE_SADDLE_IDENTITY_IN_CS_S_HOLD",
    )


def build_vendor_b601_stow():
    """Import exact VENDOR-CAD-03 STOW geometry and expose eight traceable groups."""

    registration = json.loads(REGISTRATION_JSON.read_text(encoding="utf-8"))
    registered_order = list(registration["adopted"].keys())
    if registered_order != GROUP_ORDER:
        raise RuntimeError(
            f"Unexpected donor group order: {registered_order}; "
            f"expected {GROUP_ORDER}"
        )

    imported = import_step(ARM_STEP)
    raw_groups = list(imported.children)
    if len(raw_groups) != len(GROUP_ORDER):
        raise RuntimeError(
            f"Vendor STOW STEP has {len(raw_groups)} top-level groups; expected 8"
        )

    traced_groups = []
    for group_id, raw_group in zip(GROUP_ORDER, raw_groups):
        registration_status = registration["adopted"][group_id]["method"]
        material = (
            f"VENDOR_GEOMETRY_READ_ONLY;GROUP={group_id};"
            f"REGISTRATION={registration_status};"
            f"{MASS_AUTHORITY};{CLAIM_LIMIT}"
        )
        solids = list(raw_group.solids())
        for solid_index, solid in enumerate(solids, start=1):
            solid.label = (
                f"B601_STOW_{group_id}_VENDOR_SOLID_{solid_index:03d}_READ_ONLY"
            )
            solid.color = GROUP_COLORS[group_id]
            solid.material = material
        traced_groups.append(
            Compound(
                children=solids,
                label=(
                    f"B601_VENDOR_STOW_{group_id}_{GROUP_NAMES[group_id]}_"
                    "READ_ONLY"
                ),
                material=material,
            )
        )

    return Compound(
        children=traced_groups,
        label="B601_VENDOR_STOW_EXACT_GEOMETRY_READ_ONLY_IDENTITY_IN_CS_S",
        material=f"{MASS_AUTHORITY};{CLAIM_LIMIT}",
    )


def _envelope_shell(
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    label: str,
    color: Color,
    material: str,
    wall_mm: float = 0.80,
):
    lower, upper = bounds
    size = tuple(upper[index] - lower[index] for index in range(3))
    center = tuple((upper[index] + lower[index]) / 2.0 for index in range(3))
    inner_size = tuple(value - 2.0 * wall_mm for value in size)
    if min(inner_size) <= 0.0:
        raise ValueError("Envelope wall is larger than its bounding volume")
    outer = Box(
        *size,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(center))
    inner = Box(
        *inner_size,
        align=(Align.CENTER, Align.CENTER, Align.CENTER),
    ).located(Location(center))
    shell = outer - inner
    return _tag(shell, label, material, color)


def build_mode_a_envelope():
    return _envelope_shell(
        MODE_A_BOUNDS_MM,
        "MODE_A_12U_DEPLOYER_CURRENT_CORE_BOX_PROXY_TRANSPARENT_HOLD",
        Color(0.94, 0.16, 0.12, 0.20),
        "REFERENCE_NON_PHYSICAL;NO_LAUNCHER_DEPLOYER_ICD_BOUND;"
        "ARCHITECTURE_NOT_PACKAGING_COMPLIANT_AGAINST_CURRENT_CORE_BOX_PROXY;"
        + CLAIM_LIMIT,
    )


def build_mode_b_envelope():
    return _envelope_shell(
        MODE_B_BOUNDS_MM,
        "MODE_B_12U_CLASS_BUS_EXTERNAL_SERVICE_MODULE_PROVISIONAL_"
        "TRANSPARENT_HOLD",
        Color(0.18, 0.48, 0.90, 0.13),
        "REFERENCE_NON_PHYSICAL;PROVISIONAL_TWO_FILE_UNION;"
        "NOT_FINAL_FLIGHT_ENVELOPE;HUMAN_DECISION_REQUIRED;"
        + CLAIM_LIMIT,
    )


def build_component_map(include_arm: bool = True):
    components = {
        "primary_structure": build_primary_structure(),
        "external_references": build_legacy_external_references_filtered(),
        "solar_stow": build_solar_stow_reference(),
        "bridge_adapter": build_bridge_adapter(),
        "main_saddle": build_main_saddle(),
        "grip_saddle": build_grip_saddle(),
    }
    if include_arm:
        components["b601_stow"] = build_vendor_b601_stow()
    components["mode_a_envelope"] = build_mode_a_envelope()
    components["mode_b_envelope"] = build_mode_b_envelope()
    return components


def build_full_integration():
    components = build_component_map(include_arm=True)
    return Compound(
        children=list(components.values()),
        label=(
            "B51_FULL_SPACECRAFT_B601_STOW_ENGINEERING_CANDIDATE_HOLD_"
            "H9_H10_MOTION_OPEN"
        ),
        material=f"{MASS_AUTHORITY};{CLAIM_LIMIT}",
    )


def build_solar_state_reference():
    components = build_component_map(include_arm=False)
    components["solar_deployed_endpoint"] = (
        build_solar_deployed_moving_panel_reference()
    )
    return Compound(
        children=list(components.values()),
        label=(
            "B51_SOLAR_STOW_AND_DEPLOYED_ENDPOINT_REFERENCE_"
            "ENGINEERING_CANDIDATE_HOLD"
        ),
        material=(
            "B601_REAL_STOW_BOUND_BY_PRIMARY_INTEGRATION_STEP;"
            "ENDPOINTS_ONLY_NO_CONTINUOUS_SWEEP;"
            + CLAIM_LIMIT
        ),
    )


def source_contract():
    return {
        "model": MODEL_NAME,
        "frame": "CS_S",
        "placements": "IDENTITY_FOR_ALL_IMPORTED_CS_S_OCCURRENCES",
        "mode_a_bounds_mm": MODE_A_BOUNDS_MM,
        "mode_b_bounds_mm": MODE_B_BOUNDS_MM,
        "vendor_group_order": GROUP_ORDER,
        "mass_authority": MASS_AUTHORITY,
        "claim_limit": CLAIM_LIMIT,
        "inputs": {
            "layout_source": str(LAYOUT_SOURCE),
            "vendor_b601_stow_step": str(ARM_STEP),
            "registration_json": str(REGISTRATION_JSON),
            "bridge_step": str(BRIDGE_STEP),
            "main_saddle_step": str(MAIN_SADDLE_STEP),
            "grip_saddle_step": str(GRIP_SADDLE_STEP),
        },
    }

