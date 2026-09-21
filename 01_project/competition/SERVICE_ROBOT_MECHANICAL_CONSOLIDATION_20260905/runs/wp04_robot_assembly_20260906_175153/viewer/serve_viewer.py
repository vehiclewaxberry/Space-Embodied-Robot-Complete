"""Loopback-only static server restricted to the packaged viewer directory."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse,json
from urllib.parse import unquote,urlsplit
HERE=Path(__file__).resolve().parent
DELIVERABLES={
    '/deliverables/overview.md':'START_HERE_ZH.md',
    '/deliverables/assembly_procedure.md':'ASSEMBLY_PROCEDURE_ZH.md',
    '/deliverables/mechanical_inputs.md':'MECHANICAL_INPUT_REGISTER_ZH.md',
    '/deliverables/result.json':'results/WP04_RESULT.json',
    '/deliverables/system_interfaces.json':'contracts/SYSTEM_INTERFACES.json',
    '/deliverables/digital_body_contract.json':'contracts/DIGITAL_BODY_CONSUMER_CONTRACT.json',
    '/deliverables/release_state_contract.json':'contracts/RELEASE_STATE_CONTRACT.json',
    '/deliverables/BOM.csv':'candidate/BOM.csv',
    '/deliverables/design_parameters.json':'candidate/design_parameters.json',
    '/deliverables/structure_parking.step':'candidate/servicer_structure_parking.step',
    '/deliverables/structure_released.step':'candidate/servicer_structure_released.step',
    '/deliverables/structure_service.step':'candidate/servicer_structure_service.step',
}
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(HERE),**kwargs)
    def translate_path(self,path):
        request=unquote(urlsplit(path).path)
        if request in DELIVERABLES:return str(HERE.parent/DELIVERABLES[request])
        relative=request.lstrip('/')
        candidate=(HERE/relative).resolve()
        if not candidate.is_relative_to(HERE):return str(HERE/'__forbidden__')
        return str(candidate)
    def end_headers(self):
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);a=p.parse_args()
    s=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(json.dumps({'url':f'http://127.0.0.1:{a.port}/index.html','directory':str(HERE)},ensure_ascii=False),flush=True)
    s.serve_forever()
