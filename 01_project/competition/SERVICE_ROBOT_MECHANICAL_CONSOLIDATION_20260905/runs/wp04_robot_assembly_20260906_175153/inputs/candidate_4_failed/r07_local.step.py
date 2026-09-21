from build123d import Compound
from spacecraft_model import build
from r07_design import affected_ids
def gen_step():
    model,shapes,r=build('service',include_arm=False)
    ids=set(affected_ids({},r))
    ids.update(x['id'] for x in r['instances'] if x['parent_assembly']=='ROOT_STRUCTURE')
    ids.update(x['id'] for x in r['instances'] if x['id'].startswith('hold_crossbeam_'))
    return Compound(label='WP04_R07_ROOT_CONNECTIONS_CANDIDATE',children=[shapes[k] for k in sorted(ids)])
