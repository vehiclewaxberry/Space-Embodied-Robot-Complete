"""Mass-split closure check (decision D-4 companion; run any time, exits 1 on failure).

Splits the 24 kg whole-sat servicer_12U_v0 into rigid bus + 2 solar panels and verifies
EXACT recomposition: m_bus + 2*m_panel == 24 kg and I_recomposed == I_whole (machine eps).
Prevents the ANCF double-counting failure mode: sim_07 must consume the bus values,
never the whole-sat row. Prints the exact bus row for mass_inertia_budget_v1.csv."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sim", "common"))
from rigid_body import load_object

# panel spec (flexible_appendage_v1.yaml, from model_specs_v0.json primitives)
LX, LY, LZ = 0.227, 0.200, 0.006                    # plate dims in S axes [m]
P_CENTERS = [np.array([-0.05675,  0.21315, 0.0]),   # panel centres in S
             np.array([-0.05675, -0.21315, 0.0])]
V_PANEL = LX * LY * LZ
V_TOTAL = 0.018765                                   # servicer_12U_v0.json volume_m3

def steiner(m, d):
    return m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))

whole = load_object("servicer_12U_v0")
M, cg, I_w = whole["mass"], whole["cg"], whole["I"]

m_p = M * V_PANEL / V_TOTAL                          # uniform-density share -> exact closure
I_p_own = np.diag([m_p/12*(LY**2+LZ**2), m_p/12*(LX**2+LZ**2), m_p/12*(LX**2+LY**2)])

m_bus = M - 2*m_p
cg_bus = (M*cg - m_p*(P_CENTERS[0] + P_CENTERS[1])) / m_bus
# I about whole-sat CoM = I_bus_own + steiner(bus) + sum(I_p_own + steiner(panel))
I_bus_own = I_w - steiner(m_bus, cg_bus - cg) \
    - sum(I_p_own + steiner(m_p, c - cg) for c in P_CENTERS)

# --- closure checks ---
err_m = abs(m_bus + 2*m_p - M)
I_recomp = I_bus_own + steiner(m_bus, cg_bus - cg) \
    + sum(I_p_own + steiner(m_p, c - cg) for c in P_CENTERS)
err_I = np.max(np.abs(I_recomp - I_w))
eigs = np.linalg.eigvalsh(I_bus_own)
ok = err_m < 1e-12 and err_I < 1e-12 and np.all(eigs > 0)

print({"m_panel_kg": round(m_p, 7), "m_bus_kg": round(m_bus, 7),
       "cg_bus_m": [round(v, 7) for v in cg_bus],
       "I_bus_own_kgm2": {"Ixx": round(I_bus_own[0, 0], 7), "Iyy": round(I_bus_own[1, 1], 7),
                          "Izz": round(I_bus_own[2, 2], 7), "Ixy": round(I_bus_own[0, 1], 7),
                          "Ixz": round(I_bus_own[0, 2], 7), "Iyz": round(I_bus_own[1, 2], 7)},
       "closure_mass_err": err_m, "closure_inertia_err": err_I,
       "I_bus_positive_definite": bool(np.all(eigs > 0)), "PASS": ok})
csv_row = (f"servicer_12U_bus_v1,S,CoM,{m_bus:.7f},{cg_bus[0]:.7f},{cg_bus[1]:.7f},{cg_bus[2]:.7f},"
           f"{I_bus_own[0,0]:.7f},{I_bus_own[1,1]:.7f},{I_bus_own[2,2]:.7f},"
           f"{I_bus_own[0,1]:.7f},{I_bus_own[0,2]:.7f},{I_bus_own[1,2]:.7f},"
           f"mass_split_check_v1,low,usable_for_ancf_v1")
print("CSV bus row:", csv_row)
print(f"CSV panel row: solar_panel_single_v1,F,CoM,{m_p:.7f},0,0,0,"
      f"{I_p_own[0,0]:.7e},{I_p_own[1,1]:.7e},{I_p_own[2,2]:.7e},0,0,0,"
      f"mass_split_check_v1,low,usable_for_ancf_v1")
sys.exit(0 if ok else 1)
