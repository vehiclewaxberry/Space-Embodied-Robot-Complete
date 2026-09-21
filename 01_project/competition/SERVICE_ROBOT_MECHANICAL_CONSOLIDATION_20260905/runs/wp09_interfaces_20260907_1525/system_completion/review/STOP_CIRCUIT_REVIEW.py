"""Independent stable-logic review of actual KiCad XML; no CAD or hardware I/O.

Component truth functions are separate from the author's scenario simulator.
This is not SPICE, timing, metastability, contact-bounce, or power-ramp proof.
"""
from pathlib import Path
import datetime, hashlib, itertools, json, xml.etree.ElementTree as ET
C = Path(__file__).resolve().parents[1]
E = C / 'electrical_delta'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = []
def check(name, condition, evidence=None):
    checks.append({'name': name, 'pass': bool(condition), 'evidence': evidence})
    assert condition, name

j = read(E/'STOP_CIRCUIT_CONNECTIVITY.json')
parts = {p['ref']: p for p in j['parts']}
x = ET.parse(E/'wp09_stop_circuit.net.xml')
pins, nodes, pin_types = {}, {}, {}
for net in x.findall('.//nets/net'):
    name = net.get('name').lstrip('/')
    nodes[name] = []
    for q in net.findall('node'):
        key = (q.get('ref'), q.get('pin'))
        check('XML_unique_pin_'+'.'.join(key), key not in pins)
        pins[key] = name
        nodes[name].append(key)
        pin_types[key] = q.get('pintype')
def n(ref, pin): return pins[(ref, str(pin))]
check('XML_component_membership', {q.get('ref') for q in x.findall('.//components/comp')} == set(parts))
connected = []
for p in parts.values():
    for q in p['pins']:
        key = (p['ref'], q['number'])
        if q['net']:
            connected.append(key)
            check('JSON_XML_pin_'+'.'.join(key), pins.get(key) == q['net'])
        elif key in pins:
            check('NC_no_hidden_connection_'+'.'.join(key), len(nodes[pins[key]]) == 1 and pins[key].startswith('unconnected-'))
check('connected_count', len(connected) == 222)
check('component_count', len(parts) == 71)
check('connected_net_count', len({pins[k] for k in connected}) == 39)

# Physical pin assignments, checked against the locked manufacturer pin tables.
critical = {
 'U101': {1:'STOP_3V3',3:'EN_STOP',4:'STOP_GND',5:'STOP_3V3',6:'WDI',7:'FAULT_N_RAW',8:'FAULT_N_RAW',9:'STOP_GND'},
 'U102': {1:'FAULT_N_RAW',2:'STOP_GND',3:'STOP_3V3',5:'STOP_3V3',6:'STOP_3V3'},
 'U103': {1:'FAULT_N_RAW',2:'STOP_GND',3:'STOP_3V3',5:'STOP_5V',6:'STOP_3V3'},
 'U104': {1:'FAULT_N_RAW',2:'STOP_GND',3:'STOP_3V3',5:'SENSE_24V',6:'STOP_3V3'},
 'U107': {1:'SAFE_N',2:'HB_SEEN',3:'RESET_EDGE',4:'STOP_3V3',5:'ARMED',7:'STOP_GND',9:'RUN_LATCH',10:'STOP_3V3',11:'START_EDGE',12:'ARMED',13:'RUN_CLEAR_N',14:'STOP_3V3'},
 'U108': {1:'SAFE_N',2:'STOP_3V3',3:'WDI_FALL',4:'STOP_3V3',5:'HB_SEEN',7:'STOP_GND',10:'STOP_3V3',11:'STOP_GND',12:'STOP_GND',13:'STOP_GND',14:'STOP_3V3'},
 'U112': {1:'STOP_5V',2:'STOP_GND',3:'RUN_DRIVE',4:'STOP_GND',5:'GATE_DRV'},
 'U119': {1:'STOP_GND',2:'RUN_LATCH',3:'STOP_GND',4:'RUN_LEVEL_5V',5:'STOP_5V'},
 'R111': {1:'RUN_LEVEL_5V',2:'RUN_DRIVE'}, 'R112':{1:'RUN_DRIVE',2:'STOP_GND'},
 'R115':{1:'AUX_RETURN',2:'STOP_GND'}, 'R116':{1:'AUX_RETURN',2:'AUX_SENSE'},
 'J105':{1:'STOP_5V',2:'AUX_RETURN'},
 'R123':{1:'RUN_LATCH',2:'STOP_GND'},
}
for ref, spec in critical.items():
    for pin, net in spec.items(): check(f'physical_pin_{ref}.{pin}', n(ref,pin)==net)
