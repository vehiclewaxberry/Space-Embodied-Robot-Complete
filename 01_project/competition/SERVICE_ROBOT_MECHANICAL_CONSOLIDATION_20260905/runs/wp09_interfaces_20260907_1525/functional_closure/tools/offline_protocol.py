"""Pure byte-array protocol fixture. No serial, CAN, sockets, GPIO or device I/O.
This is an own-protocol ground fixture, not a MiPS or DM protocol implementation.
"""
from pathlib import Path
from dataclasses import dataclass
import json,struct,zlib,hashlib
F=Path(__file__).resolve().parents[1]
MAGIC=b'WPF1';MAX_PAYLOAD=512;TIMEOUT_MS=100
def encode(seq,payload):
 raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode()
 if len(raw)>MAX_PAYLOAD:raise ValueError('oversize')
 head=MAGIC+struct.pack('>BIH',1,seq,len(raw))+raw
 return head+struct.pack('>I',zlib.crc32(head))
def decode(raw):
 if len(raw)<15 or raw[:4]!=MAGIC:raise ValueError('header')
 version,seq,n=struct.unpack('>BIH',raw[4:11])
 if version!=1 or n>MAX_PAYLOAD or len(raw)!=n+15:raise ValueError('version_or_length')
 if zlib.crc32(raw[:-4])!=struct.unpack('>I',raw[-4:])[0]:raise ValueError('crc')
 p=json.loads(raw[11:-4]);
 if not isinstance(p,dict) or set(p)!={'command'} or p['command'] not in ['PING','STATUS','ENABLE','DISARM','RESET']:raise ValueError('command_schema')
 return seq,p['command']
@dataclass
class VirtualEndpoint:
 state:str='DISARMED'
 last_seq:int=-1
 last_valid_ms:int|None=None
 verified_virtual_inputs:bool=False
 estop:bool=False
 fault:str|None=None
 def trip(self,why):self.state='FAULT';self.fault=why
 def tick(self,now):
  if self.estop:self.trip('ESTOP')
  elif self.state=='ENABLED' and (self.last_valid_ms is None or now-self.last_valid_ms>=TIMEOUT_MS):self.trip('HEARTBEAT_TIMEOUT')
 def receive(self,raw,now):
  self.tick(now)
  try:seq,cmd=decode(raw)
  except (ValueError,UnicodeError,json.JSONDecodeError):self.trip('MALFORMED');return self.snapshot()
  if seq<=self.last_seq:self.trip('REPLAY_OR_OUT_OF_ORDER');return self.snapshot()
  self.last_seq=seq;self.last_valid_ms=now
  if cmd=='DISARM':self.state='DISARMED' if not self.estop else 'FAULT'
  elif cmd=='RESET' and not self.estop:self.state='DISARMED';self.fault=None
  elif cmd=='ENABLE' and self.state=='DISARMED':
   if self.verified_virtual_inputs and not self.estop:self.state='ENABLED'
   else:self.trip('UNKNOWN_OR_FAILED_INTERLOCK')
  return self.snapshot()
 def snapshot(self):return dict(state=self.state,fault=self.fault,virtual_enable=self.state=='ENABLED',physical_output=False,physical_transport=None)
def run():
 records=[]
 def check(name,actual,expected):
  ok=actual==expected;records.append(dict(name=name,actual=actual,expected=expected,passed=ok));assert ok,name
 def enabled():
  e=VirtualEndpoint(verified_virtual_inputs=True);e.receive(encode(1,{'command':'ENABLE'}),0);return e
 e=VirtualEndpoint();check('powerup_disarmed',e.state,'DISARMED');e.receive(encode(1,{'command':'ENABLE'}),0);check('unknown_blocks_enable',e.state,'FAULT')
 e=enabled();check('virtual_prerequisites_enable',e.state,'ENABLED');e.tick(99);check('before_deadline',e.state,'ENABLED');e.tick(100);check('deadline_trips',e.fault,'HEARTBEAT_TIMEOUT')
 e.receive(encode(2,{'command':'PING'}),101);check('late_ping_does_not_reenable',e.state,'FAULT');e.receive(encode(3,{'command':'RESET'}),102);check('reset_disarms',e.state,'DISARMED')
 e=enabled();e.estop=True;e.receive(encode(2,{'command':'RESET'}),1);check('estop_reset_rejected',e.state,'FAULT')
 e=enabled();e.receive(encode(1,{'command':'PING'}),1);check('replay_trips',e.fault,'REPLAY_OR_OUT_OF_ORDER')
 for name,raw in [('crc_corruption',encode(2,{'command':'PING'})[:-1]+b'\x00'),('truncated',encode(2,{'command':'PING'})[:-3]),('unsupported_command',encode(2,{'command':'FIRE'})),('unexpected_field',encode(2,{'command':'PING','pin':1}))]:
  e=enabled();e.receive(raw,1);check(name,e.fault,'MALFORMED')
 e=enabled();e.receive(encode(2,{'command':'DISARM'}),1);check('disarm_request',e.state,'DISARMED');check('no_physical_output',e.snapshot()['physical_output'],False)
 for seq in [0,1,65535,4294967295]:check('frame_roundtrip_'+str(seq),decode(encode(seq,{'command':'STATUS'})),(seq,'STATUS'))
 result=dict(status='PASS_OWN_PROTOCOL_OFFLINE_FIXTURE_ONLY',tests=records,test_count=len(records),hardware_tests_executed=0,transport='IN_MEMORY_BYTES_ONLY',timeout_ms_requirement=TIMEOUT_MS,timeout_is_measured=False,actual_DM_stop_latency_ms=None,actual_MiPS_protocol_implemented=False,actual_safety_relay_implemented=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=['No claim of hardware emergency-stop integrity, bus dropout protection or gravity holding','Heartbeat deadline is a chosen fixture requirement; no operating-system or hardware timing guarantee','Safety interlock inputs are virtual test inputs, not acquired sensors','CRC is corruption detection, not authentication','Sequence state persistent only within fixture lifetime; reconnect starts disarmed; no cross-boot cryptographic replay protection'])
 (F/'results/OFFLINE_PROTOCOL_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (F/'inputs/OWN_PROTOCOL_CONTRACT.json').write_text(json.dumps(dict(magic='WPF1',version=1,endianness='big',header='magic4 version1 seq4 payload_length2',payload='UTF8 JSON exactly one command field',crc='CRC32(header+payload),4bytes big-endian',max_payload=512,commands=['PING','STATUS','ENABLE','DISARM','RESET'],heartbeat_timeout_requirement_ms=100,command_semantics='VIRTUAL FIXTURE ONLY; ENABLE never drives hardware',default='DISARMED',interlocks=['Verified pin polarity and return','Protection and monitored K1 feedback','Regeneration absorption through power loss','Temperature and bus voltage','Mechanical arm support and safe work volume','Deliberate enable after reset'],hardware_interface=None),ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(tests=len(records),passed=all(x['passed'] for x in records),physical_tests=0)))
if __name__=='__main__':run()
