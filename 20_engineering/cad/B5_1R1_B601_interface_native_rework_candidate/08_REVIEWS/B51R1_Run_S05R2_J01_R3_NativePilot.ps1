[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Create','ColdVerify')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R3'
$carrierDir = Join-Path $root '03_CAD\12_DRIVER_READY_CARRIERS'
$pilotDir = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT'
$checkpointDir = Join-Path $pilotDir 'CHECKPOINTS'
$assemblyTemplate = 'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_assembly.asmdot'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$toolSource = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R3_NativePilotTool.cs'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R3_NativePilotTool.dll'
$toolSourceBytes = 83524
$toolSourceSha256 = '92479871E8E409FD6AF34DC9829DA3D965D289A337D7620196ADB7ED9CE97F19'
$toolDllBytes = 56320
$toolDllSha256 = '0981CAB9C20096D5305982F44FAA2E24B0F53CAFA7CDF6C9BE1B91E37FF011EA'
$toolCompiler = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\MSBuild\Current\Bin\Roslyn\csc.exe'
$toolCompilerBytes = 64808
$toolCompilerSha256 = 'CF9B364171B07822F5AFA44391AE4FB4A4418D2056A5C5A018CE64F62173AB2C'

$mr2PilotGate = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R1_MR2_PILOT_COLD_REOPEN_GATE.json'
$mr2PilotReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R1_PILOT_COLD_REOPEN_RECEIPT.json'
$mr2PilotGateBytes = 1793
$mr2PilotGateSha256 = '358A42B42802CE53D83C9550E47E6526641D1FAD92E598190ABC4BC0FBBDC11B'
$mr2PilotReceiptBytes = 6065
$mr2PilotReceiptSha256 = 'DDC9C05EB489FA43F41F91F2CFA3E8ADDBDC8E880F7A55EC9E0601698D068314'
$baseCarrier = Join-Path $carrierDir 'B51R1_CARRIER_MR2_base_link.SLDPRT'
$link1Carrier = Join-Path $carrierDir 'B51R1_CARRIER_MR2_link1.SLDPRT'
$baseCarrierBytes = 104556
$baseCarrierSha256 = 'E8695447480FDD11B9C87B81E280334E47A68BECA780C4366DBA3F06279C8DFB'
$link1CarrierBytes = 107161
$link1CarrierSha256 = '4E3EDF2D494119F4A4C29E02D16A83CF559BE99ECA57113FE95BE8036721163E'
$hp01DirectReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R2_DIRECT_PART_VERIFY_RECEIPT.json'
$hp01DirectReceiptBytes = 6065
$hp01DirectReceiptSha256 = '4F1D9DC591F2F4F7F00E122EEF9E561414A43765131B93B9DD168E6C9215D883'
$r1ContextFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R1\B51R1_S05R2_J01_R1_CREATE_RECEIPT.json'
$r1ContextFailReceiptBytes = 1433
$r1ContextFailReceiptSha256 = 'AD078FF86F4924C833703F8FEC5360DBAC66279C3944E6C99A0269D2786C2448'
$r2RcwFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R2\B51R1_S05R2_J01_R2_CREATE_RECEIPT.json'
$r2RcwFailReceiptBytes = 3679
$r2RcwFailReceiptSha256 = '70CB5779F930F41FF208FDD7152E95BB4BAE6681096356CB70BFE975C4FC989B'
$j00Assembly = Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R3.SLDASM'
$pilotAssembly = Join-Path $pilotDir 'B51R1_CARRIER_J01_R3_NATIVE_PILOT.SLDASM'
$j00Checkpoint = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_J00_BASELINE_CHECKPOINT.json'
$createReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_CREATE_RECEIPT.json'
$createProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_CREATE_PROGRESS.log'
$createGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_CREATE_GATE.json'
$coldReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_COLD_REOPEN_RECEIPT.json'
$coldProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_COLD_REOPEN_PROGRESS.log'
$finalGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R3_NATIVE_1R_GATE.json'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -ne $Bytes) { throw "$Label byte count mismatch" }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) { throw "$Label SHA-256 mismatch" }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only JSON exists: $Path" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 100 -Compress) + [Environment]::NewLine), $utf8)
}

