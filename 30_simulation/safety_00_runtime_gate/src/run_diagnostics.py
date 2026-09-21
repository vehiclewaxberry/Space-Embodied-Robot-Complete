"""Measure SAFE-00 latency outside the frozen machine-Gate evidence."""
from __future__ import annotations

import json
import platform
import statistics
import time

from case_factory import (
    TEST_VECTOR_KEY_ID,
    decide_test_vector,
    make_case,
)
from safety_core import MODULE


OUTPUT = MODULE / "results" / "safety_00_latency_diagnostic.json"


def run(sample_count: int = 25) -> dict:
    latencies_us = []
    for _ in range(sample_count):
        request, evidence = make_case("N1_NORMAL_ALLOW")
        start = time.perf_counter_ns()
        response = decide_test_vector(request, evidence)
        latencies_us.append((time.perf_counter_ns() - start) / 1000.0)
        if response["decision"] != "ALLOW":
            raise RuntimeError("diagnostic nominal case did not ALLOW")

    ordered = sorted(latencies_us)
    p95_index = max(0, int(0.95 * len(ordered) + 0.999999) - 1)
    result = {
        "schema_version": "safe00-latency-diagnostic-v1",
        "non_gate_diagnostic": True,
        "frozen_evidence": False,
        "excluded_from_evidence_manifest_hashes": True,
        "authorization_mode": "PUBLIC_TEST_VECTOR_NOT_PRODUCTION",
        "authorization_key_id": TEST_VECTOR_KEY_ID,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "sample_count": sample_count,
        "latency_us": {
            "median": statistics.median(latencies_us),
            "p95": ordered[p95_index],
            "max": max(latencies_us),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result


def main() -> int:
    print(json.dumps(run(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
