"""Two constant-power branches behind a shared battery contact loop.

All voltages are differential. R_shared counts each mated power pole once,
including the return pole; it is not a pair of paralleled power pins.
The solver selects the upper-voltage algebraic branch. This is NOT a dynamic
stability proof, a BMS model, or an enable/disable time-domain simulation.
"""
import math


def current(v, resistance, power):
    if power == 0:
        return 0.0
    if v <= 0 or v * v < 4 * resistance * power:
        return None
    # Rationalized lower-current quadratic root avoids cancellation at R=0.
    return 2 * power / (v + math.sqrt(max(0.0, v*v-4*resistance*power)))


def derivative(v, resistance, power):
    if power == 0:
        return 0.0
    disc = v*v-4*resistance*power
    if disc <= 0:
        return -math.inf
    i = current(v, resistance, power)
    return -i / math.sqrt(disc)


def solve(pack_v, shared_r, main_r, main_pre_r, aux_r, main_w, aux_w,
          controller_a=0.003):
    assert pack_v > 0 and min(shared_r, main_r, main_pre_r, aux_r,
                              main_w, aux_w, controller_a) >= 0
    assert main_r >= main_pre_r
    shift = main_pre_r * controller_a
    lower = max(shift + 2*math.sqrt(main_r*main_w),
                2*math.sqrt(aux_r*aux_w), 1e-10)

    def branches(v):
        return current(v-shift, main_r, main_w), current(v, aux_r, aux_w)

    def f(v):
        im, ia = branches(v)
        if im is None or ia is None:
            return math.inf
        return v + shared_r*(im+ia+controller_a)-pack_v

    def df(v):
        return 1 + shared_r*(derivative(v-shift, main_r, main_w)
                             + derivative(v, aux_r, aux_w))

    if pack_v < lower:
        return dict(equilibrium_found=False,
                    reason='PACK_BELOW_BRANCH_HIGH_VOLTAGE_DOMAIN')
    if shared_r == 0:
        v = pack_v
    else:
        lo = lower + max(1e-10, lower*1e-12)
        if lo >= pack_v or df(pack_v) <= 0:
            return dict(equilibrium_found=False,
                        reason='NO_UPPER_ROOT_IN_HIGH_VOLTAGE_BRANCH_DOMAIN')
        if df(lo) >= 0:
            minimum = lo
        else:
            left, right = lo, pack_v
            for _ in range(100):
                mid = (left+right)/2
                if df(mid) < 0: left = mid
                else: right = mid
            minimum = (left+right)/2
        if f(minimum) > 1e-10:
            return dict(equilibrium_found=False,
                        reason='SHARED_PATH_HAS_NO_UPPER_ROOT',
                        minimum_voltage_residual_V=f(minimum))
        left, right = minimum, pack_v
        for _ in range(100):
            mid = (left+right)/2
            if f(mid) <= 0: left = mid
            else: right = mid
        v = (left+right)/2
    im, ia = branches(v)
    if im is None or ia is None:
        return dict(equilibrium_found=False, reason='BRANCH_ROOT_UNDEFINED')
    total = im+ia+controller_a
    fused = v-main_pre_r*(im+controller_a)
    main_in = fused-(main_r-main_pre_r)*im
    aux_in = v-aux_r*ia
    heat = dict(shared_contact_loop=total*total*shared_r,
                main_before_sense=(im+controller_a)**2*main_pre_r,
                main_after_sense=im*im*(main_r-main_pre_r),
                auxiliary_branch=ia*ia*aux_r,
                controller_allocation=fused*controller_a)
    residual = pack_v*total-main_w-aux_w-sum(heat.values())
    assert abs(residual) < 1e-7 and abs(f(v)) < 1e-9
    return dict(equilibrium_found=True, junction_V=v, main_fused_V=fused,
                main_input_V=main_in, aux_input_V=aux_in, main_A=im, aux_A=ia,
                controller_A=controller_a, battery_A=total,
                input_power_W=pack_v*total, heat_W=heat,
                power_balance_residual_W=residual,
                shared_voltage_residual_V=f(v),
                algebraic_branch_slope=df(v) if shared_r else 1.0,
                dynamic_stability_verified=False)


def hold_boundary(pack_v, required_sense_v, shared_r, main_r, main_pre_r,
                  aux_r, main_w, aux_w, controller_a=0.003):
    """Invert a fixed MAIN_FUSED threshold; not a selected battery cutoff."""
    im = current(required_sense_v, main_r-main_pre_r, main_w)
    if im is None:
        return None
    vj = required_sense_v+main_pre_r*(im+controller_a)
    ia = current(vj, aux_r, aux_w)
    if ia is None:
        return None
    total = im+ia+controller_a
    return dict(sense_threshold_V=required_sense_v,
                junction_required_V=vj, main_A=im, battery_A=total,
                maximum_shared_loop_R_ohm_at_given_pack_V=(pack_v-vj)/total,
                required_pack_V_for_given_shared_R=vj+shared_r*total,
                mission_operating_minimum_or_cutoff_selected=False)