for ref,pin in [('U101',7),('U101',8),('U102',1),('U103',1),('U104',1)]:
    check(f'open_drain_fault_wired_{ref}.{pin}',pin_types[(ref,str(pin))]=='open_collector' and n(ref,pin)=='FAULT_N_RAW')
for buf, resistor, connector_pin, inp in [('U116','R120',4,'RUN_LATCH'),('U117','R121',5,'SAFE_N'),('U118','R122',6,'AUX_CLOSED_3V3')]:
    check(buf+'_status_open_drain', parts[buf]['mpn']=='SN74LVC1G07DBVR' and pin_types[(buf,'4')]=='open_collector')
    check(buf+'_input', n(buf,2)==inp)
    check(buf+'_receiver_domain_only_pullup', n(resistor,1)==n('J102',8)=='MCU_VIO' and n(resistor,2)==n(buf,4)==n('J102',connector_pin))
    check(buf+'_status_network_only_buffer_pullup_receiver',set(nodes[n(buf,4)])=={(buf,'4'),(resistor,'2'),('J102',str(connector_pin))})
check('incoming_WDI_Ioff_buffer',parts['U115']['mpn']=='SN74LVC1G17DBVR' and n('U115',2)=='HEARTBEAT_FILTER' and n('U115',4)==n('U101',6))
check('external_permits_via_Ioff_gate',parts['U114']['mpn']=='SN74LVC1G08DBVR' and n('U114',1)==n('J102',2) and n('U114',2)==n('J102',7))
check('aux_5V_via_Ioff_Schmitt',parts['U113']['mpn']=='SN74LVC1G17DBVR' and n('U113',2)==n('R116',2) and n('U113',5)=='STOP_3V3')
check('AHCT_input_leakage_source_not_output_Ioff_claim',parts['U119']['mpn']=='SN74AHCT1G125DBVR')
check('precision_510k_package_0805',parts['R105']['mpn']=='TNPW0805510KBEEA')

# Generic synchronous event simulation built from XML pin numbers.
gates = []
for ref,p in parts.items():
    mpn = p['mpn']
    if mpn.startswith(('SN74LVC1G17','SN74LVC1G07')): gates.append(('BUF',[n(ref,2)],n(ref,4)))
    elif mpn.startswith('SN74LVC2G17'):
        gates.extend([('BUF',[n(ref,1)],n(ref,6)),('BUF',[n(ref,3)],n(ref,4))])
    elif mpn.startswith('SN74LVC1G04'): gates.append(('NOT',[n(ref,2)],n(ref,4)))
    elif mpn.startswith('SN74LVC1G08'): gates.append(('AND',[n(ref,1),n(ref,2)],n(ref,4)))
    elif mpn.startswith('SN74AHCT1G125'):
        check('AHCT_enable_tied_low', n(ref,1)=='STOP_GND')
        gates.append(('BUF',[n(ref,2)],n(ref,4)))
flops = []
for ref,p in parts.items():
    if p['mpn'].startswith('SN74LVC74A'):
        for cp,dp,clk,pre,qp in [(1,2,3,4,5),(13,12,11,10,9)]:
            if any(q['number']==str(qp) and q['net'] for q in p['pins']):
                flops.append(tuple(n(ref,k) for k in (cp,dp,clk,pre,qp)))
check('three_used_flip_flops',len(flops)==3)

