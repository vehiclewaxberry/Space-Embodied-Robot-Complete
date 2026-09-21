"""Right rear rib two-bolt local candidate; two replacements, eight hardware, one context."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
def gen_step():
    from rear_rib_detail import build
    return build()[2]
