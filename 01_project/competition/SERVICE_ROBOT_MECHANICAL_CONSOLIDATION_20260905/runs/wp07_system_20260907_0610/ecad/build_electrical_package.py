"""Read frozen text/ECAD sources and emit the WP07 electrical review package.

Standard library only. Does not run KiCad, source code, CAD, COM or hardware.
PCB dimensions are extracted from actual Edge.Cuts, not from a catalogue rectangle.
"""
from __future__ import annotations
import bisect, csv, datetime, hashlib, html, itertools, json, math, os, re, shutil, subprocess
from pathlib import Path

R = Path(__file__).resolve().parents[1]
ROOT = next(p for p in R.parents if (p/'PROJECT_MAP.md').is_file())
EXT = ROOT/'80_third_party/external/spacecraft_layout_refs'
OUT = R/'ecad'
RESULTS = R/'results'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

class Node(list):
    def __init__(self, line):
        super().__init__(); self.line = line

def parse_sexpr(path):
    text = path.read_text(encoding='utf-8-sig')
    newlines = [m.start() for m in re.finditer('\n', text)]
    stack, root = [], None
    for match in re.finditer(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text):
        token = match[0]
        if token == '(':
            node = Node(bisect.bisect_left(newlines, match.start())+1)
            if stack: stack[-1].append(node)
            else:
                if root is not None: raise ValueError('Multiple root expressions')
                root = node
            stack.append(node)
        elif token == ')':
            if not stack: raise ValueError('Unbalanced ECAD expression')
            stack.pop()
        else:
            if not stack: raise ValueError('Atom outside root')
            # Only unescape ECAD quotes and slashes; do not execute or interpret text.
            if token.startswith('"'): token = re.sub(r'\\(["\\])', r'\1', token[1:-1])
            stack[-1].append(token)
    if stack or root is None or root[0] != 'kicad_pcb': raise ValueError('Invalid PCB root')
    return root

def children(n, tag): return [x for x in n if isinstance(x,Node) and x and x[0]==tag]
def one(n,tag):
    found=children(n,tag)
    return found[0] if found else None
def atom(n,tag,default=None):
    x=one(n,tag); return x[1] if x is not None and len(x)>1 else default
def xy(n,tag): return [float(v) for v in one(n,tag)[1:3]]

def transform_xy(point, at):
    a=math.radians(float(at[3]) if len(at)>3 else 0.)
    return [float(at[1])+math.cos(a)*point[0]+math.sin(a)*point[1],
            float(at[2])-math.sin(a)*point[0]+math.cos(a)*point[1]]

def all_edge_nodes(tree):
    rows=[(n,None) for n in tree if isinstance(n,Node) and atom(n,'layer')=='Edge.Cuts']
    for fp in children(tree,'module')+children(tree,'footprint'):
        for edge in fp:
            if not isinstance(edge,Node) or atom(edge,'layer')!='Edge.Cuts':continue
            n=Node(edge.line); n.append(edge[0].replace('fp_','gr_',1))
            for item in edge[1:]:
                if isinstance(item,Node) and item[0] in ('start','mid','end','center'):
                    transformed=Node(item.line);transformed.extend([item[0]]+[str(v) for v in transform_xy([float(x) for x in item[1:3]],one(fp,'at'))]);n.append(transformed)
                else:n.append(item)
            rows.append((n,dict(footprint=fp[1],footprint_line=fp.line,layer=atom(fp,'layer'),at=list(one(fp,'at')[1:]))))
    return rows

def arc_geometry(n):
    if one(n,'mid') is None:
        center,start=xy(n,'start'),xy(n,'end')
        sweep=math.radians(float(atom(n,'angle')))
        a0=math.atan2(start[1]-center[1],start[0]-center[0])
        radius=math.dist(center,start)
    else:
        start,mid,end=xy(n,'start'),xy(n,'mid'),xy(n,'end')
        ax,ay=start; bx,by=mid; cx,cy=end
        d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
        if abs(d)<1e-12: raise ValueError('Collinear arc points')
        aa=ax*ax+ay*ay; bb=bx*bx+by*by; cc=cx*cx+cy*cy
        center=[(aa*(by-cy)+bb*(cy-ay)+cc*(ay-by))/d,
                (aa*(cx-bx)+bb*(ax-cx)+cc*(bx-ax))/d]
        radius=math.dist(center,start)
        a0=math.atan2(ay-center[1],ax-center[0]); am=math.atan2(by-center[1],bx-center[0]); ae=math.atan2(cy-center[1],cx-center[0])
        sweep=(ae-a0)%(2*math.pi)
        if (am-a0)%(2*math.pi)>sweep+1e-10: sweep-=2*math.pi
    end=[center[0]+radius*math.cos(a0+sweep),center[1]+radius*math.sin(a0+sweep)]
    pts=[start,end]
    for a in [0,math.pi/2,math.pi,3*math.pi/2]:
        delta=(a-a0)%(2*math.pi) if sweep>=0 else (a0-a)%(2*math.pi)
        if delta<=abs(sweep)+1e-10: pts.append([center[0]+radius*math.cos(a),center[1]+radius*math.sin(a)])
    return dict(start_mm=start,end_mm=end,center_mm=center,radius_mm=radius,sweep_deg=math.degrees(sweep)),pts

