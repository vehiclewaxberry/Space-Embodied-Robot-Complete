"""Resolve the reviewer's inherited V29 fields without upgrading qualification."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
p=C/'CANDIDATE_V30.json'; c=json.loads(p.read_text()); s=json.loads((A/'power/LUG_HARNESS_SELECTION_V30.json').read_text())
before=hashlib.sha256(p.read_bytes()).hexdigest();old={k:c[k].copy() for k in ['mechanical','terminal_delta','mechanical_delta']}
m=c['mechanical'];m.update(terminal_wire_OD_mm=sum(s['wire']['jacket_OD_mm'])/2,terminal_wire_OD_range_mm=s['wire']['jacket_OD_mm'],terminal_wire_core_area_mm2=None,terminal_wire_conductor_bundle_OD_range_mm=s['wire']['conductor_bundle_OD_mm'],terminal_wire_mpn=s['wire']['mpn'],terminal_wire_size_status='OEM 10 AWG candidate bound; port ampacity and installed qualification OPEN; area not inferred from bundle OD')
c['terminal_delta'].update(lug_bound=True,lug_source_bound=True,lug_mpn=s['lug']['mpn'],lug_bound_scope='OEM drawing and uncrimped reference CAD; not physical termination qualification',crimp_qualified=False)
c['mechanical_delta']['scope']='V29_PARENT_SNAPSHOT; current module is mechanical_local_delta V30'
p.write_text(json.dumps(c,indent=2));after=hashlib.sha256(p.read_bytes()).hexdigest()
act=C/'SOURCE_ACTIVATION_V30.json';d=json.loads(act.read_text());d['candidate_sha256']=after;act.write_text(json.dumps(d,indent=2))
(C/'CANDIDATE_FIELD_CORRECTION_V30.json').write_text(json.dumps(dict(before_sha256=before,after_sha256=after,prior_fields=old,reason='readonly review found stale inherited wire size and lug binding fields',geometry_changed=False,qualification_upgraded=False),indent=2))
print(after)
