"""Prepare derivative integrator from frozen source, never execute parent top-level writes."""
from pathlib import Path
import hashlib
D=Path(__file__).resolve().parents[1]
C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
original=C/'tools/integrate_stop_ecad.py'
text=original.read_text(encoding='utf-8')
text=text.replace("C=Path(__file__).resolve().parents[1];N=C.parent/'reuse_closure';E=C/'ecad';S=C/'electrical_delta'",
"D=Path(__file__).resolve().parents[1];C=D.parent/'wp09_interfaces_20260907_1525/system_completion';N=C.parent/'reuse_closure';E=D/'ecad';S=D/'electrical'")
text=text.replace("(N/'ecad/MASTER_FROM_TO.csv')","(C/'ecad/MASTER_FROM_TO.csv')")
start=text.index("for k,a,b,sig in [('SC_PWR24'")
end=text.index("pinrows=list",start)
text=text[:start]+text[end:]
text=text.replace("'wp09-resume-system:'","'wp10-aux-supply-system:'")
text=text.replace("ACTUAL_STOP_SUBPAGE_TERMINAL_ASSIGNMENT; connector_MPN_and_harness_unbound","WP10_ACTUAL_STOP_SUPPLY_DRIVER_REVISION; connector_MPN_and_harness_unbound")
text=text.replace("; electrical_delta/STOP_PIN_NET_MAP.csv","; WP10 electrical/STOP_PIN_NET_MAP.csv")
text=text.replace("WP09 actual stop subpage integration; GSE branch; flight energy/propulsion unbound","WP10 actual auxiliary supplies and driver; GSE candidate; full system open")
text=text.replace("'old_wire_ids_preserved':70","'old_wire_ids_preserved':len(parent_rows)")
text=text.replace("'3V3_and_5V1_sources_bound':False","'auxiliary_supply_derivative_source':'WP10 electrical circuit; source guarantees and open conditions are separately verified'")
text=text.replace("str(N/'ecad/MASTER_FROM_TO.csv')","str(C/'ecad/MASTER_FROM_TO.csv')")
# Keep parent source geometry and actual circuit regeneration distinct.
text += "\nassert len(rows)==len(parent_rows)==72\nassert len({r['wire_id'] for r in rows})==72\n"
target=D/'tools/integrate_ecad.py'
assert not target.exists()
target.write_text(text,encoding='utf-8')
print({'prepared':str(target),'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest()})

