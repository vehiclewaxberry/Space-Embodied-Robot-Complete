"""Render a CAD-skill snapshot through a verified native-GLB fallback.

The CAD snapshot CLI resolves and validates the STEP job first.  For this
388-solid assembly its selector-topology GLB exceeds Chromium's practical
memory limit, so this wrapper keeps the resolved STEP job and swaps only the
browser render payload to the native GLB derived from that same immutable STEP.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path


CAD_SCRIPTS = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad"
    r"\0.3.9\skills\cad\scripts"
)
sys.path.insert(0, str(CAD_SCRIPTS))

import snapshot.__main__ as snapshot  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--native-glb", type=Path, required=True)
    parser.add_argument("--expected-step-sha256", required=True)
    args = parser.parse_args()

    cwd = Path.cwd().resolve()
    job_path = (cwd / args.job).resolve() if not args.job.is_absolute() else args.job.resolve()
    native_glb = (
        (cwd / args.native_glb).resolve()
        if not args.native_glb.is_absolute()
        else args.native_glb.resolve()
    )
    if not job_path.is_file():
        raise SystemExit(f"snapshot job missing: {job_path}")
    if not native_glb.is_file() or native_glb.stat().st_size <= 0:
        raise SystemExit(f"native GLB missing or empty: {native_glb}")

    raw_job = json.loads(job_path.read_text(encoding="utf-8"))
    packet = snapshot.resolve_render_job_packet(raw_job, cwd=cwd)
    if len(packet["jobs"]) != 1:
        raise SystemExit("fallback requires exactly one resolved snapshot job")
    resolved_job = packet["jobs"][0]
    resolved = dict(resolved_job["resolved"])
    step_path = Path(str(resolved["inputPath"])).resolve()
    step_hash_before = sha256(step_path)
    expected = args.expected_step_sha256.upper()
    if step_hash_before != expected:
        raise SystemExit(
            f"STEP hash mismatch before render: {step_hash_before} != {expected}"
        )
    root_path = Path(str(resolved["rootPath"])).resolve()
    try:
        native_glb.relative_to(root_path)
    except ValueError as exc:
        raise SystemExit(
            f"native GLB must remain inside render root: {native_glb}"
        ) from exc

    resolved["glbPath"] = str(native_glb)
    resolved["glbUrl"] = snapshot.asset_url_for_path(native_glb, root_path)
    resolved_job["resolved"] = resolved
    result = asyncio.run(snapshot.render_resolved_job_packet(packet))
    snapshot.write_render_outputs(result)
    snapshot.print_render_result(result)

    step_hash_after = sha256(step_path)
    if step_hash_after != step_hash_before:
        raise SystemExit("STEP hash changed during native-GLB snapshot render")
    print(
        json.dumps(
            {
                "status": "B5_0_SNAPSHOT_NATIVE_GLB_FALLBACK_PASS",
                "step_path": str(step_path),
                "step_sha256_unchanged": step_hash_after,
                "native_glb_path": str(native_glb),
                "native_glb_bytes": native_glb.stat().st_size,
                "native_glb_sha256": sha256(native_glb),
                "renderer": "CAD_SKILL_SNAPSHOT_RUNTIME",
                "deviation": (
                    "selector-topology GLB crashed Chromium; resolved STEP job "
                    "rendered with same-STEP native GLB payload"
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
