"""Conditional catalog-box angular-impulse sizing; no actual nozzle inference."""
import itertools,math
from coupled_adapter import HERE,WP09,read,sha,dump,load_candidate

def run():
    c=load_candidate();contract=read(c['propulsion']['source_contract'])
    ref=contract['source_references']['FROZEN_PROPULSION_MODEL'];assert sha(ref['path'])==ref['sha256']
    old=read(ref['path']);H=old['task_reference']['historical_capture']['H_combined_COM_magnitude_Nms_csv']
    rows=[]
    for part in old['candidates']:
        radius=math.sqrt(sum((d/1000)**2 for d in part['envelope_mm']))/2
        impulse_lower=H/radius
        rows.append(dict(id=part['id'],historical_H_Nms=H,catalog_box_radius_m=radius,
            H_upper_if_all_nozzles_in_box_Nms=part['total_impulse_Ns']*radius,
            required_total_impulse_lower_Ns=impulse_lower,
            propellant_lower_kg_at_catalog_Isp=impulse_lower/(part['Isp_s']*9.80665),
            hardware_nozzles_contained_by_box=None,net_force_zero_or_fixed_frame_zero_total_force_required=True,
            actual_task_feasibility='UNKNOWN',catalog_shape_is_not_controlled_max_installation_envelope=True))
    cp=next(x for x in rows if x['id']=='CPOD8_RCM')
    cp['time_lower_s_assuming_at_most_two_12mN_jets']=cp['required_total_impulse_lower_Ns']/(2*.012)
    cp['two_jet_concurrency_allowed_by_command_ICD']=None
    dims=c['mechanical']['CPOD_project_carrier_mm'][:2]
    out=dict(candidate_sha256=sha(HERE/'CANDIDATE.json'),source_script_sha256=sha(__file__),
      historical_input_sha256=ref['sha256'],rows=rows,
      derivation='For contained r within radius rho and sum(J)=0: |sum(r cross J)| <= rho*sum|J|. This assumption is NOT established for the installed candidate.',
      C_POD_hardware_qualification=False,mission_budget_closed=False,
      command_min_width_s=c['propulsion']['minimum_command_width_s'],
      equivalent_MIB_duration_s=[.0005/.012,.0005/.008],equivalent_duration_is_command_duration=False,
      project_carrier_planar_size_mm=dims,OEM_mating_holes_defined=False)
    dump('PROPULSION_RESOURCE_SCREEN.json',out)
    print([(r['id'],r['H_upper_if_all_nozzles_in_box_Nms'],r['propellant_lower_kg_at_catalog_Isp']) for r in rows])

if __name__=='__main__':run()
