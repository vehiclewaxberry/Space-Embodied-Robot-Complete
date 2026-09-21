from common import *
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_Label,TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool
def name(label):
    a=TDataStd_Name();return a.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(),a) else ''
def extract(p,tag):
    reader=STEPCAFControl_Reader();reader.SetNameMode(True);assert reader.ReadFile(str(p))==1
    doc=TDocStd_Document(TCollection_ExtendedString('XmlXCAF'));assert reader.Transfer(doc)
    st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main());roots=TDF_LabelSequence();st.GetFreeShapes(roots);out=[]
    def visit(label,T=np.eye(4),instance=''):
        if st.IsReference_s(label):
            ref=TDF_Label();assert st.GetReferredShape_s(label,ref);tr=st.GetLocation_s(label).Transformation();m=np.eye(4)
            for i in range(3):
                for j in range(4):m[i,j]=tr.Value(i+1,j+1)
            return visit(ref,T@m,name(label))
        seq=TDF_LabelSequence()
        if st.GetComponents_s(label,seq,False) and seq.Length():
            for i in range(1,seq.Length()+1):visit(seq.Value(i),T)
        else:
            s=moved(st.GetShape_s(label),T);ident=f'{tag}_{len(out):03d}';labelname=name(label) or instance
            r=emit(ident,s,'SOURCE_GEOMETRY',sub='source/'+tag,source_label=labelname,instance_label=instance,source_assembly_sha256=sha(p))
            out.append(r);print(ident,labelname,'solids',r['expected_solids'],'bbox',r['expected_local_bbox_mm'],flush=True)
    for i in range(1,roots.Length()+1):visit(roots.Value(i))
    full=load(p);vol=sum(r['expected_volume_mm3'] for r in out)
    # OCP integrates an entire compound differently from summing per-leaf adaptive integrals.
    # Compare the reassembled compound with the source compound at the same granularity.
    recombined=g.volume(compound([source(r) for r in out]));assert abs(recombined-g.volume(full))<max(1e-4,recombined*1e-9)
    write(D/'inputs'/f'{tag}_SOURCE_MAP.json',{'source_path':str(p),'source_sha256':sha(p),'rows':out,'component_instances':len(out),
        'solid_occurrences':sum(r['expected_solids'] for r in out),'volume_sum_mm3':vol,'source_full_volume_mm3':g.volume(full),
        'recombined_compound_volume_mm3':recombined,'per_leaf_vs_compound_integration_difference_mm3':vol-recombined,
        'frame':'Assembly local coordinates; component transforms applied once during canonical extraction'})
    return out
if __name__=='__main__':
    extract(IMPL/'coupled_closure/main_input_lugs_v30.step','V30')
    extract(D/'cad/source/V36_MAIN_INPUT_NATIVE_EXPORT.step','V36')
