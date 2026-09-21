"""Adversarial release-precondition checks, executing only the pre-write prefix."""
from pathlib import Path
from unittest.mock import patch
import ast,copy,json,hashlib,sys
A=Path(__file__).resolve().parents[1];P=A/'tools/publish_cap_terminal_revision.py'
tree=ast.parse(P.read_text(encoding='utf-8'));prefix=[]
for node in tree.body:
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='dump':break
    prefix.append(node)
else:raise AssertionError('Missing first publication write boundary')
code=compile(ast.Module(body=prefix,type_ignores=[]),str(P),'exec')
original=Path.read_text;results=[]
def exercise(name,target=None,mutation=None):
    def altered(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        if target and path.resolve()==(A/target).resolve():
            value=json.loads(text);mutation(value);return json.dumps(value)
        return text
    rejected=False
    try:
        with patch.object(Path,'read_text',altered),patch.object(sys,'argv',[str(P)]):exec(code,{'__file__':str(P),'__name__':'__publication_preflight__'})
    except AssertionError:rejected=True
    assert rejected==(mutation is not None),name
    results.append(dict(name=name,correctly_rejected=rejected,baseline_success=mutation is None))
exercise('actual_current_inputs_accepted')
exercise('MCP_error_response_rejected','results/ERC_MCP_CROSSCHECK.json',lambda v:v['result'].update(isError=True))
exercise('MCP_nonzero_violation_rejected','results/ERC_MCP_CROSSCHECK.json',lambda v:v['result']['content'][0].update(text='ERC result: 1 violation(s)\n  Errors: 1  Warnings: 0  Info: 0'))
exercise('CLI_failed_command_rejected','results/POWER_LOOP_VERIFICATION.json',lambda v:v.update(ERC_command_succeeded=False))
exercise('CLI_empty_sheet_report_rejected','results/POWER_LOOP_ERC.json',lambda v:v.update(sheets=[]))
exercise('CAD_empty_result_set_rejected','results/CAP_TERMINAL_CAD_PCB_V17.json',lambda v:v.update(results=[]))
exercise('SHOT_duplicate_JSON_without_image_rejected','results/CAP_TERMINAL_CAD_PCB_SHOT_V17.json',lambda v:v.update(results=[v['results'][0],copy.deepcopy(v['results'][0])]))
exercise('SHOT_wrong_published_image_rejected','results/CAP_TERMINAL_CAD_ASSEMBLY_SHOT_V17.json',lambda v:v['results'][1].update(image='review/C203_PCB_V17.png'))
files=['tools/publish_cap_terminal_revision.py','tools/test_cap_terminal_publication.py','results/CAP_TERMINAL_VISUAL_REVIEW_V17.json','results/ERC_MCP_CROSSCHECK.json','results/CAP_TERMINAL_CAD_PCB_V17.json','results/CAP_TERMINAL_CAD_ASSEMBLY_V17.json','results/CAP_TERMINAL_CAD_PCB_SHOT_V17.json','results/CAP_TERMINAL_CAD_ASSEMBLY_SHOT_V17.json','results/CAP_TERMINAL_LAYOUT_EXPORT_V17.json']
out=dict(schema='WP10_V17_PUBLICATION_PREFLIGHT_REGRESSION',passed=True,test_count=len(results),tests=results,publication_writes_executed=False,inputs={p:hashlib.sha256((A/p).read_bytes()).hexdigest() for p in files})
(A/'results/CAP_TERMINAL_PUBLICATION_TESTS_V17.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,tests=len(results),publication_writes_executed=False)))
