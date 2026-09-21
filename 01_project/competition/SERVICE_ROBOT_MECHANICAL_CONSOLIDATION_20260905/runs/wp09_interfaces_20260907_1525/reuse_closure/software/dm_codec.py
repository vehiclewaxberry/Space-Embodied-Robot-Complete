"""Offline Python port of selected MotorBridge pure DM codec functions.

Derived from motorbridge c48ebc4b2f250aa1f411a580d9d7b626e187040f,
motor_vendors/damiao/src/protocol.rs and motor_core/src/dm_serial.rs.
Copyright (c) 2026 motorbridge. MIT license: ../sources/motorbridge/LICENSE.
Modification: no I/O; reject nonfinite inputs; strict standard eight-byte frames;
bounded streaming parser and more conservative framing validation.
This executes Python, not the Rust library. No captured hardware frames included.
"""
from dataclasses import dataclass
import math
import struct

def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def finite(*xs):
    if any(not math.isfinite(x) for x in xs):
        raise ValueError('nonfinite protocol value')

@dataclass(frozen=True)
class Limits:
    p: float
    v: float
    t: float

# Protocol scaling ranges, NOT current joint travel / safe speed / continuous torque.
MODELS = {'4310': Limits(12.5, 30.0, 10.0), '4340P': Limits(12.5, 10.0, 28.0)}
STATUS = {0:'DISABLED', 1:'ENABLED', 8:'OVER_VOLTAGE', 9:'UNDER_VOLTAGE',
          10:'OVER_CURRENT', 11:'MOS_OVER_TEMP', 12:'ROTOR_OVER_TEMP',
          13:'LOST_COMM', 14:'OVERLOAD'}

def float_to_uint(x, lo, hi, bits):
    finite(x, lo, hi)
    if not lo < hi or bits not in (12,16): raise ValueError('range / bits')
    x,lo,hi=f32(x),f32(lo),f32(hi)
    return int(f32(f32(f32(min(hi,max(lo,x))-lo)*f32((1<<bits)-1))/f32(hi-lo)))

def uint_to_float(x, lo, hi, bits):
    if not 0 <= x < 1 << bits: raise ValueError('encoded range')
    return f32(f32(f32(f32(x)*f32(hi-lo))/f32((1<<bits)-1))+f32(lo))

def encode_mit(pos, vel, torque, kp, kd, limits):
    p=float_to_uint(pos,-limits.p,limits.p,16)
    v=float_to_uint(vel,-limits.v,limits.v,12)
    t=float_to_uint(torque,-limits.t,limits.t,12)
    k=float_to_uint(kp,0,500,12); d=float_to_uint(kd,0,5,12)
    return bytes([p>>8,p&255,v>>4,((v&15)<<4)|(k>>8),k&255,d>>4,((d&15)<<4)|(t>>8),t&255])

def decode_feedback(data, limits):
    if not isinstance(data,bytes) or len(data)!=8: raise ValueError('feedback requires eight bytes')
    p=(data[1]<<8)|data[2]; v=(data[3]<<4)|(data[4]>>4); t=((data[4]&15)<<8)|data[5]
    return {'motor_id':data[0]&15,'status':data[0]>>4,
            'status_name':STATUS.get(data[0]>>4,'UNKNOWN'),
            'position_rad':uint_to_float(p,-limits.p,limits.p,16),
            'velocity_rad_s':uint_to_float(v,-limits.v,limits.v,12),
            'torque_nm':uint_to_float(t,-limits.t,limits.t,12),
            'mos_temperature_c':data[6],'rotor_temperature_c':data[7]}

@dataclass(frozen=True)
class Frame:
    arbitration_id: int
    data: bytes

def encode_dm_serial(frame):
    if type(frame.arbitration_id) is not int or not 0<=frame.arbitration_id<=0x7ff:
        raise ValueError('requires standard CAN ID')
    if not isinstance(frame.data,bytes) or len(frame.data)!=8: raise ValueError('DLC8 required')
    out=bytearray(30)
    out[:4]=bytes.fromhex('55 aa 1e 03')
    out[4:8]=(1).to_bytes(4,'little');out[8:12]=(10).to_bytes(4,'little')
    out[13:17]=frame.arbitration_id.to_bytes(4,'little');out[18]=8;out[21:29]=frame.data
    return bytes(out)  # upstream CRC byte is zero, NOT an integrity guarantee.

class RxParser:
    """Conservative project parser for upstream's 16-byte DM serial RX envelope."""
    def __init__(self): self.buffer=bytearray(); self.rejected=0
    def feed(self, data):
        if not isinstance(data, bytes): raise ValueError('bytes only')
        if len(data)+len(self.buffer)>1024:
            self.buffer.clear(); raise ValueError('bounded RX buffer overflow')
        self.buffer.extend(data);frames=[]
        while self.buffer:
            if self.buffer[0]!=0xaa: self.buffer.pop(0);continue
            if len(self.buffer)<16:break
            raw=self.buffer[:16]
            aid=int.from_bytes(raw[3:7],'little')
            if raw[1]!=0x11 or raw[2]!=8 or raw[15]!=0x55 or aid>0x7ff:
                self.rejected+=1;self.buffer.pop(0);continue
            del self.buffer[:16];frames.append(Frame(aid,bytes(raw[7:15])))
        return frames
