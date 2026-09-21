from geometry import *
import math

def route(end_x,dz,level_y):
    r=14.;dy=-math.sqrt(r*r-dz*dz);v=np.array([0.,dy/r,dz/r]);u=np.array([-1.,0,0]);z=118+dz
    path=g.Path3D([65,-80,118],v.tolist());path.arc([51,-80,118],np.cross(v,u),math.pi/2)
    path.line([49,path.p[1],z]);path.offset(u,[0,1,0],level_y-path.p[1],r)
    path.line([6,level_y,z]);path.offset(u,[0,1,0],-80-level_y,r)
    path.offset(u,[0,0,-1],dz,r);path.line([end_x,-80,118]);s=path.solid()
    last=None;errors=[]
    for cmd in path.commands:
        if 'arc' in cmd:
            c=cmd['arc'];n=np.array(c['normal']);sgn=np.sign(c['angle_rad'])
            a=np.cross(n,np.array(c['start'])-c['center'])*sgn;b=np.cross(n,np.array(c['end'])-c['center'])*sgn
        else:a=b=np.array(cmd['line_end'])-cmd['line_start']
        a=a/np.linalg.norm(a);b=b/np.linalg.norm(b)
        if last is not None:errors.append(float(np.linalg.norm(a-last)))
        last=b
    assert max(errors)<1e-8,errors
    verr=abs(g.volume(s)-math.pi*4*path.length);assert verr<1e-5,verr
    return s,{'commands':path.commands,'arcs':path.arcs,'start':path.start.tolist(),'end':path.p.tolist(),
        'tangent_continuity_max_error':max(errors),'analytic_volume_error_mm3':verr,'return_start_X_mm':6,
        'OD_mm':4.,'radius_mm':14.,'centerline_length_mm':path.length,'cut_length_mm':None,'cable_MPN':None}

def run():
    rows=state_rows()['service'];r3=read(D/'inputs/MOUNT_LAYOUT.json');changes={r['id']:r for r in r3['replacements']};rows=[changes.get(r['id'],r) for r in rows]+r3['additions']
    exclude={'release_power_data_route_0_0','release_power_data_route_1_0','WP10_INTERNAL_BATTERY_BYPASS','release_power_data_route_0_1','release_power_data_route_1_1'}
    obstacles=[r for r in rows if r['id'] not in exclude];trials=[];best=None
    for dz,ly in [(7,-89),(8,-89),(9,-89),(7,-89.5),(8,-89.5),(9,-89.5)]:
        shape,p=route(-115.,dz,ly);hits=[];near=[];unknown=[]
        for o in candidates(shape,obstacles,3.):
            old=source(o)
            try:v=g.volume(common(shape,old));dist=distance(shape,old)
            except Exception as e:unknown.append(o['id']);continue
            if v>1e-6:hits.append({'id':o['id'],'volume_mm3':v})
            near.append({'id':o['id'],'distance_mm':dist,'role':o.get('representation_role')})
        near.sort(key=lambda x:x['distance_mm']);q={'rise_mm':dz,'corridor_Y_mm':ly,'collisions':hits,'unknown':unknown,'closest':near[:6]};trials.append(q)
        print('TRIAL',dz,ly,'hits',len(hits),'min',near[0] if near else None,flush=True)
        if not hits and not unknown:
            score=near[0]['distance_mm'] if near else 3
            if best is None or score>best[0]:best=(score,dz,ly)
    write(D/'results/PASSAGE_SEARCH.json',{'scope':'bounded geometric candidate search, shared functional corridor, no physical wire qualification','trials':trials,'best':best,'excluded_known_functional_endpoints':sorted(exclude)})
    if best:
        parts=[]
        for ident,end in [('release_power_data_route_0_0',-115.),('release_power_data_route_1_0',-40.)]:
            s,p=route(end,best[1],best[2]);parts.append(emit(ident,s,'FUNCTIONAL_ROUTE_ENVELOPE',parameters=p))
        write(D/'inputs/PASSAGE_LAYOUT.json',{'replacements':parts,'best_nominal_gap_mm':best[0],'target_nominal_gap_mm':2.0,
            'full_motion_checked':False,'shared_corridor_not_two_separate_cables':True})

if __name__=='__main__':run()
