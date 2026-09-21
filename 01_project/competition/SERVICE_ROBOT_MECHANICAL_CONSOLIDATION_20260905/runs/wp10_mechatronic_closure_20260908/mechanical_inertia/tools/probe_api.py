from pathlib import Path
import json
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
M=Path(__file__).resolve().parents[1]
packet=json.loads((M.parent/'mechanical_intake/PARAMETER_PACKET.json').read_text())
row=next(x for x in packet['instances'] if x['mass']['identity']=='CANDIDATE_GEOMETRY_MATERIAL_MODEL')
reader=STEPControl_Reader();Interface_Static.SetCVal_s('xstep.cascade.unit','MM')
assert reader.ReadFile(row['geometry_by_state']['service']['source_step']['path'])==IFSelect_RetDone
assert reader.TransferRoots()>0
s=reader.OneShape();explorer=TopExp_Explorer(s,TopAbs_SOLID);count=0
while explorer.More():count+=1;explorer.Next()
p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p)
r={'GProp_MatrixOfInertia_doc':GProp_GProps.MatrixOfInertia.__doc__,
   'BRep_volume_doc':BRepGProp.VolumeProperties_s.__doc__,
   'first_id':row['id'],'source_volume':row['source_volume']['estimate'],'import_volume':p.Mass(),
   'reader_FileUnits_doc':STEPControl_Reader.FileUnits.__doc__,
   'reader_system_length_unit':reader.SystemLengthUnit(),
   'valid':BRepCheck_Analyzer(s).IsValid(),'solids':count,'center':[p.CentreOfMass().X(),p.CentreOfMass().Y(),p.CentreOfMass().Z()],
   'matrix':[[p.MatrixOfInertia().Value(i,j) for j in range(1,4)] for i in range(1,4)]}
(M/'results/API_PROBE.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r))
