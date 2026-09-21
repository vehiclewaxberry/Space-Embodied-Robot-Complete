"""Deterministic, low-memory analytic builder for the 340.5 mm bus structure candidate.

This module never imports a CAD kernel and never emits STEP/FCStd.  It produces the
source-only engineering ledger, a GUM/Monte-Carlo uncertainty screen, a nonqualifying
rail-stiffness screen, and a fail-closed PRB-17 delta.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
INPUT_PATH = PACKAGE / "BUS_PRIMARY_STRUCTURE_DESIGN_INPUTS_V1.json"


def _json_write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _mat_zero() -> list[list[float]]:
    return [[0.0, 0.0, 0.0] for _ in range(3)]


def _mat_add(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[a[i][j] + b[i][j] for j in range(3)] for i in range(3)]


def _mat_sub(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[a[i][j] - b[i][j] for j in range(3)] for i in range(3)]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _transpose(a: list[list[float]]) -> list[list[float]]:
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _rotation_x(deg: float) -> list[list[float]]:
    angle = math.radians(deg)
    c, s = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def _parallel_axis(mass: float, r: tuple[float, float, float]) -> list[list[float]]:
    x, y, z = r
    rr = x * x + y * y + z * z
    return [
        [mass * (rr - x * x), -mass * x * y, -mass * x * z],
        [-mass * x * y, mass * (rr - y * y), -mass * y * z],
        [-mass * x * z, -mass * y * z, mass * (rr - z * z)],
    ]


def _jacobi_eigenvalues_symmetric(a: list[list[float]]) -> list[float]:
    m = [[float(a[i][j]) for j in range(3)] for i in range(3)]
    for _ in range(64):
        pairs = [(0, 1), (0, 2), (1, 2)]
        p, q = max(pairs, key=lambda ij: abs(m[ij[0]][ij[1]]))
        if abs(m[p][q]) < 1.0e-15:
            break
        phi = 0.5 * math.atan2(2.0 * m[p][q], m[q][q] - m[p][p])
        c, s = math.cos(phi), math.sin(phi)
        for k in range(3):
            if k not in (p, q):
                mkp, mkq = m[k][p], m[k][q]
                m[k][p] = m[p][k] = c * mkp - s * mkq
                m[k][q] = m[q][k] = s * mkp + c * mkq
        app, aqq, apq = m[p][p], m[q][q], m[p][q]
        m[p][p] = c * c * app - 2.0 * s * c * apq + s * s * aqq
        m[q][q] = s * s * app + 2.0 * s * c * apq + c * c * aqq
        m[p][q] = m[q][p] = 0.0
    return sorted([m[i][i] for i in range(3)])


def _add_box(
    items: list[dict],
    part: str,
    material: str,
    sign: int,
    center_mm: tuple[float, float, float],
    dims_mm: tuple[float, float, float],
    rotation_x_deg: float = 0.0,
    feature: str = "solid",
) -> None:
    items.append(
        {
            "kind": "box",
            "part": part,
            "material": material,
            "sign": sign,
            "center_mm": center_mm,
            "dims_mm": dims_mm,
            "rotation_x_deg": rotation_x_deg,
            "feature": feature,
        }
    )


def _add_cylinder_x(
    items: list[dict],
    part: str,
    material: str,
    sign: int,
    center_mm: tuple[float, float, float],
    length_mm: float,
    diameter_mm: float,
    feature: str,
) -> None:
    items.append(
        {
            "kind": "cylinder_x",
            "part": part,
            "material": material,
            "sign": sign,
            "center_mm": center_mm,
            "length_mm": length_mm,
            "diameter_mm": diameter_mm,
            "feature": feature,
        }
    )


def _local_yz_to_s(u_mm: float, v_mm: float, clocking_deg: float, cy_mm: float, cz_mm: float) -> tuple[float, float]:
    # The M3R transform maps its local in-plane axes with an effective S-frame
    # rotation of clocking-90 deg.  This reproduces the measured T_S_M3R_LOCAL rows.
    angle = math.radians(clocking_deg)
    s, c = math.sin(angle), math.cos(angle)
    return cy_mm + s * u_mm + c * v_mm, cz_mm - c * u_mm + s * v_mm


def nominal_parameters(inputs: dict) -> dict[str, float]:
    """Return the design-basic geometry, not the uncertainty-distribution centre.

    Most design basics equal their Type-B distribution centres.  The M6 H11
    clearance is the intentional exception: geometry is drawn at the 6.600 mm
    basic size, while uncertainty propagation is centred on 6.645 mm.
    """

    values = {
        name: float(record["nominal"])
        for name, record in inputs["uncertainty_model"]["variables"].items()
    }
    source = inputs["parameters"]
    values.update(
        {
            "frame_inner_half_span_mm": float(source["frame_inner_half_span_mm"]),
            "deck_passage_y_mm": float(source["deck_passage_y_mm"]),
            "deck_passage_z_mm": float(source["deck_passage_z_mm"]),
            "m6_half_pitch_mm": float(source["front_interface_m6_pattern_local_half_pitch_mm"]),
            "m6_hole_diameter_mm": float(source["front_interface_m6_clearance_hole_diameter_mm"]),
        }
    )
    return values


def uncertainty_centre_parameters(inputs: dict, design_basic: dict[str, float]) -> dict[str, float]:
    values = dict(design_basic)
    for name, record in inputs["uncertainty_model"]["variables"].items():
        values[name] = float(record["nominal"])
    return values


def build_primitives(p: dict[str, float]) -> tuple[list[dict], dict]:
    items: list[dict] = []
    mat_primary = "AL7075_T651_PRIMARY_CANDIDATE"
    mat_secondary = "AL6061_T6_SECONDARY_CANDIDATE"

    length = p["bus_length_mm"]
    cross = p["bus_cross_mm"]
    half_x = length / 2.0
    outer_half = cross / 2.0
    rail = p["rail_square_mm"]
    inner_half = p["frame_inner_half_span_mm"]
    rail_center = outer_half - rail / 2.0
    frame_t = p["frame_thickness_mm"]
    mid_outer_half = outer_half - p["mid_frame_inset_mm"]
    web_half = p["cross_web_width_mm"] / 2.0

    if not (length > 0 and cross > 0 and rail > 0 and inner_half > web_half > 0 and mid_outer_half > inner_half):
        raise ValueError("Invalid structural dimensions")

    rail_labels = [
        ("LNG_PY_PZ", rail_center, rail_center),
        ("LNG_PY_NZ", rail_center, -rail_center),
        ("LNG_NY_PZ", -rail_center, rail_center),
        ("LNG_NY_NZ", -rail_center, -rail_center),
    ]
    for label, y, z in rail_labels:
        _add_box(items, label, mat_primary, 1, (0.0, y, z), (length, rail, rail), feature="continuous_longeron")

    def ring_frame(label: str, x_center: float, out_half: float) -> None:
        _add_box(items, label, mat_primary, 1, (x_center, 0.0, 0.0), (frame_t, 2.0 * out_half, 2.0 * out_half), feature="frame_outer")
        _add_box(items, label, mat_primary, -1, (x_center, 0.0, 0.0), (frame_t, 2.0 * inner_half, 2.0 * inner_half), feature="frame_inner_window")
        slot = min(rail, out_half - inner_half)
        slot_center = inner_half + slot / 2.0
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                _add_box(items, label, mat_primary, -1, (x_center, sy * slot_center, sz * slot_center), (frame_t, slot, slot), feature="longeron_seat")

    ring_frame("FRM_REAR", -half_x + frame_t / 2.0, outer_half)
    ring_frame("FRM_MID2", -length / 6.0, mid_outer_half)
    ring_frame("FRM_MID1", length / 6.0, mid_outer_half)

    # Monolithic front frame/spider backing: outer square minus four quadrant
    # windows, rail seats, and the central passage.  The cruciform connects all
    # four frame sides to the clocked forward interface land.
    front = "FRM_FRONT_SPIDER_MONOLITHIC"
    x_front_back = half_x - frame_t / 2.0
    _add_box(items, front, mat_primary, 1, (x_front_back, 0.0, 0.0), (frame_t, cross, cross), feature="front_backing_outer")
    window = inner_half - web_half
    window_center = (inner_half + web_half) / 2.0
    for sy in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            _add_box(items, front, mat_primary, -1, (x_front_back, sy * window_center, sz * window_center), (frame_t, window, window), feature="front_backing_quadrant_window")
            _add_box(items, front, mat_primary, -1, (x_front_back, sy * rail_center, sz * rail_center), (frame_t, rail, rail), feature="front_longeron_seat")
    _add_cylinder_x(items, front, mat_primary, -1, (x_front_back, p["pattern_center_y_mm"], p["pattern_center_z_mm"]), frame_t, p["front_passage_diameter_mm"], "front_backing_central_passage")

    land_t = p["interface_land_thickness_mm"]
    land_center_x = half_x + land_t / 2.0
    effective_yz_rotation = p["pattern_clocking_deg"] - 90.0
    _add_box(
        items,
        front,
        mat_primary,
        1,
        (land_center_x, p["pattern_center_y_mm"], p["pattern_center_z_mm"]),
        (land_t, p["interface_land_square_mm"], p["interface_land_square_mm"]),
        rotation_x_deg=effective_yz_rotation,
        feature="clocked_160mm_interface_land",
    )
    _add_cylinder_x(items, front, mat_primary, -1, (land_center_x, p["pattern_center_y_mm"], p["pattern_center_z_mm"]), land_t, p["front_passage_diameter_mm"], "interface_central_passage")
    pocket_r = p["lightening_hole_radius_mm"]
    for u, v in ((pocket_r, 0.0), (-pocket_r, 0.0), (0.0, pocket_r), (0.0, -pocket_r)):
        y, z = _local_yz_to_s(u, v, p["pattern_clocking_deg"], p["pattern_center_y_mm"], p["pattern_center_z_mm"])
        _add_cylinder_x(items, front, mat_primary, -1, (land_center_x, y, z), land_t, p["lightening_hole_diameter_mm"], "interface_lightening_hole")
    pitch = p["m6_half_pitch_mm"]
    m6_points = []
    for u in (-pitch, pitch):
        for v in (-pitch, pitch):
            y, z = _local_yz_to_s(u, v, p["pattern_clocking_deg"], p["pattern_center_y_mm"], p["pattern_center_z_mm"])
            m6_points.append([half_x + land_t, y, z])
            _add_cylinder_x(items, front, mat_primary, -1, (land_center_x, y, z), land_t, p["m6_hole_diameter_mm"], "interface_m6_clearance_hole")

    # Decks and their two face doublers.  Decks sit inside the middle frame
    # aperture; the frame itself occupies only the surrounding ring.
    deck_t = p["deck_thickness_mm"]
    deck_d = 2.0 * inner_half
    passage_y = p["deck_passage_y_mm"]
    passage_z = p["deck_passage_z_mm"]
    deck_passage_points = []
    for label, x_station in (("DECK_MID2", -length / 6.0), ("DECK_MID1", length / 6.0)):
        deck_passage_points.append([x_station, passage_y, passage_z])
        _add_box(items, label, mat_secondary, 1, (x_station, 0.0, 0.0), (deck_t, deck_d, deck_d), feature="equipment_deck")
        _add_cylinder_x(items, label, mat_secondary, -1, (x_station, passage_y, passage_z), deck_t, p["deck_passage_diameter_mm"], "deck_harness_passage")
        for suffix, side in (("A", -1.0), ("B", 1.0)):
            doubler_label = f"{label}_DOUBLER_{suffix}"
            doubler_t = p["doubler_thickness_mm"]
            x_doubler = x_station + side * (deck_t / 2.0 + doubler_t / 2.0)
            _add_cylinder_x(items, doubler_label, mat_secondary, 1, (x_doubler, passage_y, passage_z), doubler_t, p["doubler_outer_diameter_mm"], "deck_doubler_outer")
            _add_cylinder_x(items, doubler_label, mat_secondary, -1, (x_doubler, passage_y, passage_z), doubler_t, p["deck_passage_diameter_mm"], "deck_doubler_inner")

    # Six removable closure panels preserve the V2.1 service split.  Middle
    # frames are inset by 3 mm so these panel solids do not overlap them.
    panel_t = p["panel_thickness_mm"]
    panel_x_min = -half_x + frame_t
    panel_x_max = half_x - frame_t
    panel_len = panel_x_max - panel_x_min
    panel_span = 2.0 * inner_half
    _add_box(items, "PNL_TOP", mat_secondary, 1, (0.0, 0.0, outer_half - panel_t / 2.0), (panel_len, panel_span, panel_t), feature="non_structural_panel")
    _add_box(items, "PNL_BOTTOM", mat_secondary, 1, (0.0, 0.0, -outer_half + panel_t / 2.0), (panel_len, panel_span, panel_t), feature="non_structural_panel")
    split = length / 6.0
    for side_name, sy in (("LEFT", 1.0), ("RIGHT", -1.0)):
        aft_len = split - panel_x_min
        fwd_len = panel_x_max - split
        _add_box(items, f"PNL_{side_name}_AFT", mat_secondary, 1, ((panel_x_min + split) / 2.0, sy * (outer_half - panel_t / 2.0), 0.0), (aft_len, panel_t, panel_span), feature="non_structural_panel")
        _add_box(items, f"PNL_{side_name}_FWD", mat_secondary, 1, ((split + panel_x_max) / 2.0, sy * (outer_half - panel_t / 2.0), 0.0), (fwd_len, panel_t, panel_span), feature="non_structural_panel")

    lightening_points = []
    for u, v in ((pocket_r, 0.0), (-pocket_r, 0.0), (0.0, pocket_r), (0.0, -pocket_r)):
        y, z = _local_yz_to_s(u, v, p["pattern_clocking_deg"], p["pattern_center_y_mm"], p["pattern_center_z_mm"])
        lightening_points.append([half_x + land_t, y, z])

    derived = {
        "body_x_range_mm": [-half_x, half_x],
        "outer_half_span_mm": outer_half,
        "inner_half_span_mm": inner_half,
        "rail_center_abs_yz_mm": rail_center,
        "mid_frame_outer_half_span_mm": mid_outer_half,
        "frame_stations_x_mm": [-half_x, -length / 6.0, length / 6.0, half_x],
        "panel_x_range_mm": [panel_x_min, panel_x_max],
        "front_transition_x_range_mm": [half_x, half_x + land_t],
        "D_BUS_MATE_candidate_x_mm": half_x + land_t,
        "interface_effective_yz_rotation_deg": effective_yz_rotation,
        "m6_hole_centres_S_at_D_BUS_MATE_mm": sorted(m6_points, key=lambda row: (row[1], row[2])),
        "lightening_hole_centres_S_at_D_BUS_MATE_mm": sorted(lightening_points, key=lambda row: (row[1], row[2])),
        "deck_passage_centres_S_mm": sorted(deck_passage_points),
        "parameter_source_contract": {
            "frame_inner_half_span_mm": "parameters.frame_inner_half_span_mm",
            "m6_half_pitch_mm": "parameters.front_interface_m6_pattern_local_half_pitch_mm",
            "deck_passage_y_mm": "parameters.deck_passage_y_mm",
            "deck_passage_z_mm": "parameters.deck_passage_z_mm",
            "design_basic_m6_hole_diameter_mm": "parameters.front_interface_m6_clearance_hole_diameter_mm",
            "uncertainty_centre_m6_hole_diameter_mm": "uncertainty_model.variables.m6_hole_diameter_mm.nominal",
        },
        "feature_counts": {
            feature: sum(1 for item in items if item["feature"] == feature)
            for feature in sorted({item["feature"] for item in items})
        },
        "physical_member_labels": sorted({item["part"] for item in items}),
    }
    return items, derived


def _primitive_properties(item: dict, densities: dict[str, float]) -> tuple[float, tuple[float, float, float], list[list[float]], float]:
    sign = float(item["sign"])
    density = densities[item["material"]]
    cx, cy, cz = (v / 1000.0 for v in item["center_mm"])
    if item["kind"] == "box":
        dx, dy, dz = (v / 1000.0 for v in item["dims_mm"])
        volume = dx * dy * dz
        mass = sign * density * volume
        local = [
            [mass * (dy * dy + dz * dz) / 12.0, 0.0, 0.0],
            [0.0, mass * (dx * dx + dz * dz) / 12.0, 0.0],
            [0.0, 0.0, mass * (dx * dx + dy * dy) / 12.0],
        ]
        rotation = _rotation_x(float(item.get("rotation_x_deg", 0.0)))
        inertia_com = _mat_mul(_mat_mul(rotation, local), _transpose(rotation))
    else:
        length = item["length_mm"] / 1000.0
        radius = item["diameter_mm"] / 2000.0
        volume = math.pi * radius * radius * length
        mass = sign * density * volume
        inertia_com = [
            [0.5 * mass * radius * radius, 0.0, 0.0],
            [0.0, mass * (3.0 * radius * radius + length * length) / 12.0, 0.0],
            [0.0, 0.0, mass * (3.0 * radius * radius + length * length) / 12.0],
        ]
    r = (cx, cy, cz)
    inertia_origin = _mat_add(inertia_com, _parallel_axis(mass, r))
    return mass, r, inertia_origin, sign * volume


def _aggregate(items: list[dict], densities: dict[str, float]) -> dict:
    mass = 0.0
    first = [0.0, 0.0, 0.0]
    inertia_origin = _mat_zero()
    signed_volume = 0.0
    for item in items:
        m, r, io, vol = _primitive_properties(item, densities)
        mass += m
        signed_volume += vol
        for i in range(3):
            first[i] += m * r[i]
        inertia_origin = _mat_add(inertia_origin, io)
    if mass <= 0.0:
        raise ValueError("Aggregate mass must be positive")
    cg = tuple(value / mass for value in first)
    inertia_cg = _mat_sub(inertia_origin, _parallel_axis(mass, cg))
    eigenvalues = _jacobi_eigenvalues_symmetric(inertia_cg)
    triangle = all(eigenvalues[i] <= sum(eigenvalues) - eigenvalues[i] + 1.0e-12 for i in range(3))
    return {
        "mass_kg": mass,
        "signed_volume_m3": signed_volume,
        "cg_S_m": list(cg),
        "inertia_about_cg_S_kg_m2": inertia_cg,
        "principal_moments_kg_m2": eigenvalues,
        "checks": {
            "mass_positive": mass > 0.0,
            "volume_positive": signed_volume > 0.0,
            "inertia_symmetric": max(abs(inertia_cg[i][j] - inertia_cg[j][i]) for i in range(3) for j in range(3)) < 1.0e-12,
            "inertia_positive_definite": eigenvalues[0] > 0.0,
            "triangle_inequalities": triangle,
        },
    }


def compute_model(p: dict[str, float], include_parts: bool = True) -> dict:
    items, derived = build_primitives(p)
    densities = {
        "AL7075_T651_PRIMARY_CANDIDATE": p["density_7075_kg_m3"],
        "AL6061_T6_SECONDARY_CANDIDATE": p["density_6061_kg_m3"],
    }
    total = _aggregate(items, densities)
    if include_parts:
        parts = {}
        for label in sorted({item["part"] for item in items}):
            group = [item for item in items if item["part"] == label]
            record = _aggregate(group, densities)
            record["material"] = group[0]["material"]
            record["primitive_terms"] = len(group)
            parts[label] = record
        total["parts"] = parts
    total["derived_geometry"] = derived
    total["primitive_term_count"] = len(items)
    return total


def _quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty values")
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def uncertainty_screen(inputs: dict, nominal_p: dict[str, float], nominal: dict) -> dict:
    variables = inputs["uncertainty_model"]["variables"]
    uncertainty_centre = uncertainty_centre_parameters(inputs, nominal_p)
    contributions = []
    variance = 0.0
    for name, record in variables.items():
        half_width = float(record["half_width"])
        u = half_width / math.sqrt(3.0)
        step = max(abs(float(record["nominal"])) * 1.0e-7, half_width * 1.0e-3, 1.0e-8)
        p_hi = dict(uncertainty_centre)
        p_lo = dict(uncertainty_centre)
        p_hi[name] += step
        p_lo[name] -= step
        sensitivity = (
            compute_model(p_hi, include_parts=False)["mass_kg"]
            - compute_model(p_lo, include_parts=False)["mass_kg"]
        ) / (2.0 * step)
        contribution = (sensitivity * u) ** 2
        variance += contribution
        contributions.append(
            {
                "variable": name,
                "unit": "as_named",
                "estimate": float(record["nominal"]),
                "half_width": half_width,
                "distribution": record["distribution"],
                "type": record["type"],
                "standard_uncertainty": u,
                "sensitivity_kg_per_input_unit": sensitivity,
                "variance_contribution_kg2": contribution,
                "status": record["status"],
            }
        )
    u_gum = math.sqrt(variance)
    contributions.sort(key=lambda row: row["variance_contribution_kg2"], reverse=True)

    sample_count = int(inputs["uncertainty_model"]["monte_carlo_samples"])
    rng = random.Random(int(inputs["uncertainty_model"]["monte_carlo_seed"]))
    channels = {name: [] for name in ("mass_kg", "cg_x_m", "cg_y_m", "cg_z_m", "Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}
    for _ in range(sample_count):
        trial = dict(uncertainty_centre)
        for name, record in variables.items():
            trial[name] = float(record["nominal"]) + rng.uniform(-float(record["half_width"]), float(record["half_width"]))
        result = compute_model(trial, include_parts=False)
        inertia = result["inertia_about_cg_S_kg_m2"]
        cg = result["cg_S_m"]
        values = {
            "mass_kg": result["mass_kg"],
            "cg_x_m": cg[0],
            "cg_y_m": cg[1],
            "cg_z_m": cg[2],
            "Ixx": inertia[0][0],
            "Iyy": inertia[1][1],
            "Izz": inertia[2][2],
            "Ixy": inertia[0][1],
            "Ixz": inertia[0][2],
            "Iyz": inertia[1][2],
        }
        for name, value in values.items():
            channels[name].append(value)

    mc = {}
    for name, values in channels.items():
        mean = sum(values) / len(values)
        std = math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))
        mc[name] = {
            "mean": mean,
            "standard_deviation": std,
            "q02p5": _quantile(values, 0.025),
            "q97p5": _quantile(values, 0.975),
        }

    ratio = mc["mass_kg"]["standard_deviation"] / u_gum if u_gum > 0.0 else None
    k = float(inputs["uncertainty_model"]["coverage_factor"])
    project_policy = inputs["uncertainty_model"]["project_policy"]
    project_relative_u = float(project_policy["mass_relative_standard_uncertainty"])
    project_standard_u = nominal["mass_kg"] * project_relative_u
    return {
        "schema": "BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1",
        "generated_date_local": "2026-08-24",
        "measurand": "mass of the explicitly modelled source-only bus structural candidate, excluding bridge, M3R, fasteners, coatings, equipment and harness",
        "estimate_kg": nominal["mass_kg"],
        "estimate_geometry_basis": "DESIGN_BASIC_DIMENSIONS",
        "distribution_centre_exception": {
            "variable": "m6_hole_diameter_mm",
            "design_basic_mm": nominal_p["m6_hole_diameter_mm"],
            "uncertainty_distribution_centre_mm": uncertainty_centre["m6_hole_diameter_mm"],
            "interval_mm": [
                uncertainty_centre["m6_hole_diameter_mm"] - float(variables["m6_hole_diameter_mm"]["half_width"]),
                uncertainty_centre["m6_hole_diameter_mm"] + float(variables["m6_hole_diameter_mm"]["half_width"]),
            ],
        },
        "gum_linear": {
            "standard_uncertainty_kg": u_gum,
            "expanded_uncertainty_kg": k * u_gum,
            "coverage_factor": k,
            "coverage_interpretation": "approximately 95 percent only under the stated Type-B screening model; not a flight/material traceability statement",
            "effective_degrees_of_freedom": "INFINITE_TYPE_B_SCREENING_ASSUMPTION",
            "uncertainty_budget": contributions,
            "authority": "LOCAL_INPUT_SENSITIVITY_DIAGNOSTIC_ONLY__NOT_DOWNSTREAM_PROJECT_U",
        },
        "project_policy": {
            **project_policy,
            "estimate_kg": nominal["mass_kg"],
            "standard_uncertainty_kg": project_standard_u,
            "standard_uncertainty_coverage_factor": 1.0,
            "downstream_value_controls": True,
            "local_gum_may_replace_project_policy": False,
        },
        "monte_carlo": {
            "sample_count": sample_count,
            "seed": int(inputs["uncertainty_model"]["monte_carlo_seed"]),
            "input_distributions": "independent rectangular screening distributions; correlation data absent and not invented",
            "outputs": mc,
            "mass_standard_deviation_to_gum_ratio": ratio,
            "crosscheck_consistent_within_5_percent": ratio is not None and abs(ratio - 1.0) <= 0.05,
        },
        "classification": "TYPE_B_DESIGN_MODEL_SCREEN__NOT_MEASUREMENT__NOT_SOURCE_PROPERTY_UNCERTAINTY",
        "promotion_block": inputs["uncertainty_model"]["promotion_block"],
        "reporting_statement": f"Candidate structure mass = {nominal['mass_kg']:.6f} kg; downstream project-policy standard uncertainty u = {project_standard_u:.6f} kg (15 percent, k=1). Local input-sensitivity diagnostic only: u = {u_gum:.6f} kg and U = {k*u_gum:.6f} kg (k={k:.1f}).",
    }


def stiffness_screen(inputs: dict, p: dict[str, float]) -> dict:
    a = p["rail_square_mm"] / 1000.0
    area_one = a * a
    d = (p["bus_cross_mm"] / 2.0 - p["rail_square_mm"] / 2.0) / 1000.0
    local_i = a ** 4 / 12.0
    bundle_i = 4.0 * (local_i + area_one * d * d)
    e = 71.0e9
    screen = inputs["structural_screen_inputs"]
    length = float(screen["front_half_span_m"])
    cases = screen["same_case_peak_wrenches_at_stage_b_to_bus"]
    normal = cases["NORMAL_TENSION_BENDING"]
    shear = cases["SHEAR_TORSION"]
    axial_force = float(normal["axial_force_N"])
    bending_moment = float(normal["bending_moment_Nm"])
    transverse_force = float(shear["transverse_force_N"])
    torsional_moment = float(shear["torsional_moment_Nm"])
    half_sine = screen["half_sine_inputs"]
    derived_peak_force = math.pi * float(half_sine["impulse_Ns"]) / (2.0 * float(half_sine["contact_duration_s"]))
    derived_peak_couple = math.pi * float(half_sine["couple_impulse_Nms"]) / (2.0 * float(half_sine["contact_duration_s"]))
    derived_bending_moment = (
        derived_peak_force
        * (float(half_sine["base_lever_m"]) + float(half_sine["stage_b_to_bus_lever_offset_m"]))
        + derived_peak_couple
    )
    derivation_residuals = {
        "normal_axial_force_N": abs(axial_force - derived_peak_force),
        "normal_bending_moment_Nm": abs(bending_moment - derived_bending_moment),
        "shear_transverse_force_N": abs(transverse_force - derived_peak_force),
        "shear_torsional_moment_Nm": abs(torsional_moment - derived_peak_couple),
    }
    ei = e * bundle_i
    ea = e * 4.0 * area_one
    return {
        "schema": "BUS_PRIMARY_STRUCTURE_STIFFNESS_SCREEN_V1",
        "model": screen["rail_only_model"],
        "load_case_id": screen["load_case_id"],
        "load_source": screen["load_source"],
        "prohibited_legacy_mix": screen["prohibited_legacy_mix"],
        "EA_total_N": ea,
        "Iy_bundle_m4": bundle_i,
        "Iz_bundle_m4": bundle_i,
        "EIy_N_m2": ei,
        "EIz_N_m2": ei,
        "front_half_span_m": length,
        "front_half_span_m": length,
        "same_case_peak_wrenches_at_stage_b_to_bus": cases,
        "half_sine_load_derivation_audit": {
            "derived_peak_force_N": derived_peak_force,
            "derived_peak_couple_Nm": derived_peak_couple,
            "derived_stage_b_to_bus_bending_moment_Nm": derived_bending_moment,
            "absolute_residuals": derivation_residuals,
            "matches_declared_same_case_within_1e_minus_12": max(derivation_residuals.values()) <= 1.0e-12,
        },
        "normal_tension_bending_screen": {
            "axial_elongation_m": axial_force * length / ea,
            "bending_tip_translation_m": bending_moment * length ** 2 / (2.0 * ei),
            "bending_tip_rotation_rad": bending_moment * length / ei,
            "axial_average_stress_MPa": axial_force / (4.0 * area_one) / 1.0e6,
        },
        "shear_torsion_screen": {
            "transverse_bending_tip_translation_m": transverse_force * length ** 3 / (3.0 * ei),
            "transverse_bending_tip_rotation_rad": transverse_force * length ** 2 / (2.0 * ei),
            "torsional_moment_Nm": torsional_moment,
            "torsional_response": "UNKNOWN_NO_VALIDATED_TORSIONAL_LOAD_PATH_OR_TORSION_CONSTANT",
        },
        "verdict": "COMPUTED_NONQUALIFYING_STIFF_BOUND__NO_STRUCTURAL_PASS",
        "excluded_compliance": [
            "front interface land and cruciform local bending",
            "frame-longeron joints",
            "bridge-front-spider bolted joint",
            "deck and panel shear participation",
            "material/property/temperature allowables",
            "launcher and test boundary conditions"
        ],
        "formal_fea_credit": False,
    }


def verify_source_pins(inputs: dict) -> list[dict]:
    rows = []
    for pin in inputs["source_pins"]:
        path = ROOT / pin["path"]
        actual = _sha256(path) if path.is_file() else None
        rows.append(
            {
                **pin,
                "exists": path.is_file(),
                "actual_sha256": actual,
                "verified": actual == pin["sha256"],
            }
        )
    return rows


def read_prebind_authority(inputs: dict) -> dict:
    contract = inputs["prebind_authority"]
    frontier = json.loads((ROOT / contract["frontier_path"]).read_text(encoding="utf-8"))
    gate = json.loads((ROOT / contract["gate_path"]).read_text(encoding="utf-8"))
    prb17 = next(row for row in frontier["effective_criteria"] if row["id"] == "PRB-17")
    return {
        "frontier_path": contract["frontier_path"],
        "gate_path": contract["gate_path"],
        "effective_summary": frontier["effective_summary"],
        "prb17": {"state": prb17["state"], "pass": prb17["pass"], "evidence": prb17["evidence"]},
        "gate_package_validation": gate["package_validation"],
        "gate_technical_outcome": gate["technical_outcome"],
        "authority_flags": gate["authority_flags"],
        "matches_declared_contract": (
            frontier["effective_summary"] == contract["expected_effective_summary"]
            and {"state": prb17["state"], "pass": prb17["pass"]} == contract["expected_PRB_17"]
            and gate["package_validation"] == "PASS"
            and gate["technical_outcome"] == "HOLD"
            and gate["next_stage_authorized"] is False
            and gate["release_credit"] is False
        ),
    }


def bus_mass_decomposition(inputs: dict, structure: dict) -> dict:
    """Solve a bookkeeping residual that exactly preserves the existing bus lump."""

    boundary = inputs["mass_boundary"]
    total_mass = float(boundary["existing_bus_mass_budget_kg"])
    total_com = tuple(float(v) for v in boundary["existing_bus_com_S_m"])
    total_inertia_cg = [[float(v) for v in row] for row in boundary["existing_bus_inertia_about_com_S_kg_m2"]]
    structure_mass = float(structure["mass_kg"])
    structure_com = tuple(float(v) for v in structure["cg_S_m"])
    structure_inertia_cg = structure["inertia_about_cg_S_kg_m2"]
    residual_mass = total_mass - structure_mass
    if residual_mass <= 0.0:
        raise ValueError("Structure mass leaves no positive residual bus budget")

    residual_com = tuple(
        (total_mass * total_com[i] - structure_mass * structure_com[i]) / residual_mass
        for i in range(3)
    )
    total_inertia_origin = _mat_add(total_inertia_cg, _parallel_axis(total_mass, total_com))
    structure_inertia_origin = _mat_add(
        structure_inertia_cg, _parallel_axis(structure_mass, structure_com)
    )
    residual_inertia_origin = _mat_sub(total_inertia_origin, structure_inertia_origin)
    residual_inertia_cg = _mat_sub(
        residual_inertia_origin, _parallel_axis(residual_mass, residual_com)
    )
    principal = _jacobi_eigenvalues_symmetric(residual_inertia_cg)
    physical = (
        residual_mass > 0.0
        and principal[0] > 0.0
        and all(principal[i] <= sum(principal) - principal[i] + 1.0e-12 for i in range(3))
    )

    recomposed_mass = structure_mass + residual_mass
    recomposed_com = tuple(
        (structure_mass * structure_com[i] + residual_mass * residual_com[i]) / recomposed_mass
        for i in range(3)
    )
    recomposed_origin = _mat_add(structure_inertia_origin, residual_inertia_origin)
    recomposed_cg = _mat_sub(recomposed_origin, _parallel_axis(recomposed_mass, recomposed_com))
    mass_error = abs(recomposed_mass - total_mass)
    com_error = max(abs(recomposed_com[i] - total_com[i]) for i in range(3))
    inertia_error = max(
        abs(recomposed_cg[i][j] - total_inertia_cg[i][j])
        for i in range(3)
        for j in range(3)
    )
    return {
        "schema": "BUS_MASS_DECOMPOSITION_BRIDGE_V1",
        "generated_date_local": "2026-08-24",
        "purpose": "simulation bookkeeping candidate that exposes the detailed structure without adding mass to the existing bus lump",
        "existing_bus_lump": {
            "mass_kg": total_mass,
            "com_S_m": list(total_com),
            "inertia_about_com_S_kg_m2": total_inertia_cg,
            "standard_uncertainty_kg": boundary["existing_bus_mass_standard_uncertainty_kg"],
            "authority": boundary["existing_bus_property_authority"],
        },
        "explicit_structure_candidate": {
            "mass_kg": structure_mass,
            "com_S_m": list(structure_com),
            "inertia_about_com_S_kg_m2": structure_inertia_cg,
            "mass_standard_uncertainty_kg": None,
            "uncertainty_reference": "BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1.json",
            "authority": "SOURCE_ONLY_TECHNICAL_CANDIDATE",
        },
        "algebraic_residual_equipment_and_unmodelled_component": {
            "mass_kg": residual_mass,
            "com_S_m": list(residual_com),
            "inertia_about_com_S_kg_m2": residual_inertia_cg,
            "principal_moments_kg_m2": principal,
            "mass_standard_uncertainty_kg": None,
            "uncertainty_status": "UNKNOWN_CORRELATION_WITH_EXISTING_BUS_LUMP__NO_ROOT_SUM_SQUARE_SUBTRACTION",
            "collision_geometry": None,
            "authority": "ALGEBRAIC_BOOKKEEPING_RESIDUAL_NOT_PHYSICAL_LAYOUT_MEASUREMENT",
        },
        "recomposition_audit": {
            "mass_abs_error_kg": mass_error,
            "com_max_abs_error_m": com_error,
            "inertia_max_abs_error_kg_m2": inertia_error,
            "residual_inertia_physically_admissible": physical,
            "exact_within_1e_minus_12": max(mass_error, com_error, inertia_error) <= 1.0e-12,
        },
        "consumption_rule": boundary["residual_property_rule"],
        "prohibited_operation": "Do not add the explicit structure mass to the 23.3032134 kg bus lump. Replace the lump by structure plus this residual only in a versioned simulation candidate.",
        "m7_mass_ledger_mutated": False,
        "sim13_rebind_authorized": False,
        "release_credit": False,
    }


def build_reports() -> None:
    inputs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    p = nominal_parameters(inputs)
    model = compute_model(p)
    prebind = read_prebind_authority(inputs)
    bus_budget = float(inputs["mass_boundary"]["existing_bus_mass_budget_kg"])
    model["schema"] = "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1"
    model["generated_date_local"] = "2026-08-24"
    model["artifact_class"] = "DETERMINISTIC_ANALYTIC_DESIGN_MODEL__SOURCE_ONLY"
    model["mass_boundary"] = {
        "candidate_structure_mass_kg": model["mass_kg"],
        "existing_bus_budget_kg": bus_budget,
        "candidate_structure_fraction_of_bus_budget": model["mass_kg"] / bus_budget,
        "residual_bus_equipment_and_unmodelled_mass_budget_kg": bus_budget - model["mass_kg"],
        "interpretation": inputs["mass_boundary"]["new_candidate_rule"],
        "m7_mass_ledger_mutated": False,
    }
    model["load_path"] = [
        "B601 physical installation face x=208.0 mm",
        "4xM4 candidate/as-built pattern into M3R Stage A",
        "8xM5 candidate Stage A-to-B joint and locator",
        "M3R Stage B x=196.0..208.0 mm",
        "4xM6 candidate joint",
        "hash-frozen M6 bridge candidate x=185.25..196.0 mm",
        "D_BUS_MATE_PHYSICAL x=185.25 mm (same numeric transform as, but never an alias of, M_DYNAMICS)",
        "front interface land x=170.25..185.25 mm",
        "front cruciform backing/frame x=158.25..170.25 mm",
        "four continuous longerons plus MID1/MID2/rear frames and two decks"
    ]
    model["interface_frames"] = {
        "matrix_semantics": inputs["coordinate_convention"]["matrix_semantics"],
        "D_BUS_MATE_PHYSICAL": inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"],
        "M_DYNAMICS_NONPHYSICAL": inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"],
        "D_BUS_M6_PATTERN": inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"],
        "rule": inputs["operational_geometry"]["coincident_datum_rule"],
    }
    model["source_pins"] = verify_source_pins(inputs)
    model["upstream_prebind_authority"] = prebind
    model["known_configuration_drifts"] = inputs["known_configuration_drifts"]
    model["retained_holds"] = inputs["retained_holds"]
    model["stiffness_screen"] = stiffness_screen(inputs, p)
    uncertainty = uncertainty_screen(inputs, p, model)
    decomposition = bus_mass_decomposition(inputs, model)
    decomposition["explicit_structure_candidate"]["mass_standard_uncertainty_kg"] = uncertainty["project_policy"]["standard_uncertainty_kg"]
    decomposition["explicit_structure_candidate"]["mass_standard_uncertainty_coverage_factor"] = 1.0
    decomposition["explicit_structure_candidate"]["uncertainty_authority"] = "PROJECT_POLICY_ANALYTIC_IDEALIZATION_15_PERCENT"
    decomposition["explicit_structure_candidate"]["local_sensitivity_diagnostic_standard_uncertainty_kg"] = uncertainty["gum_linear"]["standard_uncertainty_kg"]
    model["bus_mass_decomposition_candidate"] = decomposition
    _json_write(PACKAGE / "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.json", model)
    _json_write(PACKAGE / "BUS_MASS_DECOMPOSITION_BRIDGE_V1.json", decomposition)

    _json_write(PACKAGE / "BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1.json", uncertainty)

    expected_holes = [
        [185.25, -93.008837537, 33.77187797],
        [185.25, -33.842249889, -93.111197758],
        [185.25, 33.874238191, 92.938465618],
        [185.25, 93.040825839, -33.94461011],
    ]
    actual_holes = model["derived_geometry"]["m6_hole_centres_S_at_D_BUS_MATE_mm"]
    hole_residual = max(abs(actual_holes[i][j] - expected_holes[i][j]) for i in range(4) for j in range(3))
    pins_ok = all(row["verified"] for row in model["source_pins"])
    package_has_cad = any(PACKAGE.glob("*.step")) or any(PACKAGE.glob("*.stp")) or any(PACKAGE.glob("*.FCStd"))
    execution_evidence = {
        "preimport_authority_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_PREIMPORT_AUTHORITY_RECORD_V1.json").is_file(),
        "generation_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_GENERATION_RECORD_V1.json").is_file(),
        "gate_invalidation_record": (PACKAGE / "BUS_PRIMARY_STRUCTURE_GATE_INVALIDATED_BY_EXECUTION_V1.json").is_file(),
        "run_consumption_records": sum(1 for _ in (PACKAGE / ".bus_primary_structure_run_consumption").glob("*.json")) if (PACKAGE / ".bus_primary_structure_run_consumption").is_dir() else 0,
        "override_consumption_records": sum(1 for _ in (PACKAGE / ".bus_primary_structure_override_consumption").glob("*.json")) if (PACKAGE / ".bus_primary_structure_override_consumption").is_dir() else 0,
        "active_cad_writer_lock": (PACKAGE / ".bus_primary_structure_active_run.lock").is_file(),
    }
    execution_attempt_present = any(bool(value) for value in execution_evidence.values())
    feature_counts = model["derived_geometry"]["feature_counts"]
    checks = {
        "G01_SOURCE_PINS_HASH_VERIFIED": pins_ok,
        "G02_OPERATIONAL_BODY_340P5_X_226P3_X_226P3": (
            model["derived_geometry"]["body_x_range_mm"] == [-170.25, 170.25]
            and inputs["operational_geometry"]["bus_body_length_mm"] == 340.5
            and inputs["operational_geometry"]["bus_cross_section_y_mm"] == 226.3
            and inputs["operational_geometry"]["bus_cross_section_z_mm"] == 226.3
            and model["derived_geometry"]["outer_half_span_mm"] == 113.15
        ),
        "G03_FOUR_LONGERONS_AND_FOUR_FRAME_STATIONS": len([k for k in model["parts"] if k.startswith("LNG_")]) == 4 and len(model["derived_geometry"]["frame_stations_x_mm"]) == 4,
        "G04_FRONT_TRANSITION_CLOSES_170P25_TO_185P25": model["derived_geometry"]["front_transition_x_range_mm"] == [170.25, 185.25],
        "G05_D_BUS_MATE_DISTINCT_SEMANTICS": (
            inputs["operational_geometry"]["stations_x_mm"]["D_BUS_MATE_PHYSICAL"]
            == inputs["operational_geometry"]["stations_x_mm"]["M_DYNAMICS_NONPHYSICAL"]
            and inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"]
            == inputs["operational_geometry"]["T_S_M_DYNAMICS_NONPHYSICAL"]
            and inputs["operational_geometry"]["T_S_D_BUS_M6_PATTERN"]
            != inputs["operational_geometry"]["T_S_D_BUS_MATE_PHYSICAL"]
            and "same numeric transform" in inputs["operational_geometry"]["coincident_datum_rule"]
            and "never be aliased" in inputs["operational_geometry"]["coincident_datum_rule"]
        ),
        "G06_M6_PATTERN_REPRODUCES_FROZEN_BRIDGE": hole_residual <= 1.0e-9,
        "G07_REGISTERED_OPENINGS_MAP_TO_EXPLICIT_REINFORCEMENT_FEATURES": (
            all(bool(row["doubler"]) for row in inputs["openings_register"])
            and feature_counts.get("deck_doubler_outer") == 4
            and feature_counts.get("deck_doubler_inner") == 4
            and feature_counts.get("clocked_160mm_interface_land") == 1
            and feature_counts.get("front_backing_central_passage") == 1
            and feature_counts.get("interface_central_passage") == 1
        ),
        "G08_CANDIDATE_MASS_POSITIVE_AND_WITHIN_BUS_BUDGET": 0.0 < model["mass_kg"] < bus_budget,
        "G09_RESIDUAL_EQUIPMENT_BUDGET_POSITIVE": (
            model["mass_boundary"]["residual_bus_equipment_and_unmodelled_mass_budget_kg"] > 0.0
            and decomposition["recomposition_audit"]["residual_inertia_physically_admissible"]
            and decomposition["recomposition_audit"]["exact_within_1e_minus_12"]
        ),
        "G10_INERTIA_PHYSICALLY_ADMISSIBLE": all(model["checks"].values()),
        "G11_LOCAL_GUM_MC_AGREE_AND_PROJECT_15_PERCENT_U_CONTROLS": (
            uncertainty["monte_carlo"]["crosscheck_consistent_within_5_percent"]
            and abs(uncertainty["project_policy"]["standard_uncertainty_kg"] - model["mass_kg"] * 0.15) <= 1.0e-12
            and uncertainty["project_policy"]["downstream_value_controls"] is True
        ),
        "G12_SAME_CASE_STIFFNESS_RESULT_NONQUALIFYING": (
            model["stiffness_screen"]["verdict"] == "COMPUTED_NONQUALIFYING_STIFF_BOUND__NO_STRUCTURAL_PASS"
            and model["stiffness_screen"]["load_case_id"] == "LC-014_CAPTURE_150KG_TC5MS_WP4_DERIVED_BOUNDING"
            and model["stiffness_screen"]["half_sine_load_derivation_audit"]["matches_declared_same_case_within_1e_minus_12"] is True
            and model["stiffness_screen"]["shear_torsion_screen"]["torsional_response"] == "UNKNOWN_NO_VALIDATED_TORSIONAL_LOAD_PATH_OR_TORSION_CONSTANT"
        ),
        "G13_M7_MASS_LEDGER_NOT_MUTATED": model["mass_boundary"]["m7_mass_ledger_mutated"] is False,
        "G14_NO_CAD_OR_EXECUTION_ATTEMPT_EVIDENCE_PRESENT": not package_has_cad and not execution_attempt_present,
        "G15_EXECUTION_AND_RELEASE_FALSE": (
            not inputs["authority_boundary"]["cad_generation_authorized"]
            and not inputs["authority_boundary"]["manufacturing_released"]
            and not inputs["authority_boundary"]["release_credit"]
            and not execution_attempt_present
        ),
        "G16_UPSTREAM_PRB17_HOLD_AND_EFFECTIVE_PREBIND_UNCHANGED": prebind["matches_declared_contract"],
    }
    gate = {
        "schema": "BUS_PRIMARY_STRUCTURE_SOURCE_GATE_V1",
        "generated_date_local": "2026-08-24",
        "artifact_class": "SOURCE_ONLY_TECHNICAL_CANDIDATE_GATE",
        "checks": checks,
        "score": {"passed": sum(bool(v) for v in checks.values()), "total": len(checks)},
        "all_checks_passed": all(checks.values()),
        "verdict": "PASS_SOURCE_ONLY_TECHNICAL_CANDIDATE_WITH_EXPLICIT_HOLDS" if all(checks.values()) else "HOLD_SOURCE_ONLY_TECHNICAL_CANDIDATE_DEFECT",
        "hole_pattern_max_abs_residual_mm": hole_residual,
        "execution_evidence": execution_evidence,
        "prb17_verdict": "HOLD_NOT_OWNER_EFFECTIVE_NOT_CAD_GENERATED_NOT_MANUFACTURING_AUTHORITY",
        "effective_prebind_pass_count_before": prebind["effective_summary"]["pass"],
        "effective_prebind_pass_count_after": prebind["effective_summary"]["pass"],
        "cad_snapshot": "SKIPPED_NO_VISIBLE_CAD_GENERATED",
        "next_stage_authorized": False,
        "release_credit": False
    }
    _json_write(PACKAGE / "BUS_PRIMARY_STRUCTURE_SOURCE_GATE_V1.json", gate)

    technical_subcriteria = {
        "P17_01_operational_track_geometry": "PASS_TECHNICAL_CANDIDATE",
        "P17_02_physical_member_tree": "PASS_TECHNICAL_CANDIDATE",
        "P17_03_front_transition_170P25_to_185P25": "PASS_TECHNICAL_CANDIDATE",
        "P17_04_D_BUS_MATE_semantics": "PASS_TECHNICAL_CANDIDATE",
        "P17_05_bus_side_4xM6_geometry": "CANDIDATE_DEFINED__FASTENER_STACK_HOLD",
        "P17_06_openings_and_reinforcement_register": "PASS_TECHNICAL_CANDIDATE",
        "P17_07_continuous_named_load_path": "PASS_TECHNICAL_CANDIDATE",
        "P17_08_manufacturing_authority_native_cad_step_joint_release": "HOLD",
    }
    local_closed = sum(value != "HOLD" for value in technical_subcriteria.values())
    delta = {
        "schema": "UNIFIED_R2_PREBIND_STRUCTURE_DELTA_V1",
        "generated_date_local": "2026-08-24",
        "scope": "PRB-17 detailed 12U primary structure",
        "upstream_prebind_authority": prebind,
        "technical_definition_subcriteria": technical_subcriteria,
        "technical_definition_count": {"closed_or_candidate_defined": local_closed, "required": len(technical_subcriteria)},
        "PRB_17": prebind["prb17"]["state"],
        "reason": "The source-only candidate removes the unnamed geometric gap and defines members/openings, but owner effectiveness, detailed joints, native/neutral CAD, manufacturing definition and qualification remain absent.",
        "prebind_count_change": 0,
        "execution_authority_created": execution_attempt_present,
        "execution_evidence": execution_evidence,
        "release_credit": False
    }
    _json_write(PACKAGE / "UNIFIED_R2_PREBIND_STRUCTURE_DELTA_V1.json", delta)

    report_md = f"""# 12U 主承力结构参数化候选 V1（340.5 mm 运行轨）

