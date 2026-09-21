[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$candidateRoot = Split-Path -Parent $PSScriptRoot
$targetPath = Join-Path $PSScriptRoot 'B51R1_MASTER_SKELETON_V2.SLDPRT'
$receiptPath = Join-Path $PSScriptRoot 'B51R1_MASTER_SKELETON_V2_NATIVE_BUILD_ATTEMPT_002.json'
$builderPath = Join-Path $PSScriptRoot 'B51R1_MasterSkeletonNativeBuilder.dll'
$interopPath = 'F:\Windows_profile\solidworks\SOLIDWORKS\api\redist\SolidWorks.Interop.sldworks.dll'

$processes = @(
    Get-Process -Name 'SLDWORKS' -ErrorAction SilentlyContinue
)
if ($processes.Count -ne 1) {
    throw "Expected exactly one authorized visible SLDWORKS process; found $($processes.Count)."
}
if (-not $processes[0].Responding) {
    throw "The authorized SLDWORKS process is not responding before build start."
}
if (-not (Test-Path -LiteralPath $interopPath -PathType Leaf)) {
    throw "SolidWorks interop assembly not found: $interopPath"
}
if (-not (Test-Path -LiteralPath $builderPath -PathType Leaf)) {
    throw "Compiled builder not found: $builderPath"
}
if (Test-Path -LiteralPath $targetPath) {
    throw "Final target already exists; refusing overwrite: $targetPath"
}

[void][Reflection.Assembly]::LoadFrom($interopPath)
[void][Reflection.Assembly]::LoadFrom($builderPath)

$result = [B51R1MasterSkeletonNativeBuilder]::Run(
    $targetPath,
    $receiptPath
)

[pscustomobject]@{
    candidate_root = $candidateRoot
    builder_result = $result
    target = $targetPath
    target_exists = Test-Path -LiteralPath $targetPath
    receipt = $receiptPath
    receipt_exists = Test-Path -LiteralPath $receiptPath
    progress_log = [IO.Path]::Combine(
        [IO.Path]::GetDirectoryName($receiptPath),
        [IO.Path]::GetFileNameWithoutExtension($receiptPath) + '_PROGRESS.log'
    )
} | ConvertTo-Json -Depth 3

exit $result
