from fixed_heat_common import parameters,tim_local
def gen_step():return tim_local(next(d for d in parameters()['devices'] if d['id']=='U202_CHB'))