## 工程结论

本包建立了可重建的主结构源与解析质量模型，补上了 `x=170.25→185.25 mm` 的前端承力过渡。`D_BUS_MATE_PHYSICAL` 与 `M_DYNAMICS_NONPHYSICAL` 数值变换相同但语义不可别名；孔阵时钟角与偏置只由第三基准 `D_BUS_M6_PATTERN` 承载。本轮没有生成 STEP/FCStd，也没有升级 PRB-17、制造或飞行结论。

## 名义构型

- 本体：`340.5 × 226.3 × 226.3 mm`，S 系 `x=[-170.25,+170.25] mm`。
- 主通道：4 根 `15 × 15 mm` 连续 7075-T651 候选纵梁。
- 横向构件：后框、MID2、MID1 与一体式前框/十字扩散结构。
- 舱板：2 块 `8 mm` 6061-T6 候选甲板，均带 `Ø30 mm` 通道与双面 `Ø50/Ø30 × 2 mm` 补强环。
- 外板：6 块 `1.5 mm` 可拆非承力封板。
- 前端：一体式前框后层 `x=158.25..170.25 mm`；时钟化 `160 mm` 接口台 `x=170.25..185.25 mm`；哈希冻结的 M6 载荷桥候选几何为 `x=185.25..196.0 mm`，不等于飞行发布。
- 前端孔系：`4×Ø6.6 @ local (±70,±70) mm`，按 M3R 实测变换进入 S 系；对拍最大残差 `{hole_residual:.3e} mm`。