class Logic:
    def __init__(self):
        self.ext={'hb':False,'reset':False,'start':False,'hw':True,'bus':True,'stop_closed':True,'wdo':True,'uv3':False,'uv5':False,'uv24':False}
        self.q={f[4]:False for f in flops}; self.previous={f[2]:False for f in flops}
        self.net={}; self.step()
    def step(self, **changes):
        self.ext.update(changes); e=self.ext
        self.net.update({'STOP_GND':False,'STOP_3V3':True,'STOP_5V':True,'MCU_VIO':True,n('U115',2):e['hb'],n('U105',1):e['reset'],n('U105',3):e['start'],n('U114',1):e['hw'],n('U114',2):e['bus'],n('U113',2):False})
        for loop in range(30):
            self.net.update(self.q)
            for _ in range(20):
                old=dict(self.net)
                self.net[n('U101',3)] = self.net.get(n('J103',5),False) and e['stop_closed']
                self.net[n('U101',7)] = not (e['wdo'] or e['uv3'] or e['uv5'] or e['uv24'] or not self.net[n('U101',3)])
                for op,ins,out in gates:
                    v=[self.net.get(k,False) for k in ins]
                    self.net[out]=not v[0] if op=='NOT' else all(v)
                if old==self.net: break
            qnext=dict(self.q)
            for clr,d,clk,pre,q in flops:
                assert self.net[pre], 'Preset unexpectedly active'
                if not self.net[clr]: qnext[q]=False
                elif self.net[clk] and not self.previous[clk]: qnext[q]=self.net[d]
            self.previous={f[2]:self.net[f[2]] for f in flops}
            if qnext==self.q: return bool(self.net[n('U107',9)])
            self.q=qnext
        raise AssertionError('Combinational/event network did not converge')
    def hb(self): self.step(hb=True); self.step(hb=False)
    def arm(self): self.step(reset=True); self.step(reset=False)
    def running(self):
        self.step(wdo=False); self.hb(); self.arm(); self.step(start=True)
        assert self.net[n('U107',9)]

scenarios=[]
def scenario(name, condition):
    check(name,condition); scenarios.append(name)
s=Logic(); s.step(wdo=False); s.arm()
scenario('RESET_before_first_WDI_cannot_arm',not s.net['ARMED'] and not s.net['HB_SEEN'])
s.hb(); s.arm(); scenario('first_HB_then_RESET_can_arm',s.net['ARMED'])
scenario('new_START_after_RESET_release_runs',s.step(start=True))
scenario('RESET_held_clears_RUNNING',not s.step(reset=True))
scenario('START_edge_while_RESET_held_cannot_run',not s.step(start=False) and not s.step(start=True))
s.step(reset=False);scenario('RESET_release_with_START_held_cannot_run',not s.net['RUN_LATCH'])
s.step(start=False);scenario('new_START_after_RESET_release_restores',s.step(start=True))
s=Logic();s.step(wdo=False,start=True);s.hb();s.arm()
scenario('START_held_before_arm_does_not_autostart',not s.net['RUN_LATCH'])
s.step(start=False);scenario('held_START_must_release_then_press',s.step(start=True))

faults=[('wdo',True),('uv3',True),('uv5',True),('uv24',True),('hw',False),('bus',False),('stop_closed',False)]
for key,value in faults:
    s=Logic();s.running();s.step(**{key:value})
    scenario(key+'_clears_all_three_memory_bits',not any(s.q.values()))
    s.step(**{key:not value});s.hb()
    scenario(key+'_recovery_held_START_no_restart',not s.net['RUN_LATCH'])
    s.step(start=False);s.step(start=True)
    scenario(key+'_new_START_without_reset_still_off',not s.net['RUN_LATCH'])
    s.arm();scenario(key+'_reset_does_not_trigger_held_START',not s.net['RUN_LATCH'])
    s.step(start=False);scenario(key+'_fresh_reset_and_START_can_run',s.step(start=True))
    s.step(reset=True);s.step(**{key:value});s.step(**{key:not value});s.hb()
    scenario(key+'_RESET_held_across_fault_cannot_arm',not s.net['ARMED'] and not s.net['RUN_LATCH'])
for mask in range(1,1<<len(faults)):
    s=Logic();s.running();changes={k:v for i,(k,v) in enumerate(faults) if mask>>i&1};s.step(**changes)
    scenario(f'all_fault_combinations_{mask}_clear_memory',not any(s.q.values()))

