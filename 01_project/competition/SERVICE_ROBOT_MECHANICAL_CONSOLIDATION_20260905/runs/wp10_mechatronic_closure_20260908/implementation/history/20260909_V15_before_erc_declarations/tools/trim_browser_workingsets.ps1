$ErrorActionPreference = 'Stop'
# User 2026-09-09 explicitly requested background memory cleanup after closing tabs.
# EmptyWorkingSet is a reversible residency trim, not process termination.
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Wp10WorkingSetTrim {
 [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
 [DllImport("psapi.dll", SetLastError=true)] public static extern bool EmptyWorkingSet(IntPtr handle);
 [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);
}
'@
function MemorySnapshot {
 $mem = Get-CimInstance Win32_OperatingSystem
 [pscustomobject]@{ available_MiB=[math]::Round($mem.FreePhysicalMemory/1024,2); free_virtual_MiB=[math]::Round($mem.FreeVirtualMemory/1024,2) }
}
$before = MemorySnapshot
$actions = @()
$candidates = Get-Process -Name chrome,msedge -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 64MB }
foreach ($taskProcess in $candidates) {
 $residentBefore=$taskProcess.WorkingSet64
 $taskHandle=[Wp10WorkingSetTrim]::OpenProcess(0x500,$false,$taskProcess.Id)
 $ok=$false
 if ($taskHandle -ne [IntPtr]::Zero) {
  try { $ok=[Wp10WorkingSetTrim]::EmptyWorkingSet($taskHandle) }
  finally { [void][Wp10WorkingSetTrim]::CloseHandle($taskHandle) }
 }
 $actions += [pscustomobject]@{ id=$taskProcess.Id; name=$taskProcess.ProcessName; RSS_before_MiB=[math]::Round($residentBefore/1MB,2); trimmed=$ok; terminated=$false }
}
$after = MemorySnapshot
$record = [pscustomobject]@{ method='EmptyWorkingSet'; scope='chrome,msedge resident working sets only'; process_termination=$false; unsaved_documents_closed=$false; persistent_committed_memory_freed_claim=$false; before=$before; after=$after; actions=$actions }
$outputPath=Join-Path $PSScriptRoot '../logs/browser_workingset_cleanup_20260909.json'
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outputPath -Encoding utf8
$record | Select-Object method,before,after,@{n='trimmed_processes';e={@($actions|Where-Object trimmed).Count}} | ConvertTo-Json -Depth 4