def pcb_card(board, schematic, key):
    tree=parse_sexpr(board)
    thickness_node=one(one(tree,'general'),'thickness')
    edges, bounds_pts, endpoints, unsupported=[],[],[],[]
    for n,owner in all_edge_nodes(tree):
        kind=n[0]; item=dict(kind=kind,source_line=n.line,footprint_owner=owner)
        if kind=='gr_line':
            item.update(start_mm=xy(n,'start'),end_mm=xy(n,'end'))
            pts=[item['start_mm'],item['end_mm']]; endpoints.extend(pts)
        elif kind=='gr_arc':
            geometry,pts=arc_geometry(n); item.update(geometry)
            endpoints.extend([item['start_mm'],item['end_mm']])
        elif kind in ('gr_rect','gr_circle'):
            if kind=='gr_rect':
                a,b=xy(n,'start'),xy(n,'end'); item.update(start_mm=a,end_mm=b); pts=[a,b]
            else:
                c,e=xy(n,'center'),xy(n,'end'); radius=math.dist(c,e)
                item.update(center_mm=c,radius_mm=radius)
                pts=[[c[0]-radius,c[1]-radius],[c[0]+radius,c[1]+radius]]
        else:
            unsupported.append(dict(kind=kind,line=n.line)); continue
        edges.append(item); bounds_pts.extend(pts)
    if not bounds_pts: raise ValueError('No actual board Edge.Cuts')
    groups=[]
    for pt in endpoints:
        found=next((g for g in groups if math.dist(pt,g['point_mm'])<=1e-5),None)
        if found: found['degree']+=1
        else: groups.append(dict(point_mm=pt,degree=1))
    bad_vertices=[g for g in groups if g['degree']!=2]
    lower=[min(p[i] for p in bounds_pts) for i in range(2)]
    upper=[max(p[i] for p in bounds_pts) for i in range(2)]
    holes=[]; connections=[]; unhandled_footprint_edges=[]
    for fp in children(tree,'module')+children(tree,'footprint'):
        ref=next((v[2] for v in children(fp,'property') if v[1]=='Reference'),None)
        if ref is None: ref=next((v[2] for v in children(fp,'fp_text') if v[1]=='reference'),None)
        value=next((v[2] for v in children(fp,'property') if v[1]=='Value'),None)
        if value is None: value=next((v[2] for v in children(fp,'fp_text') if v[1]=='value'),None)
        at=one(fp,'at'); origin=[float(v) for v in at[1:3]]; angle=float(at[3]) if len(at)>3 else 0.
        owns_outline=any(isinstance(el,Node) and atom(el,'layer')=='Edge.Cuts' for el in fp)
        is_mount='mountinghole' in str(fp[1]).lower() or 'mountinghole' in str(value).lower()
        for pad in children(fp,'pad'):
            is_outline_drill=owns_outline and pad[2]=='np_thru_hole'
            if (is_mount or is_outline_drill) and one(pad,'drill'):
                drill=one(pad,'drill'); coords=xy(pad,'at'); a=math.radians(angle)
                global_xy=[origin[0]+math.cos(a)*coords[0]+math.sin(a)*coords[1],
                           origin[1]-math.sin(a)*coords[0]+math.cos(a)*coords[1]]
                nums=[float(v) for v in drill[1:] if isinstance(v,str) and re.fullmatch(r'[0-9.]+',v)]
                holes.append(dict(reference=ref,footprint=fp[1],pad=pad[1],pad_type=pad[2],
                    role_evidence='NAMED_MOUNTING_HOLE_FOOTPRINT' if is_mount else 'NPTH_IN_BOARD_OUTLINE_FOOTPRINT_MOUNTING_INTENT_REQUIRES_REVIEW',
                    source_line=pad.line,footprint_line=fp.line,center_pcb_mm=global_xy,
                    center_outline_min_mm=[global_xy[i]-lower[i] for i in range(2)],
                    drill_mm=nums,slot=drill[1]=='oval',
                    net=one(pad,'net')[2] if one(pad,'net') else None))
            if (str(ref).startswith('J') or str(ref).startswith('CF')) and one(pad,'net'):
                connections.append(dict(reference=ref,value=value,pad=pad[1],net=one(pad,'net')[2],source_line=pad.line))
    complete=not unsupported and not unhandled_footprint_edges and not bad_vertices
    title=one(tree,'title_block')
    return dict(id=key,pcb_path=str(board),pcb_sha256=sha(board),schematic_path=str(schematic),schematic_sha256=sha(schematic),
        selected_for_wp07=False,adoption_status='REFERENCE_ONLY_NOT_SELECTED_HARDWARE',
        extraction_method='STATIC_KICAD_SEXPR_EDGE_CUTS_ARC_EXTREMA_AND_MOUNTING_PAD_DRILL',
        coordinates='SOURCE_PCB_X_RIGHT_Y_DOWN_MM; NO SPACECRAFT_PLACEMENT_ASSIGNED',
        pcb_format_version=atom(tree,'version'),generator_version=atom(tree,'generator_version',atom(tree,'host')),
        legacy_host_declaration=list(one(tree,'host')[1:]) if one(tree,'host') else None,
        design_revision=atom(title,'rev') if title else None,
        thickness_mm=float(thickness_node[1]),thickness_source_line=thickness_node.line,
        outline=dict(bounds_mm=[lower,upper],size_mm=[upper[i]-lower[i] for i in range(2)],edges=edges,
            static_outline_complete=complete,unsupported=unsupported,unhandled_footprint_edges=unhandled_footprint_edges,
            endpoint_tolerance_mm=1e-5,unclosed_or_branch_vertices=bad_vertices,
            note='Static edge graph and extrema only; no DRC, self-intersection, manufacture or assembly-fit acceptance'),
        mounting_holes=holes,connector_pad_net_evidence=connections,
        populated_height_mm=None,spacecraft_T_S_PCB=None,actual_component_selection=None,
        erc_status='NOT_RUN',drc_status='NOT_RUN',physical_fit_status='NOT_EVALUATED',energization_allowed=False)

