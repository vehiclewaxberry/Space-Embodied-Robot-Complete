"""Offline mechanical preconditions only; independent of SAFE-00; no hardware."""
import math

STATION_REQUIREMENTS = {
    "WITHDRAW_PINS": {"pin_clear": False, "pin_locked": True, "cap_clear": False, "cap_closed": True, "shoe_clear": False, "shoe_engaged": True, "mast_folded": False, "mast_upright": True},
    "OPEN_CAPS": {"pin_clear": True},
    "LOWER_SHOES": {"pin_clear": True, "cap_clear": True},
    "FOLD_MASTS": {"pin_clear": True, "cap_clear": True, "shoe_clear": True},
    "ARM_FIRST_MOTION": {"pin_clear": True, "cap_clear": True, "shoe_clear": True, "mast_folded": True, "mast_park_locked": True},
    "DEPLOY_WINGS": {"pin_clear": True, "cap_clear": True, "shoe_clear": True, "mast_folded": True, "mast_park_locked": True},
    "SERVICE_ARM_MOTION": {"pin_clear": True, "cap_clear": True, "shoe_clear": True, "mast_folded": True, "mast_park_locked": True},
}
OPPOSED = (("pin_clear", "pin_locked"), ("cap_clear", "cap_closed"),
           ("shoe_clear", "shoe_engaged"), ("mast_folded", "mast_upright"))
GLOBAL_REQUIRED = ("power_healthy", "communications_healthy", "harness_clear", "no_fault")

def finite_number(v):
    return type(v) in (int, float) and math.isfinite(v)

def evaluate_release_step(action, packet, expected_binding, now_s, max_age_s):
    """Caller time and max_age are synthetic policy inputs, not trusted hardware.

    No clock reader, nonce store, runtime safety shield or actual sensor reader
    exists here. Even a logically satisfied snapshot never authorizes hardware.
    """
    reasons = []
    def reject(reason):
        reasons.append(reason)
    if not isinstance(action, str):
        return result(["ACTION_NOT_STRING"])
    if action not in STATION_REQUIREMENTS:
        reject("UNREGISTERED_ACTION")
    if not isinstance(packet, dict):
        return result(["PACKET_NOT_OBJECT"])
    if packet.get("schema") != "WP04_OFFLINE_RELEASE_SNAPSHOT_V1":
        reject("WRONG_SCHEMA")
    if packet.get("action") != action:
        reject("ACTION_BINDING_MISMATCH")
    keys = ("configuration_id", "receipt_sha256", "contract_sha256", "snapshot_id")
    if not isinstance(expected_binding, dict) or set(expected_binding) != set(keys) or any(not isinstance(expected_binding.get(k), str) or not expected_binding[k] for k in keys):
        reject("EXPECTED_BINDING_INCOMPLETE")
    elif packet.get("binding") != expected_binding:
        reject("CONTEXT_BINDING_MISMATCH")
    if not finite_number(now_s) or not finite_number(max_age_s) or max_age_s <= 0:
        reject("INVALID_OFFLINE_TIMING_POLICY")
    stamp = packet.get("timestamp_s")
    if not finite_number(stamp):
        reject("INVALID_TIMESTAMP")
    elif finite_number(now_s) and finite_number(max_age_s):
        if stamp > now_s:
            reject("FUTURE_TIMESTAMP")
        elif now_s - stamp > max_age_s:
            reject("STALE_SNAPSHOT")
    if packet.get("source_class") != "OFFLINE_DESIGN_FIXTURE":
        reject("UNSUPPORTED_SOURCE_CLASS")
    def read_signal(signals, key, desired, scope):
        v = signals.get(key) if isinstance(signals, dict) else None
        if not isinstance(v, dict):
            reject(scope + ":" + key + ":MISSING_SIGNAL")
            return
        if v.get("valid") is not True or v.get("health") != "OK":
            reject(scope + ":" + key + ":INVALID_OR_DISCONNECTED")
        if type(v.get("value")) is not bool:
            reject(scope + ":" + key + ":UNKNOWN_OR_NONBOOLEAN")
        elif v["value"] is not desired:
            reject(scope + ":" + key + ":PRECONDITION_FALSE")
        t = v.get("timestamp_s")
        if not finite_number(t) or not finite_number(now_s) or not finite_number(max_age_s) or t > now_s or now_s - t > max_age_s:
            reject(scope + ":" + key + ":STALE_OR_INVALID_SIGNAL_TIME")
    globals_ = packet.get("global_signals")
    for name in GLOBAL_REQUIRED:
        read_signal(globals_, name, True, "global")
    if action == "WITHDRAW_PINS":
        read_signal(globals_, "residual_load_unloaded", True, "global")
    if action in ("WITHDRAW_PINS", "OPEN_CAPS", "LOWER_SHOES", "FOLD_MASTS", "DEPLOY_WINGS"):
        read_signal(globals_, "arm_stationary", True, "global")
    if action in ("ARM_FIRST_MOTION", "SERVICE_ARM_MOTION"):
        read_signal(globals_, "arm_drive_healthy", True, "global")
    if action == "DEPLOY_WINGS":
        read_signal(globals_, "arm_service_ready", True, "global")
    stations = packet.get("stations")
    if not isinstance(stations, list) or len(stations) != 2 or any(not isinstance(s, dict) for s in stations):
        reject("STATION_SET_INCOMPLETE")
        stations = []
    elif sorted(str(s.get("station_id")) for s in stations) != ["A", "B"]:
        reject("STATION_IDENTITY_MISMATCH")
    for station in stations:
        sid = str(station.get("station_id"))
        signals = station.get("signals")
        for key, desired in STATION_REQUIREMENTS.get(action, {}).items():
            read_signal(signals, key, desired, sid)
        if isinstance(signals, dict):
            for a, b in OPPOSED:
                va, vb = signals.get(a), signals.get(b)
                if isinstance(va, dict) and isinstance(vb, dict) and va.get("value") is True and vb.get("value") is True:
                    reject(sid + ":" + a + ":" + b + ":CONTRADICTORY_CONFIRMATION")
        else:
            reject(sid + ":SIGNALS_NOT_OBJECT")
    wings = packet.get("wings")
    if action in ("ARM_FIRST_MOTION", "DEPLOY_WINGS", "SERVICE_ARM_MOTION"):
        if not isinstance(wings, list) or len(wings) != 2 or any(not isinstance(w, dict) for w in wings) or sorted(str(w.get("wing_id")) for w in wings) != ["+Y", "-Y"]:
            reject("WING_IDENTITY_OR_COVERAGE_MISMATCH")
        else:
            key = "deployed_and_locked" if action == "SERVICE_ARM_MOTION" else "stowed_and_held"
            for wing in wings:
                read_signal(wing.get("signals"), key, True, str(wing["wing_id"]))
                signals=wing.get("signals")
                if isinstance(signals,dict):
                    a,b=signals.get("stowed_and_held"),signals.get("deployed_and_locked")
                    if isinstance(a,dict) and isinstance(b,dict) and a.get("value") is True and b.get("value") is True:
                        reject(str(wing["wing_id"])+":CONTRADICTORY_WING_STATE")
    return result(reasons)

def result(reasons):
    return dict(logical_status="BLOCKED" if reasons else "LOGICAL_PRECONDITIONS_SATISFIED_OFFLINE",
                reasons=reasons, hardware_command_authorized=False, hardware_command_issued=False,
                actual_sensor_state_verified=False, legacy_SAFE00_credit_inherited=False,
                scientific_or_control_gate=False)
