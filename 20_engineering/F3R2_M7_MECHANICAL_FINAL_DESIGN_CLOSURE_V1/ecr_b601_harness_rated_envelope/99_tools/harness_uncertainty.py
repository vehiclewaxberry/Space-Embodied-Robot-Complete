# -*- coding: utf-8 -*-
"""Deterministic Type-B Monte Carlo propagation for the B601 harness.

The module is deliberately independent of FreeCAD so the Route-B builder and
stand-alone validators can use the same uncertainty model.  Coordinates enter
in millimetres and are converted once, at the function boundary, to metres.

The ten harness outputs are ordered as::

    [m, cgx, cgy, cgz, Ixx, Iyy, Izz, Ixy, Ixz, Iyz]

Mass properties use the spacecraft ``S`` frame and inertia is about the
reported centre of mass.  A single random variable is used for every repeated
item in a category (all 24 wires, both connectors, all 18 clamps, and both
strain-reliefs).  This implements 100 % within-category correlation while the
category-level input variables remain mutually independent.

This is a design-model uncertainty calculation, not a flight or as-built
statistical confidence statement.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np


DEFAULT_SEED = 20260823
DEFAULT_N = 8192
OUTPUT_ORDER = (
    "mass_kg",
    "cg_x_m",
    "cg_y_m",
    "cg_z_m",
    "Ixx_kg_m2",
    "Iyy_kg_m2",
    "Izz_kg_m2",
    "Ixy_kg_m2",
    "Ixz_kg_m2",
    "Iyz_kg_m2",
)
OUTPUT_UNITS = (
    "kg",
    "m",
    "m",
    "m",
    "kg*m^2",
    "kg*m^2",
    "kg*m^2",
    "kg*m^2",
    "kg*m^2",
    "kg*m^2",
)
SYSTEM_OUTPUT_ORDER = OUTPUT_ORDER + (
    "principal_moment_1_kg_m2",
    "principal_moment_2_kg_m2",
    "principal_moment_3_kg_m2",
)
SYSTEM_OUTPUT_UNITS = OUTPUT_UNITS + ("kg*m^2", "kg*m^2", "kg*m^2")
PHYSICAL_DOMAIN_TOLERANCE_KG_M2 = 1.0e-12
BASE_REJECTION_MAX_DRAW_MULTIPLIER = 200


def nominal_constants() -> dict[str, Any]:
    """Return the frozen nominal values and explicit SI units.

    Uniform specifications are represented by their bounds and midpoint.
    ``cut_length_standard_uncertainty_m`` is already a standard uncertainty;
    it is therefore used directly as the normal distribution's sigma.
    """

    cut_length_m = 4.001158
    wire_each = 0.00427
    wire_count = 24
    sleeve = 0.5 * (0.010 + 0.040)
    connector = 0.5 * (0.015 + 0.040)
    clamp = 0.5 * (0.003 + 0.008)
    strain = 0.5 * (0.005 + 0.015)
    connector_count = 2
    clamp_count = 18
    strain_count = 2
    linear_mass = wire_count * wire_each + sleeve
    total_mass = (
        cut_length_m * linear_mass
        + connector_count * connector
        + clamp_count * clamp
        + strain_count * strain
    )
    return {
        "schema": "B601_HARNESS_NOMINAL_CONSTANTS_V1",
        "cut_length_m": cut_length_m,
        "cut_length_standard_uncertainty_m": 0.003,
        "cut_length_distribution": "normal",
        "wire_count": wire_count,
        "single_wire_linear_mass_kg_per_m": wire_each,
        "single_wire_linear_mass_relative_half_width": 0.10,
        "single_wire_linear_mass_bounds_kg_per_m": [
            wire_each * 0.90,
            wire_each * 1.10,
        ],
        "sleeve_linear_mass_kg_per_m": sleeve,
        "sleeve_linear_mass_bounds_kg_per_m": [0.010, 0.040],
        "connector_count": connector_count,
        "connector_mass_kg_each": connector,
        "connector_mass_bounds_kg_each": [0.015, 0.040],
        "clamp_count": clamp_count,
        "clamp_mass_kg_each": clamp,
        "clamp_mass_bounds_kg_each": [0.003, 0.008],
        "strain_relief_count": strain_count,
        "strain_relief_mass_kg_each": strain,
        "strain_relief_mass_bounds_kg_each": [0.005, 0.015],
        "bundle_linear_mass_kg_per_m": linear_mass,
        "slack_point_uniform_half_width_m_per_axis": 0.030,
        "global_installation_offset_uniform_half_width_m_per_axis": 0.002,
        "total_mass_kg": total_mass,
        "units": {
            "length": "m",
            "linear_mass": "kg/m",
            "mass": "kg",
            "center_of_mass": "m",
            "inertia": "kg*m^2",
            "input_geometry": "mm",
        },
        "correlation_policy": {
            "within_repeated_category": 1.0,
            "between_category_level_inputs": 0.0,
        },
        "metrology_status": "TYPE_B_DESIGN_MODEL__NOT_FLIGHT_OR_AS_BUILT",
    }


def _as_points(name: str, values: Sequence[Sequence[float]], *, minimum: int) -> np.ndarray:
    points = np.asarray(values, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] < minimum:
        raise ValueError(f"{name} must have shape (N, 3) with N >= {minimum}")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} contains a non-finite coordinate")
    return points * 1.0e-3


def _components_to_matrix(values: Sequence[float]) -> np.ndarray:
    comp = np.asarray(values, dtype=float)
    if comp.shape != (6,):
        raise ValueError("inertia components must have shape (6,)")
    ixx, iyy, izz, ixy, ixz, iyz = comp
    return np.asarray(
        [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]], dtype=float
    )


def _components_batch_to_matrix(values: np.ndarray) -> np.ndarray:
    """Convert an ``(..., 6)`` component array to ``(..., 3, 3)``."""

    comp = np.asarray(values, dtype=float)
    if comp.ndim < 1 or comp.shape[-1] != 6:
        raise ValueError("inertia component array must end in dimension 6")
    matrix = np.empty(comp.shape[:-1] + (3, 3), dtype=float)
    matrix[..., 0, 0] = comp[..., 0]
    matrix[..., 1, 1] = comp[..., 1]
    matrix[..., 2, 2] = comp[..., 2]
    matrix[..., 0, 1] = matrix[..., 1, 0] = comp[..., 3]
    matrix[..., 0, 2] = matrix[..., 2, 0] = comp[..., 4]
    matrix[..., 1, 2] = matrix[..., 2, 1] = comp[..., 5]
    return matrix


def _matrix_components(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    return np.stack(
        (
            matrix[..., 0, 0],
            matrix[..., 1, 1],
            matrix[..., 2, 2],
            matrix[..., 0, 1],
            matrix[..., 0, 2],
            matrix[..., 1, 2],
        ),
        axis=-1,
    )


def _parallel_axis_batch(mass: np.ndarray, displacement: np.ndarray) -> np.ndarray:
    mass = np.asarray(mass, dtype=float)
    displacement = np.asarray(displacement, dtype=float)
    d2 = np.einsum("...i,...i->...", displacement, displacement)
    eye = np.eye(3, dtype=float)
    return mass[..., None, None] * (
        d2[..., None, None] * eye
        - np.einsum("...i,...j->...ij", displacement, displacement)
    )


def _safe_correlation(samples: np.ndarray) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    centred = samples - np.mean(samples, axis=0, keepdims=True)
    scale = np.sqrt(np.sum(centred * centred, axis=0))
    covariance_numerator = centred.T @ centred
    denominator = np.outer(scale, scale)
    correlation = np.divide(
        covariance_numerator,
        denominator,
        out=np.zeros_like(covariance_numerator),
        where=denominator > 0.0,
    )
    np.fill_diagonal(correlation, 1.0)
    return np.clip(correlation, -1.0, 1.0)


def _physical_domain_checks(samples: np.ndarray) -> dict[str, Any]:
    """Audit mass and inertia samples against the physical rigid-body domain."""

    samples = np.asarray(samples, dtype=float)
    if samples.ndim != 2 or samples.shape[1] < 10:
        raise ValueError("mass-property samples must have at least ten columns")
    count = int(samples.shape[0])
    inertia = _components_batch_to_matrix(samples[:, 4:10])
    principal = np.linalg.eigvalsh(inertia)
    positive_mass = samples[:, 0] > 0.0
    positive_definite = principal[:, 0] > 0.0
    triangle_margin = principal[:, 0] + principal[:, 1] - principal[:, 2]
    triangle = triangle_margin >= -PHYSICAL_DOMAIN_TOLERANCE_KG_M2
    return {
        "sample_count": count,
        "positive_mass_pass_count": int(np.count_nonzero(positive_mass)),
        "positive_mass_pass_rate": float(np.mean(positive_mass)),
        "positive_definite_pass_count": int(np.count_nonzero(positive_definite)),
        "positive_definite_pass_rate": float(np.mean(positive_definite)),
        "triangle_inequality_pass_count": int(np.count_nonzero(triangle)),
        "triangle_inequality_pass_rate": float(np.mean(triangle)),
        "min_principal_moment": float(np.min(principal[:, 0])),
        "min_principal_moment_kg_m2": float(np.min(principal[:, 0])),
        "min_triangle_margin": float(np.min(triangle_margin)),
        "min_triangle_margin_kg_m2": float(np.min(triangle_margin)),
        "triangle_tolerance_kg_m2": PHYSICAL_DOMAIN_TOLERANCE_KG_M2,
        "all_samples_in_physical_domain": bool(
            np.all(positive_mass) and np.all(positive_definite) and np.all(triangle)
        ),
    }


def _summary_receipt(
    samples: np.ndarray,
    nominal_vector: np.ndarray,
    output_order: Sequence[str],
    output_units: Sequence[str],
) -> tuple[list[dict[str, Any]], list[list[float]], dict[str, Any]]:
    samples = np.asarray(samples, dtype=float)
    n = int(samples.shape[0])
    means = np.mean(samples, axis=0)
    standard = np.std(samples, axis=0, ddof=1)
    quantiles = np.quantile(samples, [0.025, 0.975], axis=0)
    half = samples[: n // 2]
    half_mean = np.mean(half, axis=0)
    half_standard = np.std(half, axis=0, ddof=1)
    eps = np.finfo(float).eps
    mean_shift_u = np.abs(half_mean - means) / np.maximum(standard, eps)
    std_shift_relative = np.abs(half_standard - standard) / np.maximum(standard, eps)

    outputs: list[dict[str, Any]] = []
    convergence_outputs: list[dict[str, Any]] = []
    for index, (name, unit) in enumerate(zip(output_order, output_units)):
        outputs.append(
            {
                "name": name,
                "unit": unit,
                "nominal": float(nominal_vector[index]),
                "monte_carlo_mean": float(means[index]),
                "standard_uncertainty": float(standard[index]),
                "coverage_factor_k": 2.0,
                "expanded_uncertainty_k2": float(2.0 * standard[index]),
                "quantile_2p5": float(quantiles[0, index]),
                "quantile_97p5": float(quantiles[1, index]),
                "evaluation_type": "B",
                "degrees_of_freedom": "infinite_assumed_for_type_B_model",
            }
        )
        convergence_outputs.append(
            {
                "name": name,
                "half_mean": float(half_mean[index]),
                "full_mean": float(means[index]),
                "absolute_mean_shift": float(abs(half_mean[index] - means[index])),
                "mean_shift_as_fraction_of_full_standard_uncertainty": float(mean_shift_u[index]),
                "half_standard_uncertainty": float(half_standard[index]),
                "full_standard_uncertainty": float(standard[index]),
                "relative_standard_uncertainty_shift": float(std_shift_relative[index]),
            }
        )
    convergence = {
        "comparison": "first_N_over_2_samples_vs_all_N_samples",
        "half_N": int(n // 2),
        "full_N": n,
        "diagnostic_thresholds": {
            "max_mean_shift_as_fraction_of_full_standard_uncertainty": 0.10,
            "max_relative_standard_uncertainty_shift": 0.10,
        },
        "max_mean_shift_as_fraction_of_full_standard_uncertainty": float(np.max(mean_shift_u)),
        "max_relative_standard_uncertainty_shift": float(np.max(std_shift_relative)),
        "diagnostic_pass": bool(np.max(mean_shift_u) <= 0.10 and np.max(std_shift_relative) <= 0.10),
        "per_output": convergence_outputs,
        "qualification_effect": "DIAGNOSTIC_ONLY_NOT_A_FLIGHT_QUALIFICATION_GATE",
    }
    return outputs, _safe_correlation(samples).tolist(), convergence


def _line_shape_moments(points_m: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Return length, unit-mass first moment, and unit-mass raw second moment."""

    a = points_m[:-1]
    b = points_m[1:]
    lengths = np.linalg.norm(b - a, axis=1)
    if np.any(lengths <= 1.0e-12):
        keep = lengths > 1.0e-12
        a, b, lengths = a[keep], b[keep], lengths[keep]
    total_length = float(np.sum(lengths))
    if not total_length > 0.0:
        raise ValueError("points_mm defines no non-zero cable segment")
    weights = lengths / total_length
    first = np.sum(weights[:, None] * 0.5 * (a + b), axis=0)
    aa = np.einsum("ki,kj->kij", a, a)
    bb = np.einsum("ki,kj->kij", b, b)
    ab = np.einsum("ki,kj->kij", a, b)
    ba = np.einsum("ki,kj->kij", b, a)
    raw_second_per_segment = (aa + bb) / 3.0 + (ab + ba) / 6.0
    raw_second = np.sum(weights[:, None, None] * raw_second_per_segment, axis=0)
    return total_length, first, raw_second


