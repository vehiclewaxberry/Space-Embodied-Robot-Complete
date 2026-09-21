"""OEM-bound candidate passives. Pure data: importing does not write files."""
R_URL='https://www.vishay.com/docs/28758/tnpw_e3.pdf'
C_URL='https://www.wima.de/wp-content/uploads/media/e_WIMA_MKP_2.pdf'
TIMING_PASSIVES={}
for ref,ohms,code in [
 ('R203',47500,'47K5'),('R204',5900,'5K90'),('R205',120000,'120K'),
 ('R206',10000,'10K0'),('R207',30100,'30K1')]:
 TIMING_PASSIVES[ref]=dict(MPN='TNPW0603'+code+'BEEA',manufacturer='Vishay',
  resistance_ohm=ohms,initial_tolerance_fraction=.001,TCR_per_K=25e-6,
  general_mode_P70_W=.110,general_mode_max_film_C=125,operating_voltage_max_V=100,
  source_url=R_URL,source_file='sources/tnpw_e3_20260410_v24.pdf',
  source_revision='28758 Rev10-Apr-2026',source_pages=[1,2,4],
  source_sha256='6f0508c568cb355aaf2accdd33fe3a780d3ea5ef207c4c9a71839a8acadc33a5',
  footprint='Resistor_SMD:R_0603_1608Metric',
  status='SELECTED_CANDIDATE_THERMAL_LIFE_AND_LAYOUT_OPEN',
  order_code_basis='OEM part-number table: B=0.1%, E=25ppm/K, EA=lead-free reel. Stock not verified.')
TIMING_PASSIVES['C201']=dict(MPN='MKP2C041001N00JSSD',manufacturer='WIMA',
 C_nominal_F=1e-6,initial_tolerance_fraction=.05,rated_DC_V=63,temperature_C=[-55,100],
 insulation_resistance_ohm_lower=1e11,IR_test_scope='20C, 50V for1min; transfer to TIMER voltage is a declared ohmic sensitivity, not full-temperature guarantee',
 dielectric='metallized polypropylene',dielectric_absorption_reference_fraction=.0005,
 effective_C_requirement_F=[.9e-6,1.1e-6],effective_C_full_environment_verified=False,
 body_LWH_mm=[7.2,11,16],pitch_mm=5,pitch_exit_tolerance_mm=.5,lead_diameter_nominal_mm=.5,
 bulk_lead_length_mm=[4,6],body_and_lead_diameter_tolerances_verified=False,
 DC_voltage_derating_fraction_per_K_above85C=.0135,
 source_url=C_URL,source_file='sources/wima_mkp2_v24.pdf',source_revision='03.26',
 source_pages=[1,2],source_sha256='1c8527fb1fef607bbf2f67997225102f0cc8e0a433816fe65fe4e58064fe0ec4',
 footprint='WP10_TIMING:C201_MKP2_1uF_P5_Slot2',
 status='SELECTED_CANDIDATE_EFFECTIVE_C_LEAKAGE_AND_MOUNT_OPEN',
 order_code_basis='MKP2C041001N00 + J(5%) + S(bulk) + SD(6-2mm leads)')

