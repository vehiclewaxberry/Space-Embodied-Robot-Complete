from pathlib import Path
M=Path(__file__).resolve().parents[1]
src=(M/'tools/read_material_inertia.py').read_text()
src=src.replace("r={'index':job['index'],", "r={'worker_sha256':sha(__file__),'method_revision':'V2_GK_LOCAL_DEFAULT_POSE','index':job['index'],")
src=src.replace("representative=bodies[job['instances'][0]];world=[]", "representative=bodies[job['instances'][0]];world=[];dpose=d0")
src=src.replace("center=rot@np.asarray(d9['COM_local_mm'])+tmm", "center=rot@np.asarray(dpose['COM_local_mm'])+tmm")
src=src.replace('pw,dw=props(transformed,1e-9,center.tolist())', 'pw,dw=props(transformed,None,center.tolist())')
src=src.replace("target_I=rot@np.asarray(d9['I_COM_local_mm5'])@rot.T", "target_I=rot@np.asarray(dpose['I_COM_local_mm5'])@rot.T")
src=src.replace("verr=abs(dw['volume_mm3']-d9['volume_mm3'])/d9['volume_mm3']", "verr=abs(dw['volume_mm3']-dpose['volume_mm3'])/dpose['volume_mm3']")
src=src.replace("I_origin=target_I+d9['volume_mm3']", "I_origin=target_I+dpose['volume_mm3']")
src=src.replace("'actual_BRep_rigid_placement_reintegrated':True", "'actual_BRep_rigid_placement_reintegrated':True,'pose_check_integration_method':'default face quadrature against default local integrals; primary GK checked by algebra in collector'")
(M/'tools/read_material_inertia_v2.py').write_text(src,encoding='utf-8')
