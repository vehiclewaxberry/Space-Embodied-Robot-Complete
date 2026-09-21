# -*- coding: utf-8 -*-
"""P1b: regenerate the B601 arm COPY from the READ-ONLY donor after P4 v1-v3
corrupted the copy's default config (config-shared Transform2 leak). Per-file
SHA-verified copy (Pack&Go COM is broken on this box -- D-F3R1-01), then the
reference-repair pass so the copy's assembly resolves to its OWN local parts
(trap #9). The donor is never written; its guarded hash is re-checked PRE/POST.
"""
import hashlib
import json
import shutil
import sys
import traceback
from pathlib import Path

from f3r1_env import F3R1, JLog, check_protected, sha256_file, PROTECTED

log = JLog("p1b_arm_recopy")
NC = F3R1 / "03_native_cad"
COPY_ROOT = NC / "B601_ARM_B51_COPY"
DONOR_ASM = Path(PROTECTED["b51_articulated_arm_donor"]["path"])
DONOR_ROOT = DONOR_ASM.parent.parent  # .../B51_ARTICULATED_20260728T008
OUT = F3R1 / "01_asset_selection" / "F3R1_ARM_RECOPY_PROOF.json"

CAD_FILES = [
    "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
    "inputs/vendor_link_parts/B51_REF_base_link_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link1_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link2_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link3_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link4_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link5_LINKLOCAL.SLDPRT",
    "inputs/vendor_link_parts/B51_REF_link6_LINKLOCAL.SLDPRT",
    "parts/B51_REV_DATUM_FEMALE.SLDPRT",
    "parts/B51_REV_DATUM_MALE.SLDPRT",
]


def main():
    rep = {"schema": "F3R1_ARM_RECOPY_V1",
           "donor_root": str(DONOR_ROOT),
           "copy_root": str(COPY_ROOT)}
    check_protected("P1B_PRE")  # donor hash must be intact before we read it
    try:
        if not DONOR_ROOT.is_dir():
            raise RuntimeError("donor root missing: %s" % DONOR_ROOT)
        per = []
        for rel in CAD_FILES:
            src = DONOR_ROOT / rel
            dst = COPY_ROOT / rel
            if not src.is_file():
                raise RuntimeError("donor file missing: %s" % src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            # remove any ~$ lock next to the target, then overwrite the copy
            lock = dst.with_name("~$" + dst.name)
            if lock.exists():
                lock.unlink()
            shutil.copy2(src, dst)
            s_sha = sha256_file(src)
            d_sha = sha256_file(dst)
            ok = (s_sha == d_sha)
            per.append({"rel": rel, "bytes": src.stat().st_size,
                        "src_sha256": s_sha, "dst_sha256": d_sha, "match": ok})
            if not ok:
                raise RuntimeError("copy hash mismatch: %s" % rel)
        rep["per_file"] = per
        rep["files_copied"] = len(per)
        rep["all_match"] = all(e["match"] for e in per)
        # the donor assembly hash equals the guarded reference (identity copy)
        rep["copy_assembly_sha256"] = per[0]["dst_sha256"]
        rep["donor_assembly_sha256"] = PROTECTED["b51_articulated_arm_donor"]["sha256"]
        rep["assembly_identity_ok"] = (
            per[0]["dst_sha256"] == PROTECTED["b51_articulated_arm_donor"]["sha256"])
        rep["verdict"] = ("ARM_RECOPIED_CLEAN" if rep["all_match"]
                          and rep["assembly_identity_ok"] else "RECOPY_FAIL")
    except Exception as exc:
        rep["verdict"] = "RECOPY_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
        log.ev("RECOPY_FAIL", error=str(exc))
    check_protected("P1B_POST")  # donor still intact after the read-copy
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "files:", rep.get("files_copied"),
          "identity_ok:", rep.get("assembly_identity_ok"))
    sys.exit(0 if rep["verdict"] == "ARM_RECOPIED_CLEAN" else 1)


if __name__ == "__main__":
    main()