def _sample_harness_inputs(n: int, seed: int) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    constants = nominal_constants()
    rng = np.random.default_rng(int(seed))
    wire_bounds = constants["single_wire_linear_mass_bounds_kg_per_m"]
    inputs = {
        "cut_length_m": rng.normal(
            constants["cut_length_m"], constants["cut_length_standard_uncertainty_m"], n
        ),
        "single_wire_linear_mass_kg_per_m": rng.uniform(*wire_bounds, n),
        "sleeve_linear_mass_kg_per_m": rng.uniform(0.010, 0.040, n),
        "connector_mass_kg_each": rng.uniform(0.015, 0.040, n),
        "clamp_mass_kg_each": rng.uniform(0.003, 0.008, n),
        "strain_relief_mass_kg_each": rng.uniform(0.005, 0.015, n),
        "slack_x_m": rng.uniform(-0.030, 0.030, n),
        "slack_y_m": rng.uniform(-0.030, 0.030, n),
        "slack_z_m": rng.uniform(-0.030, 0.030, n),
        "install_x_m": rng.uniform(-0.002, 0.002, n),
        "install_y_m": rng.uniform(-0.002, 0.002, n),
        "install_z_m": rng.uniform(-0.002, 0.002, n),
    }
    specifications = [
        {
            "name": "cut_length_m",
            "unit": "m",
            "nominal": constants["cut_length_m"],
            "standard_uncertainty": constants["cut_length_standard_uncertainty_m"],
            "distribution": "normal",
        },
        {
            "name": "single_wire_linear_mass_kg_per_m",
            "unit": "kg/m",
            "nominal": constants["single_wire_linear_mass_kg_per_m"],
            "bounds": wire_bounds,
            "standard_uncertainty": (wire_bounds[1] - wire_bounds[0]) / np.sqrt(12.0),
            "distribution": "uniform",
        },
        {
            "name": "sleeve_linear_mass_kg_per_m",
            "unit": "kg/m",
            "nominal": constants["sleeve_linear_mass_kg_per_m"],
            "bounds": [0.010, 0.040],
            "standard_uncertainty": (0.040 - 0.010) / np.sqrt(12.0),
            "distribution": "uniform",
        },
        {
            "name": "connector_mass_kg_each",
            "unit": "kg",
            "nominal": constants["connector_mass_kg_each"],
            "bounds": [0.015, 0.040],
            "standard_uncertainty": (0.040 - 0.015) / np.sqrt(12.0),
            "distribution": "uniform",
        },
        {
            "name": "clamp_mass_kg_each",
            "unit": "kg",
            "nominal": constants["clamp_mass_kg_each"],
            "bounds": [0.003, 0.008],
            "standard_uncertainty": (0.008 - 0.003) / np.sqrt(12.0),
            "distribution": "uniform",
        },
        {
            "name": "strain_relief_mass_kg_each",
            "unit": "kg",
            "nominal": constants["strain_relief_mass_kg_each"],
            "bounds": [0.005, 0.015],
            "standard_uncertainty": (0.015 - 0.005) / np.sqrt(12.0),
            "distribution": "uniform",
        },
    ]
    for prefix, half_width in (("slack", 0.030), ("install", 0.002)):
        for axis in "xyz":
            specifications.append(
                {
                    "name": f"{prefix}_{axis}_m",
                    "unit": "m",
                    "nominal": 0.0,
                    "bounds": [-half_width, half_width],
                    "standard_uncertainty": half_width / np.sqrt(3.0),
                    "distribution": "uniform",
                }
            )
    provenance = {
        "cut_length_m": {
            "source": "R2_HRN_05_DERIVED_CANDIDATE",
            "authority": "R2_HRN_05_DERIVED_CANDIDATE",
        },
        "single_wire_linear_mass_kg_per_m": {
            "source": "https://www.te.com/en/product-7534143001.html",
            "authority": "TE_VENDOR_PROXY_PLUS_10_PERCENT_DESIGN_RANGE",
        },
        "sleeve_linear_mass_kg_per_m": {
            "source": "DESIGN_CLASS_ASSUMPTION__NO_SELECTED_PART",
            "authority": "DESIGN_CLASS_ASSUMPTION",
        },
        "connector_mass_kg_each": {
            "source": "DESIGN_CLASS_ASSUMPTION__NO_SELECTED_PART",
            "authority": "DESIGN_CLASS_ASSUMPTION",
        },
        "clamp_mass_kg_each": {
            "source": "DESIGN_CLASS_ASSUMPTION__NO_SELECTED_PART",
            "authority": "DESIGN_CLASS_ASSUMPTION",
        },
        "strain_relief_mass_kg_each": {
            "source": "DESIGN_CLASS_ASSUMPTION__NO_SELECTED_PART",
            "authority": "DESIGN_CLASS_ASSUMPTION",
        },
    }
    for item in specifications:
        item["evaluation_type"] = "B"
        item["degrees_of_freedom"] = "infinite_assumed_for_type_B_model"
        if item["name"].startswith(("slack_", "install_")):
            item["source"] = "ODR40_DESIGN_MODEL_ASSUMPTION"
            item["authority"] = "ODR40_DESIGN_MODEL_ASSUMPTION"
        else:
            item.update(provenance[item["name"]])
    return inputs, specifications


