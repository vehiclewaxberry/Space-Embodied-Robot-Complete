from pathlib import Path
import runpy
A=Path(__file__).resolve().parents[1]
for name in ['check_bottom_mount_geometry.py','prepare_fixed_heat_integration.py','check_cold_path_geometry.py']:
    print('RUN',name,flush=True);runpy.run_path(str(A/'tools'/name),run_name='__main__')
