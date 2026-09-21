from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_assembly
def gen_step():return local_assembly.assembly()
