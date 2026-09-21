"""Derive actual new-system checks from sealed integration checker, preserving input scope."""
from pathlib import Path
D=Path(__file__).resolve().parents[1]
C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
text=(C/'tools/verify_stop_ecad_integration.py').read_text(encoding='utf-8')
text=text.replace("C=Path(__file__).resolve().parents[1];E=C/'ecad';S=C/'electrical_delta';N=C.parent/'reuse_closure'",
"C=Path(__file__).resolve().parents[1];E=C/'ecad';S=C/'electrical';N=C.parent/'wp09_interfaces_20260907_1525/system_completion'")
text=text.replace("'SYSTEM_STOP_ECAD_INTEGRATION_V1'","'WP10_SYSTEM_AUX_SUPPLY_INTEGRATION_V1'")
text=text.replace("'PASS_ACTUAL_HIERARCHY_NET_BINDINGS__ELECTRICAL_DESIGN_OPEN'","'PASS_ACTUAL_REVISED_SUPPLY_HIERARCHY_NET_BINDINGS__SYSTEM_DESIGN_OPEN'")
# source branch preserved, no old extra power wire append.
text=text.replace("check('MCU_VIO_not_stop_3V3_or_5V',","check('MCU_VIO_not_stop_3V3_or_5V',")
p=D/'tools/verify_ecad.py';assert not p.exists()
p.write_text(text,encoding='utf-8')
print(p)

