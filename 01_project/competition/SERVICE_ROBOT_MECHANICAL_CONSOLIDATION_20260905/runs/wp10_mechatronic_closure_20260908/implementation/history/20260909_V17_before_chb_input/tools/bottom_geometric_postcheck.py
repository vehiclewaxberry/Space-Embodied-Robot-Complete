from pathlib import Path
import runpy
A=Path(__file__).resolve().parents[1]
for name in ['build_radiator_obstacle_bounds.py','verify_step_frame_repair.py','check_bottom_tool_clearance.py']:
    runpy.run_path(str(A/'tools'/name),run_name='__main__')
