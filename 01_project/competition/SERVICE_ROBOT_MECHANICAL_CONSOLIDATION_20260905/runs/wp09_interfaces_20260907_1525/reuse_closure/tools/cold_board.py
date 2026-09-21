from pathlib import Path
import json,sys,importlib.util
sys.dont_write_bytecode=True
N=Path(__file__).resolve().parents[1];R=N.parent
sp=importlib.util.spec_from_file_location('frozen_board_helper',R.parent/'wp09_electro_propulsion_20260907_1350/tools/build_module_native.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
p=N/'mechanical/native/RS422_GSE_SPLICE_BOARD.SLDPRT';out=N/'results/NATIVE_BOARD.json';r=dict(status='RUNNING',progress=[],save_attempts=[],path=str(p),native_sha256=m.sha(p),physical_release=False);b=m.ModuleBuilder(out,r)
try:
 docs=b.documents();assert len(docs)==1 and m.normalized(docs[0][1]['path'])==m.normalized(str(p)) and not docs[0][1]['dirty']
 b.close_own_saved(docs[0][0],p,r['native_sha256']);opened=b.sw.OpenDoc6(str(p),1,3,'',0,0);assert opened[0] is not None and opened[1]==0
 cold=b.wrap(opened[0],'IModelDoc2');b.activate(cold,p);part=b.wrap(cold,'IPartDoc');bs=part.GetBodies2(0,False) or [];assert len(bs)==1
 body=b.wrap(bs[0],'IBody2');r['actual_solids']=len(bs);r['body_box_m']=list(body.GetBodyBox());r['roundtrip']=b.save_new(cold,N/'mechanical/RS422_GSE_BOARD_roundtrip.step')
 b.close_own_saved(cold,p,r['native_sha256']);assert not b.documents();b.sw.ExitApp();assert m.sha(p)==r['native_sha256']
 r['status']='PASS_COLD_NATIVE_ONE_BODY_PENDING_BREP_EQUIVALENCE';b.checkpoint('completed')
finally:b.pythoncom.CoUninitialize()