function Get-Mr2PilotInputs {
    Assert-File $mr2PilotGate $mr2PilotGateBytes $mr2PilotGateSha256 'MR2 Pilot R1 accepted cold-reopen Gate'
    Assert-File $mr2PilotReceipt $mr2PilotReceiptBytes $mr2PilotReceiptSha256 'MR2 Pilot R1 accepted cold-reopen receipt'
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $mr2PilotGate | ConvertFrom-Json
    if ($gate.schema -ne 'B51R1_S05R2_PC_R1_GATE_V1' -or
        $gate.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or $gate.gate_pass -ne $true) {
        throw 'MR2 Pilot R1 cold-reopen Gate is not PASS'
    }
    if ([IO.Path]::GetFullPath([string]$gate.receipt.path) -ne [IO.Path]::GetFullPath($mr2PilotReceipt)) {
        throw 'MR2 Pilot R1 cold-reopen receipt path mismatch'
    }
    if ([long]$gate.receipt.bytes -ne $mr2PilotReceiptBytes -or
        [string]$gate.receipt.sha256 -ne $mr2PilotReceiptSha256) {
        throw 'MR2 Pilot R1 Gate receipt binding differs from the accepted receipt'
    }
    $receiptState = Get-Content -Raw -Encoding UTF8 -LiteralPath $mr2PilotReceipt | ConvertFrom-Json
    if ($receiptState.schema -ne 'B51R1_S05R2_R1_DRIVER_READY_COLD_REOPEN_V3' -or
        $receiptState.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or
        [long]$receiptState.verified_part_count -ne 2 -or $receiptState.normal_application_exit -ne $true) {
        throw 'MR2 Pilot R1 accepted cold-reopen receipt contract mismatch'
    }
    $parts = @($gate.parts)
    if ($parts.Count -ne 2 -or @($parts.link | Select-Object -Unique).Count -ne 2) {
        throw 'MR2 Pilot Gate does not contain two unique Carrier parts'
    }
    $result = @()
    foreach ($link in @('base_link','link1')) {
        $part = @($parts | Where-Object { $_.link -eq $link })
        if ($part.Count -ne 1) { throw "MR2 Gate part is not unique: $link" }
        $expectedPath = if ($link -eq 'base_link') { $baseCarrier } else { $link1Carrier }
        if ([IO.Path]::GetFullPath([string]$part[0].path) -ne [IO.Path]::GetFullPath($expectedPath)) {
            throw "MR2 Gate path mismatch: $link"
        }
        $expectedBytes = if ($link -eq 'base_link') { $baseCarrierBytes } else { $link1CarrierBytes }
        $expectedSha = if ($link -eq 'base_link') { $baseCarrierSha256 } else { $link1CarrierSha256 }
        $expectedFeatures = if ($link -eq 'base_link') { 27 } else { 29 }
        if ([long]$part[0].bytes -ne $expectedBytes -or [string]$part[0].sha256 -ne $expectedSha -or
            [long]$part[0].feature_count -ne $expectedFeatures -or [long]$part[0].body_count -ne 0 -or
            [long]$part[0].external_reference_count -ne 0) {
            throw "MR2 Gate accepted part binding is invalid: $link"
        }
        $receiptPart = @($receiptState.parts | Where-Object { $_.link -eq $link })
        if ($receiptPart.Count -ne 1 -or [long]$receiptPart[0].feature_count -ne $expectedFeatures -or
            [long]$receiptPart[0].body_count -ne 0 -or [long]$receiptPart[0].external_reference_count -ne 0 -or
            [string]$receiptPart[0].sha256_before_after -ne $expectedSha) {
            throw "MR2 accepted receipt part binding is invalid: $link"
        }
        Assert-File $expectedPath $expectedBytes $expectedSha "MR2_ACCEPTED_$link"
        $result += [ordered]@{link=$link;path=$expectedPath;bytes=$expectedBytes;sha256=$expectedSha;feature_count=$expectedFeatures;body_count=0;external_reference_count=0}
    }
    return $result
}

