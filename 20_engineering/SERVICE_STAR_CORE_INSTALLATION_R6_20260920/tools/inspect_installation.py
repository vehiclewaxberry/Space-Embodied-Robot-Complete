from geometry import *
rows=state_rows()['service'];rr={r['id']:r for r in rows}
region=box(-172,-90,-10,-40,85,55)
out=[]
for r in candidates(region,rows):
    lo,hi=world_bounds(r)
    out.append({'id':r['id'],'lo':lo.tolist(),'hi':hi.tolist(),'group':r['group'],'role':r.get('representation_role')})
write(D/'inputs/HOST_REGION_BOUNDS.json',out)
for r in out:
    if not any(k in r['id'].lower() for k in ('bolt','washer','nut','screw','rod','m3','m4','m5','m6')):
        print(r)
print('Host region rows',len(out))
