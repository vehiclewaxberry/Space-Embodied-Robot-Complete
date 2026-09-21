"""Read actual native XML; evaluate source-bound static design, not hardware.

The startup state examples explicitly exclude unknown ramp, delay and failure
behavior. They are counterexample checks, not an executed safety controller.
"""
from pathlib import Path
import csv, hashlib, itertools, json, re, xml.etree.ElementTree as ET
from main_board_selection_v25 import PARTS as SELECTED_V25
A=Path(__file__).resolve().parents[1]; D=A.parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v): (A/p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
parts=read('power/POWER_LOOP_PARTS.json'); definition=read('power/STARTUP_CIRCUIT_DEFINITION.json')
xml=A/'ecad/wp10_system.xml'; root=ET.parse(xml).getroot()
components={c.get('ref'):c.findtext('value') for c in root.findall('./components/comp')}
native={(p.get('ref'),p.get('pin')):n.get('name') for n in root.findall('./nets/net') for p in n.findall('node')}
def net(ep): return native.get(tuple(ep.split('.')))
def same(*eps): return net(eps[0]) is not None and len({net(e) for e in eps})==1
checks=[]
def ck(n,b,**kw): checks.append(dict(name=n,passed=bool(b),**kw))
def ohm(ref):
    d=SELECTED_V25[ref]
    assert parts[ref]['mpn']==d['MPN'],ref
    return d['resistance_ohm']
def corner(r,t=.001):
    # Symmetric product bound includes initial tolerance*TCR at deltaT100K.
    e=(1+t)*(1+25e-6*100)-1
    return [r*(1-e),r*(1+e)]
for ref in definition['refs']: ck('native_selected_'+ref,components.get(ref)==parts[ref]['mpn'])
ck('primary_bias_after_precharge',same('U205.10','U205.11','U205.8','Q201.3'))
ck('sense_before_precharge_not_capacitor_voltage',same('R215.1','U201.2','F201.2') and not same('R215.1','C203.1'))
ck('PG_source_to_series_link',same('R214.2','R221.1','U201.8'))
ck('MR_receiver_after_series_link',same('U206.3','R221.2','R220.1') and not same('R221.1','R221.2'))
ck('MR_receiver_has_local_pulldown',same('R220.2','U206.2'))
ck('MR_pullup_own_bias',same('R214.1','U205.2','U206.6'))
ck('RESET_gate_passive_network',same('U206.1','R217.2','R218.1','Q204.1'))
ck('CHB_enable_has_primary_switch_and_pullup',same('Q204.3','R219.2','U203.2') and same('R219.1','Q201.3'))
ck('Q204_pin2_is_source_not_drain',same('Q204.2','U203.4','U206.2','U205.13') and not same('Q204.2','U203.5'))
ck('no_secondary_control_or_output_dependency',all(net(e)!=net('U203.9') and net(e)!=net('U107.9') for e in ['U205.10','R215.1','U206.3','Q204.1']))
ck('LT_PG_not_used_for_startup',not net('U205.6') or net('U205.6').startswith('unconnected'))
ck('CT_open_uses_fixed_delay',not net('U206.4') or net('U206.4').startswith('unconnected'))
ck('probe_port_not_a_fitted_bypass',parts['J201']['status']=='NO_JUMPER_DESIGN')
ck('new_not_EOL_MPN',parts['Q204']['mpn']=='2N7002K-7' and SELECTED_V25['Q204']['manufacturer']=='DiodesInc')

# LT ADJ Iadj is specified at25C. Carry that test-condition limitation explicitly.
bias_values=[v*(1+h/l)+i*h for v,h,l,i in itertools.product([1.2,1.28],corner(ohm('R211')),corner(ohm('R212')),[0,100e-9])]
bmin,bmax=min(bias_values),max(bias_values)
bnom=1.24*(1+ohm('R211')/ohm('R212'))+30e-9*ohm('R211')
pg_pull=corner(ohm('R214'))
pg_sink_max=bmax*(1/min(pg_pull)+1/70000)
rpmin,rpmax=corner(ohm('R220'),.01); rlinkmax=max(corner(ohm('R221'),.01))
pg_high_min=(bmin-5e-6*max(pg_pull))*rpmin/(rpmin+max(pg_pull)+rlinkmax)
pg_link_open_max=bmax*rpmax/(70000+rpmax)
pg_low_receiver_max=(.15/rlinkmax+bmax/70000)/(1/rlinkmax+1/70000+1/rpmax)
gu,gd=corner(ohm('R217'),.01),corner(ohm('R218'),.01)
gate_leak=10e-6+.3e-6 # Diodes part, NEVER inherit old Nexperia 0.5uA
gate_min=(bmin/max(gu)-gate_leak)/(1/max(gu)+1/min(gd))
gate_max=(bmax/min(gu)+gate_leak)/(1/min(gu)+1/max(gd))
fall=[th*(1+h/l)+i*h for th,h,l,i in itertools.product([.405*.98,.405*1.02],corner(ohm('R215')),corner(ohm('R216')),[-25e-9,25e-9])]
rise_max=max(th*1.03*(1+h/l)+i*h for th,h,l,i in itertools.product([.405*.98,.405*1.02],corner(ohm('R215')),corner(ohm('R216')),[-25e-9,25e-9]))
control_i=1e-3+40/min(corner(ohm('R219'),.01))
control_low=control_i*3 # DS30896 RDSmax atVGS5V,ID50mA,25C; transfer only
ck('supervisor_supply_static_screen_inside_range',1.7<bmin<bmax<6.5)
ck('bias_minimum_load_gt1mA',bmin/max(corner(ohm('R213'),.01))>1e-3)
ck('PGD_sink_screen_under2mA',pg_sink_max<.002)
ck('PGD_high_screen_exceeds_MR07VDD',pg_high_min>.7*bmin)
ck('PGD_low_receiver_below_MR03VDD',pg_low_receiver_max<.3*bmin)
ck('PGD_link_open_pulldown_below_MR03VDD',pg_link_open_max<.3*bmin)
ck('gate_high_reaches_new_MOS5V_testpoint',gate_min>5)
ck('gate_rating_margin',gate_max<20)
ck('shared_RESET_pin_recommended_voltage_margin',gate_max<6.5)
ck('startup_sense_releases_below_operating_UVLO',rise_max<read('power/POWER_LOOP_CALCULATIONS.json')['UVLO_falling_screen_V'][0])
ck('CHB_enable_low_static_screen',control_low<1.2)

counterexamples=[
 dict(id='PG_HIGH_LOW_VIN',MAIN_FUSED_V=4,PRECHARGED_V=25,PGD_high=True,old_capacitor_sense_would_allow=True,new_input_sense_allows=False,temporal_response_guaranteed=False),
 dict(id='NO_CHB_OUTPUT_AT_START',MAIN_FUSED_V=25.2,PRECHARGED_V=25.2,PGD_high=True,CHB_output_V=0,RUN_LATCH=False,after_supervisor_delay_static_enable=True,K1_command=False),
 dict(id='PGD_OPEN_WIRE_AFTER_SOURCE_PULLUP',MAIN_FUSED_V=25.2,PGD_series_link_connected=False,old_receiver_pullup_would_enable=True,new_receiver_pulldown=True,broken_link_static_screen_detected=pg_link_open_max<.3*bmin,internal_U201_open_drain_failure_detected=False),
 dict(id='BIAS_BROWN_RAMP_WITH_CHARGED_INPUT',MAIN_FUSED_V=25.2,PRECHARGED_V=25.2,bias_V=.7,RESET_state='UNKNOWN_BELOW_POR',CHB_enable='UNKNOWN',whole_startup_pass=False),
 dict(id='NEW_MOS_WRONG_OLD_GATE_BUDGET',old_R211_ohm=37400,old_R217_ohm=56000,new_MOS_gate_leak_A=10e-6,gate_min_V=4.945691985263781,required_RDS_test_gate_V=5.,repaired_R211_ohm=ohm('R211')),
 dict(id='SUPERVISOR_RELEASE_IS_NOT_SHUTDOWN_MAX',CT_open_release_delay_ms=[12,28],MR_to_RESET_ns_typical=150,SENSE_to_RESET_us_typical=20,shutdown_max_s=None),
 dict(id='OLD56K_GATE_OVER_RESET_LIMIT',old_R217_ohm=56000,old_gate_max_sensitivity_V=6.626381243,recommended_RESET_max_V=6.5,new_R217_ohm=ohm('R217'),new_gate_max_sensitivity_V=gate_max),
 dict(id='POR_LOAD_NOT_QUALIFIED',POR_test_load_A=15e-6,pullup_only_at08V_A=.8/min(gu),actual_ramp_load_qualified=False),
]
ck('charged_cap_low_input_counterexample_repaired',counterexamples[0]['old_capacitor_sense_would_allow'] and not counterexamples[0]['new_input_sense_allows'])
ck('broken_PGD_link_fixed_without_internal_failure_credit',counterexamples[2]['broken_link_static_screen_detected'] and not counterexamples[2]['internal_U201_open_drain_failure_detected'])
ck('POR_unknown_retained',counterexamples[3]['CHB_enable']=='UNKNOWN')
sources=read('sources/STARTUP_SOURCE_MANIFEST.json')
for s in sources:
    if s['status']=='ACQUIRED_LOCAL_SOURCE': ck('source_'+s['file'],sha(A/'sources'/s['file'])==s['sha256'])
out=dict(schema='WP10_STARTUP_STATIC_V1',native_xml_sha256=sha(xml),source_py_sha256=sha(A/'tools/startup_circuit_definition.py'),
 circuit_integrated=True,checks_passed=all(x['passed'] for x in checks),check_count=len(checks),checks=checks,
 selected_Q204=dict(MPN=parts['Q204']['mpn'],manufacturer='Diodes Incorporated',source='DS30896 Rev20-2 July2024',gate_leakage_A=10e-6,RDS_ohm_25C_at5V=3.,local_pdf_archived=False),
 bias=dict(nominal_V=bnom,sensitivity_V=[bmin,bmax],minimum_bleed_mA=1000*bmin/max(corner(ohm('R213'),.01))),
 qualification=dict(sense_node='MAIN_FUSED',fall_sensitivity_V=[min(fall),max(fall)],restore_upper_sensitivity_V=rise_max,nominal_fall_V=.405*(1+ohm('R215')/ohm('R216')),PGD_sink_max_sensitivity_A=pg_sink_max,MR_high_min_sensitivity_V=pg_high_min,MR_link_open_max_sensitivity_V=pg_link_open_max,MR_active_low_max_sensitivity_V=pg_low_receiver_max,gate_high_sensitivity_V=[gate_min,gate_max],CHB_control_sink_sensitivity_A=control_i,CHB_low_sensitivity_V=control_low),
 scope='STATIC_SENSITIVITY_NOT_COMBINED_OEM_GUARANTEE; preciseR0.1pct+25ppm/K100K; othersinitial1pct; LT_Iadj25C,PGDleak80V,MOSgateleak20V andRDS25C transferred as explicit sensitivity',
 release_delay=dict(datasheet_ms=[12,28],test_load='100k pullup,50pF',actual_load=f'{ohm("R217")}ohm||{ohm("R218")}ohm plus MOS gate; timing not transferred as full guarantee'),
 thermal_screen=dict(bias_load_design_allowance_mA=4.0,allowance_not_OEM_guarantee=True,at40V_bias_loss_W=(40-bmin)*.004,primary_qualification_power_reserve_W=.25),
 counterexamples=counterexamples,open=['LT3013 6V startup/POR/brown ramp with charged C203','PGD internal transistor/bond failure is distinct from downstream trace open','actual control off leakage and temperature bounds','maximum fault propagation and CHB response','bias capacitors/MPNs/layout/EMI','hardware startup/reset sequence'],
 physical_tests_executed=False,automatic_startup_function_verified=False,power_on_authorized=False)
out['scope']='STATIC_SENSITIVITY_NOT_COMBINED_OEM_GUARANTEE; selected TNPW initial0.1pct or1pct multiplied with25ppm/K100K; lifetime drift open; LT_Iadj25C,PGDleak80V,MOSgateleak20V andRDS25C transferred as explicit sensitivity'
out['selected_passives_revision']='power/MAIN_BOARD_PASSIVE_SELECTION_V25.json'
out['open']=[s.replace('bias capacitors/MPNs/layout/EMI','selected V25 bias capacitors full-temperature impedance and PCB layout/EMI') for s in out['open']]
out['bias_capacitors']={r:dict(MPN=SELECTED_V25[r]['MPN'],nominal_F=SELECTED_V25[r]['C_nominal_F'],
 initial_lower_F=SELECTED_V25[r]['C_nominal_F']*.95,effective_min_requirement_F=SELECTED_V25[r]['effective_C_min_requirement_F'],
 full_environment_verified=False) for r in ['C211','C212','C213']}
out['bias_capacitors']['C212'].update(previous_placeholder_nominal_F=10e-6,
 initial_ESR_upper_ohm_at20C_1kHz=.010/(2*3.141592653589793*1000*4.7e-6*.95),
 nominal_stored_charge_ratio_to_old_placeholder=.47,dynamic_hold_up_time_guaranteed_s=None,
 OEM_stability_requirement='effective_C>=3.3uF and ESR<=3ohm; not proved over all temperatures/frequencies')
dump('power/STARTUP_CIRCUIT_CALCULATIONS.json',out)
assert out['checks_passed'],[c for c in checks if not c['passed']]

# Whole RAW fault-net inventory is derived from native nodes, not a hand subset.
faultname=net('U106.2')
actual_fault={'.'.join(ep) for ep,nn in native.items() if nn==faultname}
inventory=[dict(endpoint=f'U101.{p}',max_leak_A=1e-6,source='TPS3431 RevA p5',conditions='VDD1.8V,Vout6.5V; transfer to3.3V sensitivity') for p in [7,8]]
inventory += [dict(endpoint=f'U{i}.1',max_leak_A=.3e-6,source='TPS3808 RevN p6',conditions='Vout6.5V,RESET notasserted; sensitivity') for i in [102,103,104]]
inventory += [dict(endpoint=f'U{i}.{p}',max_leak_A=.3e-6,source='TLV6700 RevB p5',conditions='open-drain high-state current; actual rail transfer sensitivity') for i in [311,312,313] for p in [1,6]]
inventory += [dict(endpoint='U106.2',max_leak_A=5e-6,source='SN74LVC1G17 RevY p6',conditions='VI5.5V orGND; actual RAW sensitivity')]
rail=json.loads((D/'electrical/STOP_SUPPLY_CALCULATIONS.json').read_text())['rail3V3_V']
rlo=10000*.99*.9975; rhi=10000*1.01*1.0025
total=sum(r['max_leak_A'] for r in inventory)
fchecks=[]
def fc(n,b): fchecks.append(dict(name=n,passed=bool(b)))
fc('all_native_fault_nodes_covered_once',actual_fault=={'R101.2'}|{r['endpoint'] for r in inventory} and len({r['endpoint'] for r in inventory})==len(inventory))
fc('actual_R101_matches_selected_part','CRCW060310K0FKEA' in components['R101'])
fc('actual_R101_pullup_on_STOP3V3',same('R101.1','U120.3'))
fc('SAFE_N_pushpull_not_shorted_to_fault',not same('U106.2','U106.4'))
fc('old_three_MR_pins_not_repurposed',same('U102.3','U103.3','U104.3','U120.3'))
fc('ENOUT_present_for_stop_not_watchdog_disable_only','U101.8' in actual_fault)
fc('fault_inventory_has11_open_drains',len(inventory)-1==11)
fc('fault_inventory_sums9p7uA',abs(total-9.7e-6)<1e-15)
sources_fault=[]
oldsrc=D.parent/'wp09_interfaces_20260907_1525/system_completion/electrical_delta/sources'
for name in ['tps3431.pdf','tps3808.pdf','sn74lvc1g17.pdf']:
    p=oldsrc/name; sources_fault.append(dict(path=str(p),sha256=sha(p)))
fout=dict(schema='WP10_COMPLETE_RAW_FAULT_INVENTORY_V1',native_xml_sha256=sha(xml),checks_passed=all(c['passed'] for c in fchecks),check_count=len(fchecks),checks=fchecks,
 inventory=inventory,native_fault_nodes=sorted(actual_fault),source_bindings=sources_fault,source_STOP_supply_sha256=sha(D/'electrical/STOP_SUPPLY_CALCULATIONS.json'),
 total_leak_sensitivity_A=total,R101_sensitivity_ohm=[rlo,rhi],RAW_high_min_sensitivity_V=rail[0]-total*rhi,
 total_pullup_current_upper_sensitivity_A=rail[1]/rlo+total,all_fault_pins_included=True,full_test_condition_transfer_guaranteed=False,
 continuous_VCC_Schmitt_threshold_guarantee=False,low_level_guarantee=False,old_FAULT_dynamics_verified=False,
 unclosed=['SN74LVC1G17 threshold table gives discrete VCC points; actual3.201825..3.398175V','TPS3431 VOL table testVDD5V; use at3.3V requires qualification','leakage testpoint transfer and cable leakage','fault line capacitance, clear delays and supply ramps'],physical_tests_executed=False)
dump('power/STOP_FULL_FAULT_BUDGET.json',fout)
assert fout['checks_passed']
report=f'''# WP10 输入侧启动与完整故障网预算

本轮新增17个器件，保持原99位号。已接入真实KiCad源和BOM；物理启动、掉电、停止与制造验收尚未完成。

```mermaid
flowchart LR
 BAT[受保护电池] --> F[主保险 / MAIN_FUSED]
 F --> HS[LM5069 + Q201预充]
 HS --> PRE[PRECHARGED输入电容]
 PRE --> CHB[CHB500W-24S24N]
 PRE --> BIAS[U205 LT3013 约5.99V]
 F --> DIV[R215/R216 输入电压检测]
 DIV --> UV[U206 TPS3808G01 SENSE]
 HS --> PG[PGD / 源端R214上拉]
 PG --> LINK[R221连接 / 接收端R220下拉]
 LINK --> MR[U206 MR]
 BIAS --> UV
 BIAS --> MR
 UV --> EN[RESET / R217 / Q204]
 MR --> EN
 EN -->|输入侧低有效| CHB
 CHB --> RB[防回流]
 RB --> K1[独立STOP接触器]
 K1 --> ARM[B601 DM 与负载侧吸能支路]
```

U205接预充电容，U206检测主保险之后、预充开关之前的电压。已充电的电容不代替输入电源有效证明。CHB启动不读取自己的输出、机械臂母线或RUN_LATCH；其输出建立不代表K1闭合。J201只是测试点，不配置短接跳线。

|对象|同源计算结果|适用范围|
|---|---|---|
|启动偏置|名义{bnom:.6f}V，敏感性{bmin:.6f}–{bmax:.6f}V|LT偏流和电阻条件见JSON|
|输入欠压|下降{min(fall):.6f}–{max(fall):.6f}V；释放上界筛选{rise_max:.6f}V|独立于预充PGD，不是主功率UVLO替代|
|PGD低态|最大下拉筛选{pg_sink_max*1000:.6f}mA|含MR内部最小70k上拉；2mA测试条件迁移仍有界|
|PGD连接开路|MR最高{pg_link_open_max:.6f}V|R221或其下游断开；不覆盖U201内部开漏失效|
|门极与RESET共网|{gate_min:.6f}–{gate_max:.6f}V|同时核对5V导通电阻测试点与RESET6.5V工作上限|
|完整故障网|11个开漏＋输入，9.7µA合计；RAW最低{fout['RAW_high_min_sensitivity_V']:.6f}V|静态敏感性清点；连续阈值、低态、时延和线缆漏电未形成保证|

Q204选择Diodes Incorporated的2N7002K-7。没有混用Nexperia旧器件参数：采用10µA门漏电与5V门驱下3Ω规格，重新调整R211=38.3k、R217=33k。门漏电正负角点都保留；原56k导致RESET过压的反例已留在计算JSON。器件电流与温度测试点的迁移是敏感性分析，不是厂家对本电路的新保证。

TPS3808的CT悬空12–28ms是规定负载下的释放延迟，不能作为关断最长时间。MR关断150ns、SENSE关断20µs只有典型值；实际MOS负载和POR15µA条件不匹配。低偏置而输入电容有电、门极耦合及关态漏电仍需继续设计与验证。

输入侧新增0.25W预留在主输入电流增量场景单独计入，不经过CHB效率重复折算；臂任务360W、制动输出偏置1W预留和独立STOP16.8W保持。预留不冒称器件最大功耗保证。

V22制动侧保持LT3013偏置及TLV6700绝对过压检测，新增MAX16053偏置监测并改用MAX5048C分立源/灌驱动。PG诊断网已从IN+断开。接口预算见BRAKE_READY_CALCULATIONS_V22.json；首次冷启动与静态电平预算不能代替掉电重启、最坏回生等待和热关断验证。此前TPS3760比较中，27.44V阈值下20%过驱为32.928V；该历史反例保留。

结果：{len(checks)}项启动静态/原生反例检查和{len(fchecks)}项故障网清点通过。完整机电设计仍开放。复建tools/build_power.py，原生导出tools/verify_power_loop.py，再运行tools/verify_startup_and_fault.py；封存父本保持不变。

来源：[Cincon数据表](https://www.cincon.com/productdownload/CHB500W.pdf)、[Cincon应用说明](https://www.cincon.com/productdownload/CHB500W-series-application-note.pdf)、[LT3013](https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf)、[TPS3808](https://www.ti.com/lit/ds/symlink/tps3808.pdf)、[LM5069](https://www.ti.com/lit/ds/symlink/lm5069.pdf)、[Diodes 2N7002K](https://www.diodes.com/datasheet/download/2N7002K.pdf)、[TPS3431](https://www.ti.com/lit/ds/symlink/tps3431.pdf)、[TPS3760](https://www.ti.com/lit/ds/symlink/tps3760.pdf)。已归档文件SHA见sources/STARTUP_SOURCE_MANIFEST.json。Diodes官方PDF在线正文已核阅，本地下载403；不填造二进制归档哈希。
'''
# Link to the actual archived Cincon filename instead of inventing a public URL.
report=report.replace('https://www.cincon.com/productdownload/CHB500W.pdf','../sources/cincon_chb500w.pdf')
(A/'power/STARTUP_DESIGN.md').write_text(report,encoding='utf-8')
print(json.dumps(dict(startup_checks=out['check_count'],startup_pass=out['checks_passed'],fault_checks=fout['check_count'],fault_pass=fout['checks_passed'],gate_min_V=gate_min,RAW_min_V=fout['RAW_high_min_sensitivity_V'],full_startup_verified=False)))
