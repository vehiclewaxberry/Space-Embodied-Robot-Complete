from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from system_model import build
def gen_step():return build('released')