function Get-RecoveryPrerequisites {
    Assert-File $hp01DirectReceipt $hp01DirectReceiptBytes $hp01DirectReceiptSha256 'J01 R3 direct-open health receipt'
    Assert-File $r1ContextFailReceipt $r1ContextFailReceiptBytes $r1ContextFailReceiptSha256 'J01 R1 context failure receipt'
    Assert-File $r2RcwFailReceipt $r2RcwFailReceiptBytes $r2RcwFailReceiptSha256 'J01 R2 RCW failure receipt'

    $direct = Get-Content -Raw -Encoding UTF8 -LiteralPath $hp01DirectReceipt | ConvertFrom-Json
    if ($direct.schema -ne 'B51R1_S05R2_R1_DRIVER_READY_COLD_REOPEN_V3' -or
        $direct.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or
        [long]$direct.verified_part_count -ne 2 -or $direct.normal_document_close -ne $true -or
        $direct.normal_application_exit -ne $true -or [long]$direct.save3_call_count -ne 0 -or
        [long]$direct.save_as_call_count -ne 0) {
        throw 'J01 R3 direct-open health receipt contract mismatch'
    }
    $directParts = @($direct.parts)
    if ($directParts.Count -ne 2 -or @($directParts.link | Select-Object -Unique).Count -ne 2) {
        throw 'J01 R3 direct-open health receipt does not bind two unique parts'
    }
    foreach ($link in @('base_link','link1')) {
        $part = @($directParts | Where-Object { $_.link -eq $link })
        if ($part.Count -ne 1) { throw "J01 R3 direct-open part is not unique: $link" }
        $expectedPath = if ($link -eq 'base_link') { $baseCarrier } else { $link1Carrier }
        $expectedBytes = if ($link -eq 'base_link') { $baseCarrierBytes } else { $link1CarrierBytes }
        $expectedSha = if ($link -eq 'base_link') { $baseCarrierSha256 } else { $link1CarrierSha256 }
        if ([IO.Path]::GetFullPath([string]$part[0].path) -ne [IO.Path]::GetFullPath($expectedPath) -or
            [long]$part[0].bytes -ne $expectedBytes -or [string]$part[0].sha256_before_after -ne $expectedSha -or
            [long]$part[0].body_count -ne 0 -or [long]$part[0].external_reference_count -ne 0) {
            throw "J01 R3 direct-open health binding mismatch: $link"
        }
    }

    $failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r1ContextFailReceipt | ConvertFrom-Json
    if ($failed.schema -ne 'B51R1_S05R2_J01_R1_NATIVE_PILOT_CREATE_V1' -or
        $failed.status -ne 'S05R2_J01_R1_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $failed.gate_pass -isnot [bool] -or $failed.gate_pass -ne $false -or
        [string]$failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$failed.exception -notmatch 'errors=2097152') {
        throw 'J01 R1 context failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','mate_preselection_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$failed.$field -ne 0) { throw "J01 R1 failure was not zero-action at $field" }
    }
    if ([string]$failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$failed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R1 context failure receipt does not preserve MR2 input hashes'
    }

    $rcwFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r2RcwFailReceipt | ConvertFrom-Json
    if ($rcwFailed.schema -ne 'B51R1_S05R2_J01_R2_NATIVE_PILOT_CREATE_V1' -or
        $rcwFailed.status -ne 'S05R2_J01_R2_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $rcwFailed.gate_pass -isnot [bool] -or $rcwFailed.gate_pass -ne $false -or
        [string]$rcwFailed.exception_type -ne 'System.Runtime.InteropServices.InvalidComObjectException' -or
        [string]$rcwFailed.exception -notmatch 'IAssemblyDoc.AddComponent5') {
        throw 'J01 R2 RCW failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','mate_preselection_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$rcwFailed.$field -ne 0) { throw "J01 R2 failure was not zero-action at $field" }
    }
    $rcwPreloads = @($rcwFailed.preload_operations)
    if ($rcwPreloads.Count -ne 2 -or [long]$rcwFailed.document_count_before_new_assembly -ne 2 -or
        [long]$rcwFailed.document_count_after_new_assembly -ne 3) {
        throw 'J01 R2 RCW failure did not complete the strict two-part preload transition'
    }
    foreach ($preload in $rcwPreloads) {
        if ($preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
            $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
            [long]$preload.open_errors -ne 0 -or [long]$preload.open_warnings -ne 0) {
            throw 'J01 R2 RCW failure did not preserve strict preload health evidence'
        }
    }
    if ([string]$rcwFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$rcwFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R2 RCW failure receipt does not preserve MR2 input hashes'
    }

    return @(
        [ordered]@{id='HP01_DIRECT_OPEN_PASS_RECEIPT';path=$hp01DirectReceipt;bytes=$hp01DirectReceiptBytes;sha256=$hp01DirectReceiptSha256;status=[string]$direct.status},
        [ordered]@{id='J01_R1_CONTEXT_FAIL_RECEIPT';path=$r1ContextFailReceipt;bytes=$r1ContextFailReceiptBytes;sha256=$r1ContextFailReceiptSha256;status=[string]$failed.status;error_code=2097152},
        [ordered]@{id='J01_R2_RCW_FAIL_RECEIPT';path=$r2RcwFailReceipt;bytes=$r2RcwFailReceiptBytes;sha256=$r2RcwFailReceiptSha256;status=[string]$rcwFailed.status;exception_type=[string]$rcwFailed.exception_type}
    )
}