def source_record(id, relative, excerpts):
    path=ROOT/relative; lines=path.read_text(encoding='utf-8-sig').splitlines()
    rows=[]
    for a,b in excerpts:
        if a<1 or b>len(lines): raise ValueError('Source locator out of range')
        rows.append(dict(line_start=a,line_end=b,text='\n'.join(lines[a-1:b])))
    return dict(id=id,path=str(path),sha256=sha(path),evidence_kind='LOCAL_ORIGINAL_TEXT',excerpts=rows)

def git_head(path):
    q=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True,check=False)
    return q.stdout.strip() if q.returncode==0 else None

def installed_probe():
    names=['kicad-cli','kicad','pcbnew']; path_results={n:shutil.which(n) for n in names}
    bases=[Path('C:/Program Files/KiCad'),Path('C:/Program Files (x86)/KiCad'),Path('G:/Windows_program_file/KiCad'),Path('C:/Users/stude/AppData/Local/Programs/KiCad')]
    roots=[dict(path=str(p),exists=p.exists()) for p in bases]; hits=[]
    for base in bases:
        if not base.is_dir():continue
        folders=[base,base/'bin']
        folders += [p/'bin' for p in base.iterdir() if p.is_dir()]
        for folder in folders:
            for name in names:
                p=folder/(name+'.exe')
                if p.is_file():hits.append(dict(path=str(p),sha256=sha(p)))
    return dict(method='PATH_AND_FOUR_EXACT_INSTALL_ROOTS_MAX_ONE_VERSION_DIRECTORY',roots=roots,path_results=path_results,
        discovered_executables=hits,executed=False,installed_status='FOUND_NOT_EXECUTED' if hits or any(path_results.values()) else 'NOT_FOUND_IN_BOUNDED_SEARCH',
        entire_drive_scanned=False)

MODULES=[('M01','总布置/外包络'),('M02','主次结构连接'),('M03','B601及夹爪'),('M04','保持释放'),('M05','太阳翼'),('M06','EPS'),('M07','电池'),('M08','OBC数据/任务计算'),('M09','背板卡笼载板'),('M10','ADCS'),('M11','通信天线'),('M12','感知'),('M13','线束连接器'),('M14','热控EMC'),('M15','平移推进'),('M16','AIT夹具维护')]
REQUIRED=['selected_model','operating_voltage_range_v','continuous_current_a','peak_current_a','wire_cross_section_mm2','connector_part_number','pin_map','return_bonding_definition']

def unknown():return dict(value=None,status='UNKNOWN',source_ids=[])

