import subprocess,sys
from pathlib import Path
A=Path(__file__).resolve().parents[1]
subprocess.run(['G:/Windows_program_file/Kicad/bin/python.exe','-B','-X','utf8','tools/read_terminal_board_v29.py'],cwd=A,check=True)
subprocess.run([sys.executable,'-B','-X','utf8','tools/audit_terminals_v29.py'],cwd=A,check=True)
subprocess.run([sys.executable,'-B','-X','utf8','coupled_closure/thermal_terminals_v29.py'],cwd=A,check=True)
