from spacecraft_model import build
from build123d import Compound
def gen_step():
    _,shapes,r=build('parking',include_arm=False)
    return Compound(label='WP03_ONBOARD_RETENTION_CANDIDATE',children=[shapes[x['id']] for x in r['instances'] if x['parent_assembly']=='ONBOARD_RETENTION'])