def _evaluate_harness(
    points_m: np.ndarray,
    analytic_length_m: float,
    coil_center_m: np.ndarray,
    clamps_m: np.ndarray,
    values: Mapping[str, np.ndarray],
) -> np.ndarray:
    """Evaluate all samples using category moments; no per-sample loop."""

    n = int(np.asarray(values["cut_length_m"]).size)
    _, line_first, line_raw_second = _line_shape_moments(points_m)
    install = np.column_stack(
        (values["install_x_m"], values["install_y_m"], values["install_z_m"])
    )
    slack_delta = np.column_stack(
        (values["slack_x_m"], values["slack_y_m"], values["slack_z_m"])
    )
    wire_count = nominal_constants()["wire_count"]
    rho = (
        wire_count * values["single_wire_linear_mass_kg_per_m"]
        + values["sleeve_linear_mass_kg_per_m"]
    )
    slack_length = values["cut_length_m"] - analytic_length_m
    if np.any(slack_length < 0.0):
        minimum = float(np.min(slack_length))
        raise ValueError(
            "sampled cut length is shorter than analytic route length; "
            f"minimum slack is {minimum:.9g} m"
        )

    total_mass = np.zeros(n, dtype=float)
    first_moment = np.zeros((n, 3), dtype=float)
    raw_second = np.zeros((n, 3, 3), dtype=float)

    # Distributed route: exact first and raw second moments of straight segments.
    route_mass = rho * analytic_length_m
    route_first = line_first[None, :] + install
    route_raw = (
        line_raw_second[None, :, :]
        + np.einsum("i,nj->nij", line_first, install)
        + np.einsum("ni,j->nij", install, line_first)
        + np.einsum("ni,nj->nij", install, install)
    )
    total_mass += route_mass
    first_moment += route_mass[:, None] * route_first
    raw_second += route_mass[:, None, None] * route_raw

    # Unplaced cut-length surplus at the joint-1 coil, with explicit location model.
    slack_mass = rho * slack_length
    slack_position = coil_center_m[None, :] + slack_delta + install
    total_mass += slack_mass
    first_moment += slack_mass[:, None] * slack_position
    raw_second += slack_mass[:, None, None] * np.einsum(
        "ni,nj->nij", slack_position, slack_position
    )

    def add_equal_point_group(per_item_mass: np.ndarray, locations: np.ndarray) -> None:
        nonlocal total_mass, first_moment, raw_second
        count = int(locations.shape[0])
        shifted_sum = np.sum(locations, axis=0)[None, :] + count * install
        base_raw_sum = np.einsum("ki,kj->ij", locations, locations)
        shifted_raw_sum = (
            base_raw_sum[None, :, :]
            + np.einsum("i,nj->nij", np.sum(locations, axis=0), install)
            + np.einsum("ni,j->nij", install, np.sum(locations, axis=0))
            + count * np.einsum("ni,nj->nij", install, install)
        )
        total_mass += count * per_item_mass
        first_moment += per_item_mass[:, None] * shifted_sum
        raw_second += per_item_mass[:, None, None] * shifted_raw_sum

    endpoints = np.vstack((points_m[0], points_m[-1]))
    add_equal_point_group(values["connector_mass_kg_each"], endpoints)
    add_equal_point_group(values["clamp_mass_kg_each"], clamps_m)
    add_equal_point_group(values["strain_relief_mass_kg_each"], endpoints)

    if np.any(total_mass <= 0.0):
        raise ValueError("non-positive harness mass generated")
    cg = first_moment / total_mass[:, None]
    inertia_origin = (
        np.trace(raw_second, axis1=1, axis2=2)[:, None, None] * np.eye(3)
        - raw_second
    )
    inertia_cg = inertia_origin - _parallel_axis_batch(total_mass, cg)
    inertia_cg = 0.5 * (inertia_cg + np.swapaxes(inertia_cg, 1, 2))
    return np.column_stack((total_mass, cg, _matrix_components(inertia_cg)))


