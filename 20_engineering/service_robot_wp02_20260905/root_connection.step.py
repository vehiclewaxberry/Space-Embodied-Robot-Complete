from parts_model import build,ON,HW
from build123d import Compound
def gen_step():
    model,placed,parts=build('held')
    names=[n for n in placed if n.startswith(('RB_','M6_','M5_','WP01-RB','WP01-MT'))]
    return Compound(label='WP02_ROOT_CONNECTION',children=[placed[n] for n in names])
