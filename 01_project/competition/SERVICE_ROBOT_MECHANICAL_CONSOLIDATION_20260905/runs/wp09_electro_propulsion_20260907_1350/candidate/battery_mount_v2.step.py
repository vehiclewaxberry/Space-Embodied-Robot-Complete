from pathlib import Path
import importlib.util,sys
sys.dont_write_bytecode=True
def gen_step():
    p=Path('F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/candidate/battery_mount_detail_v2.py')
    s=importlib.util.spec_from_file_location('battery_mount_source',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m.build()[2]
