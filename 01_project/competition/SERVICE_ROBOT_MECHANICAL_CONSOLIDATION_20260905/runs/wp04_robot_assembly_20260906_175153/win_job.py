"""Windows Job Object restricts and owns only this guard's child tree."""
import ctypes
from ctypes import wintypes as W
S=ctypes.c_size_t
class BASIC(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',W.DWORD),('MinimumWorkingSetSize',S),('MaximumWorkingSetSize',S),('ActiveProcessLimit',W.DWORD),('Affinity',S),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
class IO(ctypes.Structure):
    _fields_=[(n,ctypes.c_ulonglong) for n in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
class EXT(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',S),('JobMemoryLimit',S),('PeakProcessMemoryUsed',S),('PeakJobMemoryUsed',S)]
class OwnedJob:
    def __init__(self,mib):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        for name,types,ret in [('CreateJobObjectW',[W.LPVOID,W.LPCWSTR],W.HANDLE),('SetInformationJobObject',[W.HANDLE,ctypes.c_int,W.LPVOID,W.DWORD],W.BOOL),('AssignProcessToJobObject',[W.HANDLE,W.HANDLE],W.BOOL),('TerminateJobObject',[W.HANDLE,W.UINT],W.BOOL),('CloseHandle',[W.HANDLE],W.BOOL)]:
            f=getattr(self.k,name);f.argtypes=types;f.restype=ret
        self.handle=self.k.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=EXT();info.BasicLimitInformation.LimitFlags=0x2000|0x100|0x200
        info.ProcessMemoryLimit=info.JobMemoryLimit=int(mib*2**20)
        if not self.k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            self.close();raise ctypes.WinError(ctypes.get_last_error())
    def assign(self,p):
        if not self.k.AssignProcessToJobObject(self.handle,int(p._handle)):
            p.terminate();raise ctypes.WinError(ctypes.get_last_error())
    def terminate(self):
        if self.handle:self.k.TerminateJobObject(self.handle,2)
    def close(self):
        if self.handle:self.k.CloseHandle(self.handle);self.handle=None
