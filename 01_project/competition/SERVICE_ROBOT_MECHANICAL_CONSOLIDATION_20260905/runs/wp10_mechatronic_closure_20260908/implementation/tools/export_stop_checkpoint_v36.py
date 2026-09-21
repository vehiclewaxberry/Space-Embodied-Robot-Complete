"""Fresh native exports bound to unchanged current sources; separate from legacy ERC.

Run under native_delta_guard. Each --tag is a new immutable evidence directory.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess,xml.etree.ElementTree as ET
from erc_source_contract import parse,children,properties,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';R=A/'results/stop_v36/pcb'
CLI=A.parents[4]/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
# Resolve the workspace by its directory, not a user's global KiCad installation.
CLI=next(p for p in A.parents if (p/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe').is_file())/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def xml(path):
    rt=ET.parse(path).getroot()
    return {c.get('ref'):c for c in rt.findall('./components/comp')},{(n.get('ref'),n.get('pin')):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);tag=ap.parse_args().tag
    assert tag.replace('_','').isalnum()
    out=R/('native_checkpoint_'+tag);out.mkdir(exist_ok=False)
    files=sorted({*D.glob('*.kicad_sch'),*D.glob('*.kicad_sym'),*D.glob('*.kicad_pro'),*D.glob('*.pretty/*.kicad_mod'),D/'sym-lib-table',D/'fp-lib-table'})
    before={str(p):sha(p) for p in files}
    receipt=dict(schema='WP10_V36_NATIVE_EXPORT_FRESHNESS',started=datetime.datetime.now().astimezone().isoformat(),source_before=before,commands=[],status='STARTED')
    dump(out/'EXPORT_RECEIPT.json',receipt)
    commands=[('NETLIST',[str(CLI),'sch','export','netlist','--format','kicadxml','--output',str(out/'wp10_system.xml'),str(D/'wp10_system.kicad_sch')]),
              ('ERC',[str(CLI),'sch','erc','--format','json','--severity-error','--severity-warning','--exit-code-violations','--output',str(out/'SYSTEM_ERC.json'),str(D/'wp10_system.kicad_sch')])]
    for name,cmd in commands:
        q=subprocess.run(cmd,cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=170)
        (out/(name+'.stdout.log')).write_text(q.stdout,encoding='utf-8');(out/(name+'.stderr.log')).write_text(q.stderr,encoding='utf-8')
        receipt['commands'].append(dict(kind=name,argv=cmd,returncode=q.returncode));dump(out/'EXPORT_RECEIPT.json',receipt)
        if name=='NETLIST' and q.returncode:raise RuntimeError(q.stderr)
    after={str(p):sha(p) for p in files};receipt['source_after']=after
    receipt['source_unchanged_during_export']=before==after
    cs,pins=xml(out/'wp10_system.xml');oldc,oldpins=xml(D/'wp10_system.xml')
    erc=json.loads((out/'SYSTEM_ERC.json').read_text());vs=[v for s in erc['sheets'] for v in s['violations']]
    parent=json.loads((A/'results/stop_v36/PARENT_SOURCE_LOCK.json').read_text())
    parts=json.loads((R/'PHYSICAL_PARTS.json').read_text())
    root=parse((D/'wp10_system.kicad_sch').read_text());rid='/'+node_uuid(root)
    expected_paths={rid}|{rid+'/'+node_uuid(s) for s in children(root,'sheet')}
    missing_fp=[r for r,p in parts.items() if r not in cs or cs[r].findtext('footprint')!=p['footprint']]
    expected_j={str(i):('WP10_BRAKE_TEMP_'+str((i+1)//2) if i%2 else 'WP10_ARM_RETURN') for i in range(1,7)}
    actual_refs={properties(s)['Reference'] for p in D.glob('*.kicad_sch') for s in children(parse(p.read_text()),'symbol') if not properties(s)['Reference'].startswith('#')}
    checks=dict(source_unchanged_during_native_export=before==after,commands_succeeded=all(x['returncode']==0 for x in receipt['commands']),
      source_refs_equal_native_refs=set(cs)==actual_refs,only_J106_added_to_prior_native=set(cs)==set(oldc)|{'J106'},
      old_pin_connections_preserved=all(pins.get(k)==v for k,v in oldpins.items()),only_six_J106_pins_added=set(pins)-set(oldpins)=={('J106',str(i)) for i in range(1,7)},
      J106_six_sensor_pins_correct=all(pins.get(('J106',p))==net for p,net in expected_j.items()),
      all_94_selected_footprints_in_native=len(parts)==94 and not missing_fp,
      parent70_files_unchanged=all(sha(p)==h for p,h in parent.items()),
      ERC_sheets_match_hierarchy={s['uuid_path'] for s in erc['sheets']}==expected_paths and len(erc['sheets'])==15,
      ERC_zero_errors_warnings=not vs,
      ERC_severity_scope=set(erc.get('included_severities',[]))=={'error','warning'},
      ERC_ignored_rules_unchanged=erc.get('ignored_checks',[])==json.loads((A/'results/aux_v35/SYSTEM_ERC.json').read_text()).get('ignored_checks',[]),
      formal_pointer_V35=json.loads((A/'CURRENT_WORKING_CANDIDATE.json').read_text())['revision']=='V35')
    # Regression: the old validator must reject changed sources before overwriting evidence.
    old_outputs=[A/'results/stop_v36'/x for x in ['SOURCE_VERIFICATION.json','CALCULATIONS.json','V36_SYSTEM_BOM.csv','V36_PIN_NETS.csv']]
    oldhash={str(p):sha(p) for p in old_outputs}
    import sys
    q=subprocess.run([sys.executable,'-B',str(A/'tools/audit_stop_v36.py')],capture_output=True,text=True,encoding='utf-8',errors='replace',cwd=A)
    checks['legacy_validator_rejects_stale_before_writes']=q.returncode!=0 and 'STALE_NATIVE_INPUTS' in q.stderr and all(sha(p)==h for p,h in oldhash.items())
    (out/'LEGACY_VALIDATOR_REJECTION.txt').write_text(q.stderr,encoding='utf-8')
    receipt.update(status='COMPLETED',finished=datetime.datetime.now().astimezone().isoformat(),outputs={str(p):sha(p) for p in [out/'wp10_system.xml',out/'SYSTEM_ERC.json']})
    dump(out/'EXPORT_RECEIPT.json',receipt)
    result=dict(schema='WP10_V36_PHYSICAL_MAPPING_CHECKPOINT',scope='Fresh current-source ERC and94selected footprint mapping ONLY',checks=checks,scoped_check_passed=all(checks.values()),electrical_refs=len(cs),pin_records=len(pins),board_selected_refs=len(parts),missing_footprints=missing_fp,ERC_errors=sum(v['severity']=='error' for v in vs),ERC_warnings=sum(v['severity']=='warning' for v in vs),violations=vs,STOP_PCB_implemented=False,whole_design_complete=False,hardware_tests=0,
        source_bindings=before,evidence_bindings={str(out/'EXPORT_RECEIPT.json'):sha(out/'EXPORT_RECEIPT.json'),**receipt['outputs'],str(Path(__file__)):sha(Path(__file__))})
    dump(out/'CHECKPOINT_VERIFICATION.json',result)
    print(json.dumps({k:result[k] for k in ['scoped_check_passed','electrical_refs','pin_records','board_selected_refs','ERC_errors','ERC_warnings','checks']},ensure_ascii=False))
    assert result['scoped_check_passed'],'Inspect checkpoint violations; do not promote formal revision'
if __name__=='__main__':main()
