"""Bound model obstruction from same-state CAD boxes, serial STEP fallback."""
from pathlib import Path
import json,hashlib,gc
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.gp import gp_Trsf
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source_bounds(row):
    rr=STEPControl_Reader();assert int(rr.ReadFile(row['step_path']))==1;rr.TransferRoots();s=rr.OneShape()
    M=row['T_S_step'];t=gp_Trsf();t.SetValues(*[float(M[i][j]) for i in range(3) for j in range(4)])
    s=BRepBuilderAPI_Transform(s,t,True).Shape();b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b)
    assert not b.IsVoid();return list(b.Get())
def main():
    p=A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json';plan=json.loads(p.read_text());states={};hashed={};fallback=0
    ports_path=A.parents[1]/'wp09_interfaces_20260907_1525/functional_closure/results/PORTS_EMISSION.json'
    # Explicitly bound by functional_ports.py/PORTS_EMISSION, not by missing
    # product_role in the migrated instance rows.
    ground_ids=['WP09F_PWR_GLAND','WP09F_PWR_NUT','WP09F_RS422_GLAND','WP09F_RS422_NUT','WP09F_front_service_cover_GSE']
    port_parts=json.loads(ports_path.read_text())['parts']
    assert all(port_parts[k.removeprefix('WP09F_')]['product_role'] in ['GSE_REMOVABLE','GROUND_CONFIGURATION_CANDIDATE'] for k in ground_ids)
    for state,record in plan['states'].items():
        rows=[]
        for row in record['rows']:
            path=row.get('step_path');expected=row.get('source_sha256');assert path and expected,row['id']
            if path not in hashed:hashed[path]=sha(path)
            assert hashed[path]==expected,(row['id'],path)
            bb=row.get('world_bounds_mm') or row.get('bounds_mm')
            if bb:
                bounds=bb['min_mm']+bb['max_mm'];basis='PARENT_CURRENT_NATIVE_WORLD_BOUNDS_RETAINED_OR_TRANSLATED'
            else:
                bounds=source_bounds(row);basis='CURRENT_STEP_READBACK_T_S_step';fallback+=1;gc.collect()
            assert all(np.isfinite(bounds)) and all(bounds[k+3]>=bounds[k] for k in range(3))
            rows.append(dict(id=row['id'],bbox_S_mm=bounds,bbox_basis=basis,step_path=path,source_sha256=expected,
                T_S_step=row['T_S_step'],representation_role=row.get('representation_role'),product_role=row.get('product_role'),
                is_ground_only=row['id'] in ground_ids or str(row.get('product_role','')).upper().startswith('GSE') or row['id'].startswith('GSE_')))
        states[state]=rows
    out=dict(schema='WP10_RADIATOR_OBSTACLE_BOUNDING_BOXES_V1',source_plan_sha256=sha(p),states=states,
        component_count_each=plan['candidate_component_count'],unique_source_hashes_checked=len(hashed),serial_STEP_fallback_count=fallback,
        geometry_role='Outer boxes of current CAD representations: opaque-box union conservatively fills holes/gaps; finite sampled estimates are not rigorous certified view-factor bounds',
        actual_hardware_geometry_bound=False,all_current_source_files_sha_match=True,
        GSE_exclusion=dict(ids=ground_ids,source_path=str(ports_path),source_sha256=sha(ports_path)))
    (A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(states={s:len(r) for s,r in states.items()},hashes=len(hashed),fallback=fallback)))
if __name__=='__main__':main()
