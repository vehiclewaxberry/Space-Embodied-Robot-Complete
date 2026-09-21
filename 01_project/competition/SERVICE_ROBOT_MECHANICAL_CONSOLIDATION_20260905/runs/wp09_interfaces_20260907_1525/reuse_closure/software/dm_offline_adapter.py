"""Project thin adapter: protocol construction and deterministic fake transport only.
No physical transport implementation, enable, zeroing, parameter writes or firmware API.
"""
from dataclasses import dataclass
from dm_codec import Frame, MODELS, RxParser, decode_feedback, encode_mit, encode_dm_serial, finite

@dataclass(frozen=True)
class JointConfig:
    name: str
    motor_id: int
    feedback_id: int
    model: str
    firmware_revision: str
    motor_rad_per_joint_rad: float
    motor_zero_rad: float
    q_min_rad: float
    q_max_rad: float
    velocity_max_rad_s: float
    torque_max_nm: float
    kp_max_nm_rad: float
    kd_max_nm_s_rad: float
    timeout_ms: float
    evidence_kind: str

    def __post_init__(self):
        if self.evidence_kind!='SYNTHETIC_OFFLINE_FIXTURE':raise ValueError('only offline fixtures executable')
        if self.model not in MODELS or not self.firmware_revision:raise ValueError('explicit model and firmware required')
        if type(self.motor_id) is not int or not 1<=self.motor_id<=7:raise ValueError('B601 reference ID 1..7')
        if type(self.feedback_id) is not int or not 0<=self.feedback_id<=0x7ff:raise ValueError('feedback ID')
        finite(self.motor_rad_per_joint_rad,self.motor_zero_rad,self.q_min_rad,self.q_max_rad,
               self.velocity_max_rad_s,self.torque_max_nm,self.kp_max_nm_rad,self.kd_max_nm_s_rad,self.timeout_ms)
        if self.motor_rad_per_joint_rad==0 or not self.q_min_rad<self.q_max_rad or self.timeout_ms<=0:
            raise ValueError('transform, limits or timeout')
        if min(self.velocity_max_rad_s,self.torque_max_nm,self.kp_max_nm_rad,self.kd_max_nm_s_rad)<=0:
            raise ValueError('positive command limits required')

class FakeTransport:
    def __init__(self): self.tx=[]
    def send(self, raw): self.tx.append(bytes(raw))

class OfflineAdapter:
    def __init__(self, config, transport):
        if type(transport) is not FakeTransport:raise TypeError('physical / subclass transports prohibited')
        self.cfg=config; self.transport=transport;self.parser=RxParser()
        self.power_permission=False;self.latch=None;self.last_feedback_ms=None
        self.feedback=None;self.last_clock_ms=None;self.last_command_sequence=-1

    def trip(self, reason): self.latch=reason;self.power_permission=False
    def tick(self, now_ms):
        finite(now_ms)
        if now_ms<0 or (self.last_clock_ms is not None and now_ms<self.last_clock_ms):
            self.trip('CLOCK_ROLLBACK');raise ValueError('monotonic clock required')
        self.last_clock_ms=now_ms
        if self.last_feedback_ms is not None and now_ms-self.last_feedback_ms>self.cfg.timeout_ms:
            self.trip('FEEDBACK_TIMEOUT')

    def set_simulated_power_permission(self, allowed):
        if type(allowed) is not bool:raise ValueError('boolean permission')
        if allowed and self.latch:raise RuntimeError('fault latch prohibits power permission')
        self.power_permission=allowed  # software fixture input, never a hardware safety output.

    def receive(self, raw, now_ms):
        self.tick(now_ms)
        before=self.parser.rejected
        try: frames=self.parser.feed(raw)
        except ValueError:
            self.trip('FRAMING_ERROR');raise
        if self.parser.rejected>before:self.trip('FRAMING_ERROR')
        for frame in frames:
            # Stricter than upstream's accepts_frame OR: both identifiers must agree.
            if frame.arbitration_id!=self.cfg.feedback_id or (frame.data[0]&15)!=self.cfg.motor_id:
                self.trip('WRONG_ID');raise ValueError('unexpected feedback identity')
            # Registers are outside this read-only sensor adapter; ambiguous patterns are rejected.
            if frame.data[1]<=15 and frame.data[2] in (0x33,0x55):
                self.trip('NON_SENSOR_FRAME');raise ValueError('register / ambiguous frame')
            self.feedback=decode_feedback(frame.data,MODELS[self.cfg.model])
            r=self.cfg.motor_rad_per_joint_rad
            self.feedback['joint_position_rad']=(self.feedback['position_rad']-self.cfg.motor_zero_rad)/r
            self.feedback['joint_velocity_rad_s']=self.feedback['velocity_rad_s']/r
            self.feedback['joint_torque_nm']=self.feedback['torque_nm']*r
            self.last_feedback_ms=now_ms
            if self.feedback['status']==0:self.power_permission=False
            if self.feedback['status'] not in (0,1):self.trip(self.feedback['status_name'])
        return self.feedback

    def reset_while_disabled(self, now_ms):
        self.tick(now_ms)
        if self.feedback is None or self.feedback['status']!=0 or now_ms-self.last_feedback_ms>self.cfg.timeout_ms:
            raise RuntimeError('fresh disabled feedback required for explicit offline reset')
        self.latch=None;self.power_permission=False

    def command_joint_mit(self, q_rad, velocity_rad_s, torque_nm, kp, kd, now_ms, sequence):
        self.tick(now_ms);finite(q_rad,velocity_rad_s,torque_nm,kp,kd)
        if self.latch or not self.power_permission or self.feedback is None or self.feedback['status']!=1:
            raise RuntimeError('command denied by independent communication / power state')
        if type(sequence) is not int or sequence<=self.last_command_sequence:raise ValueError('local command replay')
        c=self.cfg;r=c.motor_rad_per_joint_rad
        if not c.q_min_rad<=q_rad<=c.q_max_rad or abs(velocity_rad_s)>c.velocity_max_rad_s or abs(torque_nm)>c.torque_max_nm:
            raise ValueError('joint command outside configured fixture limits')
        if not 0<=kp<=c.kp_max_nm_rad or not 0<=kd<=c.kd_max_nm_s_rad:raise ValueError('gain limits')
        p=r*q_rad+c.motor_zero_rad;v=r*velocity_rad_s;t=torque_nm/r
        mk=kp/(r*r);md=kd/(r*r);limits=MODELS[c.model]
        if abs(p)>limits.p or abs(v)>limits.v or abs(t)>limits.t or mk>500 or md>5:
            raise ValueError('motor protocol limits; reject rather than silently clip')
        payload=encode_mit(p,v,t,mk,md,limits)
        raw=encode_dm_serial(Frame(c.motor_id,payload))
        self.transport.send(raw);self.last_command_sequence=sequence
        return raw
