"""Serial saved-STEP interference check; numeric cache only, no full assembly load."""
import gc, itertools, json
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from coupled_adapter import HERE,A,sha,dump

def transform(shape,T):
    t=gp_Trsf();t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(shape,t,True).Shape()

def run(parts,pose,parent):
    assert sha(A/parent['source_plan'])==parent['source_plan_sha256']
    assert all(len(rows)==974 for rows in parent['states'].values())
    placed=[];bounds=[]
    for s in parts:
        placed.append(transform(s.wrapped,pose))
        b=s.bounding_box();bb=[*b.min,*b.max]
        corners=[[sum(pose[i][j]*v[j] for j in range(3))+pose[i][3] for i in range(3)]
                 for v in itertools.product(*[(bb[k],bb[k+3]) for k in range(3)])]
        bounds.append([min(v[k] for v in corners) for k in range(3)]+
                      [max(v[k] for v in corners) for k in range(3)])
    states={};cache={};locks={};host_identities=set()
    for state,rows in parent['states'].items():
        checked=[]
        for row in rows:
            bb=row['bbox_S_mm']
            indices=[i for i,b in enumerate(bounds) if all(min(b[k+3],bb[k+3])-max(b[k],bb[k])>1e-5 for k in range(3))]
            if not indices:continue
            path=Path(row['step_path']);expected=row['source_sha256']
            if str(path) not in locks:
                assert sha(path)==expected, 'HOST_SOURCE_DRIFT: '+str(path)
                locks[str(path)]=expected
            host_identities.add((row['id'],expected,json.dumps(row['T_S_step'])))
            keys={i:(i,expected,json.dumps(row['T_S_step'])) for i in indices}
            needed=[i for i in indices if keys[i] not in cache]
            if needed:
                reader=STEPControl_Reader();assert int(reader.ReadFile(str(path)))==1
                reader.TransferRoots();host=transform(reader.OneShape(),row['T_S_step'])
                assert BRepCheck_Analyzer(host).IsValid(), 'INVALID_HOST: '+row['id']
                for i in needed:
                    distance=BRepExtrema_DistShapeShape(placed[i],host);distance.Perform()
                    assert distance.IsDone();d=distance.Value();v=0.
                    if d<1e-7:
                        common=BRepAlgoAPI_Common(placed[i],host);common.Build();assert common.IsDone()
                        props=GProp_GProps();BRepGProp.VolumeProperties_s(common.Shape(),props);v=props.Mass()
                        assert v>=-1e-6
                        del common,props
                    cache[keys[i]]=dict(distance_mm=d,common_volume_mm3=max(0.,v))
                    del distance
                del reader,host
                gc.collect()
            for i in indices:
                checked.append(dict(new_part_index=i,new_part=parts[i].label,parent_id=row['id'],
                    representation_role=row['representation_role'],is_ground_only=row['is_ground_only'],
                    source_sha256=expected,step_path=str(path),T_S_step=row['T_S_step'],**cache[keys[i]]))
        collisions=[r for r in checked if r['common_volume_mm3']>1e-3]
        states[state]=dict(checked_pairs=checked,collisions=collisions,
            status='REJECTED_SAVED_GEOMETRY_INTERFERENCE' if collisions else 'SAVED_GEOMETRY_NO_VOLUME_INTERFERENCE_ONLY')
    out=dict(script_sha256=sha(__file__),mechanical_source_sha256=sha(HERE/'mechanical_parts.py'),
        bounds_source_sha256=sha(A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'),
        parent_plan_sha256=parent['source_plan_sha256'],T_S_module=pose,
        source_lock=locks,unique_host_files=len(locks),unique_host_identities=len(host_identities),
        unique_exact_pairs=len(cache),states=states,narrowphase_performed=True,installed=False,
        status='REJECTED_SAVED_GEOMETRY_INTERFERENCE' if any(s['collisions'] for s in states.values()) else 'SAVED_GEOMETRY_CLEAR_ONLY',
        scope='Actual saved STEP intersections for this one pose and partial PCB population. '
              'Proxy/functional-envelope intersections retain their original representation roles; '
              'no real hardware, mounting, tool, tolerance, thermal or full-assembly fit credit.')
    dump('HOST_NARROWPHASE.json',out)
    print(json.dumps(dict(host_exact_pairs=len(cache),host_collisions={k:len(v['collisions']) for k,v in states.items()},
        host_status=out['status'])),flush=True)
    return out
