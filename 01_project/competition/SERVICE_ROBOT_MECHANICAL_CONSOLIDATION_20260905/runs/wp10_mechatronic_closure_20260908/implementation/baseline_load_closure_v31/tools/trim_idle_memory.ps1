$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class V31MemoryCleanup {
 [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Auto)] public class Status {
  public uint length=64; public uint load;
  public ulong totalPhys,availPhys,totalPage,availPage,totalVirtual,availVirtual,availExtended;
 }
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool GlobalMemoryStatusEx([In,Out] Status s);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern IntPtr OpenProcess(uint rights,bool inherit,int pid);
 [DllImport("psapi.dll",SetLastError=true)] public static extern bool EmptyWorkingSet(IntPtr handle);
 [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);
}
'@
function Read-Memory {
 $taskStatus = New-Object V31MemoryCleanup+Status
 if (-not [V31MemoryCleanup]::GlobalMemoryStatusEx($taskStatus)) { throw 'Memory probe failed' }
 [pscustomobject]@{available_MiB=[math]::Round($taskStatus.availPhys/1MB,2);load_percent=$taskStatus.load}
}
$taskBefore = Read-Memory
$taskActions = @()
# Reclaim pageable resident pages; these vendor background services keep running.
foreach ($taskName in @('ROGLiveService','AcPowerNotification','asus_framework')) {
 foreach ($taskProcess in @(Get-Process -Name $taskName -ErrorAction SilentlyContinue)) {
  $taskResidentBefore = $taskProcess.WorkingSet64
  $taskHandle = [V31MemoryCleanup]::OpenProcess(0x0500,$false,$taskProcess.Id)
  if ($taskHandle -eq [IntPtr]::Zero) {
   $taskActions += [pscustomobject]@{pid=$taskProcess.Id;name=$taskName;action='TRIM_NOT_PERMITTED';error=[Runtime.InteropServices.Marshal]::GetLastWin32Error()}
   continue
  }
  try {
   $taskOK = [V31MemoryCleanup]::EmptyWorkingSet($taskHandle)
   $taskError = if($taskOK){0}else{[Runtime.InteropServices.Marshal]::GetLastWin32Error()}
   $taskProcess.Refresh()
   $taskActions += [pscustomobject]@{pid=$taskProcess.Id;name=$taskName;action='WORKING_SET_TRIM';succeeded=$taskOK;error=$taskError;before_MiB=[math]::Round($taskResidentBefore/1MB,2);after_MiB=[math]::Round($taskProcess.WorkingSet64/1MB,2);process_terminated=$false}
  } finally { [V31MemoryCleanup]::CloseHandle($taskHandle) | Out-Null }
 }
}
# SolidWorks fast-start preloader is not a CAD document session. Do not stop SLDWORKS or other apps.
if (-not (Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)) {
 foreach ($taskPreloader in @(Get-Process -Name sldworks_fs -ErrorAction SilentlyContinue)) {
  if ($taskPreloader.Path -eq 'F:\Windows_profile\solidworks\SOLIDWORKS\sldworks_fs.exe') {
   $taskCheck = Get-Process -Id $taskPreloader.Id -ErrorAction Stop
   if ($taskCheck.StartTime -eq $taskPreloader.StartTime -and $taskCheck.Path -eq $taskPreloader.Path) {
    Stop-Process -Id $taskPreloader.Id -ErrorAction Stop
    $taskActions += [pscustomobject]@{pid=$taskPreloader.Id;name='sldworks_fs';action='STOP_IDLE_FAST_START_PRELOADER';process_terminated=$true;documents_closed=0}
   }
  }
 }
}
$taskAfter = Read-Memory
$taskReceipt = [pscustomobject]@{time=(Get-Date).ToString('o');before=$taskBefore;actions=$taskActions;after=$taskAfter;native_2GiB_start_threshold_met=($taskAfter.available_MiB -ge 2048);notes='Working-set trimming is reversible paging, not a reduction in committed allocation; other concurrent activity affects free memory. No CAD documents, browsers, Codex or active worker processes were terminated.'}
$taskReceipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $PSScriptRoot '../results/MEMORY_CLEANUP.json') -Encoding utf8
$taskReceipt | ConvertTo-Json -Depth 6
