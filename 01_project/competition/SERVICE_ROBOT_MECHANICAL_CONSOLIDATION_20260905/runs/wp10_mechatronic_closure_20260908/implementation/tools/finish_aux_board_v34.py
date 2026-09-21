"""Add mounting and separate RTN thermal copper to the routed review board.

No thermal qualification is inferred from copper area or filled zones.
"""
from pathlib import Path
import json, shutil, xml.etree.ElementTree as ET
import pcbnew as k
from build_aux_v34 import mm
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34'
P=D/'wp10_aux_protection.kicad_pcb'

def main():
    b=k.LoadBoard(str(P)); assert b.GetAreaCount()==0,'Finish only the newly routed board'
    xml=ET.parse(D/'wp10_system.xml').getroot()
    comps={c.get('ref'):c for c in xml.findall('./components/comp')}
    for f in b.GetFootprints():
        c=comps[f.GetReference()]
        f.SetPath(k.KIID_PATH(c.find('sheetpath').get('tstamps').rstrip('/')+'/'+c.findtext('tstamps')))
    # Copy installed native footprints to the same revision; package is relocatable.
    lib=D/'MountingHole.pretty';lib.mkdir(exist_ok=True)
    name='MountingHole_2.7mm_M2.5'
    shutil.copy2(Path('G:/Windows_program_file/Kicad/share/kicad/footprints/MountingHole.pretty')/(name+'.kicad_mod'),lib/(name+'.kicad_mod'))
    holes=[(3.5,3.5),(56.5,3.5),(3.5,36.5),(56.5,36.5)]
    for i,(x,y) in enumerate(holes,1):
        f=k.FootprintLoad(str(lib),name);f.SetFPID(k.LIB_ID('MountingHole',name))
        f.SetReference('MH34_'+str(i));f.SetValue('M2.5 NPTH 2.7mm');b.Add(f);f.SetPosition(mm(x,y))
        f.SetAttributes(f.GetAttributes()|k.FP_BOARD_ONLY);f.Reference().SetVisible(False);f.Value().SetVisible(False)
    nets={n.GetNetname():n for n in b.GetNetsByName().values()}
    def zone(net,points,priority):
        z=k.ZONE(b);z.SetLayer(k.B_Cu);z.SetNet(nets[net]);z.SetAssignedPriority(priority)
        z.SetLocalClearance(k.FromMM(.5));z.SetMinThickness(k.FromMM(.25))
        z.SetPadConnection(k.ZONE_CONNECTION_FULL)
        o=z.Outline();o.NewOutline()
        for x,y in points:o.Append(k.FromMM(x),k.FromMM(y))
        b.Add(z)
    zone('WP10_AUX_PROTECT_RTN',[(21,11),(42,11),(42,31),(21,31)],1)
    zone('WP10_INPUT_RETURN',[(.6,.6),(59.4,.6),(59.4,39.4),(.6,39.4)],0)
    # All-layer copper-pour exclusions cover hardware washer/head envelope.
    for x,y in holes:
        for layer in [k.F_Cu,k.B_Cu]:
            z=k.ZONE(b);z.SetLayer(layer);z.SetIsRuleArea(True);z.SetDoNotAllowZoneFills(True)
            z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
            z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False) # The NPTH itself is required inside its keepout.
            o=z.Outline();o.NewOutline()
            for dx,dy in [(-3,-3),(3,-3),(3,3),(-3,3)]:o.Append(k.FromMM(x+dx),k.FromMM(y+dy))
            b.Add(z)
    k.SaveBoard(str(P),b)
    # Keep the library table project relative, including MCP-created entries.
    from erc_source_contract import parse,enc,children,val
    p=D/'fp-lib-table';t=parse(p.read_text(encoding='utf-8-sig'))
    for entry in children(t,'lib'):
        name2=val(next(q for q in children(entry,'name'))[1])
        uri=next(q for q in children(entry,'uri'));uri[1]=json.dumps('${KIPRJMOD}/'+name2+'.pretty')
    if not any(val(next(q for q in children(e,'name'))[1])=='MountingHole' for e in children(t,'lib')):
        t.append(['lib',['name','"MountingHole"'],['type','"KiCad"'],['uri','"${KIPRJMOD}/MountingHole.pretty"'],['options','""'],['descr','"Local installed library; board-only mounting holes"']])
    p.write_text(enc(t)+'\n',encoding='utf-8')
    (R/'PCB_MECHANICAL_THERMAL.json').write_text(json.dumps(dict(
        revision='V34',board_mm=[60,40,1.6],mounting_holes_mm=holes,drill_mm=2.7,
        fastener='M2.5 candidate; installed standoff height and host location unbound',
        all_layer_hardware_keepout_square_mm=6,copper_layers=2,copper_thickness_model_um=35,
        copper_thickness_is_design_nominal_not_manufactured_measurement=True,
        thermal_EP_to_RTN_vias=9,via_drill_mm=.3,via_diameter_mm=.6,
        RTN_isolated_from_primary_GND=True,RTN_zone_outline_mm=[[21,11],[42,11],[42,31],[21,31]],
        actual_thermal_resistance_K_per_W=None,thermal_or_flight_qualification=False,
        assembled_hardware_tests=0),indent=2)+'\n',encoding='utf-8')
    print('Added 4 board-only mounting holes, 2 copper zones, 8 hardware keepouts; source UUID paths corrected')

if __name__=='__main__':main()
