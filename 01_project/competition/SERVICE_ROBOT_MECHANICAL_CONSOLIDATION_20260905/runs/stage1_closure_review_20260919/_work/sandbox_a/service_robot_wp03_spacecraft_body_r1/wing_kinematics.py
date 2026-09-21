"""WP03 fixed-offset serial-hinge candidate, mm/deg; no old R2 source edits.

frames(side, angles) returns proper rigid transforms of centered300x200x2.5 boxes.
The old sign-reassigned normal is deliberately not used. Geometry validation
does not assert collision-free deployment, load capacity or flight qualification.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import numpy as np

LEAF_CHORD=300.0
LEAF_SPAN=200.0
LEAF_T=2.5
STACK_STEP=3.0
ROOT_Y=121.15  # WP03 root interface stand-off revision+5.75mm, not oldR2 qualification.
ROOT_Z=-108.15
LOCAL_BOX=(LEAF_CHORD,LEAF_SPAN,LEAF_T)
REVISION='WP03_FIXED_OFFSET_SERIAL_HINGES_R3_ROOT_STANDOFF'

def frames(side,angles):
    if side not in (-1,1):raise ValueError('side must be-1 or+1')
    if len(angles)!=3:raise ValueError('angles must be(th1,ph2,ph3) in degrees')
    th1,ph2,ph3=map(math.radians,angles)
    # Opposite third-hinge deployment; folded direction is unchanged modulo2pi.
    psi=(th1,th1+math.pi-ph2,th1-ph2+ph3)
    directions=[np.array([side*math.sin(a),math.cos(a)]) for a in psi]
    normals=[np.array([side*math.cos(a),-math.sin(a)]) for a in psi]
    roots=[np.array([side*ROOT_Y,ROOT_Z])]
    roots.append(roots[0]+LEAF_SPAN*directions[0]+STACK_STEP*normals[0])
    roots.append(roots[1]+LEAF_SPAN*directions[1]-STACK_STEP*normals[1])
    result=[]
    for i,(root,d,n) in enumerate(zip(roots,directions,normals),1):
        e1=np.array([1.,0,0]);e2=np.array([0.,d[0],d[1]]);e3=np.cross(e1,e2)
        center=root+LEAF_SPAN/2*d;tip=root+LEAF_SPAN*d
        t=np.eye(4);t[:3,:3]=np.column_stack([e1,e2,e3]);t[:3,3]=[0,*center]
        result.append({'side':side,'index':i,'T_S_leaf_center':t.tolist(),'root_S_mm':[0.,*root.tolist()],
                       'tip_S_mm':[0.,*tip.tolist()],'hinge_axis_point_S_mm':[0.,*root.tolist()],
                       'hinge_axis_direction_S':[1.,0.,0.],'localbox':list(LOCAL_BOX),'psi_rad':psi[i-1],
                       'span_direction_yz':d.tolist(),'unredirected_normal_yz':n.tolist(),
                       'revision':REVISION})
    return result

def corners(row):
    t=np.array(row['T_S_leaf_center']);half=np.array(row['localbox'])/2
    points=np.array(list(itertools.product(*zip(-half,half))))
    return points@t[:3,:3].T+t[:3,3]

def obb_relation(a,b,tolerance=1e-8):
    """Full15-axis SAT on two rectangular leaves. No AABB collision inference."""
    ta=np.array(a['T_S_leaf_center']);tb=np.array(b['T_S_leaf_center'])
    aa=ta[:3,:3];bb=tb[:3,:3];ha=np.array(a['localbox'])/2;hb=np.array(b['localbox'])/2
    delta=tb[:3,3]-ta[:3,3]
    axes=[aa[:,i] for i in range(3)]+[bb[:,i] for i in range(3)]
    axes += [np.cross(aa[:,i],bb[:,j]) for i in range(3) for j in range(3)]
    overlaps=[]
    for axis in axes:
        norm=np.linalg.norm(axis)
        if norm<1e-10:continue
        axis=axis/norm
        overlap=float(np.dot(ha,np.abs(aa.T@axis))+np.dot(hb,np.abs(bb.T@axis))-abs(np.dot(delta,axis)))
        if overlap < -tolerance:return {'relation':'OBB_STRICT_SEPARATION','separating_axis':axis.tolist(),'axis_gap_mm':-overlap}
        overlaps.append(overlap)
    minimum=min(overlaps)
    return {'relation':'OBB_TOUCHING' if minimum<=tolerance else 'OBB_POSITIVE_INTERIOR_OVERLAP',
            'minimum_tested_axis_overlap_mm':minimum,'overlap_volume_mm3':None}

def sequence():
    return ([('ROOT_DEPLOY',(a,0,0)) for a in range(0,91,5)]+
            [('LEAF2_UNFOLD',(90,a,0)) for a in range(5,181,5)]+
            [('LEAF3_UNFOLD',(90,180,a)) for a in range(5,181,5)])

def checks():
    validation=[];continuity=[];intersections=[];touching=[];pair_count=0;separated=0
    for stage,angles in sequence():
        rows=[row for side in (-1,1) for row in frames(side,angles)]
        for row in rows:
            t=np.array(row['T_S_leaf_center']);r=t[:3,:3]
            validation.append({'stage':stage,'angles_deg':angles,'side':row['side'],'leaf':row['index'],
                'determinant':float(np.linalg.det(r)),'orthogonality_error':float(np.max(np.abs(r.T@r-np.eye(3)))),
                'edge_length_mm':np.linalg.norm(r*np.array(row['localbox'])[None,:],axis=0).tolist(),
                'root_tip_length_mm':float(np.linalg.norm(np.array(row['tip_S_mm'])-row['root_S_mm']))})
        for a,b in itertools.combinations(rows,2):
            relation=obb_relation(a,b);pair_count+=1
            record={'stage':stage,'angles_deg':angles,'leaves':[[a['side'],a['index']],[b['side'],b['index']]],
                    'adjacent_same_wing':a['side']==b['side'] and abs(a['index']-b['index'])==1,**relation}
            if relation['relation']=='OBB_POSITIVE_INTERIOR_OVERLAP':intersections.append(record)
            elif relation['relation']=='OBB_TOUCHING':touching.append(record)
            else:separated+=1
    cases=[('PH2_CROSS90_ROOT0',(0,90,0),1,False),('PH3_CROSS90_ROOT0',(0,180,90),2,False),
           ('PH2_ENDPOINT',(90,180,0),1,True),('PH3_ENDPOINT',(90,180,180),2,True)]
    for label,center,index,endpoint in cases:
        for epsilon in [1e-3,1e-6,1e-9]:
            before=list(center);after=list(center);before[index]-=epsilon
            if not endpoint:after[index]+=epsilon
            for side in (-1,1):
                for a,b in zip(frames(side,before),frames(side,after)):
                    displacement=np.linalg.norm(corners(a)-corners(b),axis=1).max()
                    continuity.append({'case':label,'epsilon_deg':epsilon,'before':before,'after':after,'side':side,
                                       'leaf':a['index'],'max_corresponding_corner_displacement_mm':float(displacement)})
    landmarks=[]
    for side in (-1,1):
        for label,angles in [('STOWED',(0,0,0)),('DEPLOYED',(90,180,180))]:
            for row in frames(side,angles):
                landmarks.append({'configuration':label,**row})
    result={'schema':'WP03_SERIAL_WING_KINEMATICS_CHECK_V1','revision':REVISION,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'status':'CONTINUOUS_PROPER_FRAMES_WITH_EXPLICIT_LEAF_OVERLAP_FINDINGS' if intersections else 'SAMPLED_OBB_NO_INTERIOR_OVERLAP_CONTINUOUS_PATH_UNKNOWN',
            'old_r2_source_modified':False,'interface_change':'Fixed offsets+3*n1 then-3*n2 at serial hinge roots; no normal reassignment. Hinge3:psi3=psi2-pi+ph3. R3 relocates WP03 root fromabsY115.4 to121.15(+5.75mm); no oldR2 qualification inherited.',
            'root_interface_revision':{'old_root_y_abs_mm':115.4,'new_root_y_abs_mm':ROOT_Y,'outward_delta_mm':ROOT_Y-115.4,'hinge_root_z_mm':ROOT_Z,'arm_root_changed':False,'qualification_status':'NOT_EVALUATED_WP03_NEW_INTERFACE'},
            'prior_findings_file':'results/WING_KINEMATICS_R1_FINDINGS.json',
            'prior_findings_sha256':hashlib.sha256((Path(__file__).resolve().parent/'results/WING_KINEMATICS_R1_FINDINGS.json').read_bytes()).hexdigest(),
            'landmarks':landmarks,'frame_validation':validation,'continuity_samples':continuity,
            'all_frame_determinants_plus1':all(abs(v['determinant']-1)<1e-12 for v in validation),
            'all_edge_lengths_preserved':all(np.allclose(v['edge_length_mm'],LOCAL_BOX,rtol=0,atol=1e-10) for v in validation),
            'smallest_epsilon_max_corner_displacement_mm':max(v['max_corresponding_corner_displacement_mm'] for v in continuity if v['epsilon_deg']==1e-9),
            'sample_count':len(sequence()),'obb_pair_count':pair_count,'obb_strictly_separated_pairs':separated,
            'positive_interior_overlap_count':len(intersections),'positive_interior_overlaps':intersections,'touching_count':len(touching),'touching_pairs':touching,
            'method':'Exact separating-axis test for modeled rectangular leaf solids;5deg sampled joint sequence only. Positive overlap is geometric leaflet-box intersection, not a volume integration.',
            'unknown':['Between-sample continuous collision','Hinge barrels, brackets, latches, connectors and harness','Real panels/tolerances/loads']}
    output=Path(__file__).resolve().parent/'results/WING_KINEMATICS_CHECK.json'
    output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','all_frame_determinants_plus1','all_edge_lengths_preserved','smallest_epsilon_max_corner_displacement_mm','sample_count','obb_pair_count','positive_interior_overlap_count','touching_count']}),flush=True)
    if intersections:print(json.dumps({'first_overlap':intersections[0]}),flush=True)

if __name__=='__main__':checks()
