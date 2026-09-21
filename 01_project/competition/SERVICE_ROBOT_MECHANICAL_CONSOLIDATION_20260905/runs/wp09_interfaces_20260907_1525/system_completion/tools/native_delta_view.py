"""Independent read-only Large Design Review image; never changes CAD cold credit."""
from pathlib import Path
import sys,json,argparse,importlib.util,traceback,psutil
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];D=C/'cad';R=C/'results'
sp=importlib.util.spec_from_file_location('native_view_helper',C.parent/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);a=ap.parse_args()
out=R/f'NATIVE_DELTA_VIEW_{a.state}.json';assert not out.exists()
target=D/f'WP09D_{a.state.upper()}.SLDASM';cold=R/f'NATIVE_DELTA_COLD_{a.state}.json';j=json.loads(cold.read_text());assert j['status']=='PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES'
digest=j['native_sha256'];assert m.sha(target)==digest
r={'status':'RUNNING','mode':'view','state':a.state,'progress':[],'parts':[],'save_attempts':[],'native_sha256':digest,'cold_receipt':str(cold),'cold_receipt_sha256':m.sha(cold),'open_policy':'swOpenDocOptions_Silent|ViewOnly (1|4); separate Large Design Review visualization, no geometry/motion validation credit'};b=None
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents();r['owned_sw_pid']=int(m.val(sw,'GetProcessID'));r['preflight_available_mib']=psutil.virtual_memory().available/2**20;assert r['preflight_available_mib']>=2048
 sw.UserControl=True;sw.DocumentVisible(True,2);opened=sw.OpenDoc6(str(target),2,5,'',0,0);r.update(open_errors=opened[1],open_warnings=opened[2]);assert opened[0] is not None and opened[1]==0
 model=b.wrap(opened[0],'IModelDoc2');b.activate(model,target);r['is_view_only']=bool(m.val(model,'IsOpenedViewOnly'));assert r['is_view_only']
 model.ShowNamedView2('',7);model.ViewZoomtofit2();model.GraphicsRedraw2();bmp=D/f'WP09D_{a.state.upper()}.bmp';assert not bmp.exists();ok=bool(model.SaveBMP(str(bmp),1600,1200));assert ok and bmp.exists()
 r['native_view_capture']={'path':str(bmp),'api_ok':ok,'native_sha256':digest,'sha256':m.sha(bmp),'bytes':bmp.stat().st_size,'view':'ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_ISOMETRIC_IMAGE_ONLY'}
 assert m.sha(target)==digest and m.sha(cold)==r['cold_receipt_sha256'];sw.CloseDoc(m.val(model,'GetTitle'));assert not b.documents();sw.ExitApp();r.update(status='PASS_ACTUAL_NATIVE_LARGE_DESIGN_REVIEW_IMAGE',open_documents_after=[]);b.checkpoint('completed_view_only_closed_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
