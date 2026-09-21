"""Release only this run's empty SolidWorks session between bounded CAD stages."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import val,R,write
def main(sw,t,job):
 session=json.loads((R/'results/SW_SESSION.json').read_text(encoding='utf-8'))
 assert session['mode']=='launched_for_WP05'
 assert val(sw,'GetProcessID')==session['sw_pid']
 count=val(sw,'GetDocumentCount');assert count==0,('Will not exit with open documents',count)
 receipt={'status':'OWN_EMPTY_SESSION_EXIT_REQUESTED','session':session,'document_count':count,'time':time.time()}
 write(R/'results'/('SW_CLEAN_EXIT_'+str(session['sw_pid'])+'.json'),receipt)
 sw.ExitApp()
 return receipt
