"""Run five isolated independent recomputations and freeze determinism evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

for _thread_env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_env] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
E22_DIR = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
RESULTS = E22_DIR / "results"
INDEPENDENT_SCRIPT = HERE.parent / "independent_recompute.py"
INDEPENDENT_RESULT = RESULTS / "E23_INDEPENDENT_RECOMPUTE_V1.json"
REPLAY_RESULT = RESULTS / "E23_DETERMINISM_REPLAY_V1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n",
                    encoding="utf-8")


def main() -> int:
    env = os.environ.copy()
    runs = []
    for index in range(1, 6):
        completed = subprocess.run(
            [sys.executable, "-B", str(INDEPENDENT_SCRIPT)],
            cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True,
            check=False,
        )
        if not INDEPENDENT_RESULT.exists():
            raise RuntimeError("INDEPENDENT_RESULT_NOT_GENERATED")
        report = json.loads(INDEPENDENT_RESULT.read_text(encoding="utf-8"))
        dynamic = next(x for x in report["checks"] if x["id"] == "HF_ROM_NPZ_DYNAMIC_RECOMPUTE")
        runs.append({
            "run": index,
            "returncode": completed.returncode,
            "summary": report["summary"],
            "report_sha256": sha256(INDEPENDENT_RESULT),
            "writer_response_match_relative_max": dynamic["writer_response_match_relative_max"],
            "seven_mode_max_relative_independent": dynamic["seven_mode_max_relative_independent"],
            "blas_threads": [x["num_threads"] for x in
                             dynamic["determinism_contract"]["threadpools"]],
        })
    hashes = {x["report_sha256"] for x in runs}
    errors = [float(x["seven_mode_max_relative_independent"]) for x in runs]
    replay_pass = (
        all(x["returncode"] == 0 for x in runs) and
        all(x["summary"] == {"passed": 33, "total": 33, "failed": []} for x in runs) and
        len(hashes) == 1 and
        max(errors)-min(errors) <= 1.0e-15 and
        all(float(x["writer_response_match_relative_max"]) <= 1.0e-9 for x in runs) and
        all(x["blas_threads"] and all(int(v) == 1 for v in x["blas_threads"]) for x in runs)
    )
    output = {
        "schema": "E23_DETERMINISM_REPLAY_V1",
        "contract": (
            "five isolated processes; BLAS=1 before imports; generalized eigh driver=gvd; "
            "all independent report bytes and physical response results identical"
        ),
        "runs": runs,
        "summary": {
            "passed": 5 if replay_pass else sum(int(
                x["returncode"] == 0 and x["summary"].get("passed") == 33 and
                x["summary"].get("total") == 33) for x in runs),
            "total": 5,
            "unique_independent_report_hashes": len(hashes),
            "independent_report_sha256": next(iter(hashes)) if len(hashes) == 1 else None,
            "five_mode_max_relative_spread": max(errors)-min(errors),
        },
        "pass": replay_pass,
    }
    write_json(REPLAY_RESULT, output)
    # Regenerate the acyclic outer manifest so it also pins this replay report.
    sys.path.insert(0, str(HERE.parent))
    from independent_recompute import write_package_manifest
    write_package_manifest()
    print(json.dumps(output["summary"], indent=2))
    return 0 if replay_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