# Independent bounded calculations. Declared resistor environmental screen is +/-2%.
v5lo,v5hi=5.1*.99,5.1*1.01
r10lo,r10hi=10000*.98,10000*1.02
r1lo,r1hi=1000*.98,1000*1.02
leak=5e-6
wet_min=v5lo/r10hi-leak
wet_max=v5hi/r10lo+leak
aux_low_max=leak*(r10hi+r1hi)
aux_closed_input_min=v5lo-leak*r1hi
ahct_unloaded_min=3.8*r10lo/(r10lo+r1hi)
ucc_ih_allow=(3.8-2.4)/r1hi-2.4/r10lo
check('aux_min_5V_wetting_supply_requirement',v5lo>5)
check('aux_wetting_current_exceeds_0p1mA',wet_min>=.0001)
check('aux_open_input_below_0p8V',aux_low_max<.8)
check('aux_closed_input_above_2V',aux_closed_input_min>2)
check('aux_input_below_5p5V',v5hi+leak*r1hi<5.5)
check('AHCT_input_3V3_logic_margin',(3.234-.2)>2)
calc=read(E/'STOP_CIRCUIT_CALCULATIONS.json')
check('full_100ms_timing_not_claimed',calc['full_contact_open_100ms_proven'] is False and calc['full_chain_ns_timing_not_qualified'] is True)
check('no_physical_or_manufacturing_credit',calc['hardware_io_count']==0 and calc['manufacturing_release'] is False)
check('UCC_unbound_current_disclosed',calc['UCC_INplus_sink_actual_max_A'] is None and calc['full_worst_case_gate_logic_margin_closed'] is False and abs(calc['UCC_INplus_sink_max_allowed_A']-ucc_ih_allow)<1e-12)
check('AUX_leakage_calculation_matches',max(abs(a-b) for a,b in zip(calc['aux_wetting_current_with_input_leakage_A'],[wet_min,wet_max]))<1e-12)
check('CWD_board_leakage_excluded_disclosed',calc['board_leakage_not_included_in_CWD_bound'] is True)
erc=read(E/'STOP_ERC.json');violations=[v for s in erc['sheets'] for v in s['violations']]
check('actual_ERC_three_explicit_supply_errors',len(violations)==3 and all(v['type']=='power_pin_not_driven' for v in violations))
check('no_fake_PWR_FLAG',all(q.find('libsource').get('part')!='PWR_FLAG' for q in x.findall('.//components/comp')))
source_manifest=read(E/'sources/FINAL_SOURCE_LOCK.json')['sources']
source_bindings=[]
for row in source_manifest:
    check('primary_source_hash_'+row['file'],Path(row['path']).is_file() and sha(Path(row['path']))==row['sha256'])
    source_bindings.append({'name':row['file'],'url':row['url'],'sha256':row['sha256']})
check('17_final_locked_primary_PDFs',len(source_bindings)==17)
delivery_path=C/'results/STOP_CIRCUIT_DELIVERY.json'
delivery=read(delivery_path)
check('author_actual_delivery_counts',delivery['components']==71 and delivery['connected_pins']==222 and delivery['nets']==39)
check('author_actual_ERC_not_PASS',delivery['ERC_errors']==3 and delivery['ERC_PASS'] is False)
for row in delivery['files']:
    p=Path(row['path'])
    check('final_delivery_file_SHA_'+p.name,p.is_file() and sha(p)==row['sha256'])