function Wait-ForSolidWorks([Diagnostics.Process]$LaunchHandle) {
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $processes[0].Refresh()
        if ($processes[0].Responding -and $processes[0].MainWindowHandle -ne [IntPtr]::Zero) {
            return $processes[0].Id
        }
    }
    throw "SOLIDWORKS did not reach the sole visible responsive state; launch PID=$($LaunchHandle.Id)"
}

Assert-File $assemblyTemplate 34942 '37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC' 'Assembly template'
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SOLIDWORKS executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SOLIDWORKS interop'
Assert-File $readinessDll 5632 'DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2' 'Readiness probe'
Assert-File $toolCompiler $toolCompilerBytes $toolCompilerSha256 'J01 R3 frozen-tool compiler provenance'
Assert-File $toolSource $toolSourceBytes $toolSourceSha256 'J01 Pilot frozen source'
Assert-File $toolDll $toolDllBytes $toolDllSha256 'J01 Pilot frozen binary'
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "$Mode requires zero existing SLDWORKS processes"
}

$mr2Inputs = @(Get-Mr2PilotInputs)
$recoveryPrerequisites = @(Get-RecoveryPrerequisites)
$mr2LockedArtifacts = @(
    [ordered]@{id='MR2_PILOT_R1_COLD_GATE';path=$mr2PilotGate;bytes=$mr2PilotGateBytes;sha256=$mr2PilotGateSha256},
    [ordered]@{id='MR2_PILOT_R1_COLD_RECEIPT';path=$mr2PilotReceipt;bytes=$mr2PilotReceiptBytes;sha256=$mr2PilotReceiptSha256}
)
$recoveryLockedArtifacts = @($recoveryPrerequisites)
[IO.Directory]::CreateDirectory($sessionRoot) | Out-Null

$readinessReceipt = Join-Path $sessionRoot "B51R1_S05R2_J01_R3_$($Mode.ToUpperInvariant())_READINESS_RECEIPT.json"
$inputLock = Join-Path $sessionRoot "B51R1_S05R2_J01_R3_$($Mode.ToUpperInvariant())_INPUT_LOCK.json"
$modeOutputs = if ($Mode -eq 'Create') {
    @($readinessReceipt,$inputLock,$j00Assembly,$pilotAssembly,$j00Checkpoint,$createReceipt,$createProgress,$createGate)
} else {
    @($readinessReceipt,$inputLock,$coldReceipt,$coldProgress,$finalGate)
}
foreach ($path in $modeOutputs) {
    if (Test-Path -LiteralPath $path) { throw "Append-only $Mode output exists: $path" }
}

