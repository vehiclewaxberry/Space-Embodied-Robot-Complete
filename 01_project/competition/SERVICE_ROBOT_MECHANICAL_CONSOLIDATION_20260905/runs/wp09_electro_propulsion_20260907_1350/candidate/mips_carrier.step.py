"""WP09 mips local candidate; fixed source helper path for cadgen snapshots."""
import importlib.util,sys
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('wp09_mips_detail',r'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/candidate/module_carriers_detail.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def gen_step():
    return m.build('mips')[2]
