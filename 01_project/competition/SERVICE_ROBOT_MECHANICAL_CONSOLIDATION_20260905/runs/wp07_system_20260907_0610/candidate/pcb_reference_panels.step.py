"""Four unselected reference PCB mechanical profiles; no manufacturing/ECAD credit."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pcb_reference_panels import build_reference_set


def gen_step():
    assembly, evidence = build_reference_set()
    # stdout belongs to root's execution log. gen --write owns artifact paths.
    print("PCB_REFERENCE_BUILD_FACTS " + json.dumps(evidence, ensure_ascii=False, allow_nan=False))
    return assembly
