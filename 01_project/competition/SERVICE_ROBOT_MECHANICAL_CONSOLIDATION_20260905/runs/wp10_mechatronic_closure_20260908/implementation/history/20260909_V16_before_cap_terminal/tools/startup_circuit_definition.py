"""Primary-domain CHB enable, independent of motor bus and STOP RUN latch.

This is a physical circuit candidate, not proof of brown-ramp behavior or a
replacement for the independent K1 contactor. All pins refer to INPUT_RETURN.
"""
def add_startup(part, passive, parts, groups, nc):
    before = set(parts)
    part('U205','LT3013EDE#PBF',{'1':'NC','2':'OUT','3':'OUT','4':'ADJ','5':'GND','6':'PWRGD_NC','7':'CT_UNUSED','8':'SHDN','9':'NC','10':'IN','11':'IN','12':'NC','13':'GND_EP'},'lt3013.pdf RevE pp2-3,11-13,17','Input-side startup bias; unrelated to load-side brake bias')
    part('U206','TPS3808G01DBVR',{'1':'RESET_N','2':'GND','3':'MR_N','4':'CT_OPEN_20ms','5':'SENSE','6':'VDD'},'startup_tps3808.pdf RevN Aug2026 pp4-7','Qualify MAIN_FUSED voltage and PGD before CHB enable')
    part('Q204','2N7002K-7',{'1':'G','2':'S','3':'D'},'startup_2n7002k_diodes.pdf DiodesInc DS30896 Rev20-2 July2024 pp1,3','Primary-side open-drain CHB enable; DiodesInc part, not Nexperia EOL variant')
    for r,v,role in [
        ('R211','38.3k_0.1pct_25ppm','Startup bias feedback upper; nominal5.99V'),
        ('R212','10k_0.1pct_25ppm','Startup bias feedback lower'),
        ('R213','4.70k_1pct','Bias minimum-load bleeder'),
        ('R214','3.48k_0.1pct_25ppm','PGD pull-up placed at U201; receiver pull-down detects downstream link opening'),
        ('R215','374k_0.1pct_25ppm','Upstream MAIN_FUSED UV sense upper; not capacitor-side rail'),
        ('R216','10k_0.1pct_25ppm','Upstream UV sense lower'),
        ('R217','33k_1pct','RESET gate pull-up; bounds5V gate floor and6.5V RESET ceiling; POR load remains open'),
        ('R218','2.2M_1pct','Passive gate discharge when startup bias absent'),
        ('R219','100k_1pct','CHB control pull-up to precharged input; no floating off state'),
        ('R220','10k_1pct','MR receiver pull-down dominates internal70k pull-up on link open'),
        ('R221','100ohm_1pct','PGD signal series link; source-side pull-up, receiver-side pull-down'),
        ('C211','1uF_100V_EFFECTIVE_MIN1uF','Startup bias local input'),
        ('C212','10uF_50V_EFFECTIVE_MIN3.3uF','Startup bias stability; MPN and derating still open'),
        ('C213','100nF_25V','Supervisor bypass')]:
        passive(r,v,role)
    def g(n,*eps): groups.setdefault(n,[]).extend(eps)
    g('PRECHARGED_PLUS','U205.10','U205.11','U205.8','C211.1','R219.1')
    g('MAIN_FUSED','R215.1')
    g('INPUT_RETURN','U205.5','U205.13','U205.7','C211.2','C212.2','R212.2','R213.2','U206.2','R216.2','R218.2','C213.2','Q204.2','R220.2')
    g('STARTUP_BIAS','U205.2','U205.3','R211.1','R213.1','C212.1','U206.6','R214.1','R217.1','C213.1')
    g('STARTUP_ADJ','U205.4','R211.2','R212.1')
    g('HS_PGD','R214.2','R221.1')
    g('STARTUP_PG_RECEIVER','R221.2','R220.1','U206.3')
    g('STARTUP_INPUT_SENSE','R215.2','R216.1','U206.5')
    g('CHB_ENABLE_GATE','U206.1','R217.2','R218.1','Q204.1')
    g('CHB_ENABLE','Q204.3','R219.2')
    nc.update({'U205.1','U205.6','U205.9','U205.12','U206.4'})
    # Retain J201 as an unpopulated diagnostic point, never a fitted bypass.
    parts['J201'].update(mpn='PROJECT_CHB_ENABLE_TEST_POINTS_NO_JUMPER', role='Probe only; never bridge pins to bypass startup supervisor', status='NO_JUMPER_DESIGN')
    parts['TP201'].update(role='PGD now feeds U206 MR via input-side bias; low-input false-high independently screened',status='CONNECTED_TO_STARTUP_SUPERVISOR')
    return sorted(set(parts)-before)

def pin_type(ref,p):
    if ref=='U205':
        return 'no_connect' if p in ['1','6','9','12'] else 'power_out' if p=='2' else 'passive' if p in ['3','7'] else 'power_in' if p in ['5','10','11','13'] else 'input'
    if ref=='U206': return 'open_collector' if p=='1' else 'power_in' if p in ['2','6'] else 'input'
    return None
