"""Selected COTS chain plus pin-exact converter circuit; no energization release."""
from pathlib import Path
import json,csv,uuid,collections,ast,hashlib,shutil,subprocess,xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1];D=A.parent;R=D.parent/'wp09_interfaces_20260907_1525';E=A/'ecad';P=A/'power'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def q(s):return json.dumps(str(s),ensure_ascii=False)
def uid(s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'wp10-power-candidate:'+s))
def csvout(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
selection={'schema':'WP10_PUBLIC_SOURCE_POWER_SELECTION_V1','status':'SELECTED_ENGINEERING_CANDIDATE_NOT_CONNECTED_TO_OLD_STOP','battery':{'MPN':'RRC3570-4','PN':'110338','nominal_V':25.2,'energy_Wh':407.43,'continuous_A':30,'nominal_mass_kg':2.08,'dimensions_max_mm':[189.5,85.5,82.2],'minimum_terminal_V':None,'source':'rrc3570_4.pdf p4-5'},'manager':{'MPN':'RRC-PMM35','PN':'110297','input_V':[19,24],'battery_discharge_A':20,'charge_max_V':29.4,'charge_max_A':6,'charge_max_W':180,'logic_header_positions':6,'logic_3V3_supply_max_mA':3,'single_power_contact_A':10,'public_hole_centers_mm':None,'public_SMBus_registers':None,'source':'pmm35.pdf A p2-3; supersedes inconsistent webpage 5-pin summary'},'converter':{'MPN':'CHB500W-24S24N','quantity':1,'rated_V':24,'rated_A':21,'input_V':[9.5,40],'logic':'NEGATIVE; open=OFF; connect pin2 to pin4=ON; input-referenced','parallel':False,'mounting':'4 M3x0.5 inserts; standard mechanical OEM STEP','efficiency_full_operating_range_min':None,'output_reverse_current_allowed':False,'source':'cincon_chb500w.pdf V12; chb500w_application.pdf V13'},'integration':{'old_D_99_ref_system_unchanged':True,'old_873_assembly_unchanged':True,'candidate_new_sources':['mechanical/converter_carrier.step.py','mechanical/converter_installation.step.py','ecad/wp10_converter_reference.kicad_sch','ecad/PMM35_TOPVIEW_ENDPOINTS.csv'],'energization_allowed':False,'orbit_power_closed':False,'flight_qualified':False},'decision_basis':['single protected pack removes MB2590 pair coupling','single 21A output module removes i7C current-sharing dependency','battery has manufacturer-listed matching PMM35 charging ecosystem','store more energy without claiming solar replenishment or minimum usable energy','module-level COTS reused; adapter carrier is project responsibility'],'known_blockers':['PMM35 loaded output-voltage floor and 20A continuous operating envelope not specified; source switching transient unknown','PMM application note command addresses, GPIO/NRST semantics, Sys-Press/Sys- detection and exact mating pin numbering not public','input fuse/inrush/precharge/filter/TVS coordination remains design responsibility; 80A converter reference fuse cannot protect 20A PMM harness','output reverse blocker and regen clamp must prevent CHB output backfeed; clamp pulsed energy/time remains unbound','CHB +/-5% transient can exceed existing STOP J101.3 23.04..24.96V; stopboard supply cannot inherit old proof','charging from star P60/PDU is not connected: 19..24V input incompatible with 12V branch; source power budget/charger input limiting not yet designed','battery retention, PMM holes, whole-bay collision and conductive thermal rejection remain open']}
dump(P/'POWER_CHAIN_SELECTION.json',selection)
budget={'screen_arm_W':360.,'known_contactor_W':6.8,'new_aux_allowance_W':10.,'aux_allowance_identity':'NEW_DESIGN_ALLOCATION_NOT_MEASURED','output_allocated_W':376.8,'load_profile_confirmed':False,'cases':[]}
for v in [19.,20.,21.,22.,25.2,29.4]:
 budget['cases'].append({'loaded_input_V_assumed':v,'eta_needed_at_PMM20A':376.8/(20*v),'input_A_if_eta_0_9':376.8/(.9*v),'conditional_pass_at_eta_0_9':376.8/(.9*v)<=20})
budget.update(ideal_time_min_no_reserve=407.43/376.8*60,screen_time_min_eta_0_9_80pct_energy=407.43*.9*.8/376.8*60,screen_time_not_guaranteed=True,full_output_current_A=376.8/24,converter_capacity_utilization=376.8/(24*21),static_voltage_GSE0to50_C_screen=[24*(1-.019),24*(1+.019)],transient_5pct_with_static_screen=[24*(1-.019)*.95,24*(1+.019)*1.05],old_stop_input_interval_V=[23.04,24.96],static_bound_does_not_cover_dynamic_or_ripple=True,thermal_loss_W_at_eta09=376.8*(1/.9-1),converter_case_to_sink_required_K_per_W_for_90C_case_50C_sink=(90-50)/(376.8*(1/.9-1)),thermal_values_are_scenarios_not_guarantees=True)
dump(P/'POWER_BUDGET_SCREEN.json',budget)
# Drawing-position IDs are explicitly NOT JST or manufacturer pin numbers.
pmm=[]
for group,signals in [('PWR_LEFT_2',['VIN','GND']),('PWR_MIDDLE_4',['GND','VIN','VOUT','GND']),('PWR_RIGHT_2',['GND','VOUT']),('UI_6',['3V3_MAX3mA','SDA','SCL','GPIO1_NRST','GPIO2','GND']),('BATTERY_6',['VBAT+','SCL','SDA','SYS_PRESS','SYS_MINUS','VBAT-'])]:
 for i,signal in enumerate(signals,1):pmm.append({'drawing_group':group,'position_left_to_right_in_manufacturer_component_side_figure':i,'signal':signal,'manufacturer_pin_number':'UNPUBLISHED_NOT_INFERRED','source':'pmm35.pdf page3','cut_or_crimp_release':False})
csvout(E/'PMM35_TOPVIEW_ENDPOINTS.csv',pmm)
# The input/output conditioning boundaries stay OPEN; not falsified as ideal devices.
modules=collections.OrderedDict([('CHB500W_24S24N',['1','2','4','5','6','7','8','9']),('C_INPUT_2200u_100V',['+','-']),('C_OUT_POLY_10u_50V',['+','-']),('C_OUT_CER_1u_50V',['1','2']),('INPUT_AFTER_PROTECTION',['P','N']),('OUTPUT_TO_REVERSE_BLOCKER',['P','N']),('ENABLE_DRY_CONTACT',['A','B'])])
pinlabels={'1':'+VIN','2':'ON_OFF_INPUT_REF','4':'-VIN','5':'-VOUT','6':'-SENSE','7':'TRIM_NC','8':'+SENSE','9':'+VOUT'}
netgroups={'VIN_PROTECTED':['CHB500W_24S24N.1','C_INPUT_2200u_100V.+','INPUT_AFTER_PROTECTION.P'],'INPUT_RETURN':['CHB500W_24S24N.4','C_INPUT_2200u_100V.-','INPUT_AFTER_PROTECTION.N','ENABLE_DRY_CONTACT.B'],'ENABLE_PULL_LOW':['CHB500W_24S24N.2','ENABLE_DRY_CONTACT.A'],'VOUT_LOCAL':['CHB500W_24S24N.9','CHB500W_24S24N.8','C_OUT_POLY_10u_50V.+','C_OUT_CER_1u_50V.1','OUTPUT_TO_REVERSE_BLOCKER.P'],'OUTPUT_RETURN':['CHB500W_24S24N.5','CHB500W_24S24N.6','C_OUT_POLY_10u_50V.-','C_OUT_CER_1u_50V.2','OUTPUT_TO_REVERSE_BLOCKER.N'],'EXPLICIT_NC_TRIM':['CHB500W_24S24N.7']}
nets={ep:net for net,eps in netgroups.items() for ep in eps};tree=ast.parse((R/'reuse_closure/tools/build_ecad.py').read_text(encoding='utf-8'));defs=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['symbol_def','schematic']]
def pin_type(ep):
 if ep in ['CHB500W_24S24N.1','CHB500W_24S24N.4']:return 'power_in'
 if ep in ['CHB500W_24S24N.5','CHB500W_24S24N.9']:return 'power_out'
 if ep in ['CHB500W_24S24N.2','CHB500W_24S24N.6','CHB500W_24S24N.8']:return 'input'
 return 'passive'
