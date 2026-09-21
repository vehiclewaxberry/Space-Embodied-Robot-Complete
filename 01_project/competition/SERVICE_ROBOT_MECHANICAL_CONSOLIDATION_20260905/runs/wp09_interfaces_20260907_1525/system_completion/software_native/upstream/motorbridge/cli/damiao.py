from __future__ import annotations

import argparse
from typing import Any

from .common import _open_controller, _parse_id, _parse_rids, _vendor_defaults

DAMIAO_MODEL_LIMITS: dict[str, tuple[float, float, float]] = {
    "3507": (12.566, 50.0, 5.0),
    "4310": (12.5, 30.0, 10.0),
    "4310P": (12.5, 50.0, 10.0),
    "4340": (12.5, 10.0, 28.0),
    "4340P": (12.5, 10.0, 28.0),
    "4340_v20": (12.5, 20.0, 28.0),
    "6006": (12.5, 45.0, 20.0),
    "8006": (12.5, 45.0, 40.0),
    "8009": (12.5, 45.0, 54.0),
    "10010L": (12.5, 25.0, 200.0),
    "10010": (12.5, 20.0, 200.0),
    "H3510": (12.5, 280.0, 1.0),
    "G6215": (12.5, 45.0, 10.0),
    "H6220": (12.5, 45.0, 10.0),
    "JH11": (12.5, 10.0, 12.0),
    "6248P": (12.566, 20.0, 120.0),
}

def _match_damiao_models_by_limits(pmax: float, vmax: float, tmax: float, tol: float) -> list[str]:
    return [
        model
        for model, (mp, mv, mt) in DAMIAO_MODEL_LIMITS.items()
        if abs(mp - pmax) <= tol and abs(mv - vmax) <= tol and abs(mt - tmax) <= tol
    ]

def _suggest_damiao_models_by_limits(pmax: float, vmax: float, tmax: float, top_n: int = 3) -> list[str]:
    scored = sorted(
        (
            ((mp - pmax) ** 2 + (mv - vmax) ** 2 + (mt - tmax) ** 2, model)
            for model, (mp, mv, mt) in DAMIAO_MODEL_LIMITS.items()
        )
    )
    return [model for _, model in scored[:top_n]]

def _verify_damiao_model(motor: Any, model: str, timeout_ms: int, tol: float) -> None:
    expected = DAMIAO_MODEL_LIMITS.get(model)
    if expected is None:
        raise ValueError(f"unknown Damiao model in catalog: {model}")
    pmax = motor.get_register_f32(21, timeout_ms)
    vmax = motor.get_register_f32(22, timeout_ms)
    tmax = motor.get_register_f32(23, timeout_ms)
    matched = _match_damiao_models_by_limits(pmax, vmax, tmax, tol)
    if model in matched:
        print(
            f"[ok] model handshake passed: --model {model} "
            f"matches PMAX/VMAX/TMAX=({pmax:.3f}, {vmax:.3f}, {tmax:.3f})"
        )
        return
    suggested = ", ".join(_suggest_damiao_models_by_limits(pmax, vmax, tmax)) or "none"
    raise RuntimeError(
        f"model handshake mismatch: --model {model} expects "
        f"({expected[0]:.3f}, {expected[1]:.3f}, {expected[2]:.3f}), "
        f"device reports ({pmax:.3f}, {vmax:.3f}, {tmax:.3f}), "
        f"suggested: {suggested}. If intentional, run with --verify-model 0"
    )

def _id_dump_command(args: argparse.Namespace) -> None:
    if args.vendor != "damiao":
        raise ValueError("id-dump currently supports Damiao only")
    args.model, args.feedback_id = _vendor_defaults(args.vendor, args.model, args.feedback_id)
    motor_id = _parse_id(args.motor_id)
    feedback_id = _parse_id(args.feedback_id)
    rids = _parse_rids(args.rids)
    print(
        f"command=id-dump transport={args.transport} channel={args.channel} model={args.model} "
        f"motor_id=0x{motor_id:X} feedback_id=0x{feedback_id:X}"
    )
    ctrl = _open_controller(args, args.vendor)
    motor = ctrl.add_damiao_motor(motor_id, feedback_id, args.model)
    try:
        for rid in rids:
            try:
                value = motor.get_register_u32(rid, args.timeout_ms)
                print(f"rid={rid:>3} (u32) = {value} (0x{value:X})")
            except Exception as e_u32:
                try:
                    value_f = motor.get_register_f32(rid, args.timeout_ms)
                    print(f"rid={rid:>3} (f32) = {value_f:.6f}")
                except Exception:
                    print(f"rid={rid:>3} read failed: {e_u32}")
    finally:
        motor.close()
        ctrl.close_bus()
        ctrl.close()

def _damiao_read_param_command(args: argparse.Namespace) -> None:
    if args.vendor != "damiao":
        raise ValueError("damiao-read-param is only valid for --vendor damiao")
    args.model, args.feedback_id = _vendor_defaults(args.vendor, args.model, args.feedback_id)
    motor_id = _parse_id(args.motor_id)
    feedback_id = _parse_id(args.feedback_id)
    param_id = _parse_id(args.param_id)
    with _open_controller(args, args.vendor) as ctrl:
        motor = ctrl.add_damiao_motor(motor_id, feedback_id, args.model)
        try:
            if args.type == "u32":
                value = motor.damiao_get_param_u32(param_id, args.timeout_ms)
            else:
                value = motor.damiao_get_param_f32(param_id, args.timeout_ms)
            print(
                f"command=damiao-read-param transport={args.transport} channel={args.channel} model={args.model} "
                f"motor_id=0x{motor_id:X} feedback_id=0x{feedback_id:X} "
                f"param_id=0x{param_id:X} type={args.type} value={value}"
            )
        finally:
            motor.close()

def _damiao_write_param_command(args: argparse.Namespace) -> None:
    if args.vendor != "damiao":
        raise ValueError("damiao-write-param is only valid for --vendor damiao")
    args.model, args.feedback_id = _vendor_defaults(args.vendor, args.model, args.feedback_id)
    motor_id = _parse_id(args.motor_id)
    feedback_id = _parse_id(args.feedback_id)
    param_id = _parse_id(args.param_id)
    with _open_controller(args, args.vendor) as ctrl:
        motor = ctrl.add_damiao_motor(motor_id, feedback_id, args.model)
        try:
            if args.type == "u32":
                motor.damiao_write_param_u32(param_id, int(args.value, 0))
                verify = motor.damiao_get_param_u32(param_id, args.timeout_ms) if args.verify else None
            else:
                motor.damiao_write_param_f32(param_id, float(args.value))
                verify = motor.damiao_get_param_f32(param_id, args.timeout_ms) if args.verify else None
            if args.store:
                motor.store_parameters()
            print(
                f"command=damiao-write-param transport={args.transport} channel={args.channel} model={args.model} "
                f"motor_id=0x{motor_id:X} feedback_id=0x{feedback_id:X} "
                f"param_id=0x{param_id:X} type={args.type} value={args.value} "
                f"verify={verify} store={int(bool(args.store))}"
            )
        finally:
            motor.close()