def make_contract(sources,cards):
    modules=[]
    for id,name in MODULES:
        applicable=[] if id in ('M01','M02') else (['return_bonding_definition'] if id=='M14' else [f for f in REQUIRED if f!='wire_cross_section_mm2' or id=='M13'])
        electrically_active=id not in ('M01','M02','M09','M13','M14')
        m=dict(id=id,name_zh=name,coverage_kind='FUNCTIONAL_DOMAIN_NOT_EXCLUSIVE_MASS_OWNER',
            electrically_active=electrically_active,electrical_interface_exists=bool(applicable),
            required_fields=applicable,completion_status='INTERFACE_DRAFT_OPEN_INPUTS',fields={f:unknown() for f in applicable},
            current_hardware_confirmed=False,interface_complete=False,energization_allowed=False,
            source_ids=['wp03_equipment','wp01_interfaces'],open_inputs=list(applicable),
            wire_sizing_owner='M13' if id not in ('M01','M02','M14') else None,
            current_field_interpretation='CARRIED_BRANCH_CURRENT_NOT_SELF_CONSUMPTION' if id in ('M09','M13') else 'DEVICE_OPERATING_CURRENT_PENDING')
        if id in ('M01','M02'):
            m['completion_status']='MECHANICAL_DOMAIN_ELECTRICAL_ALLOCATION_PENDING'
            m['open_inputs']=['equipment_placement_and_connector_access','bonding_and_insulation','mechanical_electrical_boundary']
        if id=='M03':
            m.update(source_ids=['b601_voltage','b601_bom','wp02_harness','b601_thermal'],reference_design_name='B601 DM',
                documented_nominal_voltage_v=dict(value=24.,status='OEM_DOCUMENTED_REFERENCE_ONLY',source_ids=['b601_voltage']),
                open_inputs=applicable+['accepted_model_to_OEM_revision_registration','seven_motor_load_profile','regenerative_energy_path','CAN_bitrate_and_termination'])
        if id=='M14':
            m['open_inputs']=['return_bonding_definition','equipment_dissipation_and_thermal_contact_from_actual_devices']
            m['active_thermal_load_policy']='NO_HEATER_OR_FAN_SELECTED; DO_NOT_INVENT_A_THERMAL_POWER_LOAD'
        if id=='M16':m['source_ids']=['b601_bom'];m['gse_only']=True
        if id in ('M06','M07','M08','M10','M11','M12','M15'):m['source_ids']+=['equipment_candidates']
        if id=='M09':m['reference_board_ids']=['oresat_backplane_2u','pycubed_mainboard_v05']
        if id=='M05':m['reference_board_ids']=['oresat_solar_1u_gaas']
        if id=='M07':m['reference_board_ids']=['pycubed_battery_v01b']
        if id=='M13':m['source_ids']+=['wp02_harness','route_c_open_inputs']
        modules.append(m)
    nodes=[dict(id=m['id'],label=m['name_zh'],kind='FUNCTIONAL_DOMAIN',power_domain=None,selected_hardware=False) for m in modules]
    for id,label,kind in [('B01','24 V 转换／限流／再生处理待定','UNSELECTED_POWER_CONVERSION_PROTECTION'),('B02','CAN 收发／隔离策略／保护待定','UNSELECTED_COMMUNICATION_INTERFACE'),('B03','释放 A/B 驱动与互锁待定','UNSELECTED_RELEASE_DRIVER'),('B04','GSE 隔离／防反灌／上电互锁待定','UNSELECTED_GSE_INTERFACE')]:
        nodes.append(dict(id=id,label=label,kind=kind,power_domain=None,selected_hardware=False))
    for n in nodes:
        if n['id']=='M03':n['power_domain']='D_ARM_24_REFERENCE'
        if n['id']=='M16':n['power_domain']='D_GSE_24_REFERENCE'
    edge_specs=[('M05','M06','power'),('M07','M06','power'),('M06','B01','power'),('B01','M03','power'),('M06','M09','power'),('M09','M08','power'),('M09','M10','power'),('M09','M11','power'),('M09','M12','power'),('M09','M15','power'),('M06','B03','power'),('B03','M04','power'),('M08','B02','data'),('B02','M03','data'),('M08','B03','data'),('M12','M08','data'),('M10','M08','data'),('M11','M08','data'),('M15','M08','data'),('M16','B04','power'),('B04','M06','power'),('M16','M08','debug'),('M14','M13','bonding'),('M02','M14','bonding')]
    edges=[dict(id='E%02d'%(i+1),source=a,target=b,kind=kind,status='PLANNED_NOT_WIRED',connector_part_number=None,pin_map=None,
                wire_cross_section_mm2=None,continuous_current_a=None,peak_current_a=None,implemented=False,energization_allowed=False) for i,(a,b,kind) in enumerate(edge_specs)]
    return dict(schema='WP07_ELECTRICAL_INTERFACE_CONTRACT_V1',generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='ENGINEERING_PROTOTYPE_INTERFACE_REVIEW',status='DRAFT_BLOCKED_BY_MISSING_HARDWARE_INPUTS',
        hardware_selection_user_reply='PENDING',source_refs=[s['id'] for s in sources],required_electrical_fields=REQUIRED,
        modules=modules,nodes=nodes,edges=edges,
        minimal_dependency_inputs=[
            dict(id='EI01',name='实际硬件身份与版本',needed='B601 DM/RS/七电机与accepted模型绑定；EPS、电池、计算、感知、姿控、通信和推进采用型号/版本',status='PENDING_HARDWARE_REPLY',owners=['M03','M06','M07','M08','M10','M11','M12','M15']),
            dict(id='EI02',name='状态负载与能源表',needed='启动、待机、运动、释放、通信各态的允许电压、持续/峰值/再生电流与占空比；电池能量和阵列功率',status='UNKNOWN_NOT_ZERO',owners=['M03','M04','M05','M06','M07','M08','M10','M11','M12','M15']),
            dict(id='EI03',name='电源转换与保护拓扑',needed='原始电池母线、B601 24 V受控支路、航电支路、A/B释放支路、GSE防反灌/上电互锁的选型与额定',status='UNSELECTED',owners=['M04','M06','M07','M09','M16']),
            dict(id='EI04',name='唯一接线表',needed='接头配对PN与针序视角、逐针电源/信号/回流、CAN速率/终端、导体截面及线号、屏蔽和搭接',status='UNKNOWN_NOT_FILLED',owners=['M13','M14']),
            dict(id='EI05',name='真实热界面',needed='实选设备耗散和温限、导热接触面/热阻、绝缘与搭接；不假定主动热控负载',status='UNKNOWN',owners=['M14']),
            dict(id='EI06',name='PCB及设备安装绑定',needed='选定ECAD版本、裸板轮廓/安装孔、已装元件高度、连接器插拔包络与T_S_PCB；机械域负责分配和安装',status='REFERENCE_CARDS_AVAILABLE_ADOPTION_PENDING',owners=['M01','M02','M09'])],
        voltage_domains=[dict(id='D_ARM_24_REFERENCE',nominal_v=24.,range_v=None,source_ids=['b601_voltage'],reference_only=True),
            dict(id='D_ORESAT_2S_REFERENCE',nominal_v=None,range_v=[6.,8.4],source_ids=['oresat_backplane'],reference_only=True),
            dict(id='D_PYCUBED_2S_REFERENCE',nominal_v=None,range_v=None,charge_float_v=8.4,source_ids=['pycubed_power'],reference_only=True),
            dict(id='D_GSE_24_REFERENCE',nominal_v=24.,range_v=None,rated_supply_current_a=14.6,source_ids=['b601_bom'],reference_only=True,gse_only=True),
            dict(id='D_ONBOARD_RAW_UNSELECTED',nominal_v=None,range_v=None,source_ids=[],reference_only=False)],
        source_interpretation=[
            '14.6 A is the LRS-350-24 ground supply rating, not B601 measured current.',
            'PyCubed 4.5–18 V note belongs to its 3.3 V regulator branch; do not use it as complete board input rating.',
            'PyCubed VSOLAR 9–40 V does not imply a 24 V motor output; local charger note is 400 mA and float 8.4 V.',
            'All third-party pin maps remain reference-only; none is selected as a WP07 flight or prototype harness pinout.',
            'Functional coverage overlaps; do not add module masses or count a shared box twice.'],
        forbidden_direct_domain_pairs=[['D_ARM_24_REFERENCE','D_ORESAT_2S_REFERENCE'],['D_GSE_24_REFERENCE','D_ORESAT_2S_REFERENCE'],['D_ARM_24_REFERENCE','D_PYCUBED_2S_REFERENCE']],
        hardware_energization_allowed=False,manufacturing_release=False,flight_qualification=False,
        reference_board_ids=[c['id'] for c in cards],gate_policy='UNKNOWN_IS_BLOCKING; DRAFT_CHECK_PASS_IS_NOT_ELECTRICAL_COMPLETION')