scope={'E':E,'q':q,'uid':uid,'dump':dump,'collections':collections,'pin_type':pin_type}
class CompactLayout(ast.NodeTransformer):
 def visit_BinOp(self,node):
  self.generic_visit(node)
  if isinstance(node.op,(ast.Mod,ast.FloorDiv)) and isinstance(node.right,ast.Constant) and node.right.value==6:node.right.value=3
  return node
 def visit_Constant(self,node):
  if node.value==91.44:node.value=114.3
  elif node.value==88.9:node.value=71.12
  return node
defs=[CompactLayout().visit(x) for x in defs]
exec(compile(ast.Module(body=defs,type_ignores=[]),'isolated_pure_ecad_definitions','exec'),scope)
mapping=scope['schematic']('wp10_converter_reference',modules,nets,'WP10 converter candidate - OPEN interfaces','A3')
path=E/'wp10_converter_reference.kicad_sch';s=path.read_text(encoding='utf-8')
# A deliberately unused trim pin gets a real KiCad no-connect marker, not a net.
pt=ast.parse((D/'tools/integrate_ecad.py').read_text(encoding='utf-8'))
ps={'json':json,'re':__import__('re')};pd=[x for x in pt.body if isinstance(x,ast.FunctionDef) and x.name in ['parse','enc','val','children']]
exec(compile(ast.Module(body=pd,type_ignores=[]),'pure_sexpression_parser','exec'),ps)
st=ps['parse'](s);ep='CHB500W_24S24N.7'
ref_changes={'U2':'C1','U3':'C2','U4':'C3','U5':'J1','U6':'J2','U7':'SW1'}
def change_refs(n):
 if not isinstance(n,list):return
 if n and n[0]=='property' and len(n)>2 and n[1]=='"Reference"' and ps['val'](n[2]) in ref_changes:n[2]=q(ref_changes[ps['val'](n[2])])
 if n and n[0]=='reference' and len(n)>1 and ps['val'](n[1]) in ref_changes:n[1]=q(ref_changes[ps['val'](n[1])])
 for x in n:change_refs(x)
