from pathlib import Path
import runpy
A=Path(__file__).resolve().parents[1]
for name in ['build_radiator_obstacle_bounds.py','verify_step_frame_repair.py','prepare_cold_native.py']:
    print('RUN',name,flush=True);runpy.run_path(str(A/'tools'/name),run_name='__main__')
