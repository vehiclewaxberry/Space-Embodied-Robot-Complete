"""Check the actual SolidWorks row-vector convention with a known 90 degree case."""
from pathlib import Path
import sys,pythoncom
from win32com.client import VARIANT
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import wrap,R,write
def main(sw,t,job):
 u=wrap(sw.GetMathUtility(),'IMathUtility',t)
 transform=wrap(u.CreateTransform(VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,[0.,1.,0.,-1.,0.,0.,0.,0.,1.,1.,2.,3.,1.,0.,0.,0.])),'IMathTransform',t)
 p=wrap(u.CreatePoint(VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,[.01,0.,0.])),'IMathPoint',t)
 world=wrap(p.MultiplyTransform(transform),'IMathPoint',t)
 observed=[x*1000 for x in world.ArrayData];expected=[1000.,2010.,3000.]
 error=max(abs(x-y) for x,y in zip(observed,expected))
 result={'status':'PASS' if error<=1e-5 else 'FAIL','known_rotation_degrees':90,'axis':'Z','local_mm':[10,0,0],'translation_mm':[1000,2000,3000],'observed_world_mm':observed,'expected_world_mm':expected,'max_error_mm':error,'method':'Actual SolidWorks IMathPoint.MultiplyTransform'}
 write(R/'results/NATIVE_MATH_CONVENTION_CHECK.json',result)
 assert result['status']=='PASS',result
 return result
