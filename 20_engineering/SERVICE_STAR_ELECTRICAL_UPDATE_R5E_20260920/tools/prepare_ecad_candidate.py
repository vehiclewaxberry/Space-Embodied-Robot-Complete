"""Copy reviewed source schematics and prepare MCP custom-property edits only."""
from build_electrical_update import D, ROOT, IMPL, read, write, sha, require
import re
import shutil

src=IMPL/'ecad/revisions/v36'
dest=D/'ecad/selection_candidate'
audit=read(D/'results/reviewer/SCHEMATIC_SOURCE_HASH_AUDIT.json')
require(all(r['match'] for r in audit['schematics']), 'Source schematic lock failed')
require(not dest.exists(), 'Candidate folder already exists; do not overwrite edited schematics')
dest.mkdir(parents=True)
for r in audit['schematics']:
    p=ROOT/r['path'];require(sha(p)==r['expected'],'Schematic drift after review')
    shutil.copyfile(p,dest/p.name)
# Local symbol definitions/tables are useful to the KiCad editor. Do not copy stale XML/PCBs.
for p in src.iterdir():
    if p.is_file() and (p.suffix in ['.kicad_sym','.kicad_pro'] or p.name in ['sym-lib-table','fp-lib-table']):
        shutil.copyfile(p,dest/p.name)
    if p.is_dir() and p.name.endswith('.pretty'):
        for f in p.glob('*.kicad_mod'):
            t=dest/p.name/f.name;t.parent.mkdir(exist_ok=True);shutil.copyfile(f,t)
updates=read(D/'inputs/SELECTION_UPDATES.json')
bom={r['ref']:r for r in read(D/'bom/ELECTRICAL_SELECTION_BOM_R5E.json')}
updates.append({'ref':'U301','status':bom['U301']['selection_status'],'open_items':bom['U301']['open_items']})
plan={}
for u in updates:
    ref=u['ref'];b=bom[ref]
    found=[f for f in dest.glob('*.kicad_sch') if re.search(r'\(property\s+"Reference"\s+"'+re.escape(ref)+r'"',f.read_text(encoding='utf-8'))]
    require(len(found)==1, 'Reference must belong to exactly one source sheet: '+ref)
    plan.setdefault(found[0].name,{})[ref]={'properties':{
        'R5E_CandidateMPN':b['candidate_MPN'] or ('TNPW0805665KBEEA + TNPW060311K0BEEA; SERIES_ECO_NOT_IMPLEMENTED' if ref=='R305' else 'NOT_A_SEPARATE_PROCUREMENT_PART'),
        'R5E_CandidateFootprint':b['candidate_footprint'] or 'UNKNOWN_OR_PROJECT_INTERFACE',
        'R5E_SelectionStatus':u['status'],
        'R5E_Datasheet':b['source'],
        'R5E_OpenItems':' | '.join(u['open_items']) if isinstance(u['open_items'],list) else str(u['open_items']),
        'R5E_ReadyToPower':'false',
    }}
    if ref == 'C301':
        plan[found[0].name][ref]['properties'].update({
            'R5E_CandidateValue':'1.5uF 100V +/-5%',
            'R5E_EffectiveCapacitanceRequirement':'>=1uF at actual operating conditions; NOT_VERIFIED',
        })
write('inputs/ECAD_MCP_EDIT_PLAN.json',{'scope':'CANDIDATE_CUSTOM_PROPERTIES_ONLY; original values, footprint assignments, wires and pin map unchanged','destination':str(dest).replace('\\','/'),'sheets':plan})
write('results/ECAD_COPY_RECEIPT.json',{'source_review':str((D/'results/reviewer/SCHEMATIC_SOURCE_HASH_AUDIT.json').relative_to(ROOT)).replace('\\','/'),
                                      'copied_schematics':len(audit['schematics']),'references_to_annotate':len(updates),
                                      'source_hashes':{r['path']:r['expected'] for r in audit['schematics']},
                                      'PCB_copied_or_modified':False,'topology_change':False})
print({k:len(v) for k,v in plan.items()})
