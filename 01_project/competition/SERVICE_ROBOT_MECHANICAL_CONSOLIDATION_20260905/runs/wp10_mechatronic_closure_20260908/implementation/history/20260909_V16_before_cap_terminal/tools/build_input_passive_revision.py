from pathlib import Path
import runpy
A=Path(__file__).resolve().parents[1]
for item in ['integrate_power_loop.py','verify_power_loop.py','build_regen_screen.py','verify_load_side_brake.py','verify_startup_and_fault.py','check_shared_battery_path.py','check_input_passives.py','check_fuse_coordination.py']:
 print('Running '+item,flush=True)
 runpy.run_path(str(A/'tools'/item),run_name='__main__')