change_refs(st)
for m in mapping.values():m['ref']=ref_changes.get(m['ref'],m['ref'])
dump(E/'wp10_converter_reference_ENDPOINT_MAP.json',mapping)
remove_ids={uid('wp10_converter_reference'+ep+suffix) for suffix in ['wire','label']}
for node in list(st):
 if isinstance(node,list) and node and node[0] in ['wire','label']:
  u=ps['children'](node,'uuid')
  if u and ps['val'](u[0][1]) in remove_ids:st.remove(node)
st.append(ps['parse'](f'(no_connect (at 50.8 45.72) (uuid {q(uid("TRIM_NC"))}))'))
s=ps['enc'](st)
notes=['Selected MPN: CHB500W-24S24N. Pins 3 and 10 do not exist in standard model.', 'Negative logic: open=OFF; dry contact pulls pin 2 to INPUT return pin 4. No input/output return tie.', 'Local sense: 8 to 9; 6 to 5. Pin 7 trim intentionally open. Sense is not routed across a contactor.', 'C1: 2200uF/100V ESR<0.12 ohm. C2: >=10uF polymer ESR<=0.05 ohm. C3: 1uF ceramic.', 'Capacitor MPN/ripple/derating and fuse/TVS/filter/precharge NOT RELEASED. Values follow OEM app note.', 'OUTPUT BOUNDARY REQUIRES REVERSE BLOCKING + VERIFIED REGEN SINK before any DM bus connection.', 'PMM35 chain selected separately. Loaded Vin floor, commands, 20A contact sharing still require verification.', 'Existing STOP board range 23.04..24.96V does NOT cover full converter transient (+/-5%). No direct substitution.']
s=s.rstrip()[:-1]+''.join(f'(text {q(n)} (at 25 {211+i*5} 0) (effects (font (size 1.15 1.15)) (justify left)) (uuid {q(uid(n))}))' for i,n in enumerate(notes))+')';path.write_text(s,encoding='utf-8')
(E/'wp10_converter_reference.kicad_pro').write_text('{}',encoding='utf-8');(E/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "WP09") (type "KiCad") (uri "${KIPRJMOD}/WP09.kicad_sym") (options "") (descr "Candidate source")))',encoding='utf-8')
csvout(E/'CONVERTER_PHYSICAL_PIN_NET.csv',[{'module':'CHB500W-24S24N','pin':pin,'function':pinlabels[pin],'net':nets['CHB500W_24S24N.'+pin],'source':'Datasheet V12 p10; App Note V13 p3'} for pin in modules['CHB500W_24S24N']])
dump(E/'OPEN_BOUNDARIES.json',{'energy_source':'INPUT_AFTER_PROTECTION is a connector boundary, not a fabricated power source','output':'OUTPUT_TO_REVERSE_BLOCKER is not a motor bus until conditioning exists','no_isolation_return_short':True,'unchanged_parent_system':str(D/'ecad/wp09_system.kicad_sch'),'parent_sha256':sha(D/'ecad/wp09_system.kicad_sch'),'whole_system_integrated':False})
bom=[{'role':'battery','manufacturer':'RRC','MPN':'RRC3570-4','quantity':1,'status':'SELECTED_CANDIDATE','source':'rrc3570_4.pdf'}, {'role':'charging and power path','manufacturer':'RRC','MPN':'RRC-PMM35','quantity':1,'status':'SELECTED_CANDIDATE_INTERFACE_PARTIAL','source':'pmm35.pdf'}, {'role':'single isolated converter','manufacturer':'Cincon','MPN':'CHB500W-24S24N','quantity':1,'status':'SELECTED_CANDIDATE','source':'cincon_chb500w.pdf'}, {'role':'local thermal carrier','manufacturer':'PROJECT','MPN':'WP10_CHB_CARRIER_6061_MODEL','quantity':1,'status':'GEOMETRY_CANDIDATE_NOT_MANUFACTURING_RELEASE','source':'mechanical/converter_carrier.step.py'}]
csvout(P/'SELECTED_BOM.csv',bom)
print(json.dumps({'selected_COTS':3,'converter_circuit_symbols':len(modules),'physical_converter_pins':8,'public_PMM_drawing_positions':len(pmm),'whole_system_release':False}))

# The seven-symbol sheet is lineage only. The active power deliverable is the
# integrated hierarchy derived from the original 99-reference system.
import runpy
runpy.run_path(str(A/'tools/integrate_power_loop.py'),run_name='__main__')
if (A/'tools/build_thermal_interface.py').exists():
 runpy.run_path(str(A/'tools/build_thermal_interface.py'),run_name='__main__')
# Run build_regen_screen.py after native netlist export, so its topology evidence
# refers to the actual exported revision, not a stale generator intention.
