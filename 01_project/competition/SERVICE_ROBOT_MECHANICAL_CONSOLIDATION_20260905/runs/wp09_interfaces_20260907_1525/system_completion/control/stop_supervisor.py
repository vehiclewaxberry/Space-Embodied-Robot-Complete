"""Offline executable stop/permission policy; no bus, hardware, or motor I/O.

The physical adapter must supply validated observations and bounded timers.
This policy does not implement a safety-rated stop, contactor or regen clamp.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class State(str,Enum):
    INHIBITED='INHIBITED'
    READY='READY'
    RUNNING='RUNNING'
    DECELERATING='DECELERATING'
    SUPPORTED='SUPPORTED'
    CONTACT_OPEN='CONTACT_OPEN_REQUESTED'
    FAULT='FAULT'

@dataclass(frozen=True)
class Observation:
    sequence:int
    time_ms:int
    binding_verified:bool=False
    independent_stop_chain_ok:Optional[bool]=None
    bus_supply_ok:Optional[bool]=None
    converter_thermal_ok:Optional[bool]=None
    brake_thermal_ok:Optional[bool]=None
    regen_path_available:Optional[bool]=None
    return_path_ok:Optional[bool]=None
    can_heartbeat_ok:Optional[bool]=None
    aux_closed:Optional[bool]=None
    load_bus_discharged:Optional[bool]=None
    residual_energy_bounded:Optional[bool]=None
    support_engaged:Optional[bool]=None
    explicit_reset:bool=False
    run_request:bool=False
    stop_request:bool=False

@dataclass(frozen=True)
class Command:
    state:State
    motion_permit:bool
    coil_request:bool
    decelerate_request:bool
    faults:tuple

class Supervisor:
    def __init__(self):
        self.state=State.INHIBITED
        self.last_sequence=-1
        self.last_time=-1
        self.previous_reset=False
        self.previous_run=False
        self.faults=[]

    def step(self,o:Observation)->Command:
        reset_edge=o.explicit_reset and not self.previous_reset
        run_edge=o.run_request and not self.previous_run
        self.previous_reset=o.explicit_reset
        self.previous_run=o.run_request
        telemetry_fresh=o.sequence>self.last_sequence and o.time_ms>self.last_time
        self.last_sequence=max(self.last_sequence,o.sequence)
        self.last_time=max(self.last_time,o.time_ms)
        required=('independent_stop_chain_ok','bus_supply_ok','converter_thermal_ok','brake_thermal_ok','regen_path_available','return_path_ok','can_heartbeat_ok')
        missing=[k for k in required if getattr(o,k) is not True]
        if not telemetry_fresh: missing.append('replayed_or_nonmonotonic_observation')
        if not o.binding_verified: missing.append('physical_interface_binding_absent')
        if missing:
            self.faults=sorted(set(self.faults+missing));self.state=State.FAULT
        elif self.state in (State.INHIBITED,State.FAULT,State.CONTACT_OPEN):
            # A reset is accepted only with actual support and two observations of the switched side.
            if reset_edge and o.support_engaged is True and o.aux_closed is False and o.load_bus_discharged is True and not o.run_request:
                self.faults=[];self.state=State.READY
        elif self.state==State.READY:
            # Closing the power path is a separate, explicit event; no automatic restart.
            if o.stop_request:self.state=State.CONTACT_OPEN
            elif run_edge and o.support_engaged is True:self.state=State.RUNNING
        elif self.state==State.RUNNING:
            if o.stop_request:self.state=State.DECELERATING
        elif self.state==State.DECELERATING:
            if o.residual_energy_bounded is True and o.support_engaged is True:
                self.state=State.SUPPORTED
        elif self.state==State.SUPPORTED:
            self.state=State.CONTACT_OPEN
        # A commanded-open contact with measured live bus must not be called isolated.
        # Discharge wait and contact-travel timers belong to the physical adapter; this class does not guess them.
        coil=self.state in (State.RUNNING,State.DECELERATING,State.SUPPORTED)
        motion=self.state==State.RUNNING and o.aux_closed is True and o.load_bus_discharged is False
        return Command(self.state,motion,coil,self.state==State.DECELERATING,tuple(self.faults))
