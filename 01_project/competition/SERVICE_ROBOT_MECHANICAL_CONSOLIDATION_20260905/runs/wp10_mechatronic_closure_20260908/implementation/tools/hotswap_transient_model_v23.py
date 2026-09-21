"""Low-memory reduced LM5069 model. No import-time writes or native CAD loads.

Instantaneous regulation, a fixed protected-pack voltage and algebraic auxiliary
load are declared abstractions. This is NOT a gate-charge/SPICE/BMS model.
The controlled block includes Q201 and the unallocated post-shunt wire loss;
its energy upper-bounds Q201 only within this lumped circuit, not in hardware.
"""
from dataclasses import dataclass
import math
from shared_battery_path import current


@dataclass(frozen=True)
class Circuit:
    pack_v: float
    shared_r: float
    pre_r: float
    total_main_r: float
    aux_r: float
    aux_w: float
    rs: float
    rpwr: float
    power_scale: float
    vcl: float
    uv_rise: float
    uv_fall: float
    cap_f: float = .00264
    controller_a: float = .003
    cap_leak_a: float = .003
    bias_w: float = .25

    @property
    def block_on_r(self):
        # The old total ALREADY contains shunts + Q201. No double counting.
        r = self.total_main_r - self.pre_r - self.rs
        assert r >= .021, 'Allocation below Q201 25C maximum Rds alone'
        return r

    def source(self, main_a):
        before_aux = self.pack_v - self.shared_r*(main_a+self.controller_a)
        ia = current(before_aux, self.shared_r+self.aux_r, self.aux_w)
        if ia is None:
            raise ValueError('No auxiliary high-voltage algebraic root')
        junction = before_aux-self.shared_r*ia
        fused = junction-self.pre_r*(main_a+self.controller_a)
        return ia, junction, fused

    def limit_power(self, drop):
        # TI Rev G p20 Eq9 rearranged, with explicit test-condition transfer.
        return self.power_scale*(self.rpwr/(1.30e5*self.rs)+.00118*drop/self.rs)

    def regulated(self, out_v):
        def drop(i):
            return self.source(i)[2]-i*self.rs-out_v
        left, right = 0., self.pack_v/(self.total_main_r+self.shared_r)
        for _ in range(38):
            mid=(left+right)/2
            if drop(mid)>mid*self.block_on_r:left=mid
            else:right=mid
        ion=(left+right)/2
        ceiling=min(ion,self.vcl/self.rs)
        # A fully-on endpoint can have low loss beyond a high-loss region.
        # Find the first limiting root, not a spurious high-current root.
        def h(i):
            d=drop(i)
            return i*d-self.limit_power(d)
        lo,hi=0.,ceiling
        for _ in range(30):
            a=lo+(hi-lo)/3;b=hi-(hi-lo)/3
            if h(a)<h(b):lo=a
            else:hi=b
        peak=(lo+hi)/2
        if h(peak)>1e-9:
            lo,hi=0.,peak
            for _ in range(38):
                mid=(lo+hi)/2
                if h(mid)<0:lo=mid
                else:hi=mid
            i=(lo+hi)/2;mode='POWER_LIMIT'
        else:
            i=ceiling
            mode='CURRENT_LIMIT' if ion>self.vcl/self.rs+1e-7 else 'ON'
        ia,vj,vf=self.source(i);d=vf-i*self.rs-out_v
        total=i+ia+self.controller_a
        heat=dict(shared=total**2*self.shared_r,pre=(i+self.controller_a)**2*self.pre_r,
                  shunts=i*i*self.rs,controlled_block=i*d,aux=ia*ia*self.aux_r,
                  controller=vf*self.controller_a)
        residual=self.pack_v*total-self.aux_w-out_v*i-sum(heat.values())
        assert abs(residual)<1e-7
        return dict(main_a=i,aux_a=ia,battery_a=total,fused_v=vf,block_drop_v=d,
                    block_w=i*d,limit_w=self.limit_power(d),mode=mode,
                    power_balance_residual_w=residual,heat_w=heat)

    def precharge(self, dv=.025, trace=False):
        cold=self.source(0.)[2]
        if cold<self.uv_rise:
            return dict(outcome='COLD_UVLO_OFF',cold_fused_v=cold,active_limit_s=0.,trace=[])
        t=energy=i2t=fuse_i2t=0.;minvf=cold;maxi=0.;pgtime=None;rows=[]
        max_residual=0.;last=None
        # End at first release of current/power regulation. CHB remains OFF.
        for k in range(math.ceil(self.pack_v/dv)):
            v=(k+.5)*dv;r=self.regulated(v);last=r
            minvf=min(minvf,r['fused_v']);maxi=max(maxi,r['main_a'])
            if r['fused_v']<self.uv_fall:
                return dict(outcome='UVLO_DURING_PRECHARGE',cold_fused_v=cold,
                    active_limit_s=t,voltage_at_stop_v=v,min_fused_v=minvf,
                    block_energy_j=energy,max_main_a=maxi,trace=rows)
            if r['mode']=='ON':break
            # 0.25W at >=1V, 0.25A below: a stated load scenario, not an LDO model.
            load=self.cap_leak_a+self.bias_w/max(v,1.)
            if r['main_a']<=load:
                return dict(outcome='NO_POSITIVE_CHARGE_CURRENT',active_limit_s=t,trace=rows)
            dt=self.cap_f*dv/(r['main_a']-load)
            if r['block_drop_v']<=.67 and pgtime is None:pgtime=t
            if trace and (k%4==0):rows.append(dict(t_s=t,cap_v=v,**{q:r[q] for q in
                ['main_a','aux_a','fused_v','block_drop_v','block_w','mode']}))
            t+=dt;energy+=r['block_w']*dt;i2t+=r['main_a']**2*dt
            fuse_i2t+=(r['main_a']+self.controller_a)**2*dt
            max_residual=max(max_residual,abs(r['power_balance_residual_w']))
        else:
            return dict(outcome='LIMIT_NOT_EXITED_IN_DOMAIN',active_limit_s=t,trace=rows)
        return dict(outcome='REGULATION_EXIT_REDUCED_MODEL',cold_fused_v=cold,
            active_limit_s=t,voltage_at_stop_v=v,min_fused_v=minvf,max_main_a=maxi,
            block_energy_j=energy,pass_path_I2t_a2s=i2t,F201_I2t_a2s=fuse_i2t,
            maximum_instantaneous_power_balance_residual_w=max_residual,
            conservative_PGD_0p67V_crossing_s=pgtime,
            CHB_enable_and_final_settling_simulated=False,trace=rows)


def timer_pulse_train(cap_f,high_v,charge_a,sink_a,segments,start_v=0.):
    """Exact affine timer charge/discharge, preserving history between pulses.
    Segments = [(seconds, limiting_bool), ...]; threshold crossing latches -1.
    No automatic reset and no fabricated gate-off maximum delay.
    """
    v=start_v;t=0.;rows=[]
    assert cap_f>0 and 0<=start_v<high_v
    for duration,limiting in segments:
        assert duration>=0
        slope=(charge_a if limiting else -sink_a)/cap_f
        if limiting and v+slope*duration>=high_v:
            elapsed=(high_v-v)/slope
            rows.append(dict(start_s=t,end_s=t+elapsed,from_v=v,to_v=high_v,limiting=True))
            return dict(latched=True,latch_s=t+elapsed,final_v=high_v,segments=rows)
        after=max(0.,v+slope*duration)
        rows.append(dict(start_s=t,end_s=t+duration,from_v=v,to_v=after,limiting=limiting))
        v=after;t+=duration
    return dict(latched=False,latch_s=None,final_v=v,segments=rows)
