"""Resume after the generic assembly self-intersection resource failure.

Only the generic assembly self-intersection pass is omitted. Per-solid BRep
checks and explicit neighboring-component intersections have separate receipts.
No software check is upgraded to a full mechanical validation.
"""
from pathlib import Path
import json,subprocess,sys
A=Path(__file__).resolve().parents[1];cad='F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
commands=[('source_instance_plan',['tools/prepare_fixed_heat_integration.py']),('thermal',['tools/fixed_radiator_budget.py'])]
for stem in ['fixed_heat_installation','upper_deck_relocated','propulsion_power_route','propulsion_data_route','fixed_heat_bay']:
    commands.append((stem+'_refs',[cad+'/inspect','refs','mechanical/'+stem+'.step','--facts','--planes','--positioning']))
    args=[cad+'/inspect','validate','mechanical/'+stem+'.step']
    if stem in ['fixed_heat_installation','fixed_heat_bay']:args+=['--skip-self-intersection']
    commands.append((stem+'_bounded_validate',args))
    commands.append((stem+'_snapshot',[cad+'/snapshot','--job',str(A/'review'/f'{stem}_snapshot.json')]))
out=dict(generic_assembly_self_intersection='INCOMPLETE_MEMORY_GUARD_NO_PASS_CREDIT',per_solid_and_interface_checks_separate=True,commands=[])
for name,args in commands:
    r=subprocess.run([sys.executable,'-B','-X','utf8',*args],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (A/'logs'/f'fixed_heat_resume_{name}.stdout.log').write_text(r.stdout,encoding='utf-8')
    (A/'logs'/f'fixed_heat_resume_{name}.stderr.log').write_text(r.stderr,encoding='utf-8')
    out['commands'].append(dict(name=name,returncode=r.returncode,args=args))
    (A/'results/FIXED_HEAT_BOUNDED_REVIEW_SEQUENCE.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(name,r.returncode,flush=True)
    if r.returncode:break
assert len(out['commands'])==len(commands) and all(r['returncode']==0 for r in out['commands']),out
