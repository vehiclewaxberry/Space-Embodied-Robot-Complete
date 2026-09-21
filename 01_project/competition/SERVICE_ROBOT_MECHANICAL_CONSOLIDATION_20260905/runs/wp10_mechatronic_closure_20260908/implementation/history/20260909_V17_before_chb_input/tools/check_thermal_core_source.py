from pathlib import Path
import json,runpy,hashlib,itertools
import numpy as np
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
A=Path(__file__).resolve().parents[1];h=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'));p=json.loads((A/'mechanical/NATIVE_COLD_INPUTS.json').read_text());part={r['id']:r for r in p['parts']}
def precise(s):
    f=h['prop'](s);levels=[]
    for eps in [1e-8,1e-10]:
        gp=GProp_GProps();error=BRepGProp.VolumePropertiesGK_s(s,gp,Eps=eps,OnlyClosed=True,IsUseSpan=True)
        assert 0<=error<1e-6
        levels.append(dict(Eps=eps,volume_mm3=gp.Mass(),estimated_relative_error=error))
    assert abs(levels[-1]['volume_mm3']-levels[-2]['volume_mm3'])<1e-4
    f.update(nonadaptive_volume_mm3=f['measure'],measure=levels[-1]['volume_mm3'],quadrature_levels=levels)
    return f
path=A/'mechanical/thermal_core.step';ss=h['parts'](h['read'](path));facts=[h['prop'](s) for s in ss];assert len(ss)==38 and all(BRepCheck_Analyzer(s).IsValid() for s in ss)
remaining=set(range(38));checks=[]
for r in p['rows']:
    q=part[r['native_part_id']];b=q['expected_local_bbox_mm'];corners=np.array(list(itertools.product(*zip(b['min_mm'],b['max_mm']))));T=np.array(r['T_S_step']);assert np.allclose(T[:3,:3],np.round(T[:3,:3]))
    assert np.allclose(T[:3,:3].T@T[:3,:3],np.eye(3),atol=1e-12,rtol=0) and abs(np.linalg.det(T[:3,:3])-1)<1e-12 and np.array_equal(T[3],[0,0,0,1])
    pts=corners@T[:3,:3].T+T[:3,3];expected=np.r_[pts.min(0),pts.max(0)]
    # Compare in the same S frame and with the same quadrature. The diagnostic
    # found a default-integral serialization discrepancy; its exact origin is
    # not certified. GK convergence does not certify absolute volume accuracy.
    assert hashlib.sha256(Path(q['step_path']).read_bytes()).hexdigest()==q['source_sha256']
    tr=gp_Trsf();tr.SetValues(*[float(T[j,k]) for j in range(3) for k in range(4)])
    local=h['read'](q['step_path']);reference_shape=BRepBuilderAPI_Transform(local,tr,True).Shape()
    high_accuracy=r['id']=='U202_CHB'
    reference=precise(reference_shape) if high_accuracy else h['prop'](reference_shape)
    local_volume=precise(local)['measure'] if high_accuracy else q['expected_volume_mm3']
    candidates=[i for i in remaining if np.max(abs(np.array(facts[i]['bbox'])-expected))<1e-5]
    if high_accuracy:
        for i in candidates:facts[i]=precise(ss[i])
    local_relative_change=abs(reference['measure']-local_volume)/local_volume
    assert local_relative_change<1e-6
    matches=[i for i in remaining if np.max(abs(np.array(facts[i]['bbox'])-expected))<1e-5 and abs(facts[i]['measure']-reference['measure'])<1e-4]
    assert len(matches)==1,(r['id'],matches)
    index=matches[0];remaining.remove(index);checks.append(dict(id=r['id'],solid_index=index,passed=True,
      S_frame_reference_volume_mm3=reference['measure'],S_frame_volume_error_mm3=facts[index]['measure']-reference['measure'],
      reference_quadrature_levels=reference.get('quadrature_levels'),assembly_quadrature_levels=facts[index].get('quadrature_levels'),
      original_nonadaptive_volume_error_mm3=facts[index].get('nonadaptive_volume_mm3',facts[index]['measure'])-reference.get('nonadaptive_volume_mm3',reference['measure']),
      local_to_S_integral_relative_change=local_relative_change,bbox_error_mm=float(np.max(abs(np.array(facts[index]['bbox'])-expected)))))
out=dict(schema='WP10_THERMAL_CORE_SOURCE_MATCH_V2',native_input_sha256=hashlib.sha256((A/'mechanical/NATIVE_COLD_INPUTS.json').read_bytes()).hexdigest(),step_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),count=38,checks=checks,checks_passed=not remaining,matching='One-to-one actual STEP solid bbox+same-frame volume, proper rigid transforms; CHB GK spline-span quadrature with two refinement levels; others analytic/default integration',bbox_tolerance_mm=1e-5,same_frame_volume_tolerance_mm3=1e-4,absolute_volume_or_mass_certified=False,full_BRep_shape_equivalence_verified=False,native_assembly_verified=False,quadrature_counterexample='results/COLD_SOURCE_MATCH_DIAGNOSTIC.json')
(A/'results/THERMAL_CORE_SOURCE_MATCH.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(count=38,passed=out['checks_passed'])))
