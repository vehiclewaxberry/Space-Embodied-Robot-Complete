"""Main input PCB candidate data; import has no filesystem side effects."""
from timer_passive_definition_v24 import TIMING_PASSIVES
PARTS={}
for ref,ohm,code,size,tol in [
 ('R211',38300,'38K3','0603',.001),('R212',10000,'10K0','0603',.001),
 ('R213',4700,'4K70','0603',.01),('R214',3480,'3K48','0603',.001),
 ('R215',374000,'374K','0805',.001),('R216',10000,'10K0','0603',.001),
 ('R217',33000,'33K0','0603',.01),('R218',2200000,'2M20','1210',.01),
 ('R219',100000,'100K','0603',.01),('R220',10000,'10K0','0603',.01),
 ('R221',100,'100R','0603',.01)]:
 d=dict(TIMING_PASSIVES['R203'])
 metric={'0603':'1608','0805':'2012','1210':'3225'}[size]
 d.update(MPN='TNPW'+size+code+('B' if tol==.001 else 'F')+'EEA',
  resistance_ohm=ohm,initial_tolerance_fraction=tol,
  general_mode_P70_W={'0603':.110,'0805':.140,'1210':.330}[size],
  operating_voltage_max_V={'0603':100,'0805':150,'1210':200}[size],
  footprint=f'Resistor_SMD:R_{size}_{metric}Metric',source_pages=[1,2,3,4],
  order_code_basis='OEM 28758 B=0.1% or F=1%, E=25ppm/K, EA=lead-free reel; E-series and size range verified; availability not claimed')
 PARTS[ref]=d
for ref,mpn,c,body,series,minimum in [
 ('C202','MKP2D031001F00JSSD',100e-9,[7.2,5,10],'MKP2',None),
 ('C211','MKS2D041501M00JSSD',1.5e-6,[7.2,8.5,14],'MKS2',1e-6),
 ('C212','MKS2D044701O00JSSD',4.7e-6,[7.2,11,18],'MKS2',3.3e-6),
 ('C213','MKP2D031001F00JSSD',100e-9,[7.2,5,10],'MKP2',None)]:
 PARTS[ref]=dict(MPN=mpn,manufacturer='WIMA',C_nominal_F=c,
  initial_tolerance_fraction=.05,rated_DC_V=100,body_LWH_mm=body,
  effective_C_min_requirement_F=minimum,effective_C_full_environment_verified=False,
  pitch_mm=5,pitch_exit_tolerance_mm=.5,lead_diameter_nominal_mm=.5,
  bulk_lead_length_mm=[4,6],body_and_lead_diameter_tolerances_verified=False,
  source_url='https://www.wima.de/wp-content/uploads/media/e_WIMA_'+series[:-1]+'_'+series[-1]+'.pdf',
  source_file='sources/wima_mkp2_v24.pdf' if series=='MKP2' else 'sources/wima_mks2_v25.pdf',
  source_sha256='1c8527fb1fef607bbf2f67997225102f0cc8e0a433816fe65fe4e58064fe0ec4' if series=='MKP2' else '2a64392db00b639b6d0fca1d9e1a3aa38c1a5138ca6796a713914a9918d05fe9',
  source_revision='03.26',source_pages=[1,2],
  dielectric='metallized polypropylene' if series=='MKP2' else 'metallized polyester',
  footprint='WP10_INPUT:'+series+'_'+mpn[4:14]+'_P5_Slot2',
  temperature_C=[-55,100],DC_derating_above85C='Use OEM curve; not an orbital qualification',
  status='SELECTED_CANDIDATE_EFFECTIVE_C_IMPEDANCE_LAYOUT_OPEN',
  order_code_basis='OEM row prefix + J(5%) + S(bulk) + SD(6-2mm lead); no procurement action')
BOARD_REFS=['F201','U201','Q201','R201','R202',*['R'+str(i) for i in range(203,208)],'C201','C202','D201','D202',
 'U205','U206','Q204',*['R'+str(i) for i in range(211,222)],'C211','C212','C213']
assert len(BOARD_REFS)==31 and len(set(BOARD_REFS))==31
CORE={
 'U201':('LM5069MM-1','Texas Instruments','WP10_INPUT:LM5069_DGS10_P0p5_NoEP','https://www.ti.com/lit/ds/symlink/lm5069.pdf','RevG DGS0010A pp3,36-37'),
 'Q201':('IXTH75N10L2','Littelfuse IXYS','WP10_INPUT:IXTH_TO247_G1D2S3_P5p45_Slots','https://www.littelfuse.com/assetdocs/Littelfuse-Discrete-MOSFETs-N-Channel-Linear-IXT-75N10-Datasheet.PDF?assetguid=EA051E16-AAA9-4983-A975-8D0C07325D72','DS100200(9/09) Advance p2'),
 'R201':('WSLP27262L000FEA','Vishay','WP10_INPUT:WSLP2726_KelvinSplit_TwoTerminals','https://www.vishay.com/docs/30179/wslp2726.pdf','30179 Rev29-Jun-2026 p2'),
 'R202':('WSLP2726L2000FEA','Vishay','WP10_INPUT:WSLP2726_KelvinSplit_TwoTerminals','https://www.vishay.com/docs/30179/wslp2726.pdf','30179 Rev29-Jun-2026 p2'),
 'U205':('LT3013EDE#PBF','Analog Devices','WP10_INPUT:LT3013_DE12_EP13_3x4_Pin1LeftTop','https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf','RevE pp2,11,19'),
 'U206':('TPS3808G01DBVR','Texas Instruments','Package_TO_SOT_SMD:SOT-23-6','https://www.ti.com/lit/ds/symlink/tps3808.pdf','RevN DBV pp4,36-37'),
 'Q204':('2N7002K-7','DiodesInc','Package_TO_SOT_SMD:SOT-23','https://www.diodes.com/assets/datasheets/ds30896.pdf','DS30896 Rev20-2 pp1,7; online read, local PDF absent'),
 'D201':('SMBJ30A-13-F','Diodes Incorporated','WP10_INPUT:SMBJ30A_A1K2','https://www.diodes.com/datasheet/download/SMBJ5.0%28C%29A-SMBJ170%28C%29A.pdf','DS19002 Rev20-2 May2017 pp1,5-6; online read'),
 'D202':('STPS3H100U','STMicroelectronics','WP10_INPUT:STPS3H100U_A1K2','https://www.st.com/resource/en/datasheet/stps3h100.pdf','DS6597 Rev3 pp5-6,9; online read, local requests timed out'),
}
for ref,(mpn,mfr,fp,url,rev) in CORE.items():
 PARTS[ref]=dict(MPN=mpn,manufacturer=mfr,footprint=fp,source_url=url,source_revision=rev,
  status='SELECTED_FOOTPRINT_CANDIDATE_QUALIFICATION_OPEN')
PARTS['Q201']['status']='ADVANCE_DATASHEET_GEOMETRY_CANDIDATE_SOA_THERMAL_OPEN'
for ref in ['D201','D202']:PARTS[ref]['pins']={'1':'A','2':'K'}
PARTS['D202'].update(replaces='MBR3100',replacement_reason='Diodes MBR3100 marked Obsolete; STPS3H100U Active at2026-09-10',
 active_source_url='https://www.st.com/en/diodes-and-rectifiers/stps3h100.html',
 old_status_url='https://www.diodes.com/part/view/MBR3100',IF_AV_A=3,VRRM_V=100,
 surge_test=dict(A=75,pulse_s=.010,waveform='single half sine'),system_clamp_verified=False)
