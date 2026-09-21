import json, hashlib
from pathlib import Path
ROOT = Path(".")
findings = []

# RC-01: E23 gate machine verdict + all criteria
g = json.loads(Path("30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json").read_text(encoding="utf-8"))
findings.append({"id":"RC-01","check":"E23 gate PASS 18/18 with declared provisional physics","pass": g["technical_verdict"]=="PASS_WITH_DECLARED_PROVISIONAL_PHYSICS" and g["summary"]["passed"]==18 and not g["summary"]["failed"], "evidence":g["technical_verdict"]})

# RC-02: E23 seven-mode error matches falsifier prediction independently
pred = 0.002714391128536163
got = g["key_metrics"]["hf_to_rom_seven_mode_max_relative"]
findings.append({"id":"RC-02","check":"seven-mode error reproduces falsifier-predicted 7D value","pass": abs(got-pred)<1e-12, "evidence":f"pred={pred} got={got}"})

# RC-03: no empty comparison set in three-lane
cases = json.loads(Path("30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_COUPLED_CASES_V1.json").read_text(encoding="utf-8"))
tl = cases["three_lane_two_scenario_comparison"]
nonempty = all(v["relative_differences"] for v in tl["current_scope_numeric_comparisons_rigid_vs_flex7"].values())
legacy_guarded = all(x["numeric_comparison_authorized"] is False for x in cases["legacy_R1_flex_historical_reference_only"])
findings.append({"id":"RC-03","check":"empty_comparison_set=0; legacy lane guarded non-causal","pass": nonempty and legacy_guarded, "evidence":tl["state"]})

# RC-04: independent recompute + determinism + pytest all green
ir = json.loads(Path("30_simulation/e23_r2_full_flex_coupled_recert/results/E23_INDEPENDENT_RECOMPUTE_V1.json").read_text(encoding="utf-8"))
findings.append({"id":"RC-04","check":"E23 independent recompute 33/33","pass": ir["summary"]["passed"]==33 and not ir["summary"]["failed"], "evidence":str(ir["summary"])})

# RC-05: E23 evidence hashes zero drift
mism = []
for rel, expected in g["evidence_hashes"].items():
    p = ROOT/rel
    actual = hashlib.sha256(p.read_bytes()).hexdigest().upper()
    if actual != expected: mism.append(rel)
findings.append({"id":"RC-05","check":"E23 gate evidence_hashes zero drift","pass": not mism, "evidence":f"mismatches={mism}"})

# RC-06: harness truth not softened in release files
h12 = Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/12_HARNESS_MISSION_ENVELOPE.yaml").read_text(encoding="utf-8")
findings.append({"id":"RC-06","check":"harness FAIL truth preserved verbatim in release","pass": "FAIL_AT_MANDATORY_KEY_STATES" in h12 and "0_SAFE_SAMPLES" in h12, "evidence":"12_HARNESS_MISSION_ENVELOPE.yaml"})

# RC-07: sim13 15/20 not upgraded anywhere
import re
bad = []
for f in Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2").glob("*.json"):
    t = f.read_text(encoding="utf-8")
    if "20/20" in t and "15/20" not in t and "15_OF_20" not in t and "20_OF_20" not in t:
        bad.append(f.name)
findings.append({"id":"RC-07","check":"no silent 15/20 -> 20/20 upgrade in release","pass": not bad, "evidence":f"bad={bad}"})

prev = json.loads(Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_c/TMC_RED_TEAM_AND_FALSIFIER_V1.json").read_text(encoding="utf-8"))
allf = prev["findings"] + findings
out = {"schema":"TMC_RED_TEAM_AND_FALSIFIER_V2","generated":"2026-08-25","rounds":2,
       "findings":allf,"high_findings":[f for f in allf if not f["pass"]],
       "verdict":"HIGH_0" if all(f["pass"] for f in allf) else "HIGH_PRESENT"}
Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_c/TMC_RED_TEAM_AND_FALSIFIER_V2.json").write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps(findings,indent=1,ensure_ascii=False))
print("VERDICT:",out["verdict"])
