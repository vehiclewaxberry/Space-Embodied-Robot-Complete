"""VIZ-Gate 0 acceptance test 6 -- strict single-file dashboard contract.

This closes the gap between merely "offline" and the requested self-contained
HTML deliverable.  It verifies that the six MP4 files and the complete
interactive explorer is embedded as a deterministic runtime payload (the
standalone duplicate Plotly bundle is replaced by parent.Plotly), that no
relative or network fetch target remains, and that the required
coordinate-frame metadata is present and numerically well formed.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap as vb  # noqa: E402

import base64               # noqa: E402
import csv                  # noqa: E402
import hashlib              # noqa: E402
import json                 # noqa: E402
import math                 # noqa: E402
import re                   # noqa: E402


DASHBOARD = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                         "project_visualization_v0.html")
EXPLORER = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                        "grasp_geometry_explorer_v0.html")
FRAME_CSV = os.path.join(vb.VIZ_TABLES_DIR, "frame_registry_v1.csv")
VIDEO_DIR = os.path.join(REPO, "40_evidence", "artifacts", "visualization", "videos")
VIDEO_FILES = [
    "anim_v01_target_tumble.mp4",
    "anim_v02_b601_approach.mp4",
    "anim_v03_base_reaction.mp4",
    "anim_v04_capture_impulse.mp4",
    "anim_v05_flex_diagnostic.mp4",
    "anim_v06_gate_explanation.mp4",
]
REQUIRED_FRAMES = {"I", "S", "B", "M", "E", "T", "G1", "G2", "G3"}
SIM07_REPLAY_SOURCE = os.path.join(REPO, "70_tools", "project_visualization", "src",
                                   "sim07_flex_replay.py")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def main(verbose=True):
    details = []
    assert os.path.isfile(DASHBOARD), f"missing dashboard: {DASHBOARD}"
    html = _read_bytes(DASHBOARD).decode("utf-8")

    # A. Six embedded MP4 payloads must be byte-identical to the source files.
    pat_video = re.compile(
        r'<video\b[^>]*data-file="([^"]+)"[^>]*'
        r'src="data:video/mp4;base64,([^"]+)"[^>]*>')
    embedded = pat_video.findall(html)
    names = [name for name, _ in embedded]
    assert names == VIDEO_FILES, f"embedded video order/names differ: {names}"
    for name, payload in embedded:
        decoded = base64.b64decode(payload, validate=True)
        source = _read_bytes(os.path.join(VIDEO_DIR, name))
        assert _sha(decoded) == _sha(source), f"embedded MP4 differs: {name}"
    details.append("6/6 MP4 payloads embedded byte-for-byte as data URIs")

    # B. The full explorer (not a thumbnail or relative link) is embedded as a
    # payload.  A multi-MB data URL is intentionally forbidden because Chrome
    # leaves an over-limit iframe blank; parent JS hydrates a blank iframe.
    iframe = re.search(
        r'<iframe\b[^>]*data-file="grasp_geometry_explorer_v0\.html"[^>]*>',
        html)
    assert iframe, "embedded interactive explorer iframe not found"
    assert not re.search(r'\bsrc\s*=', iframe.group(0)), \
        "explorer iframe must not use the over-limit data-URL form"
    m = re.search(
        r'<script id="explorerPayload" type="application/octet-stream">'
        r'([A-Za-z0-9+/=]+)</script>', html)
    assert m, "embedded explorer payload not found"
    explorer_decoded = base64.b64decode(m.group(1), validate=True)
    # Match the builder's text-mode read (Windows CRLF is normalized to LF).
    with open(EXPLORER, encoding="utf-8") as f:
        explorer_source = f.read()
    expected_runtime, n = re.subn(
        r"<script>.*?</script>",
        "<script>window.Plotly = parent.Plotly;</script>", explorer_source,
        count=1, flags=re.S)
    assert n == 1, "standalone explorer Plotly bundle not isolated"
    old_call = 'Plotly.react("plot",'
    new_call = 'Plotly.react(document.getElementById("plot"),'
    assert expected_runtime.count(old_call) == 1
    expected_runtime = expected_runtime.replace(old_call, new_call)
    assert _sha(explorer_decoded) == _sha(expected_runtime.encode("utf-8")), \
        "embedded explorer runtime payload is not the deterministic transform"
    assert "function hydrateExplorer()" in html
    assert "new TextDecoder(\"utf-8\")" in html
    assert "doc.write(source)" in html and "hydrateExplorer();" in html
    details.append(
        "interactive explorer payload embedded and hydrated; parent Plotly "
        "is reused, avoiding both an over-limit URL and duplicate parsing")
    assert '"geometry_fail": "#d97706"' in explorer_source, \
        "explorer geometry IK_FAIL must use orange, not physical-violation red"

    # C. Strict fetch-target scan: data URIs/fragments only; no sidecars.
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", html), \
        "dashboard has external script src"
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "<script></script>",
                    html, flags=re.S)
    targets = [m.group(1).strip() for m in re.finditer(
        r'(?:src|href)\s*=\s*["\']([^"\']*)["\']', markup)]
    bad = [u[:160] for u in targets
           if u and not (u.startswith("data:") or u.startswith("#"))]
    assert not bad, f"relative/network fetch targets remain: {bad[:5]}"
    assert "视频未内嵌" not in html and "相对路径引用" not in html, \
        "stale sidecar-distribution wording remains"
    details.append(f"strict single-file scan: {len(targets)} fetch targets, all data URIs")

    # D. Frame registry contract and quaternion integrity.
    assert os.path.isfile(FRAME_CSV), f"missing {FRAME_CSV}"
    with open(FRAME_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_name = {r["frame_name"]: r for r in rows}
    missing = REQUIRED_FRAMES - set(by_name)
    assert not missing, f"required frames missing: {sorted(missing)}"
    for name, r in by_name.items():
        for field in ("translation_m", "quaternion_wxyz", "source_file",
                      "confidence", "context_note"):
            assert r[field].strip(), f"{name}: empty {field}"
        t = json.loads(r["translation_m"])
        q = json.loads(r["quaternion_wxyz"])
        assert len(t) == 3 and all(math.isfinite(float(v)) for v in t), \
            f"{name}: invalid translation {t}"
        assert len(q) == 4 and all(math.isfinite(float(v)) for v in q), \
            f"{name}: invalid quaternion {q}"
        norm = math.sqrt(sum(float(v) ** 2 for v in q))
        assert abs(norm - 1.0) < 1e-9, f"{name}: quaternion norm {norm}"
        assert f'data-frame="{name}"' in html, f"dashboard frame row missing: {name}"
    assert by_name["B"]["parent_frame"] == "S"
    assert "free-flyer" in by_name["B"]["context_note"]
    assert by_name["M"]["parent_frame"] == "S"
    details.append(
        f"frame registry {len(rows)} rows; required I/S/B/M/E/T/G1-G3 present, "
        "unit quaternions valid, B/M SSOT naming explicit")

    # E. v05 must remain a read-only evidence reel.  This static guard makes
    # a future accidental solver reintroduction fail the acceptance suite.
    sim07_source = _read_bytes(SIM07_REPLAY_SOURCE).decode("utf-8")
    forbidden = ("solve_ivp", "simulate_states", "build_beam(",
                 "sim_07a_task_response", "scipy.integrate")
    present = [token for token in forbidden if token in sim07_source]
    assert not present, f"v05 reintroduced flexible solver code: {present}"
    assert "NO_REPLAYABLE_TIME_HISTORY" in sim07_source
    assert '"ancf_recomputed": False' in sim07_source
    details.append(
        "v05 source guard: read-only existing PNG/CSV evidence; no flexible "
        "solver imports/calls and no fabricated deformation time history")

    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_dashboard_contract", "pass": True,
            "details": details}


if __name__ == "__main__":
    print("test_dashboard_contract:")
    main()
    print("PASS")
