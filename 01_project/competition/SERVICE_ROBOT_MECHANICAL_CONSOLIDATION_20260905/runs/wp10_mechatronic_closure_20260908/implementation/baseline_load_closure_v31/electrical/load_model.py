"""V31 conditional electrical power accounting, SI units, no hardware I/O.

These functions calculate supplied scenarios; they do not predict a B601 task.
Unknown inputs remain None. Shaft torque and speed must be co-located at the
same output shaft and time/window. Phase RMS current is NOT DC bus current.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

LABEL = "DESIGN_SENSITIVITY_NOT_MOTOR_PREDICTION"


def _finite(name: str, value: float | None, *, nonnegative=False):
    if value is None:
        return None
    if isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric or None")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return float(value)


def phase_energy_Wh(power_W: float | None, duration_s: float | None):
    """Constant/phase-mean signed power; no fabricated energy for unknown input."""
    power = _finite("power_W", power_W)
    duration = _finite("duration_s", duration_s, nonnegative=True)
    return None if power is None or duration is None else power * duration / 3600.0


def phase_copper_loss_W(resistance_phase_ohm, phase_currents_rms_A):
    """Sum of R_phase*I_phase_rms^2 over three phases; R at winding temperature.

    Supplying equal three-phase RMS currents is a balanced-wave assumption.
    At zero shaft speed use measured per-phase values, not an assumed rotating
    sinusoid. Torque-current telemetry is not accepted as a substitute here.
    """
    resistance = _finite("resistance_phase_ohm", resistance_phase_ohm, nonnegative=True)
    if phase_currents_rms_A is None:
        return None
    if len(phase_currents_rms_A) != 3:
        raise ValueError("three phase RMS currents required")
    currents = [_finite("phase_current_rms_A", x, nonnegative=True) for x in phase_currents_rms_A]
    if resistance is None or any(x is None for x in currents):
        return None
    return resistance * sum(x*x for x in currents)


def evaluate_axis_power(*, torque_output_Nm=None, omega_output_rad_s=None,
                        phase_resistance_ohm=None, phase_currents_rms_A=None,
                        gearbox_loss_W=None, core_and_mechanical_loss_W=None,
                        driver_loss_W=None, electronics_standby_W=None,
                        internal_energy_rate_W=None, bus_voltage_V=None):
    """Conservation-based demanded bus power, not proof that drive can supply it.

    P_bus = tau_out*omega_out + P_gear + P_copper + P_core/mechanical
            + P_driver + P_electronics + dE_internal/dt.
    Explicit zero is allowed only as a declared modeling assumption. No loss
    efficiency factor is applied again; that would double-count losses.
    Negative demand requires a qualified energy sink. It is NOT battery credit.
    """
    torque = _finite("torque_output_Nm", torque_output_Nm)
    omega = _finite("omega_output_rad_s", omega_output_rad_s)
    losses = {
        "gearbox_loss_W": _finite("gearbox_loss_W", gearbox_loss_W, nonnegative=True),
        "core_and_mechanical_loss_W": _finite("core_and_mechanical_loss_W", core_and_mechanical_loss_W, nonnegative=True),
        "driver_loss_W": _finite("driver_loss_W", driver_loss_W, nonnegative=True),
        "electronics_standby_W": _finite("electronics_standby_W", electronics_standby_W, nonnegative=True),
    }
    voltage = _finite("bus_voltage_V", bus_voltage_V)
    if voltage is not None and voltage <= 0:
        raise ValueError("bus_voltage_V must be positive")
    terms = {"shaft_mechanical_power_W": None if torque is None or omega is None else torque*omega,
             "phase_copper_loss_W": phase_copper_loss_W(phase_resistance_ohm, phase_currents_rms_A),
             **losses,
             "internal_energy_rate_W": _finite("internal_energy_rate_W", internal_energy_rate_W)}
    missing = [name for name, value in terms.items() if value is None]
    bus_power = None if missing else sum(terms.values())
    return {"label": LABEL, "terms": terms, "missing_inputs": missing,
            "status": "UNKNOWN" if missing else "CONDITIONAL_POWER_BALANCE_ONLY",
            "demanded_bus_power_W": bus_power,
            "demanded_bus_current_A": None if bus_power is None or voltage is None else bus_power/voltage,
            "regenerative_power_available_W": None if bus_power is None else max(-bus_power, 0.0),
            "battery_recovery_credit_Wh": None,
            "actuator_capacity_verified": False, "regeneration_path_verified": False}


def complete_sensitivity_scenario(motion_bus_power_W, *, hold_bus_power_W,
                                  standby_bus_power_W, gripper_bus_power_W):
    """Require hold, standby, gripper explicitly, without linking them to motion."""
    vals = {"motion_bus_power_W": motion_bus_power_W, "hold_bus_power_W": hold_bus_power_W,
            "standby_bus_power_W": standby_bus_power_W, "gripper_bus_power_W": gripper_bus_power_W}
    vals = {k: _finite(k, v, nonnegative=True) for k, v in vals.items()}
    return {"label": LABEL, **vals, "measured": False, "hardware_capacity_bound": False,
            "complete": all(v is not None for v in vals.values())}


def sampled_bus_metrics(samples: Sequence[dict]):
    """Integrate signed measured bus V*I with monotonic time and no missing data.

    Positive current flows source->arm. Report consumed and returned energy
    separately. Piecewise linear power zero-crossings are split, not clipped
    after netting. Returned energy is at measurement plane, not recovered Wh.
    I_RMS is trapezoidal integration of sampled I^2 over the same time window.
    """
    if len(samples) < 2:
        raise ValueError("at least two samples required")
    rows=[]
    for s in samples:
        vals=[_finite(k, s.get(k)) for k in ("time_s", "bus_voltage_V", "bus_current_A")]
        if any(x is None for x in vals):
            return {"status":"UNKNOWN_MISSING_SAMPLES", "consumed_Wh":None, "returned_Wh":None,
                    "net_Wh":None, "bus_current_rms_A":None}
        t,v,i=vals
        if v <= 0:
            raise ValueError("positive bus voltage required")
        rows.append((t,v,i,v*i))
    consumed=returned=integral_i2=integral_i=0.0
    for a,b in zip(rows, rows[1:]):
        dt=b[0]-a[0]
        if dt <= 0:
            raise ValueError("time must be strictly increasing")
        pa,pb=a[3],b[3]
        if pa*pb < 0:
            t0=dt*abs(pa)/(abs(pa)+abs(pb))
            pieces=[(pa*t0/2), (pb*(dt-t0)/2)]
        else:
            pieces=[(pa+pb)*dt/2]
        consumed += sum(max(x,0) for x in pieces)
        returned += sum(max(-x,0) for x in pieces)
        integral_i2 += (a[2]**2+b[2]**2)*dt/2
        integral_i += (a[2]+b[2])*dt/2
    duration=rows[-1][0]-rows[0][0]
    return {"status":"SAMPLED_BUS_ACCOUNTING_ONLY", "duration_s":duration,
            "consumed_Wh":consumed/3600, "returned_Wh":returned/3600,
            "net_Wh":(consumed-returned)/3600,
            "bus_current_mean_A":integral_i/duration,
            "bus_current_rms_A":math.sqrt(integral_i2/duration),
            "bus_current_peak_positive_A":max(max(x[2] for x in rows),0),
            "bus_current_peak_negative_A":min(min(x[2] for x in rows),0),
            "power_peak_positive_W":max(max(x[3] for x in rows),0),
            "power_peak_negative_W":min(min(x[3] for x in rows),0),
            "battery_recovery_credit_Wh":None,
            "sampling_bandwidth_qualified":False}
