"""Sequentially finish the remaining owned native candidates after reconciliation."""
from pathlib import Path
import subprocess,sys,json
HERE=Path(__file__).resolve().parent;OUT=HERE.parent
def run(name,*args):
    print('RUN',name,*args,flush=True)
    subprocess.run([sys.executable,'-B','-X','utf8',str(HERE/name),*args],cwd=OUT.parents[1],check=True)
run('reconcile_volume.py')
run('assign_native_materials.py','--plan','INCREMENT_MATERIAL_PLAN.json','--start','35','--end','36','--tag','increment')
run('build_integrated.py','groups','--start','8','--end','9')
run('build_integrated.py','groups','--start','18','--end','23')
for state in ('service','parking','released'):run('build_integrated.py','top','--state',state)
run('summarize_delivery.py')
print('SEQUENTIAL_NATIVE_DELIVERY_COMPLETED',flush=True)
