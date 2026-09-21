"""Read current KiCad boards; no SaveBoard or source mutation. Run with KiCad Python."""
from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET
import pcbnew

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
BASE = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
latest=json.loads((BASE/'coupled_closure/HANDOFF_LATEST.json').read_text('utf-8'))
entry_path=Path(latest['entry']);assert sha(entry_path)==latest['entry_sha256']
entry=json.loads(entry_path.read_text('utf-8'));binding=entry['evidence']['verification'];receipt_path=BASE/binding['path'];assert sha(receipt_path)==binding['sha256']
receipt = json.loads(receipt_path.read_text('utf-8'))
assert sha(BASE/entry['evidence']['board']['path'])==entry['evidence']['board']['sha256']
xml = BASE / receipt['netlist_xml']
assert sha(xml) == receipt['netlist_xml_sha256']
tree = ET.parse(xml).getroot()
pin_net = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name'] for net in tree.findall('./nets/net') for n in net.findall('node')}
boards=[]
for name in ['wp10_main_input', 'wp10_aux_protection', 'wp10_stop_control']:
    path=BASE/'ecad/revisions/v36'/f'{name}.kicad_pcb'
    before=sha(path); b=pcbnew.LoadBoard(str(path)); pads=[]; mismatch=[]; board_only=[]; footprints=[]; npth=[]
    for f in b.GetFootprints():
        ref=f.GetReference()
        models=[{'filename':m.m_Filename,'show':m.m_Show,'offset_mm':[m.m_Offset.x,m.m_Offset.y,m.m_Offset.z],'rotation_deg':[m.m_Rotation.x,m.m_Rotation.y,m.m_Rotation.z],'scale':[m.m_Scale.x,m.m_Scale.y,m.m_Scale.z]} for m in f.Models()]
        footprints.append({'ref':ref,'value':f.GetValue(),'footprint':f.GetFPID().GetLibNickname().wx_str()+':'+f.GetFPID().GetLibItemName().wx_str(), 'pcb_xy_mm':[pcbnew.ToMM(f.GetPosition().x),pcbnew.ToMM(f.GetPosition().y)],'rotation_deg':f.GetOrientationDegrees(),'models':models})
        for p in f.Pads():
            number=p.GetNumber(); net=p.GetNetname()
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH:
                npth.append({'ref':ref,'pin':number,'pcb_xy_mm':[pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)],'drill_xy_mm':[pcbnew.ToMM(p.GetDrillSize().x),pcbnew.ToMM(p.GetDrillSize().y)]})
            if not number or not net: continue
            r={'ref':ref,'pin':number,'net':net,'pcb_xy_mm':[pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)],'local_board_top_xyz_mm':[pcbnew.ToMM(p.GetPosition().x),-pcbnew.ToMM(p.GetPosition().y),0.0], 'coordinate_scope':'COPPER_PAD_CENTRE_NOT_MATING_CONTACT_OR_CABLE_EXIT', 'host_S_mm':None}
            pads.append(r)
            if (ref,number) not in pin_net: board_only.append(r)
            elif pin_net[(ref,number)]!=net:mismatch.append(r)
    assert before==sha(path), 'SOURCE_CHANGED_DURING_READ'
    bb=b.GetBoardEdgesBoundingBox()
    boards.append({'board':str(path),'sha256':before,'edge_bbox_pcb_xy_mm':[pcbnew.ToMM(bb.GetX()),pcbnew.ToMM(bb.GetY()),pcbnew.ToMM(bb.GetRight()),pcbnew.ToMM(bb.GetBottom())],'nominal_thickness_mm':pcbnew.ToMM(b.GetDesignSettings().GetBoardThickness()),'footprints':footprints,'npth_pads':npth,'footprints_with_declared_model':sum(bool(f['models']) for f in footprints),'electrical_pads':pads,'net_mismatches':mismatch,'board_only_pads_without_schematic_ref':board_only,'host_transform':None,'board_mounting_qualified':False})
result={'schema':'R2_ELECTRICAL_KICAD_READBACK_V1','source_xml':str(xml),'source_xml_sha256':sha(xml),'boards':boards,'mapped_pad_net_parity':all(not b['net_mismatches'] for b in boards),'board_only_pad_binding_complete':not any(b['board_only_pads_without_schematic_ref'] for b in boards),'source_unchanged':True,'scope':'Read-only connected pads, footprints and current XML parity. Four MAIN board-only PORT_* pads are separately unresolved to schematic reference; not waived into all-pad parity. No DRC rerun; board-local pad centres do not define mounted connector mating contacts.'}
(OUT/'results').mkdir(exist_ok=True,parents=True)
(OUT/'results/ELECTRICAL_PAD_READBACK.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'mapped_pad_net_parity':result['mapped_pad_net_parity'],'board_only_pad_binding_complete':result['board_only_pad_binding_complete'],'boards':[{'name':Path(b['board']).stem,'pads':len(b['electrical_pads']),'mismatches':len(b['net_mismatches']),'board_only_pads':len(b['board_only_pads_without_schematic_ref'])} for b in boards]}))
assert result['mapped_pad_net_parity']
