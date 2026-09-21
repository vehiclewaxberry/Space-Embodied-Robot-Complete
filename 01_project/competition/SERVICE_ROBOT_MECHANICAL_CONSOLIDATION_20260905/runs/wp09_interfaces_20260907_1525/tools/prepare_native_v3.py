"""Further states: remeasure the 82 new bodies; reuse only hash-verified WP08 parent body evidence."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'tools/integrate_native_v2.py').read_text()
s=s.replace("if measure:\n                comp.SetSuppression2", "if measure and k in self.report.get('new_instance_ids',[]):\n                comp.SetSuppression2")
s=s.replace("basis_probe_scope='NEW_82_INSTANCES; FULL_MATRIX_READBACK_ALL_701'", "basis_probe_scope='NEW_82_INSTANCES; FULL_MATRIX_READBACK_ALL_701',retained_body_evidence='HASH_VERIFIED_WP08_NATIVE_STATE_RECEIPT_WITH_CURRENT_COMPONENT_PATH_HASH_AND_TRANSFORM_READBACK'")
s=s.replace("solid_count=sum(x['actual_solids'] for x in observed),body_counts_are_actual=True", "solid_count=sum(r.get('expected_solids',1) for r in rows),new_body_count_actual=sum(x.get('actual_solids',0) for x in observed),retained_solid_count_hash_bound=sum(r.get('expected_solids',1) for r in rows[:619]),body_counts_are_actual=False")
s=s.replace("status='PASS_FIXED_POSE_NATIVE_DELTA_COLD_BODY_AND_TRANSFORM_CHECK'", "status='PASS_FIXED_POSE_NATIVE_NEW_BODY_AND_ALL_METADATA_WITH_HASH_BOUND_PARENT'")
p=R/'tools/integrate_native_v3.py';assert not p.exists();p.write_text(s,encoding='utf-8')
