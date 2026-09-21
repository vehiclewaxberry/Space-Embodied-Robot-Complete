"""Independent native XML review of candidate-only properties.

Compares all original component semantics and every pin/net tuple; checks all
planned properties in both XML fields and XML properties; binds the source
schematics and three immutable boards. Does not import the builder.
"""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
D=ROOT/'20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920'
R=D/'results/reviewer'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

base_path=D/'inputs/LOCKED_SYSTEM_249.xml'
candidate_path=D/'results/ECAD_CANDIDATE.xml'
plan_path=D/'inputs/ECAD_MCP_EDIT_PLAN.json'
bom_path=D/'bom/ELECTRICAL_SELECTION_BOM_R5E.json'
plan=read(plan_path); bom={x['ref']:x for x in read(bom_path)}
expected={}
for sheet,rows in plan['sheets'].items():
    for ref,row in rows.items():
        assert ref not in expected, ('Duplicate planned reference',ref)
        expected[ref]={'sheet':sheet,'properties':row['properties']}

def mapping(items,key,fn):
    out={}
    for item in items:
        k=item.attrib[key]
        assert k not in out, ('Duplicate XML key',k)
        out[k]=fn(item)
    return out

def parse(p):
    rt=ET.parse(p).getroot()
    cc={}
    for c in rt.findall('components/comp'):
        ref=c.attrib['ref'];assert ref not in cc
        fields=mapping(c.findall('fields/field'),'name',lambda e:e.text or '')
        props=mapping(c.findall('property'),'name',lambda e:e.attrib.get('value',''))
        libs=c.find('libsource');sp=c.find('sheetpath')
        units=sorted((u.attrib['name'],tuple(sorted(x.attrib['num'] for x in u.findall('pins/pin')))) for u in c.findall('units/unit'))
        semantic={'value':c.findtext('value',''),'footprint':c.findtext('footprint',''),
            'datasheet':c.findtext('datasheet',''),'description':c.findtext('description',''),
            'libsource':dict(libs.attrib) if libs is not None else {},
            'sheetpath':dict(sp.attrib) if sp is not None else {},
            'tstamps':c.findtext('tstamps',''),'units':units,
            'fields':{k:v for k,v in fields.items() if not k.startswith('R5E_')},
            'properties':{k:v for k,v in props.items() if not k.startswith('R5E_')}}
        cc[ref]={'semantic':semantic,'fields':fields,'properties':props}
    pins={};net_classes={}
    for net in rt.findall('nets/net'):
        name=net.attrib['name'];net_classes[name]=net.attrib.get('class','')
        for node in net.findall('node'):
            key=(node.attrib['ref'],node.attrib['pin'])
            assert key not in pins, ('Duplicate pin/net',key)
            pins[key]={'net':name,'node_attributes':dict(node.attrib)}
    return cc,pins,net_classes

source_sch=read(R/'SCHEMATIC_SOURCE_HASH_AUDIT.json')['schematics']
source_boards=read(R/'LOCKED_249_XML_BOARD_AUDIT.json')['boards']
copy_dir=D/'ecad/selection_candidate'
copied_sch=sorted(copy_dir.glob('*.kicad_sch'))
tracked=[base_path,candidate_path,plan_path,bom_path,*copied_sch,
    *(ROOT/x['path'] for x in source_sch),*(ROOT/x['path'] for x in source_boards.values())]
before={p.relative_to(ROOT).as_posix():sha(p) for p in tracked}
old,onets,oclasses=parse(base_path); new,nnets,nclasses=parse(candidate_path)
checks=[]
def ck(name,a,b):checks.append({'name':name,'pass':a==b,'actual':a,'expected':b})
ck('base_249_xml_sha',sha(base_path),'90497ad91d4b8ec2c39e6eda819b94e3fbcf9f908861aae22e6c90c5bf1a1939')
ck('components_ref_set',sorted(new),sorted(old))
ck('components_count',len(new),249)
ck('pin_net_count',len(nnets),795)
ck('pin_net_keys',sorted(nnets),sorted(onets))
ck('net_names_and_classes',nclasses,oclasses)
for ref in old:
    ck('original_component_semantics:'+ref,new.get(ref,{}).get('semantic'),old[ref]['semantic'])
for key,val in onets.items():
    ck('pin_net_semantics:'+'.'.join(key),nnets.get(key),val)
