from pathlib import Path
M=Path(__file__).resolve().parents[1]
s=(M/'tools/read_material_inertia_v2.py').read_text()
s=s.replace("V2_GK_LOCAL_DEFAULT_POSE", "V3_DEFAULT_FACE_WITH_ADAPTIVE_COMPARISON")
s=s.replace("err=BRepGProp.VolumePropertiesGK_s(shape,p,eps,True,True,True,True,False)","err=BRepGProp.VolumeProperties_s(shape,p,eps,True,False)")
s=s.replace("'Gauss-Kronrod integration failed'", "'Adaptive volume quadrature failed'")
s=s.replace("BRepGProp.VolumePropertiesGK(adaptive Gauss-Kronrod,OnlyClosed=True,IsUseSpan=True,CGFlag=True,IFlag=True,SkipShared=False)", "BRepGProp.VolumeProperties(adaptive face quadrature,OnlyClosed=True,SkipShared=False; eps estimates volume, NOT inertia error)")
s=s.replace("r.update(default=d0,adaptive_eps1e7=d7,adaptive_eps1e9=d9)", "r.update(default=d0,adaptive_eps1e7=d7,adaptive_eps1e9=d9,primary_property_key='default',primary_method='OCCT_DEFAULT_FACE_GAUSS_QUADRATURE',comparison_method='VOLUME_CONTROLLED_ADAPTIVE_FACE_QUADRATURE_NOT_A_STRICT_INERTIA_BOUND')")
s=s.replace("'status':'OBSERVED_TWO_TOLERANCE_CHANGE_NOT_RIGOROUS_ERROR_BOUND'", "'status':'OBSERVED_VOLUME_TOLERANCE_REFINEMENT_CHANGE_NOT_INERTIA_ERROR_BOUND'")
s=s.replace("primary GK checked by algebra in collector", "primary default integrals checked by algebra in collector")
s=s.replace("r['default_vs_adaptive']={'volume_relative_difference'", "r['default_vs_adaptive']={'volume_relative_difference'")
(M/'tools/read_material_inertia_v3.py').write_text(s,encoding='utf-8')
