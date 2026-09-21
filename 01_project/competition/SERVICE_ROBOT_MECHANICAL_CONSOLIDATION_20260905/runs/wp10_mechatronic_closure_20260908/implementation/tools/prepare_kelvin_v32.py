"""Same-candidate source revision; preserve V30/V31 parent bytes and actual nets."""
from pathlib import Path
import hashlib, json, shutil
from erc_source_contract import parse, enc, children, val, source_inventory

A = Path(__file__).resolve().parents[1]
E = A / 'ecad'
D = E / 'revisions/v32'
R = A / 'results/kelvin_v32'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def mark_symbol(s):
    old = children(s, 'duplicate_pin_numbers_are_jumpers')
    assert len(old) <= 1
    if old:
        old[0][1] = 'yes'
    else:
        s.insert(2, ['duplicate_pin_numbers_are_jumpers', 'yes'])

def main():
    if D.exists():
        raise RuntimeError('V32 revision already exists; resume, do not overwrite')
    _, pages, _ = source_inventory(E/'wp10_system.kicad_sch')
    sources = set(pages)
    sources.update(E.glob('*.kicad_sym'))
    sources.update(E.glob('*.pretty/*.kicad_mod'))
    sources.update(E/n for n in ['fp-lib-table','sym-lib-table','wp10_system.kicad_pro',
                                 'wp10_main_input.kicad_pcb','wp10_main_input.kicad_pro','wp10_system.xml'])
    sources.update(A/n for n in ['SYSTEM_CLOSURE_MATRIX.csv','sources/wslp2726.pdf',
                                  'coupled_closure/CANDIDATE_V30.json',
                                  'power/MAIN_INPUT_COPPER_LOSS_V29.json'])
    lock = {str(p): sha(p) for p in sorted(sources)}
    D.mkdir(parents=True)
    R.mkdir(parents=True, exist_ok=True)
    write(R/'PARENT_SOURCE_LOCK.json', lock)
    for p in sorted(sources):
        if p.is_relative_to(E):
            dst = D/p.relative_to(E)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    # Ensure this project resolves every local footprint library within this revision.
    table = parse((D/'fp-lib-table').read_text(encoding='utf-8-sig'))
    for lib in children(table, 'lib'):
        name = val(children(lib,'name')[0][1])
        assert (D/(name+'.pretty')).is_dir(), name
        children(lib,'uri')[0][1] = json.dumps('${KIPRJMOD}/'+name+'.pretty')
    (D/'fp-lib-table').write_text(enc(table)+'\n', encoding='utf-8')
    changed = []
    for p, embedded in [(D/'WP10POWER.kicad_sym', False),(D/'wp10_power_1.kicad_sch', True)]:
        tree = parse(p.read_text(encoding='utf-8-sig'))
        container = children(tree,'lib_symbols')[0] if embedded else tree
        found = []
        for s in children(container,'symbol'):
            name = val(s[1])
            if name.split(':')[-1] in ['R201','R202']:
                mark_symbol(s)
                found.append(name)
        assert len(found) == 2, found
        p.write_text(enc(tree)+'\n', encoding='utf-8')
        changed.append({'file':p.relative_to(D).as_posix(),'symbols':found,
                        'attribute':'duplicate_pin_numbers_are_jumpers=yes'})
    # No global symbols, power flags, pin numbers, networks or MPNs are changed.
    write(R/'SOURCE_PREPARATION.json', {
        'parent':'V30 physical + V31 input closure; same WP10 candidate',
        'active_design_sources_created':str(D), 'symbols_changed':changed,
        'parent_files_preserved':len(lock),
        'intended_pad_groups':{'R201':[['1','1'],['2','2']], 'R202':[['1','1'],['2','2']]},
        'cross_terminal_short_allowed':False,
        'basis':[{'url':'https://www.vishay.com/docs/30179/wslp2726.pdf','local':'sources/wslp2726.pdf',
                  'purpose':'Two metal terminals and recommended split Kelvin landing dimensions'},
                 {'url':'https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#jumper-pads',
                  'purpose':'Same-number pads electrically joined by attached component; source symbol sync required'}],
        'DRC_credit_pending_native_execution':True,
        'hardware_tests':0,
    })
    print(json.dumps({'revision_directory':str(D),'preserved_source_count':len(lock),'modified_symbol_definitions':4}))

if __name__ == '__main__': main()