refs_with_properties={ref for ref,c in new.items() if any(x.startswith('R5E_') for x in c['fields']) or any(x.startswith('R5E_') for x in c['properties'])}
ck('annotated_reference_set',sorted(refs_with_properties),sorted(expected))
ck('annotated_references_count',len(expected),46)
ck('planned_sheets_count',len(plan['sheets']),11)
planned_property_count=0
for ref,record in expected.items():
    e=record['properties'];c=new[ref]; planned_property_count+=len(e)
    for container in ['fields','properties']:
        actual={k:v for k,v in c[container].items() if k.startswith('R5E_')}
        ck(container+':planned_property_keys:'+ref,sorted(actual),sorted(e))
        for key,val in e.items():ck(container+':'+ref+':'+key,actual.get(key),val)
    ck('planned_sheet:'+ref,c['properties'].get('Sheetfile'),record['sheet'])
    b=bom[ref]
    candidate_mpn=b['candidate_MPN']
    if ref=='R305':
        parts=b['rating']['proposed_parts']
        ck('R305_composite_parts_documented',all(p['MPN'] in e['R5E_CandidateMPN'] for p in parts),True)
        ck('R305_explicit_unimplemented', 'SERIES_ECO_NOT_IMPLEMENTED' in e['R5E_CandidateMPN'],True)
    elif candidate_mpn:
        ck('BOM_candidate_MPN:'+ref,e['R5E_CandidateMPN'],candidate_mpn)
    else:
        ck('interface_has_no_invented_MPN:'+ref,e['R5E_CandidateMPN'],'NOT_A_SEPARATE_PROCUREMENT_PART')
    ck('BOM_candidate_footprint:'+ref,e['R5E_CandidateFootprint'],b['candidate_footprint'] or 'UNKNOWN_OR_PROJECT_INTERFACE')
    ck('BOM_status:'+ref,e['R5E_SelectionStatus'],b['selection_status'])
    ck('BOM_datasheet:'+ref,e['R5E_Datasheet'],b['source'])
    ck('BOM_open_items:'+ref,e['R5E_OpenItems'],' | '.join(b['open_items']))
    ck('not_ready_to_power:'+ref,e['R5E_ReadyToPower'],'false')
ck('C301_original_requirement_retained',new['C301']['semantic']['value'],'1uF_100V_EFFECTIVE_MIN1uF')
ck('C301_candidate_value_explicit',new['C301']['properties'].get('R5E_CandidateValue'),'1.5uF 100V +/-5%')
ck('C301_effective_requirement_not_verified',new['C301']['properties'].get('R5E_EffectiveCapacitanceRequirement'),'>=1uF at actual operating conditions; NOT_VERIFIED')
for x in source_sch:
    ck('original_schematic_unchanged:'+Path(x['path']).name,sha(ROOT/x['path']),x['expected'])
for key,x in source_boards.items():
    ck('original_board_unchanged:'+key,sha(ROOT/x['path']),x['sha256'])
ck('candidate_copy_schematic_count',len(copied_sch),15)
after={p.relative_to(ROOT).as_posix():sha(p) for p in tracked}
ck('all_read_files_stable',after,before)
fails=[x for x in checks if not x['pass']]
semantic={'components':{r:c['semantic'] for r,c in new.items()},'pin_nets':[(list(k),v) for k,v in sorted(nnets.items())],'net_classes':nclasses}
original_semantic={'components':{r:c['semantic'] for r,c in old.items()},'pin_nets':[(list(k),v) for k,v in sorted(onets.items())],'net_classes':oclasses}
out={'schema':'R5E_INDEPENDENT_CANDIDATE_NATIVE_XML_REVIEW_V1','status':'PASS__CANDIDATE_PROPERTIES_ONLY' if not fails else 'FAIL',
    'components':len(new),'pin_net_pairs':len(nnets),'nets':len(nclasses),
    'annotated_references':len(expected),'annotated_sheets':len(plan['sheets']),'planned_properties_per_container':planned_property_count,
    'candidate_source_schematics':len(copied_sch),'original_schematics_unchanged':15,'original_boards_unchanged':3,
    'electrical_semantics_sha256':digest(semantic),'original_electrical_semantics_sha256':digest(original_semantic),
    'checks_passed':sum(x['pass'] for x in checks),'checks_total':len(checks),'failed':fails,
    'checks':checks,'reviewed_hashes':before,'reviewed_hashes_after':after,
    'candidate_package_deliverable':not fails,'manufacturing_release':False,'ready_to_power':False,'flight_ready':False,
    'scope':'Native KiCad export semantic/metadata consistency and immutable source hashes only. Candidate properties do not install parts or qualify new circuitry.'}
(R/'ECAD_CANDIDATE_INDEPENDENT_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['checks','reviewed_hashes','reviewed_hashes_after']},ensure_ascii=False,indent=2))
raise SystemExit(0 if not fails else 2)
