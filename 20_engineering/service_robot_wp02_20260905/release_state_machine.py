"""Pure offline WP02 release sequence. No hardware IO, motors or sensors are driven.

All scenario feedback below is SYNTHETIC_VIRTUAL_INPUT, not validated hardware.
The result named virtual_arm_first_motion_allowed is a logical property only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = (
    "PARKED_HELD", "RELEASE_REQUESTED", "LATCH_OPEN_CONFIRMED",
    "CONTACTS_RETRACTED_CONFIRMED", "CARRIER_CLEAR_CONFIRMED",
    "ARM_FIRST_MOTION_ALLOWED",
)
FAULT = "FAULT_LATCHED"
EPS = 1e-9  # Floating arithmetic only; not a physical tolerance or margin.
PAIRS = (
    ("latch_open", "latch_closed", "pin_withdrawal_mm", "pin"),
    ("upper_retracted", "upper_contact", "upper_lift_mm", "upper"),
    ("lower_retracted", "lower_contact", "lower_drop_mm", "lower"),
    ("carrier_clear", "carrier_held", "carrier_Y_mm", "carrier"),
)


class ReleaseMachine:
    def __init__(self, parameters: dict):
        g = parameters["gse"]
        self.strokes = {"pin": float(g["latch_pin_withdrawal_mm"]),
                        "upper": float(g["upper_pad_release_lift_mm"]),
                        "lower": float(g["shoe_release_drop_mm"]),
                        "carrier": float(g["Y_slide_stroke_mm"])}
        self.setup_limits = tuple(g["shoe_adjustment_z_mm"])
        self.state = STATES[0]
        self.manual_reset_valid = False
        self.last_reason = "MANUAL_RESET_AND_INDEPENDENT_SUPPORT_REQUIRED"

    def _fault(self, reason):
        self.state = FAULT
        self.manual_reset_valid = False
        self.last_reason = reason

    def _input_problem(self, s):
        if s.get("input_class") != "SYNTHETIC_VIRTUAL_INPUT":
            return "NON_VIRTUAL_INPUT_REJECTED_NO_HARDWARE_ADAPTER"
        for key, expected in (("power_ok", True), ("timed_out", False),
                              ("external_fault", False), ("independent_support_ready", True),
                              ("unloading_ready", True)):
            if type(s.get(key)) is not bool:
                return "UNKNOWN_OR_INVALID_" + key.upper()
            if s[key] != expected:
                return "UNSAFE_" + key.upper()
        stations = s.get("stations")
        if not isinstance(stations, dict) or set(stations) != {"A", "B"}:
            return "TWO_STATION_SIGNAL_SETS_REQUIRED"
        for name, st in stations.items():
            if st.get("signal_set_valid") is not True:
                return name + "_SIGNAL_SET_INVALID_OR_UNKNOWN"
            for released, held, coordinate, stroke in PAIRS:
                if type(st.get(released)) is not bool or type(st.get(held)) is not bool:
                    return name + "_UNKNOWN_" + released.upper()
                if st[released] and st[held]:
                    return name + "_CONTRADICTORY_" + released.upper()
                x = st.get(coordinate)
                if type(x) not in (int, float) or not math.isfinite(x) or x < -EPS:
                    return name + "_INVALID_POSITION_" + coordinate.upper()
                if st[released] and x + EPS < self.strokes[stroke]:
                    return name + "_CONFIRMATION_BEFORE_REQUIRED_STROKE_" + stroke.upper()
                if st[held] and x > EPS:
                    return name + "_HELD_SIGNAL_DISAGREES_WITH_POSITION_" + stroke.upper()
            x = st.get("shoe_setup_adjustment_z_mm")
            if type(x) not in (int, float) or not math.isfinite(x):
                return name + "_UNKNOWN_SHOE_SETUP"
            if not self.setup_limits[0] <= x <= self.setup_limits[1]:
                return name + "_SHOE_SETUP_OUT_OF_CANDIDATE_RANGE"
        return None

    @staticmethod
    def _all(s, key):
        return all(st[key] is True for st in s["stations"].values())

    def _latches(self, s):
        return self._all(s, "latch_open")

    def _contacts(self, s):
        return self._all(s, "upper_retracted") and self._all(s, "lower_retracted")

    def _carriers(self, s):
        return self._all(s, "carrier_clear")

    def _fully_held(self, s):
        return all(self._all(s, pair[1]) for pair in PAIRS)

    def process(self, command: str, snapshot: dict):
        s = copy.deepcopy(snapshot)
        previous = self.state
        problem = self._input_problem(s)
        if problem:
            self._fault(problem)
        elif command == "manual_reset":
            # Manual acknowledgement is independent of a software reset request.
            if s.get("operator_manual_reset_ack") is not True:
                self._fault("RESET_REQUIRES_HUMAN_ACK")
            elif not self._fully_held(s):
                self._fault("RESET_REQUIRES_MANUALLY_RESTORED_HELD_GEOMETRY")
            else:
                self.state = STATES[0]
                self.manual_reset_valid = True
                self.last_reason = "MANUAL_RESET_ACCEPTED_NO_ARM_COMMAND_NEW_RELEASE_REQUEST_REQUIRED"
        elif self.state == FAULT:
            self.last_reason = "FAULT_PERSISTS_UNTIL_SUPPORTED_MANUAL_RESET"
        elif command not in {"observe", "request_release", "request_first_motion"}:
            self._fault("UNKNOWN_COMMAND")
        elif not self.manual_reset_valid:
            self._fault("FRESH_VALID_MANUAL_RESET_REQUIRED")
        else:
            stage = STATES.index(self.state)
            contact_moved = any(st["upper_lift_mm"] > EPS or st["lower_drop_mm"] > EPS
                                for st in s["stations"].values())
            carrier_moved = any(st["carrier_Y_mm"] > EPS for st in s["stations"].values())
            pins_moved = any(st["pin_withdrawal_mm"] > EPS for st in s["stations"].values())
            if stage == 0 and pins_moved:
                self._fault("PIN_MOTION_BEFORE_RELEASE_REQUEST")
            elif stage < 2 and contact_moved:
                self._fault("CONTACT_MOTION_BEFORE_BOTH_LATCHES_CONFIRMED")
            elif stage < 3 and carrier_moved:
                self._fault("Y_MOTION_BEFORE_BOTH_CONTACT_SETS_CONFIRMED")
            elif stage >= 2 and not self._latches(s):
                self._fault("LATCH_CONFIRMATION_LOST")
            elif stage >= 3 and not self._contacts(s):
                self._fault("CONTACT_CLEAR_CONFIRMATION_LOST")
            elif stage >= 4 and not self._carriers(s):
                self._fault("CARRIER_CLEAR_CONFIRMATION_LOST")
            elif command == "request_first_motion" and self.state != STATES[4]:
                self._fault("FIRST_MOTION_REQUEST_BEFORE_SEQUENCE_COMPLETE")
            elif self.state == STATES[0] and command == "request_release":
                if self._fully_held(s):
                    self.state = STATES[1]
                    self.last_reason = "WITHDRAW_BOTH_CAPTURED_LOCK_PINS_MANUALLY"
                else:
                    self._fault("RELEASE_REQUEST_REQUIRES_HELD_START")
            elif self.state == STATES[1] and self._latches(s):
                self.state = STATES[2]
                self.last_reason = "BOTH_LATCHES_OPEN_CONTACT_RETRACTION_MAY_BEGIN"
            elif self.state == STATES[2] and self._contacts(s):
                self.state = STATES[3]
                self.last_reason = "BOTH_UPPER_AND_LOWER_CONTACTS_RETRACTED_Y_MOTION_MAY_BEGIN"
            elif self.state == STATES[3] and self._carriers(s):
                self.state = STATES[4]
                self.last_reason = "BOTH_CARRIERS_CLEAR_WAIT_EXPLICIT_FIRST_MOTION_REQUEST"
            elif self.state == STATES[4] and command == "request_first_motion":
                self.state = STATES[5]
                self.last_reason = "VIRTUAL_LOGIC_PERMISSION_ONLY_NO_ACTUATION"
            else:
                self.last_reason = "WAIT_FOR_REQUIRED_COMPLETE_CONFIRMATIONS"
        y_allow = (self.state in STATES[3:] and self.manual_reset_valid and
                   self._latches(s) and self._contacts(s)) if self.state != FAULT else False
        arm_allow = self.state == STATES[5] and self.manual_reset_valid
        return {"previous_state": previous, "state": self.state, "command": command,
                "reason": self.last_reason, "manual_reset_valid": self.manual_reset_valid,
                "virtual_manual_Y_motion_permitted": bool(y_allow),
                "virtual_arm_first_motion_allowed": bool(arm_allow),
                "hardware_actuation_allowed": False,
                "input_class": s.get("input_class"), "snapshot": s}


def synthetic_snapshot(p, phase=0):
    g = p["gse"]
    s = {"input_class": "SYNTHETIC_VIRTUAL_INPUT", "power_ok": True,
         "timed_out": False, "external_fault": False,
         "independent_support_ready": True, "unloading_ready": True,
         "operator_manual_reset_ack": True, "stations": {}}
    for name in ("A", "B"):
        st = {"signal_set_valid": True, "shoe_setup_adjustment_z_mm": 0.0}
        for released, held, coordinate, key in PAIRS:
            active = phase >= {"pin": 1, "upper": 2, "lower": 2, "carrier": 3}[key]
            stroke = {"pin": g["latch_pin_withdrawal_mm"],
                      "upper": g["upper_pad_release_lift_mm"],
                      "lower": g["shoe_release_drop_mm"],
                      "carrier": g["Y_slide_stroke_mm"]}[key]
            st.update({released: active, held: not active, coordinate: stroke if active else 0.0})
        s["stations"][name] = st
    return s


def run_scenarios(p):
    held, pins, contact, clear = [synthetic_snapshot(p, n) for n in range(4)]
    prefix = [("manual_reset", held), ("request_release", held)]
    to_pins = prefix + [("observe", pins)]
    to_contact = to_pins + [("observe", contact)]
    to_clear = to_contact + [("observe", clear)]
    normal = to_clear + [("request_first_motion", clear)]
    cases = []

    def add(name, events, expected_state, expected_arm=False, expected_y=None, invariant=None):
        machine = ReleaseMachine(p)
        trace = [machine.process(cmd, copy.deepcopy(s)) for cmd, s in events]
        final = trace[-1]
        checks = {"expected_final_state": final["state"] == expected_state,
                  "expected_final_virtual_arm_permission": final["virtual_arm_first_motion_allowed"] == expected_arm,
                  "hardware_always_disabled": not any(t["hardware_actuation_allowed"] for t in trace)}
        if not expected_arm and name != "permission_revoked_after_unloading_loss":
            checks["no_transient_arm_permission"] = not any(t["virtual_arm_first_motion_allowed"] for t in trace)
        if expected_y is not None:
            checks["expected_final_Y_permission"] = final["virtual_manual_Y_motion_permitted"] == expected_y
        if invariant is not None:
            checks["scenario_specific_invariant"] = bool(invariant(trace))
        cases.append({"name": name, "input_class": "SYNTHETIC_VIRTUAL_INPUT",
                      "expected_final_state": expected_state, "checks": checks,
                      "passed": all(checks.values()), "trace": trace})

    add("nominal_ordered_supported_sequence", normal, STATES[5], True, True,
        lambda t: [v["state"] for v in t] == list(STATES) and not any(v["virtual_arm_first_motion_allowed"] for v in t[:-1]))
    unknown = copy.deepcopy(pins); unknown["stations"]["B"]["latch_open"] = None
    add("unknown_latch_feedback", prefix + [("observe", unknown)], FAULT, expected_y=False)
    add("release_without_valid_manual_reset", [("request_release", held)], FAULT)
    missing_support = copy.deepcopy(held); missing_support["independent_support_ready"] = False
    add("reset_without_independent_support", [("manual_reset", missing_support)], FAULT)
    missing_unloading = copy.deepcopy(held); missing_unloading["unloading_ready"] = False
    add("reset_without_unloading_ready", [("manual_reset", missing_unloading)], FAULT)
    partial_pin = copy.deepcopy(pins); partial_pin["stations"]["B"] = copy.deepcopy(held["stations"]["B"])
    add("one_lock_pin_only", prefix + [("observe", partial_pin)], STATES[1], expected_y=False)
    partial_upper = copy.deepcopy(contact)
    partial_upper["stations"]["B"].update(upper_retracted=False, upper_contact=True, upper_lift_mm=0)
    add("one_upper_contact_only", to_pins + [("observe", partial_upper)], STATES[2], expected_y=False)
    partial_lower = copy.deepcopy(contact)
    partial_lower["stations"]["B"].update(lower_retracted=False, lower_contact=True, lower_drop_mm=0)
    add("one_lower_contact_only", to_pins + [("observe", partial_lower)], STATES[2], expected_y=False)
    partial_carrier = copy.deepcopy(clear)
    partial_carrier["stations"]["B"].update(carrier_clear=False, carrier_held=True, carrier_Y_mm=0)
    add("one_carrier_clear_only", to_contact + [("observe", partial_carrier)], STATES[3])
    contradiction = copy.deepcopy(pins); contradiction["stations"]["A"]["latch_closed"] = True
    add("contradictory_latch_signals", prefix + [("observe", contradiction)], FAULT)
    timeout = copy.deepcopy(pins); timeout["timed_out"] = True
    add("timeout_latches_fault", prefix + [("observe", timeout)], FAULT)
    powerloss = copy.deepcopy(clear); powerloss["power_ok"] = False
    add("power_loss_before_arm_permission", to_clear + [("request_first_motion", powerloss)], FAULT)
    invalid_set = copy.deepcopy(clear); invalid_set["stations"]["B"]["signal_set_valid"] = False
    add("second_signal_set_invalid", to_clear + [("request_first_motion", invalid_set)], FAULT)
    add("Y_motion_before_contact_confirmation", to_pins + [("observe", clear)], FAULT)
    add("contact_motion_before_pin_confirmation", prefix + [("observe", contact)], FAULT)
    wrong_drop = copy.deepcopy(contact)
    wrong_drop["stations"]["A"].update(shoe_setup_adjustment_z_mm=-8, lower_drop_mm=0)
    add("setup_adjustment_not_release_drop", to_pins + [("observe", wrong_drop)], FAULT)
    bad_reset = copy.deepcopy(held); bad_reset["operator_manual_reset_ack"] = False
    fault_start = prefix + [("observe", timeout)]
    add("fault_reset_requires_human", fault_start + [("manual_reset", bad_reset)], FAULT)
    add("fault_reset_requires_support", fault_start + [("manual_reset", missing_support)], FAULT)
    add("manual_fault_reset_never_commands_arm", fault_start + [("manual_reset", held), ("observe", held)], STATES[0],
        invariant=lambda t: t[-2]["manual_reset_valid"] and not t[-2]["virtual_arm_first_motion_allowed"])
    add("fault_cannot_clear_by_observation", fault_start + [("observe", held)], FAULT)
    loss_after_allow = copy.deepcopy(clear); loss_after_allow["unloading_ready"] = None
    add("permission_revoked_after_unloading_loss", normal + [("observe", loss_after_allow)], FAULT,
        invariant=lambda t: t[-2]["virtual_arm_first_motion_allowed"] and not t[-1]["virtual_arm_first_motion_allowed"])
    add("carrier_clear_not_automatic_arm_permission", to_clear, STATES[4], expected_y=True)
    add("first_motion_request_cannot_skip_sequence", to_pins + [("request_first_motion", pins)], FAULT)
    partial_stroke = copy.deepcopy(contact)
    partial_stroke["stations"]["B"]["lower_drop_mm"] = p["gse"]["shoe_release_drop_mm"] - 1
    add("limit_flag_before_full_lower_drop", to_pins + [("observe", partial_stroke)], FAULT)
    # The 18 mm initial candidate was disproved by the CAD first-Y-motion check.
    # Preserve that counterexample even when the production candidate is updated.
    rejected_initial_pin = copy.deepcopy(pins)
    for station in rejected_initial_pin["stations"].values():
        station["pin_withdrawal_mm"] = 18.0
    add("rejected_initial_18mm_pin_withdrawal", prefix + [("observe", rejected_initial_pin)],
        FAULT, expected_y=False,
        invariant=lambda t: p["gse"]["latch_pin_withdrawal_mm"] > 18.0 and
        t[-1]["reason"].endswith("CONFIRMATION_BEFORE_REQUIRED_STROKE_PIN"))
    return cases


def main():
    param_path = HERE / "design_parameters.json"
    raw = param_path.read_bytes()
    p = json.loads(raw)
    cases = run_scenarios(p)
    result = {"schema": "WP02_OFFLINE_RELEASE_STATE_MACHINE_V1",
              "configuration": p["configuration_id"], "physical_state": p["physical_state"],
              "source_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "parameters_sha256": hashlib.sha256(raw).hexdigest(),
              "input_class": "SYNTHETIC_VIRTUAL_INPUT",
              "hardware_IO_present": False, "hardware_actuation_executed": False,
              "sensors_selected_or_validated": False, "actuator_selected": False,
              "manual_Y_drive": {"geometry_only": True, "diameter_mm": p["gse"]["lead_screw_d_mm"],
                                 "pitch_mm": p["gse"]["lead_screw_pitch_mm"],
                                 "lock_load_path_independent_of_screw_holding_torque": True},
              "candidate_strokes_mm": ReleaseMachine(p).strokes,
              "rejected_initial_pin_candidate": {
                  "withdrawal_mm": 18.0,
                  "reason": "CAD counterexample: carrier intersects pin during first Y motion",
                  "evidence": "results/KEY_GEOMETRY_CHECK_R1_FINDINGS.json",
                  "regression_case": "rejected_initial_18mm_pin_withdrawal",
                  "physical_test_executed": False},
              "lower_shoe_setup_z_mm": p["gse"]["shoe_adjustment_z_mm"],
              "position_epsilon_mm": EPS, "epsilon_is_hardware_tolerance": False,
              "state_sequence": list(STATES), "fault_state": FAULT,
              "scenario_count": len(cases), "passed_count": sum(c["passed"] for c in cases),
              "failed_names": [c["name"] for c in cases if not c["passed"]],
              "status": "OFFLINE_LOGIC_SCENARIOS_PASS" if all(c["passed"] for c in cases) else "OFFLINE_LOGIC_SCENARIOS_FAIL",
              "scope": "Pure virtual logic and sequence tests only. No hardware release, valid sensor signal, strength, full-path clearance or flight claim.",
              "cases": cases}
    out = HERE / "results" / "RELEASE_STATE_MACHINE.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "scenario_count", "passed_count", "failed_names")}, ensure_ascii=False))
    return 0 if not result["failed_names"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
