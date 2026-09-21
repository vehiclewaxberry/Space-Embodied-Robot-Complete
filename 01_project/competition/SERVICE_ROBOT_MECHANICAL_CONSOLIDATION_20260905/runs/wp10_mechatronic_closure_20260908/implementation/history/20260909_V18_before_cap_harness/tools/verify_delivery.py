from pathlib import Path
import json,csv,xml.etree.ElementTree as ET,hashlib,subprocess,math
A=Path(__file__).resolve().parents[1];E=A/'ecad';R=A.parents[5];exe=R/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
checks=[]
def ck(n,b,**d):checks.append(dict(name=n,passed=bool(b),**d))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
for args in [['sch','export','netlist','--format','kicadxml','-o',str(E/'wp10_converter_reference.xml')],['sch','export','pdf','-o',str(E/'wp10_converter_reference.pdf')],['sch','erc','--format','json','-o',str(A/'results/POWER_ERC.json')]]:
 p=subprocess.run([str(exe),*args,str(E/'wp10_converter_reference.kicad_sch')],capture_output=True,text=True,encoding='utf-8',errors='replace');ck('kicad_'+args[1]+'_'+args[2],p.returncode==0,stdout=p.stdout,stderr=p.stderr)
root=ET.parse(E/'wp10_converter_reference.xml').getroot();components=root.findall('./components/comp');mapping=json.loads((E/'wp10_converter_reference_ENDPOINT_MAP.json').read_text());actual={}
for net in root.findall('./nets/net'):
 for nd in net.findall('node'):actual[(nd.get('ref'),nd.get('pin'))]=net.get('name').split('/')[-1]
for ep,m in mapping.items():
 if ep=='CHB500W_24S24N.7':
  ck('trim_unused',not actual.get((m['ref'],m['pin'])) or actual[(m['ref'],m['pin'])].startswith('unconnected'))
 else:ck('native_pin_'+ep,actual.get((m['ref'],m['pin']))==m['net'])
ck('no_nonexistent_standard_pins',set(root.findall('./components/comp')[0].findall('fields/field')) is not None and 'CHB500W_24S24N.3' not in mapping and 'CHB500W_24S24N.10' not in mapping)
ck('input_output_returns_separate',mapping['CHB500W_24S24N.4']['net']!=mapping['CHB500W_24S24N.5']['net'])
v=[v for s in json.loads((A/'results/POWER_ERC.json').read_text())['sheets'] for v in s['violations']]
ck('ERC_only_two_declared_unpowered_input_boundaries',len(v)==2 and all(x['type']=='power_pin_not_driven' for x in v))
ck('no_power_flag_fabrication','PWR_FLAG' not in (E/'wp10_converter_reference.kicad_sch').read_text())
b=json.loads((A/'power/POWER_BUDGET_SCREEN.json').read_text());ck('low_voltage_failure_retained',b['cases'][0]['conditional_pass_at_eta_0_9'] is False)
ck('stop_transient_conflict_retained',b['transient_5pct_with_static_screen'][0]<23.04 and b['transient_5pct_with_static_screen'][1]>24.96)
parent=json.loads((A.parent/'mechanical_intake/PARAMETER_PACKET.json').read_text());child=json.loads((A/'mechanical/PARAMETER_PACKET.json').read_text())
for x,y in zip(parent['instances'],child['instances']):
 ck('preserve_mass_geometry_'+x['id'],all(x[k]==y[k] for k in ['id','mass','center_of_mass_local','inertia_about_COM_local','geometry_by_state']))
assert all(x['passed'] for x in checks),[x for x in checks if not x['passed']]
dump(A/'results/DELTA_SOURCE_VERIFICATION.json',{'all_checks_passed':True,'count':len(checks),'checks':checks,'whole_mechatronic_closure':False,'erc_clean':False,'ERC_open_input_boundaries':2,'native_ECAD_components':len(components)})
print(json.dumps({'passed':len(checks),'native_ECAD_components':len(components),'ERC_open':len(v),'full_system_closed':False}))