## 质量与不确定度

- 显式结构候选质量：`{model['mass_kg']:.6f} kg`。
- 结构候选质心 S：`[{model['cg_S_m'][0]:.6f}, {model['cg_S_m'][1]:.6f}, {model['cg_S_m'][2]:.6f}] m`。
- 占现有 `23.3032134 kg` bus 预算：`{100.0*model['mass_boundary']['candidate_structure_fraction_of_bus_budget']:.2f}%`。
- 未建模设备/紧固/线束剩余预算：`{model['mass_boundary']['residual_bus_equipment_and_unmodelled_mass_budget_kg']:.6f} kg`；这只是预算余量，不是设备质量测量。
- 项目下游质量标准不确定度：`u={uncertainty['project_policy']['standard_uncertainty_kg']:.6f} kg (15%, k=1)`。
- 局部 GUM Type-B 输入敏感度诊断：`u={uncertainty['gum_linear']['standard_uncertainty_kg']:.6f} kg`，`U={uncertainty['gum_linear']['expanded_uncertainty_kg']:.6f} kg (k=2)`；不得替代项目 15% 政策。
- Monte Carlo 与 GUM 的质量标准差比：`{uncertainty['monte_carlo']['mass_standard_deviation_to_gum_ratio']:.6f}`。

## 载荷路径

