from pathlib import Path
import json
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
M=Path(__file__).resolve().parents[1]
print(BRepGProp.VolumePropertiesGK_s.__doc__)
s=BRepPrimAPI_MakeCylinder(5,20).Shape();rows=[]
for eps in [1e-7,1e-9,1e-11]:
    p=GProp_GProps()
    e=BRepGProp.VolumePropertiesGK_s(s,p,eps,True,True,True,True,False)
    rows.append({'eps':eps,'err':e,'v':p.Mass(),'c':[p.CentreOfMass().X(),p.CentreOfMass().Y(),p.CentreOfMass().Z()],
        'I':[[p.MatrixOfInertia().Value(i,j) for j in range(1,4)] for i in range(1,4)]})
(M/'results/GK_PROBE.json').write_text(json.dumps({'doc':BRepGProp.VolumePropertiesGK_s.__doc__,'rows':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
