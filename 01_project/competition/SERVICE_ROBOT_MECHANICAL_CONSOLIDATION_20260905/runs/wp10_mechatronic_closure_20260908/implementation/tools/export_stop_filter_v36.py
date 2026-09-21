"""Fresh full-system native export for the explicit nine-part thermal filter delta."""
from pathlib import Path
import argparse,csv,datetime,json,subprocess
from export_stop_checkpoint_v36 import A,D,CLI,sha,dump,xml
from erc_source_contract import parse,children,properties,node_uuid
P=A/'results/stop_v36/pcb';R=P/'thermal_filter_20260916'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);tag=ap.parse_args().tag
    assert tag.replace('_','').isalnum()
    out=R/('native_'+tag);out.mkdir(exist_ok=False)
    spec=json.loads((R/'FILTER_INTENT.json').read_text());parts=json.loads((P/'PHYSICAL_PARTS.json').read_text());calc=json.loads((R/'CALCULATIONS.json').read_text())
    files=sorted({*D.glob('*.kicad_sch'),*D.glob('*.kicad_sym'),*D.glob('*.kicad_pro'),*D.glob('*.pretty/*.kicad_mod'),D/'sym-lib-table',D/'fp-lib-table',
       P/'PHYSICAL_PARTS.json',P/'BOARD_SCOPE.json',R/'FILTER_INTENT.json',R/'DELTA_PARTS.json',R/'CALCULATIONS.json',R/'PARENT_BINDING.json',Path(spec['prior_native']),Path(__file__)})
    before={str(p):sha(p) for p in files}
    receipt=dict(started=datetime.datetime.now().astimezone().isoformat(),source_before=before,commands=[],status='STARTED');dump(out/'EXPORT_RECEIPT.json',receipt)
    commands=[('NETLIST',[str(CLI),'sch','export','netlist','--format','kicadxml','--output',str(out/'wp10_system.xml'),str(D/'wp10_system.kicad_sch')]),
       ('ERC',[str(CLI),'sch','erc','--format','json','--severity-error','--severity-warning','--exit-code-violations','--output',str(out/'SYSTEM_ERC.json'),str(D/'wp10_system.kicad_sch')])]
    for name,cmd in commands:
        q=subprocess.run(cmd,cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=170)
        (out/(name+'.stdout.log')).write_text(q.stdout,encoding='utf-8');(out/(name+'.stderr.log')).write_text(q.stderr,encoding='utf-8')
        receipt['commands'].append(dict(kind=name,argv=cmd,returncode=q.returncode));dump(out/'EXPORT_RECEIPT.json',receipt)
        if name=='NETLIST' and q.returncode:raise RuntimeError(q.stderr)
    after={str(p):sha(p) for p in files}
    cs,pins=xml(out/'wp10_system.xml');oldc,oldpins=xml(spec['prior_native'])
    expected=dict(oldpins)
    for endpoint,net in {**spec['expected_added_pins'],**spec['expected_changed_existing_pins']}.items():
        ref,pin=endpoint.rsplit('.',1);expected[(ref,pin)]=net
    def wrong(n):return [{'endpoint':'.'.join(k),'actual':n.get(k),'expected':v} for k,v in expected.items() if n.get(k)!=v]+[{'extra':'.'.join(k)} for k in n.keys()-expected.keys()]
    errors=wrong(pins)
    erc=json.loads((out/'SYSTEM_ERC.json').read_text());vs=[v for s in erc['sheets'] for v in s['violations']]
    rt=parse((D/'wp10_system.kicad_sch').read_text());rid='/'+node_uuid(rt);paths={rid}|{rid+'/'+node_uuid(s) for s in children(rt,'sheet')}
    actual_refs={properties(s)['Reference'] for p in D.glob('*.kicad_sch') for s in children(parse(p.read_text()),'symbol') if not properties(s)['Reference'].startswith('#')}
    missing_fp=[r for r,p in parts.items() if r not in cs or cs[r].findtext('footprint')!=p['footprint']]
    wrong_mpn=[r for r,p in parts.items() if r not in cs or cs[r].findtext("./fields/field[@name='MPN']")!=p['MPN']]
    oldlock=json.loads((A/'results/stop_v36/PARENT_SOURCE_LOCK.json').read_text())
    negative=[]
    for name,key,bad in [('series_filter_bypass',('U311','3'),'WP10_BRAKE_TEMP_1'),('wrong_cap_supply',('C314','2'),'WP10_BRAKE_STOP_3V3'),('open_input_filter_swapped',('C315','1'),'WP10_BRAKE_TEMP_1'),('wrong_remote_pair',('J106','3'),'WP10_BRAKE_TEMP_1')]:
        n=dict(pins);n[key]=bad;negative.append(dict(name=name,detected=bool(wrong(n))))
    checks=dict(source_unchanged_during_export=before==after,commands_succeeded=all(x['returncode']==0 for x in receipt['commands']),
       native_refs_exact_source=set(cs)==actual_refs,nine_new_refs_only=set(cs)==set(oldc)|set(spec['expected_added_refs']) and len(cs)==249,
       exact795_pin_connections=len(pins)==795 and not errors,
       existing_component_values_and_footprints_preserved=all((cs[r].findtext('value'),cs[r].findtext('footprint'))==(c.findtext('value'),c.findtext('footprint')) for r,c in oldc.items()),
       all103_selected_FPs_and_MPNs_match=len(parts)==103 and not missing_fp and not wrong_mpn,
       parent70_files_unchanged=all(sha(p)==h for p,h in oldlock.items()),
       ERC15_sheets={s['uuid_path'] for s in erc['sheets']}==paths and len(erc['sheets'])==15,
       ERC_zero_errors_warnings=not vs,ERC_scope=set(erc.get('included_severities',[]))=={'error','warning'},
       ERC_ignored_unchanged=erc.get('ignored_checks',[])==json.loads((A/'results/aux_v35/SYSTEM_ERC.json').read_text()).get('ignored_checks',[]),
       calculated_filter_model_pass=calc['calculation_passed'] and all(sha(p)==h for p,h in calc['source_bindings'].items()),
       negative_connection_controls_detected=all(x['detected'] for x in negative))
    receipt.update(status='COMPLETED',finished=datetime.datetime.now().astimezone().isoformat(),source_after=after,source_unchanged=before==after,outputs={str(p):sha(p) for p in [out/'wp10_system.xml',out/'SYSTEM_ERC.json']});dump(out/'EXPORT_RECEIPT.json',receipt)
    result=dict(scope='Same current source nine-part filter connectivity + selected footprint mapping + conditional RC + ERC',scoped_pass=all(checks.values()),checks=checks,electrical_refs=len(cs),pin_records=len(pins),board_selected_refs=len(parts),ERC_errors=sum(v['severity']=='error' for v in vs),ERC_warnings=sum(v['severity']=='warning' for v in vs),violations=vs,pin_errors=errors,missing_footprints=missing_fp,wrong_MPNs=wrong_mpn,negative_controls=negative,source_bindings=before,evidence_bindings={str(out/'EXPORT_RECEIPT.json'):sha(out/'EXPORT_RECEIPT.json'),**receipt['outputs']},STOP_PCB_implemented=False,whole_design_complete=False,hardware_tests=0)
    dump(out/'VERIFICATION.json',result)
    for name,header,rows in [('SYSTEM_BOM.csv',['Reference','Value','Footprint','MPN'],[[r,c.findtext('value'),c.findtext('footprint'),c.findtext("./fields/field[@name='MPN']")] for r,c in sorted(cs.items())]),('PIN_NETS.csv',['Reference','Pin','Net'],[[r,p,n] for (r,p),n in sorted(pins.items())])]:
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
    print(json.dumps({k:result[k] for k in ['scoped_pass','electrical_refs','pin_records','board_selected_refs','ERC_errors','ERC_warnings','pin_errors','missing_footprints','wrong_MPNs','checks']},ensure_ascii=False))
    assert result['scoped_pass'],'Inspect fresh native evidence; no formal revision promotion'
if __name__=='__main__':main()