`B601@208 → Stage A → Stage B@196..208 → M6 bridge@185.25..196 → D_BUS_MATE@185.25 → front interface land@170.25..185.25 → front cruciform/frame → four longerons → MID1/MID2/rear frames and decks`。

刚度筛选只使用同一 `WP4 LC-014, T_c=5 ms` 工况：峰值力 `212.884685 N`，法向/弯曲工况弯矩 `307.053156 N·m`，剪切/扭转工况扭矩 `40.902594 N·m`。禁止与 WP7 `19.07327 N·m` 非共时数值混用；扭转响应仍为 `UNKNOWN`。

## 当前不能宣称

- 框—纵梁节点、封板夹片以及 4×M6 完整夹紧栈仍需设计和复算；M7 WP4 的 18.75 mm grip/扭矩不得直接继承。M4/M5/M6 均必须从旧 6061 模型重绑到实际 7075/6061 混材栈后重算。
- 材料值是设计筛选典型值，不是飞行 allowable；采购规范、状态、工艺、表面处理、应力腐蚀与不确定度权威仍 HOLD。
- 解析刚度只是假定刚性横框的四纵梁 stiff-bound，不含接头与局部板弯曲，因此不产生结构 PASS。
- 未生成可见 CAD，故本轮不执行快照或 CAD Viewer。后续只能使用本次运行唯一 ID 的新授权；低于 6 GiB 时必须形成 `OWNER_OVERRIDE_LOW_MEMORY` 记录且 `memory_gate_passed=false`，不得伪装为内存门 PASS。任何生成尝试会先使当前 source-only Gate 失效。
"""
    (PACKAGE / "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.md").write_text(report_md, encoding="utf-8")

    tracked = [
        INPUT_PATH,
        Path(__file__),
        PACKAGE / "bus_primary_structure_source_v1.py",
        PACKAGE / "validate_bus_primary_structure_source_v1.py",
        PACKAGE / "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.json",
        PACKAGE / "BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.md",
        PACKAGE / "BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1.json",
        PACKAGE / "BUS_MASS_DECOMPOSITION_BRIDGE_V1.json",
        PACKAGE / "BUS_PRIMARY_STRUCTURE_SOURCE_GATE_V1.json",
        PACKAGE / "UNIFIED_R2_PREBIND_STRUCTURE_DELTA_V1.json",
        PACKAGE / "BUS_PRIMARY_STRUCTURE_REPRODUCIBILITY_RECEIPT_V1.json",
        PACKAGE / "BUS_M3R_LOAD_PATH_CONTRACT_V1.md",
        PACKAGE / "README.md",
        # The validator output embeds the pre-write register audit; excluding its
        # own hash avoids a self-reference cycle while the validator source remains
        # hash-bound above.
    ]
    with (PACKAGE / "BUS_PRIMARY_STRUCTURE_SHA256_V1.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "bytes", "sha256", "status"])
        for path in tracked:
            if path.is_file():
                writer.writerow([path.relative_to(PACKAGE).as_posix(), path.stat().st_size, _sha256(path), "HASH_BOUND_SOURCE_ONLY"])


if __name__ == "__main__":
    build_reports()
