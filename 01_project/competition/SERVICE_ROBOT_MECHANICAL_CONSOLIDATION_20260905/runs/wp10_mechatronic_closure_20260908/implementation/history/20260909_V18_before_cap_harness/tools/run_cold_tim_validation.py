"""Run dependency-ordered bounded checks; stop at first failure."""
from pathlib import Path
import subprocess,sys
A=Path(__file__).resolve().parents[1]
jobs=[
 ('bounds',180,'refresh_cold_bounds.py',[]),
 ('mesh',180,'build_radiator_occlusion_mesh.py',[]),
 ('view',150,'radiator_mesh_view_screen.py',[]),
 ('thermal',180,'spatial_radiator_network.py',[]),
 ('tools',150,'check_cold_path_tools.py',[]),
 ('core',150,'review_cold_path_cad.py',['--phase','core']),
 ('source_match',120,'check_thermal_core_source.py',[]),
 ('leaves',180,'review_cold_path_cad.py',['--phase','leaves']),
 ('assemblies',180,'review_cold_path_cad.py',['--phase','assemblies']),
 ('snapshots',180,'review_cold_path_cad.py',['--phase','snapshots']),
]
start=sys.argv[1] if len(sys.argv)>1 else jobs[0][0]
assert start in [r[0] for r in jobs]
jobs=jobs[[r[0] for r in jobs].index(start):]
for tag,timeout,script,args in jobs:
    print('START',tag,flush=True)
    rc=subprocess.call([sys.executable,'-B','-X','utf8',str(A/'tools/native_delta_guard.py'),'--timeout',str(timeout),'native_delta_cold_TIM1800_'+tag,'--',sys.executable,'-B','-X','utf8',str(A/'tools'/script),*args],cwd=A)
    if rc:raise SystemExit(rc)
    print('DONE',tag,flush=True)
