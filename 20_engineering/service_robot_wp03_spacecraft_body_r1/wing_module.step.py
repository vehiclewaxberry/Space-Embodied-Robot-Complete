from spacecraft_model import build
from build123d import Compound
def gen_step():
    _,shapes,r=build('service',include_arm=False)
    return Compound(label='WP03_SOLAR_WING_MODULE',children=[shapes[x['id']] for x in r['instances'] if x['parent_assembly']=='SOLAR_WING'])
