"""V34 single consumer for the two CPL branches and three distinct IQ/leak paths.

Upper-voltage algebraic equilibrium only. No dynamic or device validation.
"""
import math
from shared_battery_path import current,derivative

def operating_point(c,pack,shared,eta,hot,copper_C=100.,contact_extra_ohm=0.):
    e=c['electrical'];m=e['aux_protection_model'];r=dict(e['main_R_components_ohm'])
    r['Q201_25C']*=hot;r['copper_20C']*=1+.00393*(copper_C-20)
    rm=sum(r.values());pre=r['fuse_typical_20C'];ra=e['aux_R_ohm']+contact_extra_ohm
    apre=m['before_efuse_IQ_ohm']+contact_extra_ohm;iq=m['quiescent_current_A'];ic=.003;leak=.003
    mw=e['main_output_W']/eta+e['startup_input_W'];aw=e['aux_output_W']/e['eta_aux']
    assert 0<=apre<=ra and ra-apre>=m['on_resistance_ohm']-1e-12 and 0<=pre<=rm and min(pack,eta,hot)>0 and shared>=0
    shift=pre*ic+rm*leak;ashift=apre*iq
    lower=max(shift+2*math.sqrt(rm*mw),ashift+2*math.sqrt(ra*aw),1e-10)
    def currents(v):
        im=current(v-shift,rm,mw);ia=current(v-ashift,ra,aw)
        return (None if im is None else im+leak),ia
    def f(v):
        im,ia=currents(v)
        return math.inf if im is None or ia is None else v+shared*(im+ia+ic+iq)-pack
    def df(v):return 1+shared*(derivative(v-shift,rm,mw)+derivative(v-ashift,ra,aw))
    if pack<=lower or df(pack)<=0:
        return dict(equilibrium_found=False,protection_class='NO_UPPER_ALGEBRAIC_ROOT')
    lo=lower+max(1e-10,lower*1e-12);hi=pack
    if df(lo)<0:
        left,right=lo,hi
        for _ in range(90):
            mid=(left+right)/2
            if df(mid)<0:left=mid
            else:right=mid
        lo=(left+right)/2
    if f(lo)>1e-10:return dict(equilibrium_found=False,protection_class='NO_UPPER_ALGEBRAIC_ROOT')
    for _ in range(90):
        mid=(lo+hi)/2
        if f(mid)<=0:lo=mid
        else:hi=mid
    v=(lo+hi)/2;im,ia=currents(v);ib=im+ia+ic+iq
    vf=v-pre*(im+ic);vm=vf-(rm-pre)*im;va=v-apre*(ia+iq);vt=va-(ra-apre)*ia
    heat=dict(shared_contact_loop=shared*ib*ib,main_before_sense=pre*(im+ic)**2,
      main_after_sense=(rm-pre)*im*im,auxiliary_before_efuse_IQ=apre*(ia+iq)**2,
      auxiliary_after_efuse_IQ=(ra-apre)*ia*ia,controller_allocation=vf*ic,
      input_capacitor_leakage=vm*leak,efuse_quiescent=va*iq)
    efuse_cond=ia*ia*m['on_resistance_ohm']
    h=dict(Q201=im*im*r['Q201_25C'],shunts=im*im*r['shunts'],fuse=heat['main_before_sense'],
      copper=im*im*r['copper_20C'],other_main=im*im*r['other_wiring_contacts_allocation'],
      shared_contact=heat['shared_contact_loop'],
      aux_branch=heat['auxiliary_before_efuse_IQ']+heat['auxiliary_after_efuse_IQ']-efuse_cond,
      efuse_conduction=efuse_cond,efuse_quiescent=va*iq,
      CHB=e['main_output_W']*(1/eta-1),THN=e['aux_output_W']*(1/e['eta_aux']-1),
      input_startup=e['startup_input_W'],input_controller=vf*ic,input_capacitor_leakage=vm*leak,
      STOP_output_allocation=e['aux_output_W'],brake_bias_output_allocation=1.)
    il=e['protection_screens']['current_limit_screen_A'];uv=e['protection_screens']['UVLO_falling_screen_V'];ov=e['protection_screens']['OVLO_rising_screen_V']
    cls='ASSUMED_ON_POINT_BLOCKED_BY_UVLO' if vf<uv[0] else 'ASSUMED_ON_POINT_BLOCKED_BY_OVLO' if vf>ov[1] else 'ASSUMED_ON_POINT_BLOCKED_BY_CURRENT_LIMIT' if im>il[1] else 'PROTECTION_CORNER_DEPENDENT' if vf<uv[1] or vf>ov[0] or im>il[0] else 'CONDITIONAL_HOLD_STARTUP_UNVERIFIED'
    au=m['UVLO_falling_screen_V'];ao=m['OVP_rising_screen_V'];ai=m['current_limit_conditional_A']
    ac='BLOCKED_BY_AUX_UV' if va<au[0] else 'BLOCKED_BY_AUX_OV' if va>ao[1] else 'BLOCKED_BY_AUX_ILIM' if ia>ai[1] else 'AUX_PROTECTION_CORNER_DEPENDENT' if va<au[1] or va>ao[0] or ia>ai[0] else 'CONDITIONAL_AUX_ON_STARTUP_UNVERIFIED'
    out=dict(equilibrium_found=True,pack_V=pack,junction_V=v,main_fused_V=vf,main_input_V=vm,aux_input_V=vt,
      efuse_input_V=va,main_A=im,aux_A=ia,battery_A=ib,controller_A=ic,main_leak_A=leak,efuse_quiescent_A=iq,
      input_power_W=pack*ib,heat_W=heat,heat_breakdown_W=h,accounted_non_arm_heat_W=sum(h.values()),
      power_balance_residual_W=pack*ib-mw-aw-sum(heat.values()),
      heat_balance_residual_W=pack*ib-(e['main_output_W']-1)-sum(h.values()),
      shared_voltage_residual_V=f(v),algebraic_branch_slope=df(v),
      main_R_ohm=rm,main_R_breakdown_ohm=r,aux_R_ohm=ra,aux_before_IQ_R_ohm=apre,shared_R_ohm=shared,eta_main=eta,active=True,
      battery_current_margin_A=e['battery_current_limit_A']-ib,main_converter_input_margin_V=vm-9.5,
      efuse_W=efuse_cond+va*iq,R202_W=im*im*.0005,R202_element_above_terminal_K=im*im*.0005*6,
      R202_terminal_temperature_C=None,efuse_junction_temperature_C=None,
      protection_class=cls,aux_protection_class=ac,aux_Ron_spec_current_domain=0.1<=ia<=2.,
      efuse_cold_UVLO_rise_margin_V=va-max(m['UVLO_rising_screen_V']),
      dynamic_stability_verified=False,hardware_feasibility='UNKNOWN_UNMEASURED_INPUTS_AND_MISSING_HEAT_PATHS',
      real_motor_terminal_power_W=None,output_distribution_loss_W=e['output_distribution_losses_W'],arm_heat_W=e['arm_local_heat_W'],
      scope='ALGEBRAIC_SENSITIVITY_NOT_DYNAMIC_STABILITY_OR_APPROVED_MISSION',
      protection_screens_are_unqualified=True,hypothetical_on_heat_not_actual_if_protection_trips=True)
    assert max(abs(out['power_balance_residual_W']),abs(out['heat_balance_residual_W']))<1e-7
    return out
