"""Re-screen the R6H horizontal installation solid by solid.

R6H's INCREMENT_STATIC_CHECK compared whole shapes with BRepAlgoAPI_Common. For
every pair involving R6H_MAIN_PCBA_INSTALLED — a 40-solid compound whose solids
self-overlap — that comparison cannot be relied on to find a collision (see
solid_wise.py for the measurement). This recomputes the same three-state screen
with the per-solid method and writes its own verdict.

R6H's own result files are not touched. This either confirms the R6H PASS on a
method that can actually detect a collision, or it finds one R6H could not see.
"""
from geometry import *
from solid_wise import overlap, solids
import time

AFFECTED = 'R6H_MAIN_PCBA_INSTALLED'


def bounds(s):
    return g.precise_bounds(s)


if __name__ == '__main__':
    lay = read(R6H / 'inputs/INSTALLATION_LAYOUT.json')
    mods = {r['id']: r for r in lay['replacements'] + lay['pose_changes']}
    delta = lay['parts'] + lay['pose_changes']
    states = c.state_rows()

    out = dict(schema='R7_R6H_SOLIDWISE_RECHECK_V1', status='RUNNING',
               method='PER_SOLID_BRepAlgoAPI_Common',
               reason='Whole-compound booleans lose real overlaps on these operands; '
                      'a pin through R6H_MAIN_PCBA_INSTALLED reads 0.000000 mm3 whole '
                      'and 70.400000 mm3 per solid',
               r6h_check_sha256=sha(R6H / 'results/INCREMENT_STATIC_CHECK.json'),
               r6h_layout_sha256=sha(R6H / 'inputs/INSTALLATION_LAYOUT.json'),
               r6h_reported_status=read(R6H / 'results/INCREMENT_STATIC_CHECK.json')['status'],
               affected_part=AFFECTED, collisions=[], unknown=[], states=[],
               pairs_checked=0, pairs_involving_affected_part=0,
               r6h_result_files_modified=False)

    t0 = time.time()
    for st, rr in states.items():
        host = [mods.get(r['id'], r) for r in rr]
        pairs = 0
        for a in delta:
            sa = source(a)
            for b in candidates(sa, host):
                if a['id'] == b['id']:
                    continue
                pairs += 1
                out['pairs_checked'] += 1
                if AFFECTED in (a['id'], b['id']):
                    out['pairs_involving_affected_part'] += 1
                v, errs = overlap(g, common, sa, source(b),
                                  a_key=(a['id'], st), b_key=(b['id'], st), bounds=bounds)
                if errs:
                    out['unknown'].append(dict(state=st, a=a['id'], b=b['id'], errors=errs))
                if v > 1e-5:
                    out['collisions'].append(dict(state=st, a=a['id'], b=b['id'], volume_mm3=v))
                    print('COLLISION %s %s/%s %.6f' % (st, a['id'], b['id'], v), flush=True)
        out['states'].append(dict(state=st, host_rows=len(host), pairs=pairs))
        print('%s: %d pairs, collisions so far %d, %.0fs' % (
            st, pairs, len(out['collisions']), time.time() - t0), flush=True)
        write(D / 'results/R6H_SOLIDWISE_RECHECK.json', out)

    out['valid'] = not out['collisions'] and not out['unknown']
    out['status'] = ('PASS_R6H_HORIZONTAL_CONFIRMED_PER_SOLID' if out['valid']
                     else 'FAIL_R6H_HORIZONTAL_COLLISION_FOUND_PER_SOLID')
    out['r6h_pass_survives_stronger_method'] = out['valid']
    out['seconds'] = round(time.time() - t0, 1)
    out.update(full_tolerance_analysis=False, thermal_performance_pass=False,
               ready_to_power=False, flight_ready=False)
    write(D / 'results/R6H_SOLIDWISE_RECHECK.json', out)
    print(out['status'], out['pairs_checked'], 'pairs,',
          out['pairs_involving_affected_part'], 'involving', AFFECTED, flush=True)
