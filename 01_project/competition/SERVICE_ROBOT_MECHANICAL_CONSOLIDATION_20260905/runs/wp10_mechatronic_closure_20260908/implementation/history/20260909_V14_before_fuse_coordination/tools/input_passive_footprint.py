"""Build dimensional C203 footprint before native schematic verification."""
from pathlib import Path
from input_passive_definition import PASSIVES
A=Path(__file__).resolve().parents[1]
def build_footprint():
    c=PASSIVES["C203"]
    out=A/'ecad/WP10_PASSIVES.pretty';out.mkdir(exist_ok=True)
    name=c['footprint'].split(':')[1]
    foot=f'''(footprint "{name}" (version 20241229) (generator "pcbnew") (layer "F.Cu")
     (descr "CANDIDATE; LXG VS D30 L50 maxD31 L52. Project pad1+; pad2-. 2mm round holes, not LI slots. Top vent +3mm; retention OPEN.")
     (attr through_hole)
     (fp_text reference "REF**" (at 0 -17) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
     (fp_text value "ELXG101VSN222MR50S" (at 0 17) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
     (fp_circle (center 0 0) (end 15 0) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
     (fp_circle (center 0 0) (end 15.5 0) (stroke (width 0.15) (type default)) (fill none) (layer "F.SilkS"))
     (fp_rect (start -16 -16) (end 16 16) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
     (fp_text user "+" (at -5 -3) (layer "F.Fab") (effects (font (size 1.5 1.5) (thickness 0.15))))
     (fp_text user "-" (at 5 -3) (layer "F.Fab") (effects (font (size 1.5 1.5) (thickness 0.15))))
     (pad "1" thru_hole rect (at -5 0) (size 3.5 3.5) (drill 2) (layers "*.Cu" "*.Mask"))
     (pad "2" thru_hole circle (at 5 0) (size 3.5 3.5) (drill 2) (layers "*.Cu" "*.Mask"))
    )'''
    (out/(name+'.kicad_mod')).write_text(foot,encoding='utf-8')
    table='(fp_lib_table (version 7) (lib (name "WP10_PASSIVES") (type "KiCad") (uri "PROJECT_DIR/WP10_PASSIVES.pretty") (options "") (descr "Public dimensional candidates; not assembly release")))'
    (A/'ecad/fp-lib-table').write_text(table.replace('PROJECT_DIR',chr(36)+'{KIPRJMOD}'),encoding='utf-8')
    return name

if __name__=="__main__":print(build_footprint())