def make_html(contract,cards):
    def esc(x):return html.escape(str(x))
    positions={'M05':(30,50),'M07':(30,155),'M06':(300,95),'B01':(590,35),'M03':(900,35),'M09':(590,205),'M08':(900,205),'B02':(900,125),'M04':(30,390),'B03':(300,330),'M10':(600,375),'M11':(900,375),'M12':(600,480),'M15':(900,480),'M16':(30,575),'B04':(300,575),'M13':(600,650),'M14':(300,650),'M02':(30,730),'M01':(900,650)}
    svg=['<svg viewBox="0 0 1180 830" role="img" aria-label="WP07 电源通信端点关系，所有连接待实施"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8ba3bb"/></marker></defs>']
    for e in contract['edges']:
        a,b=positions[e['source']],positions[e['target']]
        color={'power':'#eb9b45','data':'#6fb6ff','debug':'#ab91ee','bonding':'#8da296'}[e['kind']]
        x1,y1=a[0]+110,a[1]+35;x2,y2=b[0]+110,b[1]+35
        svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#arrow)" fill="none"><title>{e["id"]}: {e["source"]} → {e["target"]}; {e["kind"]}; 未实施</title></path>')
    for n in contract['nodes']:
        x,y=positions[n['id']];pending=n['id'].startswith('B')
        svg.append(f'<g><rect x="{x}" y="{y}" width="220" height="70" rx="8" fill="{"#4a3322" if pending else "#173047"}" stroke="#7492a9"/><text x="{x+12}" y="{y+23}" fill="#fff">{esc(n["id"]+" "+n["label"][:15])}</text><text x="{x+12}" y="{y+46}" fill="#c7d4df" font-size="11">{esc(n["label"][15:] if len(n["label"])>15 else "端点已定义 · 型号/针脚待定")}</text></g>')
    svg.append('</svg>')
    board_rows=''.join('<tr><td>'+esc(c['id'])+'</td><td>'+esc([round(x,6) for x in c['outline']['size_mm']])+'</td><td>'+esc(c['thickness_mm'])+'</td><td>'+esc(len(c['mounting_holes']))+'</td><td>参考源；未选型</td></tr>' for c in cards)
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>WP07 电源与通信接口审阅</title><style>body{margin:0;background:#0d1c29;color:#dbe7ef;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1220px;margin:auto;padding:28px}h1{font-size:27px}p{max-width:1100px}b{color:#ffd194}svg{width:100%;background:#102332;border-radius:12px;font:14px system-ui,"Microsoft YaHei"}table{border-collapse:collapse;width:100%}th,td{padding:10px;border-bottom:1px solid #3c5367;text-align:left}a{color:#8ecaff}.notice{border-left:4px solid #eaa553;padding:12px 18px;background:#283141}code{overflow-wrap:anywhere}</style><main><h1>WP07 电源 / 通信接口审阅</h1><p class="notice"><b>这是连接关系草案，所有虚线均未实施；不构成完整 PCB 原理图或上电许可。</b><br>实际硬件型号回复待收。电流、线径、连接器与针脚表缺失时，检查器保持上电阻断。</p><p>橙色：电源；蓝色：通信；紫色：地面调试；灰绿色：搭接/屏蔽。转换、隔离策略、保护和释放驱动需完成选型与电路验证。逻辑功能域可以共享实体，不重复计质量。</p>'''+''.join(svg)+'''<p><b>B601 参考输入 24 V；OreSat 参考母线 6.0–8.4 V，禁止直接混接。</b> LRS-350-24 的 14.6 A 是地面电源额定值，臂实际电流仍未知。PyCubed 太阳输入与稳压支路注释不能充当整板额定或臂供电能力。</p><h2>从真实 ECAD 提取的机电参考卡</h2><p>外形由源 Edge.Cuts 解析，尺寸为其全局极值；孔取 MountingHole 足迹的实际钻孔。保留源坐标和 SHA。未执行 ERC/DRC，也未建立本星安装变换或元件装配高度。</p><table><tr><th>板源</th><th>外形范围 mm</th><th>板厚 mm</th><th>安装钻孔记录</th><th>选择状态</th></tr>'''+board_rows+'''</table><p><a href="ELECTRICAL_INTERFACE_CONTRACT.json">接口合同</a> · <a href="ELECTRICAL_MODULE_MATRIX.csv">16 模块矩阵</a> · <a href="ECAD_REFERENCE_CARDS.json">ECAD 机电参数卡</a> · <a href="ELECTRICAL_SOURCES.json">证据与原文定位</a> · <a href="README.md">范围与复核方法</a></p></main></html>'''

def mechanical_cards_html(cards):
    sections=[]
    for c in cards:
        low,high=c['outline']['bounds_mm'];w,h=c['outline']['size_mm']
        def pair(p):return ','.join(str(x) for x in p)
        svg=[f'<svg viewBox="{low[0]-5} {low[1]-5} {w+10} {h+10}" aria-label="{c["id"]} actual Edge.Cuts and holes">']
        for e in c['outline']['edges']:
            kind=e['kind'];d=None
            if kind=='gr_line':d=f'M {pair(e["start_mm"])} L {pair(e["end_mm"])}'
            elif kind=='gr_arc':d=f'M {pair(e["start_mm"])} A {e["radius_mm"]} {e["radius_mm"]} 0 {int(abs(e["sweep_deg"])>180)} {int(e["sweep_deg"]>0)} {pair(e["end_mm"])}'
            elif kind=='gr_rect':
                a,b=e['start_mm'],e['end_mm'];d=f'M {pair(a)} L {b[0]},{a[1]} L {pair(b)} L {a[0]},{b[1]} Z'
            if d:svg.append(f'<path d="{d}" fill="none" stroke="#286848" stroke-width="0.25"><title>source line {e["source_line"]}</title></path>')
            elif kind=='gr_circle':svg.append(f'<circle cx="{e["center_mm"][0]}" cy="{e["center_mm"][1]}" r="{e["radius_mm"]}" fill="none" stroke="#286848" stroke-width="0.25"/>')
        for index,hole in enumerate(c['mounting_holes'],1):
            x,y=hole['center_pcb_mm'];r=hole['drill_mm'][0]/2
            svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ddefff" stroke="#165caf" stroke-width="0.25"><title>{html.escape(hole["reference"] or "")}: {hole["drill_mm"]} mm; source line {hole["source_line"]}</title></circle><text x="{x+2}" y="{y+1}" font-size="2.5">{index}</text>')
        svg.append('</svg>')
        rows=''.join(f'<tr><td>{i}</td><td>{html.escape(str(a["reference"]))}</td><td>{a["center_pcb_mm"][0]:.6f}, {a["center_pcb_mm"][1]:.6f}</td><td>{html.escape(str(a["drill_mm"]))}</td><td>{a["source_line"]}</td><td>{html.escape(a["role_evidence"])}</td></tr>' for i,a in enumerate(c['mounting_holes'],1))
        sections.append(f'<article><h2>{c["id"]}</h2><p>实际外形极值 {w:.6f} × {h:.6f} mm；板厚 {c["thickness_mm"]} mm。原 PCB 坐标，X 向右、Y 向下。<b>未选型；未建立本星安装变换。</b></p><p class="path">{html.escape(c["pcb_path"])}<br>SHA256 {c["pcb_sha256"]}<br>本地 HEAD {c["repository_head"]}<br>{html.escape(c["license_declared"])}</p>'+''.join(svg)+f'<table><tr><th>图号</th><th>Reference</th><th>孔心源坐标 mm</th><th>钻孔尺寸 mm</th><th>源行</th><th>角色依据</th></tr>{rows}</table></article>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>WP07 真实 ECAD 机电参考卡</title><style>body{font:15px/1.6 system-ui,"Microsoft YaHei";color:#172b3b;background:#f1f5f7;margin:0}main{max-width:1180px;margin:auto;padding:24px}article{background:white;padding:20px;margin:24px 0}svg{display:block;height:460px;max-width:100%;margin:auto;background:#f8faf7}table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #ccc;padding:6px}.path{font-size:12px;overflow-wrap:anywhere}b{color:#985a13}</style><main><h1>真实 ECAD 机电参考卡</h1><p>绿色是实际 Edge.Cuts，蓝色是实际钻孔；每条边与孔保留源行。只反映电路文件中的裸板几何，不是新增制造图；无已装元件高度、无结构承载或电气适配验证。端点闭合检查不等于 DRC、自交检查或装配验证。</p>'+''.join(sections)+'</main></html>'

def mechanical_fit_screen(cards):
    source=ROOT/'20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json'
    before=sha(source);params=json.loads(source.read_text(encoding='utf-8-sig'))
    rows=[]
    for c in cards:
        board_dims=c['outline']['size_mm']+[c['thickness_mm']]
        for box in params['equipment']:
            size=box['size_mm'];orientations=[]
            for order in itertools.permutations(range(3)):
                dims=[board_dims[i] for i in order]
                gaps=[float(size[i])-dims[i] for i in range(3)]
                orientations.append(dict(board_dimension_order_to_budget_xyz=list(order),oriented_bare_board_bbox_mm=dims,
                    budget_minus_bare_board_mm=gaps,bare_bbox_within_budget_outer_allocation=all(g>=0 for g in gaps),
                    max_axis_excess_mm=max(0.,max(-g for g in gaps))))
            count=sum(q['bare_bbox_within_budget_outer_allocation'] for q in orientations)
            rows.append(dict(board_id=c['id'],pcb_path=c['pcb_path'],pcb_sha256=c['pcb_sha256'],
                board_bbox_xyz_mm=board_dims,budget_id=box['name'],budget_outer_allocation_mm=size,
                orientations=orientations,orientation_count=6,axis_aligned_within_count=count,
                any_axis_aligned_bare_bbox_within_budget_outer_allocation=count>0,
                minimum_max_axis_excess_mm=min(q['max_axis_excess_mm'] for q in orientations),
                result='BARE_BBOX_WITHIN_OUTER_BUDGET_ONLY_NOT_ASSEMBLY_FIT' if count else 'NO_AXIS_ALIGNED_BARE_BBOX_CONTAINMENT_IN_THIS_OUTER_BUDGET',
                arbitrary_tilt_fit_evaluated=False,actual_inner_cavity_evaluated=False,selected_hardware=False))
    if sha(source)!=before:raise RuntimeError('Budget input changed during arithmetic fit screen')
    result=dict(schema='WP07_ELECTRICAL_MECHANICAL_FIT_SCREEN_V1',method='BARE_BOARD_EDGE_EXTREMA_PLUS_SOURCE_THICKNESS_VS_OUTER_BUDGET_BOX_SIX_AXIS_PERMUTATIONS',
        status='BOUNDED_ARITHMETIC_SCREEN_COMPLETED',design_parameter_path=str(source),design_parameter_sha256=before,
        ecad_cards_path=str(OUT/'ECAD_REFERENCE_CARDS.json'),ecad_cards_sha256=sha(OUT/'ECAD_REFERENCE_CARDS.json'),
        script_path=str(Path(__file__).resolve()),script_sha256=sha(__file__),board_count=len(cards),budget_count=len(params['equipment']),rows=rows,
        physical_assembly_fit_pass=False,manufacturing_release=False,arbitrary_tilt_fit_evaluated=False,
        actual_inner_cavity_evaluated=False,component_height_evaluated=False,standoff_height_evaluated=False,cable_bend_and_connector_insertion_evaluated=False,
        physical_clearance_allowance_mm=None,numeric_rule='Direct comparison of parsed mm numbers; no added physical tolerance or margin',
        interpretation=[
            'WP03 size_mm is an outer budget allocation, not a verified usable inner cavity.',
            'Only six axis-aligned permutations of bare-board bounding extents are compared. No claim is made about arbitrary tilted insertion or fit.',
            'No component, standoff, connector, cable-bend or assembly-tool volume is included.',
            'A reference board is not selected hardware. Do not scale a PCB to fit a budget box; revise mounting allocation after selection.',
            'A bounding-box result is a packaging screen, not exact material intersection, mechanical fit, strength or electrical acceptance.'])
    write_json(RESULTS/'ELECTRICAL_MECHANICAL_FIT_SCREEN.json',result)
    return result

def main():
    OUT.mkdir(exist_ok=True);RESULTS.mkdir(exist_ok=True)
    specs=[('b601_voltage','80_third_party/vendor/reBot-DevArm/README_zh.md',[(125,137)]),
        ('b601_bom','80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM/readme_zh.md',[(21,35),(127,130),(151,154),(161,174)]),
        ('b601_thermal','80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM/performance_testing/Performance_Testing_zh.md',[(53,68),(88,102)]),
        ('wp02_harness','20_engineering/service_robot_wp02_20260905/design_parameters.json',[(48,67)]),
        ('wp03_equipment','20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json',[(114,198),(241,246)]),
        ('wp01_interfaces','20_engineering/service_robot_wp01_20260905/interface_requirements.csv',[(14,14),(23,23)]),
        ('equipment_candidates','20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/EQUIPMENT_LIST_V1.yaml',[(143,194),(473,480)]),
        ('route_c_open_inputs','20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml',[(350,368)]),
        ('oresat_backplane','80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane/README.md',[(5,9),(27,68),(86,98)]),
        ('oresat_solar','80_third_party/external/spacecraft_layout_refs/oresat/oresat-solar-hardware/README.md',[(1,11),(18,28)]),
        ('pycubed_power','80_third_party/external/spacecraft_layout_refs/pycubed/hardware/mainboard-v05/Power.sch',[(1384,1399),(1424,1439)]),
        ('pycubed_battery','80_third_party/external/spacecraft_layout_refs/pycubed/hardware/batteryboard-v01/README.md',[(9,27),(32,32)]),
        ('pycubed_license','80_third_party/external/spacecraft_layout_refs/pycubed/hardware/README.md',[(11,17),(36,39)]),
        ('birds_structure','80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/README.md',[(12,13),(30,36),(40,68)])]
    sources=[source_record(*s) for s in specs]
    boards=[('pycubed_mainboard_v05','pycubed/hardware/mainboard-v05/mainboard.kicad_pcb','pycubed/hardware/mainboard-v05/mainboard.sch','pycubed/hardware','CC-BY-SA-4.0',['pycubed_license']),
        ('pycubed_battery_v01b','pycubed/hardware/batteryboard-v01b/batteryboard.kicad_pcb','pycubed/hardware/batteryboard-v01b/batteryboard.sch','pycubed/hardware','CC-BY-SA-4.0 repository; battery-v01 README separately says CC-BY-4.0; resolve exact v01b license before derivation',['pycubed_license','pycubed_battery']),
        ('oresat_backplane_2u','oresat/oresat-backplane/2U/oresat1/oresat-backplane-2u.kicad_pcb','oresat/oresat-backplane/2U/oresat1/oresat-backplane-2u.kicad_sch','oresat/oresat-backplane','CERN-OHL-S-2.0',['oresat_backplane']),
        ('oresat_solar_1u_gaas','oresat/oresat-solar-hardware/solar-module-1u-gaas/solar-module-1u-gaas.kicad_pcb','oresat/oresat-solar-hardware/solar-module-1u-gaas/solar-module-1u-gaas.kicad_sch','oresat/oresat-solar-hardware','CERN-OHL-S-2.0',['oresat_solar'])]
    cards=[]
    for key,b,s,repo,license,license_sources in boards:
        card=pcb_card(EXT/b,EXT/s,key)
        card.update(repository_path=str(EXT/repo),repository_head=git_head(EXT/repo),license_declared=license,license_source_ids=license_sources)
        cards.append(card)
    contract=make_contract(sources,cards)
    source_document=dict(schema='WP07_ELECTRICAL_SOURCES_V1',sources=sources,
        repositories=[dict(path=str(ROOT/'80_third_party/vendor/reBot-DevArm'),head=git_head(ROOT/'80_third_party/vendor/reBot-DevArm'))],
        source_read_only=True,external_downloads=False)
    write_json(OUT/'ELECTRICAL_SOURCES.json',source_document)
    write_json(OUT/'ECAD_REFERENCE_CARDS.json',dict(schema='WP07_ECAD_REFERENCE_CARDS_V1',boards=cards,source_code_executed=False,cad_or_ecad_application_executed=False))
    write_json(OUT/'ELECTRICAL_INTERFACE_CONTRACT.json',contract)
    with (OUT/'ELECTRICAL_MODULE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['module_id','name_zh','coverage_kind','electrically_active','electrical_interface_exists','required_fields','completion_status','actual_model_selected','electrical_interface_complete','energization_allowed','open_inputs','source_ids']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for m in contract['modules']:w.writerow(dict(module_id=m['id'],name_zh=m['name_zh'],coverage_kind=m['coverage_kind'],
            electrically_active=m['electrically_active'],electrical_interface_exists=m['electrical_interface_exists'],required_fields=';'.join(m['required_fields']),completion_status=m['completion_status'],
            actual_model_selected=False,electrical_interface_complete=False,energization_allowed=False,open_inputs=';'.join(m['open_inputs']),source_ids=';'.join(m['source_ids'])))
    (OUT/'ELECTRICAL_INTERFACE_REVIEW.html').write_text(make_html(contract,cards),encoding='utf-8')
    (OUT/'PCB_REFERENCE_MECH_CARDS.html').write_text(mechanical_cards_html(cards),encoding='utf-8')
    mechanical_fit_screen(cards)
    write_json(RESULTS/'ELECTRICAL_TOOL_DISCOVERY.json',installed_probe())
    hashes_before={s['path']:s['sha256'] for s in sources}
    for card in cards:
        hashes_before[card['pcb_path']]=card['pcb_sha256'];hashes_before[card['schematic_path']]=card['schematic_sha256']
    hashes_after={p:sha(p) for p in hashes_before}
    if hashes_before!=hashes_after:raise RuntimeError('A source changed during extraction')
    write_json(RESULTS/'ELECTRICAL_BUILD_RECEIPT.json',dict(schema='WP07_ELECTRICAL_BUILD_V1',status='STATIC_REFERENCE_EXTRACTION_COMPLETED',
        script_path=str(Path(__file__).resolve()),script_sha256=sha(__file__),sources_before=hashes_before,sources_after=hashes_after,
        source_files_unchanged=True,board_count=len(cards),module_count=16,hardware_energization_allowed=False,
        artifacts={str(p):sha(p) for p in OUT.iterdir() if p.is_file() and p.suffix in ('.json','.csv','.html','.md')}))
    print(json.dumps(dict(status='DRAFT_REVIEW_PACKAGE_EMITTED',cards=[dict(id=c['id'],size_mm=c['outline']['size_mm'],thickness_mm=c['thickness_mm'],holes=len(c['mounting_holes']),outline_complete=c['outline']['static_outline_complete']) for c in cards]),ensure_ascii=False))

if __name__=='__main__':main()