$coldLockedArtifacts = @()
if ($Mode -eq 'ColdVerify') {
    if (-not (Test-Path -LiteralPath $createGate -PathType Leaf)) { throw "J01 Create Gate missing: $createGate" }
    $created = Get-Content -Raw -Encoding UTF8 -LiteralPath $createGate | ConvertFrom-Json
    if ($created.schema -ne 'B51R1_S05R2_J01_R3_NATIVE_1R_CREATE_GATE_V1' -or
        $created.status -ne 'S05R2_J01_R3_NATIVE_1R_PILOT_CREATE_PASS' -or
        $created.gate_pass -isnot [bool] -or $created.gate_pass -ne $true) {
        throw 'J01 R3 Create Gate is not PASS'
    }
    if ($created.cold_reopen_authorized -isnot [bool] -or $created.cold_reopen_authorized -ne $true) {
        throw 'J01 R3 Create Gate does not authorize cold reopen'
    }
    if ([IO.Path]::GetFullPath([string]$created.receipt.path) -ne [IO.Path]::GetFullPath($createReceipt)) {
        throw 'J01 Create Gate receipt path mismatch'
    }
    if ([IO.Path]::GetFullPath([string]$created.output.path) -ne [IO.Path]::GetFullPath($pilotAssembly)) {
        throw 'J01 Create Gate output path mismatch'
    }
    Assert-File $createReceipt ([long]$created.receipt.bytes) ([string]$created.receipt.sha256) 'J01 Create receipt'
    Assert-File $pilotAssembly ([long]$created.output.bytes) ([string]$created.output.sha256) 'J01 Pilot assembly'
    $createdReceipt = Get-Content -Raw -Encoding UTF8 -LiteralPath $createReceipt | ConvertFrom-Json
    if ($createdReceipt.schema -ne 'B51R1_S05R2_J01_R3_NATIVE_PILOT_CREATE_V1' -or
        $createdReceipt.status -ne 'S05R2_J01_R3_NATIVE_1R_PILOT_CREATE_PASS' -or
        $createdReceipt.gate_pass -isnot [bool] -or $createdReceipt.gate_pass -ne $true) {
        throw 'J01 R3 Create receipt is not PASS'
    }
    if ([IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath($pilotAssembly) -or
        [IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath([string]$created.output.path) -or
        [long]$createdReceipt.output.bytes -ne [long]$created.output.bytes -or
        [string]$createdReceipt.output.sha256 -ne [string]$created.output.sha256) {
        throw 'J01 Create receipt output binding differs from the Create Gate output'
    }
    $coldLockedArtifacts = @(
        [ordered]@{id='J01_R3_CREATE_GATE';path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate},
        [ordered]@{id='J01_R3_CREATE_RECEIPT';path=$createReceipt;bytes=[long]$created.receipt.bytes;sha256=[string]$created.receipt.sha256},
        [ordered]@{id='J01_R3_PILOT_ASSEMBLY';path=$pilotAssembly;bytes=[long]$created.output.bytes;sha256=[string]$created.output.sha256}
    )
}

$launchHandle = $null
$launchedPid = $null
$exitCode = 1
try {
    $launchHandle = Start-Process -FilePath $solidworksExe -PassThru
    $launchedPid = Wait-ForSolidWorks $launchHandle
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'J01 Pilot lost the sole SOLIDWORKS process' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding -or $processes[0].MainWindowHandle -eq [IntPtr]::Zero) {
        throw 'J01 Pilot process was not stable after the zero-COM window'
    }
    Assert-File $toolSource $toolSourceBytes $toolSourceSha256 'J01 Pilot frozen source after zero-COM window'
    Assert-File $toolDll $toolDllBytes $toolDllSha256 'J01 Pilot frozen binary after zero-COM window'
    foreach ($item in $mr2LockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_LOCK_$($item.id)"
    }
    foreach ($item in $recoveryLockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "RECOVERY_LOCK_$($item.id)"
    }
    foreach ($item in $coldLockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "COLD_LOCK_$($item.id)"
    }

    Add-Type -Path $interop
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $readyCode = [B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid,$readinessReceipt)
    if ($readyCode -ne 0) { throw "Readiness probe returned $readyCode" }
    $ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') {
        throw 'J01 Pilot readiness did not pass'
    }

    $lockedItems = @(
        [ordered]@{id='CONTRACT_V4';path=(Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md');bytes=(Get-Item (Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md')).Length;sha256=Get-Sha (Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md')},
        [ordered]@{id='NATIVE_DRIVER_MAPPING_V2';path=(Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv');bytes=(Get-Item (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv')).Length;sha256=Get-Sha (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv')},
        [ordered]@{id='NATIVE_JOINT_REGISTER_V2';path=(Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv');bytes=(Get-Item (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv')).Length;sha256=Get-Sha (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv')},
        [ordered]@{id='TOLERANCE_AUTHORITY';path=(Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml');bytes=(Get-Item (Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml')).Length;sha256=Get-Sha (Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml')},
        [ordered]@{id='J01_TOOL_SOURCE';path=$toolSource;bytes=$toolSourceBytes;sha256=$toolSourceSha256},
        [ordered]@{id='J01_TOOL_BINARY';path=$toolDll;bytes=$toolDllBytes;sha256=$toolDllSha256},
        [ordered]@{id='J01_TOOL_COMPILER';path=$toolCompiler;bytes=$toolCompilerBytes;sha256=$toolCompilerSha256},
        [ordered]@{id='READINESS_RECEIPT';path=$readinessReceipt;bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt}
    )
    $lockedItems += $mr2LockedArtifacts
    $lockedItems += $recoveryLockedArtifacts
    if ($Mode -eq 'ColdVerify') { $lockedItems += $coldLockedArtifacts }
    $lock = [ordered]@{
        schema="B51R1_S05R2_J01_R3_$($Mode.ToUpperInvariant())_INPUT_LOCK_V1"
        generated_at=[DateTimeOffset]::Now.ToString('o')
        status="PASS_S05R2_J01_R3_$($Mode.ToUpperInvariant())_INPUTS_HASH_LOCKED"
        mode=$Mode
        runtime_boundary=[ordered]@{solidworks_process_id=$launchedPid;process_count=1;document_count=0;zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds}
        transaction=[ordered]@{transform2_allowed=$false;move_component_allowed=$false;set_transform_and_solve_allowed=$false;mate_controller_truth_allowed=$false;source_carrier_save_allowed=$false;formal_s05_output_allowed=$false;t005_authorized=$false}
        tool_static_release=[ordered]@{
            source=[ordered]@{path=$toolSource;bytes=$toolSourceBytes;sha256=$toolSourceSha256}
            binary=[ordered]@{path=$toolDll;bytes=$toolDllBytes;sha256=$toolDllSha256}
            compiler=[ordered]@{path=$toolCompiler;bytes=$toolCompilerBytes;sha256=$toolCompilerSha256;arguments='/nologo /target:library /platform:x64 /optimize+ /deterministic+'}
            interop=[ordered]@{path=$interop;bytes=2773312;sha256='FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB'}
        }
        mr2_inputs=$mr2Inputs
        recovery_prerequisites=$recoveryPrerequisites
        locked_items=$lockedItems
        claim_limit='J01_R3_PRELOAD_RECOVERY_NATIVE_1R_PILOT_ONLY_NO_FORMAL_S05_G4_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    if ($Mode -eq 'Create') {
        $result = [B51R1S05R2J01R3NativePilotTool]::Create(
            $launchedPid,$assemblyTemplate,$baseCarrier,$link1Carrier,$j00Assembly,
            $pilotAssembly,$j00Checkpoint,$createReceipt,$createProgress)
        if ($result -ne 0) { throw "J01 Create tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $createReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R3_NATIVE_PILOT_CREATE_V1' -or
            $data.status -ne 'S05R2_J01_R3_NATIVE_1R_PILOT_CREATE_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R3 Create receipt is not PASS'
        }
        if ($data.transform2_call_count -ne 0 -or $data.set_transform_and_solve_call_count -ne 0 -or
            $data.move_component_call_count -ne 0 -or $data.save_as_call_count -ne 2 -or $data.save3_call_count -ne 0 -or
            $data.create_mate_data_call_count -ne 5 -or $data.create_mate_call_count -ne 5 -or
            $data.add_mate5_call_count -ne 0 -or $data.mate_preselection_call_count -ne 0) {
            throw 'J01 Create prohibited API/save count mismatch'
        }
        $preloads = @($data.preload_operations)
        if ($preloads.Count -ne 2 -or [long]$data.document_count_before_new_assembly -ne 2 -or
            [long]$data.document_count_after_new_assembly -ne 3) {
            throw 'J01 R3 preload count or assembly document-count transition mismatch'
        }
        foreach ($index in 0..1) {
            $expectedRole = if ($index -eq 0) { 'BASE_MR2' } else { 'LINK1_MR2' }
            $expectedPath = if ($index -eq 0) { $baseCarrier } else { $link1Carrier }
            $expectedBytes = if ($index -eq 0) { $baseCarrierBytes } else { $link1CarrierBytes }
            $expectedSha = if ($index -eq 0) { $baseCarrierSha256 } else { $link1CarrierSha256 }
            $preload = $preloads[$index]
            if ([string]$preload.role -ne $expectedRole -or
                [IO.Path]::GetFullPath([string]$preload.path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [IO.Path]::GetFullPath([string]$preload.model_path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [long]$preload.bytes -ne $expectedBytes -or [string]$preload.sha256_before -ne $expectedSha -or
                [string]$preload.sha256_after_open -ne $expectedSha -or [long]$preload.open_errors -ne 0 -or
                [long]$preload.open_warnings -ne 0 -or [long]$preload.document_count_before -ne $index -or
                [long]$preload.document_count_after -ne ($index + 1) -or
                $preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
                $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
                $preload.held_loaded_until_add_component5 -isnot [bool] -or $preload.held_loaded_until_add_component5 -ne $true -or
                $preload.add_component5_succeeded -isnot [bool] -or $preload.add_component5_succeeded -ne $true -or
                $preload.standalone_title_closed -isnot [bool] -or $preload.standalone_title_closed -ne $true) {
                throw "J01 R3 strict preload evidence mismatch: $expectedRole"
            }
        }
        foreach ($item in $lockedItems) {
            Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "CREATE_POST_$($item.id)"
        }
        Assert-File $pilotAssembly ([long]$data.output.bytes) ([string]$data.output.sha256) 'J01 Pilot output'
        foreach ($item in $mr2Inputs) { Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_$($item.link)_POST" }
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SOLIDWORKS remains after J01 Create normal exit' }
        $gate = [ordered]@{
            schema='B51R1_S05R2_J01_R3_NATIVE_1R_CREATE_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R3_NATIVE_1R_PILOT_CREATE_PASS';gate_pass=$true
            receipt=[ordered]@{path=$createReceipt;bytes=(Get-Item $createReceipt).Length;sha256=Get-Sha $createReceipt}
            j00_checkpoint=[ordered]@{path=$j00Checkpoint;bytes=(Get-Item $j00Checkpoint).Length;sha256=Get-Sha $j00Checkpoint}
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{preloaded_before_new_assembly=$true;strict_preload_errors_and_warnings_zero=$true;preloaded_read_only_state_verified=$true;repair_error_bit_not_relaxed=$true;standalone_titles_closed_after_insertion=$true;j00_three_root_plane_mates=$true;automatic_fix_removed=$true;j01_native_hinge_angle_selection_false=$true;j01_limit_angle_reference_axis_bound=$true;native_create_mate_data_readback_pass=$true;unique_native_limit_angle_driver=$true;native_limits_0_to_5p6_rad=$true;remaining_dof_exactly_one_rotation=$true;canonical_plus_minus_one_degree_pass=$true;enhanced_branch_and_endpoint_sweep_pass=$true;ten_q0_reset_cycles_pass=$true;returned_to_q0=$true;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            cold_reopen_authorized=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R3_PRELOAD_RECOVERY_CREATE_AND_SAME_DOCUMENT_DRIVER_EVIDENCE_ONLY_PENDING_INDEPENDENT_COLD_REOPEN'
        }
        Write-JsonCreateNew $createGate $gate
        Write-Output $createGate
    }
    else {
        $result = [B51R1S05R2J01R3NativePilotTool]::ColdVerify(
            $launchedPid,$pilotAssembly,'B51R1_CARRIER_MR2_base_link.SLDPRT',
            'B51R1_CARRIER_MR2_link1.SLDPRT',$coldReceipt,$coldProgress)
        if ($result -ne 0) { throw "J01 ColdVerify tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $coldReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R3_NATIVE_PILOT_COLD_REOPEN_V1' -or
            $data.status -ne 'S05R2_J01_R3_NATIVE_1R_PILOT_COLD_REOPEN_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R3 ColdVerify receipt is not PASS'
        }
        if ($data.transform2_call_count -ne 0 -or $data.set_transform_and_solve_call_count -ne 0 -or
            $data.move_component_call_count -ne 0 -or $data.save_as_call_count -ne 0 -or $data.save3_call_count -ne 0 -or
            $data.create_mate_data_call_count -ne 0 -or $data.create_mate_call_count -ne 0 -or
            $data.add_mate5_call_count -ne 0 -or $data.mate_preselection_call_count -ne 0) {
            throw 'J01 ColdVerify prohibited API/save count mismatch'
        }
        foreach ($item in $lockedItems) {
            Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "COLD_POST_$($item.id)"
        }
        foreach ($item in $mr2Inputs) { Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_$($item.link)_POST_COLD" }
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SOLIDWORKS remains after J01 ColdVerify normal exit' }
        $create = Get-Content -Raw -Encoding UTF8 -LiteralPath $createGate | ConvertFrom-Json
        $coldReceiptBinding = [ordered]@{path=$coldReceipt;bytes=(Get-Item $coldReceipt).Length;sha256=Get-Sha $coldReceipt}
        $gate = [ordered]@{
            schema='B51R1_S05R2_J01_R3_NATIVE_1R_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R3_NATIVE_1R_PILOT_PASS';gate_pass=$true
            create_gate=[ordered]@{path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate}
            receipt=$coldReceiptBinding
            cold_reopen_receipt=$coldReceiptBinding
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{native_hinge_and_limit_mates_persisted=$true;native_limit_reference_axis_and_q0_persisted=$true;remaining_dof_exactly_one_rotation=$true;base_and_link1_not_fixed=$true;ten_cold_q0_samples_pass=$true;cold_plus_minus_one_degree_pass=$true;cold_branch_witnesses_pass=$true;returned_to_q0_after_cold_drive=$true;assembly_hash_stable=$true;mr2_input_hashes_stable=$true;normal_application_exit=$true;save_api_call_count=0;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            mr2_batch_create_authorized=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R3_PRELOAD_RECOVERY_NATIVE_1R_PILOT_GATE_ONLY_NO_COMPLETE_CHAIN_G4_T005_STRUCTURAL_MANUFACTURING_OR_FLIGHT_CREDIT'
        }
        Write-JsonCreateNew $finalGate $gate
        Write-Output $finalGate
    }
    $exitCode = 0
}
finally {
    $remaining = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    foreach ($process in $remaining) {
        $process.Refresh()
        if ($process.Responding -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
            try { [void]$process.CloseMainWindow() } catch { }
        }
    }
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($null -ne $launchHandle) { $launchHandle.Dispose() }
}

exit $exitCode
