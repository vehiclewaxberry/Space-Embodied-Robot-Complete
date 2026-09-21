"""One-time activation from MCP-authored files, before native stackup binding.

Do not rerun on an activated V17: use sync_cap_terminal_bindings.py after
cap_terminal_native.py finalize. This bootstrap intentionally starts unbound.
"""
from pathlib import Path
import json,hashlib,shutil
A=Path(__file__).resolve().parents[1]
assert not (A/'power/CAP_TERMINAL_DEFINITION.json').exists(), 'Already activated; use the current sources and sync_cap_terminal_bindings.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
name='C203_SingleFace_Terminal_D30_P10_W18'
fp='WP10_PASSIVES:'+name
src=A/'power/cap_terminal_sources';src.mkdir(exist_ok=True)
for n in [name,'C203_BoardMount_4xM3_NPTH']:
    shutil.copy2(A/f'ecad/WP10_PASSIVES.pretty/{n}.kicad_mod',src/(n+'.kicad_mod'))
terminals=[]
for ident,pin,xy,d in [('CAP_PLUS','1',[-5,0],2),('CAP_MINUS','2',[5,0],2),('WIRE_PLUS','1',[-14,14],1.8),('WIRE_MINUS','2',[14,14],1.8)]:
    terminals.append(dict(id=ident,logical_pin=pin,local_xy_mm=xy,S_face_mm=[-7,xy[0],-50-xy[1]],drill_mm=d,pad_outer_D_mm=3.5,drill_type='NPTH',native_net='WP10_PRECHARGED_PLUS' if pin=='1' else 'WP10_INPUT_RETURN'))
out=dict(schema='WP10_C203_TERMINAL_DEFINITION_V17',footprint=fp,board='ecad/wp10_c203_terminal.kicad_pcb',
    pcb_origin_xy_mm=[100,100],mechanical_frame='S_mm; Xpcb->+Ys, Ypcb->-Zs; component face Xs=-7',
    board_size_mm=[50,48,1.6],finished_copper_thickness_mm=.07,finished_copper_thickness_native_bound=False,
    thickness_scope='1.6 mm mechanical finished-board envelope; 70um is a copper design requirement, native stackup binding still pending; current PCB STEP is envelope, not material-resolved copper/laminate',
    copper_layers=['B.Cu'],terminal_features=terminals,wire=dict(MPN='55A0111-18-9',AWG=18,strands='19/30',max_bare_D_mm=1.2446,max_insulation_D_mm=1.5748,max_R20_ohm_per_m=6.23/304.8,
        source_file='sources/te_55a0111_drawing.pdf',source_sha256=sha(A/'sources/te_55a0111_drawing.pdf'),installed_cut_length_mm=None,minimum_installation_bend_radius_mm=None,physical_termination_and_strain_relief_complete=False),
    manufacturing_definition='Single printed copper face. NPTH drilled through rear copper land; no F.Cu land, no copper barrel. Do not CAM-convert to PTH or add top annular rings. Full rear solder aperture. Manufacturing/CAM review required.',
    DRC_local_process_issues_open=True,OEM_seal_side_interpretation_accepted=False,CHB_connection_complete=False,whole_design_complete=False,
    sources={q:sha(A/q) for q in ['sources/lxg_2026.pdf','sources/chemi_al_precautions_2026.pdf','sources/te_55a0111_drawing.pdf','sources/cincon_chb500w.pdf','sources/chb500w_application.pdf']})
dump('power/CAP_TERMINAL_DEFINITION.json',out)
c=json.loads((A/'mechanical/INPUT_CAP_MOUNT_DESIGN.json').read_text())
c['native_footprint']=fp;c['terminal_board_definition']='power/CAP_TERMINAL_DEFINITION.json'
c['source_files'].update({q:sha(A/q) for q in ['power/CAP_TERMINAL_DEFINITION.json',f'ecad/WP10_PASSIVES.pretty/{name}.kicad_mod']})
c['materials']['pcb']='1.6 mm finished-board envelope; single B.Cu printed-layer candidate with NPTH solder lands, copper stackup/process qualification open'
dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',c)
def replace(file,old,new):
    p=A/file;s=p.read_text(encoding='utf-8')
    if new in s:return
    expected=2 if file=='tools/input_passive_footprint.py' else 1
    assert s.count(old)==expected,(file,old)
    p.write_text(s.replace(old,new,1),encoding='utf-8')
replace('tools/input_passive_definition.py',"footprint='WP10_PASSIVES:CP_ChemiCon_VS_D30_P10_2mm_Candidate'",'footprint='+repr(fp))
replace('tools/input_passive_footprint.py',"    (out/(name+'.kicad_mod')).write_text(foot,encoding='utf-8')", "    canonical=A/'power/cap_terminal_sources'/(name+'.kicad_mod')\n    if canonical.exists():\n        import shutil\n        shutil.copy2(canonical,out/(name+'.kicad_mod'))\n    else:(out/(name+'.kicad_mod')).write_text(foot,encoding='utf-8')")
(A/'mechanical/input_cap_pcb.step.py').write_text('''"""Current terminal PCB envelope; copper layout is in the native KiCad board."""
from pathlib import Path
import json
from input_cap_mount_common import make,cx
def gen_step():
    a=Path(__file__).resolve().parents[1]
    c=json.loads((a/'power/CAP_TERMINAL_DEFINITION.json').read_text())
    board=make('PCB')
    for t in c['terminal_features']:
        if t['id'].startswith('WIRE_'):
            _,y,z=t['S_face_mm'];board=board-cx(t['drill_mm']/2,-8,-4,y,z)
    board.label='WP10_C203_PCB_V17_FINISHED_ENVELOPE_TWO_WIRE_NPTH_ADDED'
    return board
''',encoding='utf-8')
# C203 footprint is the only legitimate physical-property change since V16.
replace('tools/erc_source_contract.py',"    ck('exact_201_entity_properties_preserved',newc==oldc and len(newc)==201)","    expected_c=dict(oldc)\n    expected_c['C203']=(oldc['C203'][0],read(A/'power/CAP_TERMINAL_DEFINITION.json')['footprint'])\n    ck('201_entities_only_C203_terminal_footprint_changed',newc==expected_c and len(newc)==201)")
replace('tools/erc_source_contract.py',"A/'tools/erc_source_contract.py']", "A/'tools/erc_source_contract.py',A/'power/CAP_TERMINAL_DEFINITION.json']")
print(json.dumps(dict(source_revision='V17',entity_count=201,logical_pins_unchanged=657,added_holes=2)))
