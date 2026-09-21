"""Meaningful fail-closed negative control; restore exact contract bytes in finally."""
from geometry import *
from build_layout import validate_contract
import copy,subprocess,sys
p=D/'inputs/DESIGN_CONSTRAINTS.json';saved=p.read_bytes();old=read(p);assert validate_contract(old)
checks=[]
for k in ['hole_diameter_mm','spacer_height_mm','spacer_OD_mm','spacer_bore_mm','bolt_nominal','bolt_shank_diameter_mm','bolt_head_diameter_mm','bolt_head_height_mm','washer_OD_mm','washer_thickness_mm','nut_AF_mm','nut_height_mm']:
    q=copy.deepcopy(old);v=q['PCB_mount'][k];q['PCB_mount'][k]=v+.25 if isinstance(v,(float,int)) else 'M3x20'
    try:validate_contract(q);raise AssertionError('Negative control was accepted')
    except ValueError as e:checks.append({'field':'PCB_mount.'+k,'rejected':True,'error':str(e)})
for k in ['local_nominal_clearance_target_mm','R3_port_shift_Y_mm','R3_module_shift_Z_mm']:
    q=copy.deepcopy(old);q[k]+=.25
    try:validate_contract(q);raise AssertionError('Negative control was accepted')
    except ValueError as e:checks.append({'field':k,'rejected':True,'error':str(e)})
locked={str(x):sha(x) for x in (D/'cad').glob('*.step')}
try:
    q=copy.deepcopy(old);q['PCB_mount']['spacer_height_mm']=6;write(p,q)
    result=subprocess.run([sys.executable,'-B','-X','utf8',str(D/'tools/build_layout.py')],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode!=0 and 'FROZEN_DIMENSION_CONTRACT_MISMATCH' in result.stderr
finally:p.write_bytes(saved)
assert p.read_bytes()==saved and all(sha(x)==s for x,s in locked.items())
write(D/'results/DIMENSION_CONTRACT_NEGATIVE_CONTROL.json',{'status':'PASS_FAIL_CLOSED_DIMENSION_CONTRACT','field_controls':checks,
    'entrypoint_negative_returncode':result.returncode,'entrypoint_rejected_before_geometry_write':True,
    'CAD_files_unchanged':len(locked),'contract_bytes_restored':True,'contract_sha256':sha(p),'builder_sha256':sha(D/'tools/build_layout.py')})
print('PASS',len(checks),'field negative controls; entrypoint rejects; contract bytes restored;',len(locked),'STEP hashes unchanged')
