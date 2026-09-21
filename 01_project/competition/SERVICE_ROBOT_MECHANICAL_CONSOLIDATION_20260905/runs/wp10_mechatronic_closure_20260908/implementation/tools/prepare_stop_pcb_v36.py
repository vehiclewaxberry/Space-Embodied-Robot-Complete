"""Freeze pre-PCB source and make explicit physical ownership/footprint selections."""
from pathlib import Path
import json,shutil,hashlib
from erc_source_contract import parse,children,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';R=A/'results/stop_v36/pcb';F=Path('G:/Windows_program_file/Kicad/share/kicad/footprints')
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    R.mkdir(exist_ok=True);H=A/'history/V36_STOP_SOURCE_BEFORE_PCB_20260915'
    assert not H.exists(),'Do not repeat checkpoint creation'
    v=json.loads((R.parent/'SOURCE_VERIFICATION.json').read_text());assert v['scoped_source_check_passed'] and all(sha(Path(p))==h for p,h in v['source_bindings'].items())
    shutil.copytree(D,H/'ecad');shutil.copytree(R.parent,H/'results',ignore=shutil.ignore_patterns('pcb'))
    dump(R/'PRE_PCB_CHECKPOINT.json',dict(path=str(H),file_hashes={str(p.relative_to(H)):sha(p) for p in H.rglob('*') if p.is_file()}))
    base=json.loads((R.parent/'STOP_PARTS_INTAKE.json').read_text());refs={p['Reference'] for p in base}|{f'U{n}' for n in range(311,314)}|{f'R{n}' for n in range(341,350)}|{f'C{n}' for n in range(311,314)}
    rows={};updates={};copy_sources={}
    parts={'U101':('Package_SON:WP10_DUMMY','TPS3431SDRBR')} # replaced with exact TI land pattern below
    for p in D.glob('*.kicad_sch'):
        for s in children(parse(p.read_text()),'symbol'):
            q=properties(s);ref=q['Reference']
            if ref not in refs:continue
            value=q['Value'];mpn=q.get('MPN') or value.split(' / ')[0];manufacturer='';url='';fp=''
            if ref.startswith('U'):
                manufacturer='Texas Instruments';url='https://www.ti.com/lit/ds/symlink/'+mpn.split('DBV')[0].split('PWR')[0].split('SDRB')[0].split('DDC')[0].lower()+'.pdf'
                if ref=='U101':fp='WP10_STOP:TPS3431_DRB0008A';url='https://www.ti.com/lit/ds/symlink/tps3431.pdf'
                elif ref in ['U107','U108']:fp='Package_SO:TSSOP-14_4.4x5mm_P0.65mm'
                elif ref in ['U102','U103','U104','U105','U311','U312','U313']:fp='Package_TO_SOT_SMD:SOT-23-6'
                elif ref in ['U120','U121']:fp='Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT';manufacturer='TRACO Power';url='https://www.tracopower.com/tsr1-datasheet'
                else:fp='Package_TO_SOT_SMD:SOT-23-5'
                if ref in ['U102','U103','U104']:url='https://www.ti.com/lit/ds/symlink/tps3808.pdf'
                if ref=='U119':url='https://www.ti.com/lit/gpn/SN74LV1T04'
            elif ref.startswith('R'):
                manufacturer='Vishay';fp='Resistor_SMD:R_0603_1608Metric';url='https://www.vishay.com/docs/20035/dcrcwe3.pdf'
                if ref in ['R341','R344','R347']:mpn='TNPW06038K20BEEA'
                elif ref in ['R342','R345','R348']:mpn='TNPW0805649KBEEA'
                elif ref in ['R343','R346','R349']:mpn='TNPW0603100KBEEA'
                if mpn.startswith('TNPW'):url='https://www.vishay.com/docs/28758/tnpw_e3.pdf'
                if mpn.startswith('TNPW0805'):fp='Resistor_SMD:R_0805_2012Metric'
                if ref in ['R124','R125']:fp='WP10_STOP:Vishay_PR02_P15_24';url='https://www.vishay.com/docs/28729/pr010203.pdf'
            elif ref.startswith('C'):
                if ref in ['C311','C312','C313']:mpn='C0603C104K3RACTU'
                manufacturer='KEMET';fp='Capacitor_SMD:C_0603_1608Metric';url='https://search.kemet.com/download/specsheet/'+mpn
                if mpn=='C0603C104K3RACTU':value='C0603C104K3RACTU / 100nF X7R 25V 10%'
            elif ref=='Q101':manufacturer='Vishay';fp='Package_TO_SOT_THT:TO-220-3_Vertical';url='https://www.vishay.com/docs/91303/irl630.pdf'
            elif ref.startswith('J'):
                manufacturer='Molex';count={'J101':4,'J102':8,'J103':6,'J104':2,'J105':2}[ref]
                if ref=='J105':mpn='436500200';fp='Connector_Molex:Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal'
                else:mpn=f'430450{count}00';fp=f'Connector_Molex:Molex_Micro-Fit_3.0_43045-0{count}00_2x0{count//2}_P3.00mm_Horizontal'
                url='https://www.molex.com/en-us/products/part-detail/'+mpn;value=mpn
            assert fp and mpn and manufacturer,(ref,q)
            rows[ref]=dict(MPN=mpn,manufacturer=manufacturer,footprint=fp,source_url=url,sheet=p.name,value=value,placement_owner='STOP_CONTROL_AND_THERMAL_BOARD',scope='Engineering candidate; not space-qualified or released')
            fields=dict(value=value,footprint=fp,properties={'MPN':mpn,'Manufacturer':manufacturer,'Datasheet':url,'Physical_Owner':'STOP_CONTROL_AND_THERMAL_BOARD','PCB_Selection_Revision':'V36'})
            updates.setdefault(p.name,{})[ref]=fields
            lib,name=fp.split(':')
            if lib!='WP10_STOP':
                src=F/(lib+'.pretty')/(name+'.kicad_mod');assert src.exists(),str(src)
                dest=D/(lib+'.pretty');dest.mkdir(exist_ok=True);shutil.copy2(src,dest/src.name);copy_sources[str(src)]=sha(src)
    assert len(rows)==93
    newfp='Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal'
    rows['J106']=dict(MPN='SM06B-GHS-TB',manufacturer='JST',footprint=newfp,source_url='https://www.jst-mfg.com/product/pdf/eng/eGH.pdf',sheet='wp10_stop_detail.kicad_sch',value='SM06B-GHS-TB',placement_owner='STOP_CONTROL_AND_THERMAL_BOARD',role='Three remote NTC pairs; RAW and comparator supply stay on this PCB')
    lib,name=newfp.split(':');src=F/(lib+'.pretty')/(name+'.kicad_mod');(D/(lib+'.pretty')).mkdir(exist_ok=True);shutil.copy2(src,D/(lib+'.pretty')/src.name);copy_sources[str(src)]=sha(src)
    (D/'WP10_STOP.pretty').mkdir(exist_ok=True)
    dump(R/'PHYSICAL_PARTS.json',rows);dump(R/'MCP_PART_UPDATES.json',updates);dump(R/'INSTALLED_FOOTPRINT_SOURCES.json',copy_sources)
    dump(R/'BOARD_SCOPE.json',dict(board='wp10_stop_control.kicad_pcb',physical_refs=sorted(rows),off_board_refs=['RT311','RT312','RT313'],off_board_reason='NTCs mounted on three brake-resistor thermal objects; six-wire sensor harness',board_size_mm=[90,70,1.6],layers=2,geometry_admission='NOT_YET_INSTALLED_IN_873_HOST',primary_secondary_return='WP10_ARM_RETURN only; no primary input return on this board',requires_thermal_installation_verification=True,whole_design_complete=False))
    print(json.dumps(dict(board_refs=len(rows),existing_refs_to_assign=sum(map(len,updates.values())),checkpoint=str(H))))
if __name__=='__main__':main()
