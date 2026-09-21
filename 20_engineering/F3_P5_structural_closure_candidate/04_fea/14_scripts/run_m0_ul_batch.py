# -*- coding: utf-8 -*-
"""F3-P5A M0 Batch UL Runner: Run all 12 M0 UL cases (6 positive + 6 negative)."""
from __future__ import print_function
import os
import subprocess
import sys
import time

WS = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate"
INP_DIR = os.path.join(WS, r"04_fea\05_calculix_inputs")
OUT_DIR = os.path.join(WS, r"04_fea\06_calculix_results")
CCX = r"G:\Windows_program_file\FreeCAD\bin\ccx.exe"

# 12 UL cases
CASES = [
    ("UL_FX", 1, 1.0),      # +Fx = 1 N
    ("UL_FY", 2, 1.0),      # +Fy = 1 N
    ("UL_FZ", 3, 1.0),      # +Fz = 1 N
    ("UL_MX", 4, 1000.0),   # +Mx = 1 N·m = 1000 N·mm
    ("UL_MY", 5, 1000.0),   # +My = 1 N·m = 1000 N·mm
    ("UL_MZ", 6, 1000.0),   # +Mz = 1 N·m = 1000 N·mm
    ("UL_NEG_FX", 1, -1.0), # -Fx = -1 N
    ("UL_NEG_FY", 2, -1.0), # -Fy = -1 N
    ("UL_NEG_FZ", 3, -1.0), # -Fz = -1 N
    ("UL_NEG_MX", 4, -1000.0), # -Mx = -1 N·m
    ("UL_NEG_MY", 5, -1000.0), # -My = -1 N·m
    ("UL_NEG_MZ", 6, -1000.0), # -Mz = -1 N·m
]


def create_inp(case_name, dof, value):
    """Create CalculiX input file for a given UL case."""
    inp_content = f"""** F3-P5A M0 Beam/Shell Load Path Model
** {case_name}: Unit load DOF={dof} value={value}
** Units: mm, N, MPa
**
*HEADING
F3-P5A M0 Beam Load Path Model - {case_name}
**
** Nodes (non-collinear for beam normal definition)
*NODE
1, 0.0, 0.0, 0.0
2, 0.0, 0.0, 100.0
3, 0.0, 0.0, 200.0
4, 0.0, 0.0, 300.0
5, 0.0, 0.0, 400.0
6, 0.0, 0.0, 500.0
7, 0.0, 0.0, 600.0
8, 0.0, 0.0, 700.0
9, 0.0, 0.0, 800.0
10, 0.0, 0.0, 900.0
11, 0.0, 0.0, 1000.0
** Reference node for beam normal (not on beam axis)
100, 1.0, 0.0, 0.0
**
** Beam elements (base adapter + load bridge)
*ELEMENT, TYPE=B31
1, 1, 2
2, 2, 3
3, 3, 4
4, 4, 5
5, 5, 6
6, 6, 7
7, 7, 8
8, 8, 9
9, 9, 10
10, 10, 11
**
** Spring elements (G07/G08/Mid support)
** G07 at node 5 (z=400), stiffness 10 N/mm
** G08 at node 9 (z=800), stiffness 5 N/mm
** Mid at node 7 (z=600), stiffness 0 (non-contact backup, 2mm gap)
*ELEMENT, TYPE=SPRING1
11, 5
12, 9
**
** Boundary conditions
** Base fixed at node 1 (all DOF: ux, uy, uz)
*BOUNDARY
1, 1, 3, 0.0
**
** G07 spring stiffness (10 N/mm in Z direction)
*SPRING, ELSET=G07_SPRING
11
** Data line: spring constant, direction (3=Z)
10.0, 3
**
** G08 spring stiffness (5 N/mm in Z direction)
*SPRING, ELSET=G08_SPRING
12
5.0, 3
**
** Material (Al 7075-T6)
*MATERIAL, NAME=AL7075
*ELASTIC
71700.0, 0.33
*DENSITY
2.81E-9
**
** Beam section (rectangular, 17x17 mm for load bridge)
** Normal defined by reference node 100 (1,0,0 direction)
*BEAM SECTION, ELSET=BEAM_SET, MATERIAL=AL7075, SECTION=RECT
17.0, 17.0
100
**
** Element sets
*ELSET, ELSET=BEAM_SET
1, 2, 3, 4, 5, 6, 7, 8, 9, 10
*ELSET, ELSET=G07_SPRING
11
*ELSET, ELSET=G08_SPRING
12
**
** Step
*STEP
*STATIC
**
** Load: DOF={dof} value={value} at node 11 (top)
*CLOAD
11, {dof}, {value}
**
** Output requests
*NODE FILE
U
*EL FILE
S
**
*END STEP
"""
    inp_path = os.path.join(INP_DIR, f"F3_P5A_M0_{case_name}.inp")
    os.makedirs(os.path.dirname(inp_path), exist_ok=True)
    with open(inp_path, "w", encoding="utf-8") as f:
        f.write(inp_content)
    return inp_path


def run_ccx(inp_path, case_name):
    """Run CalculiX on the input file."""
    # Copy to short path for ccx 127-char limit
    short_path = os.path.join(os.environ["TEMP"], f"M0_{case_name}.inp")
    import shutil
    shutil.copy2(inp_path, short_path)
    job_name = short_path.replace(".inp", "")
    t0 = time.time()
    result = subprocess.run([CCX, "-i", job_name], capture_output=True, text=True, timeout=120)
    elapsed = time.time() - t0
    return {
        "case": case_name,
        "job_name": job_name,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "elapsed_s": elapsed,
    }


def main():
    results = []
    for case_name, dof, value in CASES:
        print(f"Running {case_name}...", flush=True)
        inp_path = create_inp(case_name, dof, value)
        result = run_ccx(inp_path, case_name)
        results.append(result)
        status = "PASS" if result["returncode"] == 0 else "FAIL"
        print(f"  {case_name}: {status} (elapsed={result['elapsed_s']:.1f}s)", flush=True)

    # Summary
    n_pass = sum(1 for r in results if r["returncode"] == 0)
    n_fail = sum(1 for r in results if r["returncode"] != 0)
    print(f"\nSUMMARY: {n_pass} PASS, {n_fail} FAIL out of {len(results)} cases", flush=True)

    # Copy results back to output directory
    for result in results:
        case_name = result["case"]
        job_name = result["job_name"]
        for ext in [".frd", ".sta", ".cvg", ".12d", ".dat"]:
            src = job_name + ext
            if os.path.isfile(src):
                dst = os.path.join(OUT_DIR, f"M0_{case_name}{ext}")
                import shutil
                shutil.copy2(src, dst)

    print("Results copied to output directory", flush=True)


main()
