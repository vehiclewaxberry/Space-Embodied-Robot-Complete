from pathlib import Path
C=Path(__file__).resolve().parent/"candidate"
p=C/"dynamics_handoff.py";s=p.read_text(encoding="utf-8")
s=s.replace("from candidate_context import ENGINEERING","from candidate_context import ENGINEERING\nfrom provenance_binding import validate_receipt_source, receipt_binding")
s=s.replace("HERE/'kinematics.py', HERE/'wing_kinematics.py']","HERE/'kinematics.py', HERE/'wing_kinematics.py', HERE/'root_structure.py', HERE/'r01_design.py', HERE/'candidate_context.py', HERE/'provenance_binding.py']")
s=s.replace("    source_checks = []","    for data in receipts:\n        validate_receipt_source(data, HERE)\n        for pth, value in data['geometry_sha256'].items():\n            if sha(pth) != value: raise ValueError('Final geometry identity changed')\n            hashes[str(Path(pth).resolve())] = value\n    source_checks = []")
s=s.replace("'input_sha256': hashes, 'source_files_unchanged': unchanged,","'input_sha256': hashes, 'source_files_unchanged': unchanged,\n              'receipt_bindings': {d['state']: receipt_binding(d,p) for d,p in zip(receipts,paths)},")
p.write_text(s,encoding="utf-8")
p0=C.parent.parent/"loop0_20260905/a4/strict_surface_aggregator.py"
t=p0.read_text(encoding="utf-8").replace("Both arguments are synthetic protocol records, not original WP03 receipts.","Contract/evidence are runtime-bound records supplied by the candidate pose entry.")
t=t.replace("'ISOLATED_CODE_CONTROL_NOT_CAD'","'RUNTIME_BOUND_SCOPED_SURFACE_PROTOCOL'").replace("'geometry_executed': False","'geometry_executed': evidence.get('geometry_executed') is True")
t=t.replace('"""Proposed input guard only; no claim that current consumers already enforce it."""','"""Physical-view guard used by this candidate entry."""')
t=t.replace("import json","import json\nimport math")
t=t.replace("    reasons = result['reasons']","    reasons = result['reasons']\n    def finite(v):\n        if isinstance(v,float): return math.isfinite(v)\n        if isinstance(v,dict): return all(finite(x) for x in v.values())\n        if isinstance(v,(list,tuple)): return all(finite(x) for x in v)\n        return True\n    if not finite(contract) or not finite(evidence): reasons.append('NONFINITE_PROTOCOL_VALUE')")
(C/"strict_surface_aggregator.py").write_text(t,encoding="utf-8")
print("Handoff and strict protocol upgrade applied.")

