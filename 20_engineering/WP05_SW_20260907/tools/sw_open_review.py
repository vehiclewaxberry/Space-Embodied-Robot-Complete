"""Open the already verified service assembly for the user without changing files."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import R,wrap,val,sha,write
def main(sw,t,job):
 receipt=json.loads((R/'results/WP05_ROBOT_SERVICE_COLD.json').read_text(encoding='utf-8'))
 path=Path(receipt['target']);assert sha(path)==receipt['target_sha256']
 sw.Visible=True;sw.UserControl=True;sw.DocumentVisible(True,2)
 q=sw.OpenDoc6(str(path),2,193,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0
 sw.ActivateDoc3(val(m,'GetTitle'),False,0,0)
 active=wrap(val(sw,'ActiveDoc'),'IModelDoc2',t);assert Path(val(active,'GetPathName')).resolve()==path.resolve()
 active.ClearSelection2(True);active.ShowNamedView2('',7);active.ViewZoomtofit2();active.GraphicsRedraw2()
 result={'status':'VERIFIED_ASSEMBLY_OPEN_FOR_USER','path':str(path),'sha256':sha(path),'open_errors':q[1],'open_warnings':q[2],'component_count':len(wrap(active,'IAssemblyDoc',t).GetComponents(True) or []),'native_file_unchanged':sha(path)==receipt['target_sha256']}
 try:
  import win32gui
  frame=wrap(sw.Frame(),'IFrame',t);handle=frame.GetHWnd()
  win32gui.ShowWindow(handle,3);win32gui.SetForegroundWindow(handle)
  result['foreground_requested']=True
 except Exception as error:result['foreground_error']=repr(error)
 assert result['component_count']==585 and result['native_file_unchanged']
 write(R/'results/USER_OPEN_RECEIPT.json',result)
 return result
