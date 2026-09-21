from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=(R/'tools/integrate_native.py').read_text()
s=s.replace("for xyz in ([0,0,0],[10,0,0],[0,10,0],[0,0,10]):", "for xyz in (([0,0,0],[10,0,0],[0,10,0],[0,0,10]) if k in self.report.get('new_instance_ids',[]) else []):")
s=s.replace('basis_max_error_mm=max(basis)','basis_max_error_mm=max(basis) if basis else None')
s=s.replace("parts=[],progress=[],save_attempts=[],rows=rows", "parts=[],progress=[],save_attempts=[],rows=rows,new_instance_ids=[r['id'] for r in rows[619:]],basis_probe_scope='NEW_82_INSTANCES; FULL_MATRIX_READBACK_ALL_701'")
s=s.replace("sw.OpenDoc6(str(target),2,193", "sw.OpenDoc6(str(target),2,195")
p=R/'tools/integrate_native_v2.py';assert not p.exists();p.write_text(s,encoding='utf-8')