def propagate_harness(
    points_mm: Sequence[Sequence[float]],
    analytic_length_mm: float,
    coil_center_mm: Sequence[float],
    clamp_positions_mm: Sequence[Sequence[float]],
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Propagate B601 harness mass-property design uncertainty.

    Parameters
    ----------
    points_mm:
        Ordered cable centreline polyline in frame S, millimetres.
    analytic_length_mm:
        Authoritative routed length, millimetres.  Segment geometry is used for
        shape moments; this scalar is used for the mass split between route and
        joint-1 slack.
    coil_center_mm:
        Nominal point for unplaced cut-length surplus, frame S, millimetres.
    clamp_positions_mm:
        The 18 nominal clamp positions, frame S, millimetres.
    n, seed:
        Monte Carlo sample count and deterministic PCG64 seed.

    Returns a dictionary with ``nominal``, an ``(n, 10)`` NumPy ``samples``
    array, and a JSON/YAML-safe ``uncertainty_receipt``.
    """

    n = int(n)
    if n < 4 or n % 2:
        raise ValueError("n must be an even integer >= 4 for half-vs-full comparison")
    if not np.isfinite(analytic_length_mm) or analytic_length_mm <= 0.0:
        raise ValueError("analytic_length_mm must be finite and positive")
    points_m = _as_points("points_mm", points_mm, minimum=2)
    clamps_m = _as_points("clamp_positions_mm", clamp_positions_mm, minimum=1)
    constants = nominal_constants()
    if clamps_m.shape[0] != constants["clamp_count"]:
        raise ValueError(
            f"clamp_positions_mm must contain exactly {constants['clamp_count']} positions"
        )
    coil_center_m = np.asarray(coil_center_mm, dtype=float)
    if coil_center_m.shape != (3,) or not np.all(np.isfinite(coil_center_m)):
        raise ValueError("coil_center_mm must be a finite three-vector")
    coil_center_m = coil_center_m * 1.0e-3
    analytic_length_m = float(analytic_length_mm) * 1.0e-3
    if analytic_length_m >= constants["cut_length_m"] - 6.0 * constants["cut_length_standard_uncertainty_m"]:
        raise ValueError(
            "analytic route leaves less than six cut-length standard uncertainties of slack"
        )

    values, input_specifications = _sample_harness_inputs(n, int(seed))
    samples = _evaluate_harness(
        points_m, analytic_length_m, coil_center_m, clamps_m, values
    )

    nominal_values = {
        "cut_length_m": np.asarray([constants["cut_length_m"]]),
        "single_wire_linear_mass_kg_per_m": np.asarray(
            [constants["single_wire_linear_mass_kg_per_m"]]
        ),
        "sleeve_linear_mass_kg_per_m": np.asarray(
            [constants["sleeve_linear_mass_kg_per_m"]]
        ),
        "connector_mass_kg_each": np.asarray([constants["connector_mass_kg_each"]]),
        "clamp_mass_kg_each": np.asarray([constants["clamp_mass_kg_each"]]),
        "strain_relief_mass_kg_each": np.asarray(
            [constants["strain_relief_mass_kg_each"]]
        ),
        "slack_x_m": np.zeros(1),
        "slack_y_m": np.zeros(1),
        "slack_z_m": np.zeros(1),
        "install_x_m": np.zeros(1),
        "install_y_m": np.zeros(1),
        "install_z_m": np.zeros(1),
    }
    nominal_vector = _evaluate_harness(
        points_m, analytic_length_m, coil_center_m, clamps_m, nominal_values
    )[0]
    nominal_matrix = _components_to_matrix(nominal_vector[4:])
    nominal = {
        "mass_kg": float(nominal_vector[0]),
        "cg_S_m": nominal_vector[1:4].tolist(),
        "inertia_about_own_cg_S_kg_m2": nominal_matrix.tolist(),
        "inertia_components_kg_m2": {
            name: float(value)
            for name, value in zip(
                ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"), nominal_vector[4:]
            )
        },
        "geometric_polyline_length_m": _line_shape_moments(points_m)[0],
        "analytic_route_length_m": analytic_length_m,
        "nominal_cut_length_surplus_m": constants["cut_length_m"] - analytic_length_m,
        "units": {
            "mass": "kg",
            "center_of_mass": "m",
            "inertia": "kg*m^2",
            "length": "m",
            "reference_frame": "S",
            "inertia_reference_point": "harness_center_of_mass",
        },
    }
    outputs, correlation, convergence = _summary_receipt(
        samples, nominal_vector, OUTPUT_ORDER, OUTPUT_UNITS
    )
    input_order = [item["name"] for item in input_specifications]
    standard_by_output = {item["name"]: item["standard_uncertainty"] for item in outputs}
    expanded_by_output = {item["name"]: item["expanded_uncertainty_k2"] for item in outputs}
    quantiles_by_output = {
        item["name"]: [item["quantile_2p5"], item["quantile_97p5"]]
        for item in outputs
    }
    input_correlation = np.eye(len(input_order)).tolist()
    correlation_identity = {
        "category_level_input_matrix": "identity",
        "same_category_repeated_items": {
            "24_wires": 1.0,
            "2_connectors": 1.0,
            "18_clamps": 1.0,
            "2_strain_reliefs": 1.0,
        },
        "between_categories": 0.0,
        "implementation": "one shared draw per repeated-item category",
    }
    deterministic_exact_inputs = [
        {
            "name": "wire_count",
            "value": constants["wire_count"],
            "unit": "count",
            "standard_uncertainty": 0.0,
            "distribution": "exact",
            "evaluation_type": "B_exact_design_definition",
            "degrees_of_freedom": "infinite",
            "source": "PROVISIONAL_ELECTRICAL_ARCHITECTURE_ASSUMPTION",
            "authority": "ODR40_DESIGN_MODEL_ASSUMPTION",
            "correlation_semantics": "multiplies the one shared wire-category linear-mass draw; no independent per-wire draws",
        },
        {
            "name": "connector_count",
            "value": constants["connector_count"],
            "unit": "count",
            "standard_uncertainty": 0.0,
            "distribution": "exact",
            "evaluation_type": "B_exact_design_definition",
            "degrees_of_freedom": "infinite",
            "source": "ROUTE_B_PRODUCT_DEFINITION",
            "authority": "ODR40_DESIGN_MODEL_ASSUMPTION",
            "correlation_semantics": "two items share one connector-category mass draw",
        },
        {
            "name": "clamp_count",
            "value": constants["clamp_count"],
            "unit": "count",
            "standard_uncertainty": 0.0,
            "distribution": "exact",
            "evaluation_type": "B_exact_design_definition",
            "degrees_of_freedom": "infinite",
            "source": "ROUTE_B_PRODUCT_DEFINITION",
            "authority": "ODR40_DESIGN_MODEL_ASSUMPTION",
            "correlation_semantics": "18 items share one clamp-category mass draw",
        },
        {
            "name": "strain_relief_count",
            "value": constants["strain_relief_count"],
            "unit": "count",
            "standard_uncertainty": 0.0,
            "distribution": "exact",
            "evaluation_type": "B_exact_design_definition",
            "degrees_of_freedom": "infinite",
            "source": "ROUTE_B_PRODUCT_DEFINITION",
            "authority": "ODR40_DESIGN_MODEL_ASSUMPTION",
            "correlation_semantics": "two items share one strain-relief-category mass draw",
        },
    ]
    physical_checks = _physical_domain_checks(samples)
    if not physical_checks["all_samples_in_physical_domain"]:
        raise RuntimeError(
            "harness Monte Carlo samples left the physical mass-property domain"
        )
    receipt = {
        "schema": "B601_HARNESS_TYPE_B_MONTE_CARLO_RECEIPT_V1",
        "method": "JCGM_101_STYLE_MONTE_CARLO_PROPAGATION",
        "model_status": "NON_FLIGHT_DESIGN_MODEL__NOT_AS_BUILT_STATISTICS",
        "seed": int(seed),
        "N": n,
        "random_generator": "numpy.random.PCG64",
        "output_order": list(OUTPUT_ORDER),
        "output_units": dict(zip(OUTPUT_ORDER, OUTPUT_UNITS)),
        "outputs": outputs,
        "standard_uncertainty": standard_by_output,
        "expanded_uncertainty_k2": expanded_by_output,
        "quantiles_2p5_97p5": quantiles_by_output,
        "output_correlation_matrix": correlation,
        "output_correlation_matrix_10x10": correlation,
        "inputs": input_specifications,
        "input_order": input_order,
        "input_correlation_matrix": input_correlation,
        "correlation_identity": correlation_identity,
        "input_model": {
            "input_order": input_order,
            "correlation_matrix": input_correlation,
            "distributions": {
                item["name"]: item["distribution"] for item in input_specifications
            },
            "specifications": input_specifications,
            "deterministic_exact_inputs": deterministic_exact_inputs,
            "correlation_identity": correlation_identity,
        },
        "measurement_model": {
            "mass": "L_cut*(24*rho_wire+rho_sleeve)+2*m_connector+18*m_clamp+2*m_strain",
            "geometry": "line-segment first/raw-second moments plus point masses; cut surplus at uncertain joint-1 coil point",
            "installation": "one common translation sampled uniformly +/-2 mm per S-axis",
            "slack_location": "coil centre plus independent uniform +/-30 mm per S-axis",
        },
        "coverage_statement": "U=k*u with k=2 is reported as an expanded design-model uncertainty; quantiles are empirical 2.5/97.5 percentiles and neither is a flight hardware confidence claim",
        "half_vs_full_convergence": convergence,
        "sampling": {
            "n": n,
            "seed": int(seed),
            "random_generator": "numpy.random.PCG64",
            "half_vs_full_convergence": convergence,
        },
        "physical_domain_checks": physical_checks,
        "units": nominal["units"],
    }
    return {"nominal": nominal, "samples": samples, "uncertainty_receipt": receipt}


def _extract_base_configuration(base_cfg: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    try:
        mass = float(base_cfg["mass"]["value_kg"])
        mass_u = float(base_cfg["mass"]["standard_uncertainty_kg"])
        cg = np.asarray(base_cfg["center_of_mass"]["xyz_m"], dtype=float)
        cg_u = np.asarray(
            base_cfg["center_of_mass"]["standard_uncertainty_xyz_m"], dtype=float
        )
        inertia_doc = base_cfg["inertia"]
        comp_doc = inertia_doc["components_kg_m2"]
        comp_u_doc = inertia_doc["standard_uncertainty_components_kg_m2"]
        keys = ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")
        inertia = np.asarray([comp_doc[key] for key in keys], dtype=float)
        inertia_u = np.asarray([comp_u_doc[key] for key in keys], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "base_cfg must provide mass, centre-of-mass, inertia, and every standard uncertainty"
        ) from exc
    nominal = np.concatenate(([mass], cg, inertia))
    standard = np.concatenate(([mass_u], cg_u, inertia_u))
    if nominal.shape != (10,) or standard.shape != (10,):
        raise ValueError("base_cfg mass-property vectors must contain 10 quantities")
    if not np.all(np.isfinite(nominal)) or not np.all(np.isfinite(standard)):
        raise ValueError("base_cfg contains a non-finite value")
    if mass <= 0.0 or np.any(standard < 0.0):
        raise ValueError("base mass must be positive and standard uncertainties non-negative")
    return nominal, standard


def _extract_harness_nominal(harness_nominal: Mapping[str, Any]) -> np.ndarray:
    if "nominal" in harness_nominal:
        harness_nominal = harness_nominal["nominal"]
    try:
        mass = float(harness_nominal["mass_kg"])
        cg = np.asarray(harness_nominal["cg_S_m"], dtype=float)
        matrix = np.asarray(
            harness_nominal["inertia_about_own_cg_S_kg_m2"], dtype=float
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "harness_nominal must provide mass_kg, cg_S_m, and inertia_about_own_cg_S_kg_m2"
        ) from exc
    if cg.shape != (3,) or matrix.shape != (3, 3):
        raise ValueError("harness_nominal CG/inertia shapes are invalid")
    vector = np.concatenate(([mass], cg, _matrix_components(matrix)))
    if mass <= 0.0 or not np.all(np.isfinite(vector)):
        raise ValueError("harness_nominal contains invalid values")
    return vector


def _draw_physical_base_samples(
    rng: np.random.Generator,
    nominal: np.ndarray,
    standard: np.ndarray,
    n: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Draw a truncated normal in the physical mass-property domain.

    The sequential stopping rule is evaluated in vector batches.  If a batch
    contains more valid rows than still required, only the prefix ending at the
    Nth accepted row is counted.  This is exactly equivalent to scalar
    sequential rejection while retaining vectorized eigensolves.
    """

    max_draws = int(BASE_REJECTION_MAX_DRAW_MULTIPLIER * n)
    accepted_chunks: list[np.ndarray] = []
    accepted_count = 0
    total_draws = 0
    while accepted_count < n and total_draws < max_draws:
        needed = n - accepted_count
        remaining_budget = max_draws - total_draws
        batch_size = min(max(1024, 2 * needed), 65536, remaining_budget)
        candidates = rng.normal(
            loc=nominal[None, :], scale=standard[None, :], size=(batch_size, 10)
        )
        principal = np.linalg.eigvalsh(_components_batch_to_matrix(candidates[:, 4:10]))
        triangle_margin = principal[:, 0] + principal[:, 1] - principal[:, 2]
        valid = (
            (candidates[:, 0] > 0.0)
            & (principal[:, 0] > 0.0)
            & (triangle_margin >= -PHYSICAL_DOMAIN_TOLERANCE_KG_M2)
        )
        valid_indices = np.flatnonzero(valid)
        if valid_indices.size >= needed:
            stop = int(valid_indices[needed - 1]) + 1
            accepted_chunks.append(candidates[:stop][valid[:stop]])
            total_draws += stop
            accepted_count += needed
            break
        accepted_chunks.append(candidates[valid])
        accepted_count += int(valid_indices.size)
        total_draws += batch_size

    if accepted_count != n:
        raise RuntimeError(
            "physical-domain rejection sampler exhausted its explicit draw budget: "
            f"accepted {accepted_count}/{n} from {total_draws}/{max_draws} draws"
        )
    accepted = np.vstack(accepted_chunks)
    if accepted.shape != (n, 10):
        raise RuntimeError(
            f"rejection sampler internal closure error: expected {(n, 10)}, got {accepted.shape}"
        )
    checks = _physical_domain_checks(accepted)
    if not checks["all_samples_in_physical_domain"]:
        raise RuntimeError("rejection sampler returned a non-physical accepted base sample")
    realized_mean = np.mean(accepted, axis=0)
    realized_standard = np.std(accepted, axis=0, ddof=1)
    rejected = total_draws - n
    receipt = {
        "policy": "TRUNCATED_NORMAL_REJECTION_TO_PHYSICAL_MASS_PROPERTY_DOMAIN",
        "target_distribution": "independent_normal_before_physical_domain_truncation",
        "max_draw_multiplier": BASE_REJECTION_MAX_DRAW_MULTIPLIER,
        "max_draws": max_draws,
        "total_draws": int(total_draws),
        "accepted": n,
        "rejected": int(rejected),
        "acceptance_rate": float(n / total_draws),
        "target_mean": dict(zip(OUTPUT_ORDER, nominal.tolist())),
        "target_standard_uncertainty": dict(zip(OUTPUT_ORDER, standard.tolist())),
        "realized_mean_after_truncation": dict(zip(OUTPUT_ORDER, realized_mean.tolist())),
        "realized_standard_uncertainty_after_truncation": dict(
            zip(OUTPUT_ORDER, realized_standard.tolist())
        ),
        "target_correlation_matrix": np.eye(10).tolist(),
        "realized_correlation_matrix_after_truncation": _safe_correlation(accepted).tolist(),
        "correlation_effect": "physical-domain truncation induces output correlations even though the untruncated target inputs are independent",
        "acceptance_predicate": {
            "mass": "mass_kg > 0",
            "positive_definite": "minimum principal moment > 0",
            "triangle_inequality": "lambda_1 + lambda_2 - lambda_3 >= -tolerance",
            "triangle_tolerance_kg_m2": PHYSICAL_DOMAIN_TOLERANCE_KG_M2,
        },
        "accepted_sample_physical_domain_checks": checks,
    }
    return accepted, receipt


def _combine_mass_properties(base: np.ndarray, harness: np.ndarray) -> np.ndarray:
    """Vectorized two-body combination; inputs have shape (N, 10)."""

    base_mass, harness_mass = base[:, 0], harness[:, 0]
    if np.any(base_mass <= 0.0) or np.any(harness_mass <= 0.0):
        raise ValueError("sampled mass must remain positive")
    base_cg, harness_cg = base[:, 1:4], harness[:, 1:4]
    total_mass = base_mass + harness_mass
    cg = (
        base_mass[:, None] * base_cg + harness_mass[:, None] * harness_cg
    ) / total_mass[:, None]
    base_inertia = _components_batch_to_matrix(base[:, 4:])
    harness_inertia = _components_batch_to_matrix(harness[:, 4:])
    inertia = (
        base_inertia
        + _parallel_axis_batch(base_mass, base_cg - cg)
        + harness_inertia
        + _parallel_axis_batch(harness_mass, harness_cg - cg)
    )
    inertia = 0.5 * (inertia + np.swapaxes(inertia, 1, 2))
    principal = np.linalg.eigvalsh(inertia)
    return np.column_stack((total_mass, cg, _matrix_components(inertia), principal))


def propagate_system(
    base_cfg: Mapping[str, Any],
    harness_nominal: Mapping[str, Any],
    harness_samples: np.ndarray,
    seed: int = DEFAULT_SEED + 1,
    source_path: str | None = None,
) -> dict[str, Any]:
    """Combine a base configuration and harness using deterministic Monte Carlo.

    Base mass, three CG coordinates, and six inertia components have independent
    normal *target* distributions using their declared standard uncertainties.
    Rejection then truncates that joint target to positive mass, positive-
    definite inertia, and principal-moment triangle inequalities.  The induced
    correlations and realized standard uncertainties are reported explicitly.
    Harness row-wise correlations are preserved exactly.  ``source_path`` is an
    optional machine-readable provenance label for the supplied base record.
    """

    base_nominal, base_standard = _extract_base_configuration(base_cfg)
    harness_nominal_vector = _extract_harness_nominal(harness_nominal)
    harness_samples = np.asarray(harness_samples, dtype=float)
    if harness_samples.ndim != 2 or harness_samples.shape[1] != 10:
        raise ValueError("harness_samples must have shape (N, 10)")
    n = int(harness_samples.shape[0])
    if n < 4 or n % 2:
        raise ValueError("harness_samples N must be an even integer >= 4")
    if not np.all(np.isfinite(harness_samples)):
        raise ValueError("harness_samples contains a non-finite value")

    rng = np.random.default_rng(int(seed))
    base_samples, base_rejection = _draw_physical_base_samples(
        rng, base_nominal, base_standard, n
    )
    system_samples = _combine_mass_properties(base_samples, harness_samples)
    physical_checks = _physical_domain_checks(system_samples)
    if not physical_checks["all_samples_in_physical_domain"]:
        raise RuntimeError(
            "combined system samples left the physical mass-property domain"
        )
    nominal_system_vector = _combine_mass_properties(
        base_nominal[None, :], harness_nominal_vector[None, :]
    )[0]
    nominal_inertia = _components_to_matrix(nominal_system_vector[4:10])
    nominal = {
        "mass_kg": float(nominal_system_vector[0]),
        "cg_S_m": nominal_system_vector[1:4].tolist(),
        "inertia_about_system_cg_S_kg_m2": nominal_inertia.tolist(),
        "inertia_components_kg_m2": {
            name: float(value)
            for name, value in zip(
                ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"),
                nominal_system_vector[4:10],
            )
        },
        "principal_moments_kg_m2": nominal_system_vector[10:13].tolist(),
        "units": {
            "mass": "kg",
            "center_of_mass": "m",
            "inertia": "kg*m^2",
            "principal_moments": "kg*m^2",
            "reference_frame": "S",
            "inertia_reference_point": "combined_system_center_of_mass",
        },
    }
    outputs, correlation, convergence = _summary_receipt(
        system_samples,
        nominal_system_vector,
        SYSTEM_OUTPUT_ORDER,
        SYSTEM_OUTPUT_UNITS,
    )
    base_order = list(OUTPUT_ORDER)
    standard_by_output = {item["name"]: item["standard_uncertainty"] for item in outputs}
    expanded_by_output = {item["name"]: item["expanded_uncertainty_k2"] for item in outputs}
    quantiles_by_output = {
        item["name"]: [item["quantile_2p5"], item["quantile_97p5"]]
        for item in outputs
    }
    base_correlation = np.eye(10).tolist()
    source_root = (
        str(source_path)
        if source_path is not None
        else str(
            base_cfg.get("_source_path")
            or base_cfg.get("source_path")
            or base_cfg.get("source")
            or "CALLER_BASE_CFG_SOURCE_NOT_PROVIDED"
        )
    )
    field_paths = (
        "mass.value_kg",
        "center_of_mass.xyz_m[0]",
        "center_of_mass.xyz_m[1]",
        "center_of_mass.xyz_m[2]",
        "inertia.components_kg_m2.Ixx",
        "inertia.components_kg_m2.Iyy",
        "inertia.components_kg_m2.Izz",
        "inertia.components_kg_m2.Ixy",
        "inertia.components_kg_m2.Ixz",
        "inertia.components_kg_m2.Iyz",
    )
    base_authorities = (
        str(base_cfg.get("mass", {}).get("authority", "BASE_CFG_DECLARED_DESIGN_MODEL")),
        *(
            str(
                base_cfg.get("center_of_mass", {}).get(
                    "authority", "BASE_CFG_DECLARED_DESIGN_MODEL"
                )
            )
            for _ in range(3)
        ),
        *(
            str(
                base_cfg.get("inertia", {}).get(
                    "authority", "BASE_CFG_DECLARED_DESIGN_MODEL"
                )
            )
            for _ in range(6)
        ),
    )
    realized_base_mean = np.mean(base_samples, axis=0)
    realized_base_standard = np.std(base_samples, axis=0, ddof=1)
    base_inputs = [
        {
            "name": name,
            "unit": unit,
            "nominal": float(value),
            "standard_uncertainty": float(standard),
            "target_standard_uncertainty": float(standard),
            "realized_mean_after_truncation": float(realized_mean),
            "realized_standard_uncertainty_after_truncation": float(realized_standard),
            "distribution": "normal_target_truncated_to_physical_mass_property_domain",
            "evaluation_type": "B_carried_design_model",
            "degrees_of_freedom": "infinite_assumed_for_type_B_model",
            "source": f"{source_root}#{field_path}",
            "authority": authority,
        }
        for name, unit, value, standard, realized_mean, realized_standard, field_path, authority in zip(
            base_order,
            OUTPUT_UNITS,
            base_nominal,
            base_standard,
            realized_base_mean,
            realized_base_standard,
            field_paths,
            base_authorities,
        )
    ]
    correlation_assumptions = {
        "base_covariance_status": "UNKNOWN_NOT_PROVIDED",
        "base_target_input_correlations": "ASSUMED_INDEPENDENT_BEFORE_TRUNCATION",
        "base_realized_correlations": "INDUCED_BY_PHYSICAL_DOMAIN_TRUNCATION_AND_REPORTED",
        "harness_output_correlations": "PRESERVED_BY_ROW_WISE_JOINT_SAMPLES",
        "base_vs_harness": "INDEPENDENT",
        "qualification_effect": "ASSUMPTION_REQUIRES_REPLACEMENT_WHEN_BASE_COVARIANCE_EXISTS",
    }
    receipt = {
        "schema": "B601_SYSTEM_WITH_HARNESS_TYPE_B_MONTE_CARLO_RECEIPT_V1",
        "method": "DETERMINISTIC_MONTE_CARLO_MASS_PROPERTY_COMBINATION",
        "model_status": "NON_FLIGHT_DESIGN_MODEL__NOT_AS_BUILT_STATISTICS",
        "seed": int(seed),
        "N": n,
        "random_generator": "numpy.random.PCG64",
        "output_order": list(SYSTEM_OUTPUT_ORDER),
        "output_units": dict(zip(SYSTEM_OUTPUT_ORDER, SYSTEM_OUTPUT_UNITS)),
        "outputs": outputs,
        "standard_uncertainty": standard_by_output,
        "expanded_uncertainty_k2": expanded_by_output,
        "quantiles_2p5_97p5": quantiles_by_output,
        "output_correlation_matrix": correlation,
        "output_correlation_matrix_13x13": correlation,
        "base_inputs": base_inputs,
        "base_input_order": base_order,
        "base_input_correlation_matrix": base_correlation,
        "base_rejection_sampling": base_rejection,
        "input_model": {
            "input_order": base_order,
            "correlation_matrix": base_correlation,
            "distributions": {
                name: "normal_target_truncated_to_physical_mass_property_domain"
                for name in base_order
            },
            "specifications": base_inputs,
            "harness_joint_samples": "row-wise correlations preserved",
            "physical_domain_truncation": base_rejection,
        },
        "correlation_assumptions": correlation_assumptions,
        "coverage_statement": "U=k*u with k=2 is an expanded design-model uncertainty, not a statistical flight-hardware 95 percent confidence interval",
        "half_vs_full_convergence": convergence,
        "sampling": {
            "n": n,
            "seed": int(seed),
            "random_generator": "numpy.random.PCG64",
            "half_vs_full_convergence": convergence,
            "base_rejection_sampling": base_rejection,
        },
        "physical_domain_checks": physical_checks,
        "units": nominal["units"],
    }
    return {
        "nominal": nominal,
        "samples": system_samples,
        "uncertainty_receipt": receipt,
    }


def _self_test() -> dict[str, Any]:
    points = np.asarray(
        [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [2000.0, 500.0, 0.0]],
        dtype=float,
    )
    clamps = np.column_stack(
        (np.linspace(0.0, 2000.0, 18), np.linspace(0.0, 500.0, 18), np.zeros(18))
    )
    result = propagate_harness(
        points,
        analytic_length_mm=2200.0,
        coil_center_mm=[100.0, 80.0, 40.0],
        clamp_positions_mm=clamps,
        n=256,
        seed=11,
    )
    assert result["samples"].shape == (256, 10)
    assert result["nominal"]["mass_kg"] > 0.0
    assert np.all(np.linalg.eigvalsh(result["nominal"]["inertia_about_own_cg_S_kg_m2"]) >= -1e-12)
    harness_domain = result["uncertainty_receipt"]["physical_domain_checks"]
    assert harness_domain["positive_definite_pass_count"] == 256
    assert harness_domain["triangle_inequality_pass_count"] == 256
    base = {
        "mass": {"value_kg": 31.0, "standard_uncertainty_kg": 0.5},
        "center_of_mass": {
            "xyz_m": [0.05, -0.02, 0.01],
            "standard_uncertainty_xyz_m": [0.002, 0.002, 0.002],
        },
        "inertia": {
            "components_kg_m2": {
                "Ixx": 0.8,
                "Iyy": 1.0,
                "Izz": 1.2,
                "Ixy": 0.01,
                "Ixz": 0.02,
                "Iyz": -0.01,
            },
            "standard_uncertainty_components_kg_m2": {
                "Ixx": 0.03,
                "Iyy": 0.03,
                "Izz": 0.03,
                "Ixy": 0.01,
                "Ixz": 0.01,
                "Iyz": 0.01,
            },
        },
    }
    system = propagate_system(base, result["nominal"], result["samples"], seed=12)
    assert system["samples"].shape == (256, 13)
    assert system["nominal"]["mass_kg"] > base["mass"]["value_kg"]
    system_domain = system["uncertainty_receipt"]["physical_domain_checks"]
    assert system_domain["positive_definite_pass_count"] == 256
    assert system_domain["triangle_inequality_pass_count"] == 256
    base_rejection = system["uncertainty_receipt"]["base_rejection_sampling"]
    assert base_rejection["accepted"] == 256
    assert base_rejection["total_draws"] >= 256
    return {
        "harness_samples": list(result["samples"].shape),
        "system_samples": list(system["samples"].shape),
        "nominal_harness_mass_kg": result["nominal"]["mass_kg"],
        "harness_receipt_outputs": len(result["uncertainty_receipt"]["outputs"]),
        "system_receipt_outputs": len(system["uncertainty_receipt"]["outputs"]),
        "harness_physical_domain_rate": harness_domain["positive_definite_pass_rate"],
        "system_physical_domain_rate": system_domain["positive_definite_pass_rate"],
        "base_rejection_acceptance_rate": base_rejection["acceptance_rate"],
        "status": "PASS",
    }


if __name__ == "__main__":
    import json

    print(json.dumps(_self_test(), indent=2, ensure_ascii=False))