out={
 'schema':'STOP_CIRCUIT_INDEPENDENT_XML_STABLE_LOGIC_REVIEW_V1',
 'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'PASS_TOPOLOGY_AND_STABLE_LOGIC__PHYSICAL_ANALOG_AND_SYSTEM_BOUNDARIES_OPEN',
 'component_count':len(parts),'connected_pin_count':len(connected),'connected_net_count':39,
 'checks_passed':len(checks),'checks':checks,'independent_logic_scenarios_passed':len(scenarios),
 'logic_input_basis':'Actual exported XML nets + separately implemented manufacturer pin truth functions; ideal stable/debounced logic, no timing or analog claim',
 'logic_scenarios':scenarios,
 'reviewer_hardware_io_count':0,'reviewer_CAD_or_COM_execution':False,'reviewer_actual_ERC_rerun':False,
 'reviewed_actual_ERC_errors_remaining':3,
 'source_bindings':source_bindings,
 'artifact_hashes':{p.name:sha(p) for p in [E/'STOP_CIRCUIT_CONNECTIVITY.json',E/'wp09_stop_circuit.net.xml',E/'wp09_stop_circuit.kicad_sch',E/'STOP_CIRCUIT_CALCULATIONS.json',E/'STOP_ERC.json',E/'STOP_PORT_MAP.json',E/'sources/FINAL_SOURCE_LOCK.json',delivery_path]},
 'independent_calculations':{'aux_supply_required_V':[v5lo,v5hi],'aux_wetting_current_A':[wet_min,wet_max],'aux_open_input_max_V':aux_low_max,'aux_closed_input_min_V':aux_closed_input_min,'AHCT_R_divider_no_UCC_input_load_min_V':ahct_unloaded_min,'UCC_input_sink_current_allowed_max_A_for_VIH_2p4V':ucc_ih_allow,'resistor_environmental_fraction_screen':.02,'input_leakage_A':leak},
 'findings_resolved':['Outgoing MCU status backfeed: 3 open-drain buffers and pullups only to receiver MCU_VIO','LVC74/UCC high-level mismatch: 5V TTL AHCT buffer added, input power-off current bounded by II spec (not output Ioff)','510k precision resistor changed from unavailable 0603 range to 0805'],
 'remaining_boundaries':['Actual UCC input pulldown/sink current is unbound: divider voltage ignores that current; threshold closure remains conditional on allowed sink-current inequality','Receiver MCU and MCU_VIO actual identity/range/thresholds not bound; MCU_VIO must track the receiving power domain','STOP off with MCU powered can pull status high: status is not health or hardware permit, and needs separate validity/heartbeat/time supervision','External 3V3/5.1V/24V sources, GPIO, bus voltage monitor circuit, switches/connectors and actual footprints remain open','3 supply/ERC errors remain; no board layout, contact bounce, power ramp, fault timing, thermal or contactor all-temperature release proof','GX11 12ms max applies to manufacturer 25C table scope; complete chain 100ms is unproven; AUX not certified safety mirror'],
 'whole_mechatronic_design_complete':False,'manufacturing_release':False,'flight_release':False,
}
(C/'review/STOP_CIRCUIT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'review/STOP_CIRCUIT_REVIEW_ZH.md').write_text(f'''# STOP 子电路独立复核

最终实际 KiCad XML 网表：{len(parts)} 器件、{len(connected)} 已接引脚、39 网络。独立复核 {len(checks)} 项通过，其中 {len(scenarios)} 个稳定逻辑反例通过；这不是模拟电路或实物测试。

已确认 WDO、ENOUT 和三路欠压开漏输出共同清除 ARM/RUN/HB_SEEN；首次心跳之前不可复位使能。RESET 持续按下强制 RUN 清零；START 持续按下、单项或任意组合故障恢复均不会自行启动。按新的心跳、RESET 及重新 START 顺序可恢复。

复核推动修复 MCU 反向掉电反灌：三个状态经开漏输出且仅由接收 MCU_VIO 上拉；心跳、许可和 AUX 输入有 Ioff 缓冲。STOP 掉电时上拉状态可以为高，不能单独解释为健康或作为硬件放行。

LVC74 到 UCC 的无保证电平已增加 5 V TTL 缓冲。UCC 内部下拉电流尚未给出受控上界；3.442 V 仅为忽略该电流的分压值。独立计算允许 UCC 吸收电流上界为 {ucc_ih_allow*1000:.6f} mA，实际是否满足仍需受控参数或台测。

AUX 在声明的 5.1 V ±1% 源及电阻 ±2% 筛选下，最小湿润电流 {wet_min*1000:.6f} mA，开路输入漏电上界 {aux_low_max:.6f} V。该电源是待实现要求，非实测供电保证；AUX 不是安全镜像触点。

保留实际 ERC 三个供源错误，以及电源/MCU/母线检测器/按钮连接器/PCB 封装土地等未绑定事项。没有执行硬件、CAD 或重跑作者 ERC；已读取并哈希绑定实际导出记录。整链 100 ms、全温接触器动作及实物抗故障性未获验证。详见同名 JSON。
''',encoding='utf-8')
print(json.dumps({k:out[k] for k in ['status','checks_passed','independent_logic_scenarios_passed','component_count','connected_pin_count']},ensure_ascii=False))
