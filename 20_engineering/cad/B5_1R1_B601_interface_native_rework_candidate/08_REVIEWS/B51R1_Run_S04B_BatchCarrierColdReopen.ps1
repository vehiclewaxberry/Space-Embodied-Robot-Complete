[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S04B'
$s03bRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S03B'
$carrierDir = Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$writerDll = Join-Path $PSScriptRoot 'B51R1_NativeDocumentTextPropertyWriter.dll'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S03B_S04B_BatchCarrierTool.dll'
$s03bReceipt = Join-Path $s03bRoot 'B51R1_S03B_BATCH_CARRIER_CREATE_RECEIPT.json'
$s03bGate = Join-Path $s03bRoot 'B51R1_S03B_REMAINING_NINE_CARRIER_GATE.json'
$activation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V18_POOL_A_A07_S04B_ACTIVATION.yaml'
$manifest = Join-Path $sessionRoot 'B51R1_S04B_CARRIER_MANIFEST.json'
$readinessReceipt = Join-Path $sessionRoot 'B51R1_S04B_READINESS_RECEIPT.json'
$inputLock = Join-Path $sessionRoot 'B51R1_S04B_INPUT_LOCK.json'
$receipt = Join-Path $sessionRoot 'B51R1_S04B_ALL_CARRIER_COLD_REOPEN_RECEIPT.json'
$progress = Join-Path $sessionRoot 'B51R1_S04B_PROGRESS.log'
$gate = Join-Path $sessionRoot 'B51R1_S04B_ALL_TEN_CARRIER_GATE.json'
$sessionReceipt = Join-Path $sessionRoot 'B51R1_S04B_SESSION_RECEIPT.json'
$s05Activation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V19_POOL_A_A08_S05_ACTIVATION.yaml'

function Get-Sha([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -ne $Bytes) { throw "$Label byte count mismatch" }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) { throw "$Label SHA-256 mismatch" }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only output exists: $Path" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 50) + [Environment]::NewLine), $utf8)
}

function Write-TextCreateNew([string]$Path, [string]$Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only output exists: $Path" }
    $utf8 = New-Object Text.UTF8Encoding($false)
    $stream = New-Object IO.FileStream($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $writer = New-Object IO.StreamWriter($stream, $utf8)
        try { $writer.Write($Value) } finally { $writer.Dispose() }
    } finally { if ($null -ne $stream) { $stream.Dispose() } }
}

foreach ($output in @($manifest,$readinessReceipt,$inputLock,$receipt,$progress,$gate,$sessionReceipt,$s05Activation)) {
    if (Test-Path -LiteralPath $output) { throw "S04B append-only output already exists: $output" }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw 'S04B requires zero existing SLDWORKS processes before launch'
}
if (-not (Test-Path -LiteralPath $s03bReceipt) -or -not (Test-Path -LiteralPath $s03bGate) -or -not (Test-Path -LiteralPath $activation)) {
    throw 'S04B requires the completed S03B receipt, Gate and A07 activation'
}
$created = Get-Content -Raw -Encoding UTF8 -LiteralPath $s03bReceipt | ConvertFrom-Json
if ($created.status -ne 'S03B_REMAINING_NINE_CARRIERS_CREATED' -or $created.created_part_count -ne 9) {
    throw 'S03B receipt does not authorize S04B'
}
$s03bGateData = Get-Content -Raw -Encoding UTF8 -LiteralPath $s03bGate | ConvertFrom-Json
if ($s03bGateData.status -ne 'S03B_REMAINING_NINE_CARRIERS_CREATED' -or -not $s03bGateData.s04b_authorized) {
    throw 'S03B Gate does not authorize S04B'
}

$parts = @([ordered]@{
    link='base_link';path=(Join-Path $carrierDir 'B51R1_CARRIER_base_link.SLDPRT')
    sha256='1151ECD78BC18AD9CCBF2B3EC86365879D09B0CCF14425C17A09DD84119F7F62';feature_count=21
})
foreach ($part in $created.parts) {
    $parts += [ordered]@{link=[string]$part.link;path=[string]$part.path;sha256=[string]$part.part_sha256;feature_count=[int]$part.feature_count}
}
if ($parts.Count -ne 10 -or @($parts.link | Select-Object -Unique).Count -ne 10) { throw 'S04B manifest construction did not produce ten unique links' }
foreach ($part in $parts) {
    if (-not (Test-Path -LiteralPath $part.path -PathType Leaf) -or (Get-Sha $part.path) -ne $part.sha256) {
        throw "S04B part precondition failed: $($part.link)"
    }
}

$lockedItems = @(
    [ordered]@{id='ACTIVE_R1';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_R1.SLDPRT';bytes=232433;sha256='7BE2D46AC5015ED9E318F3DD60C623F3B3B63015EA1E4CDBE100E1EB15363DFD'},
    [ordered]@{id='PROTECTED_V2';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT';bytes=232506;sha256='71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA'},
    [ordered]@{id='PROTECTED_STAGE_A';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT';bytes=511198;sha256='5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'},
    [ordered]@{id='ACCEPTED_URDF';path='00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf';bytes=11321;sha256='1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164'},
    [ordered]@{id='CARRIER_REGISTER_V2';path='04_CONFIGURATION/B51R1_CARRIER_REGISTER_V2.csv';bytes=5302;sha256='52F4EC1CEA59B2AD73677C36829E68E3024B8911002F7F24270D6E38100B99B5'},
    [ordered]@{id='JOINT_SIDE_TRANSFORM_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv';bytes=2933;sha256='F833BE927C91FED962741B02596D279E87E4949458F0EDDEB81DBC8D78A2EC01'},
    [ordered]@{id='NATIVE_JOINT_REGISTER_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_JOINT_REGISTER_V2.csv';bytes=3818;sha256='B0B811DDCF26DAFCC4DCEFE4BB71305D471C1373C45F9262C1E66E7B7F61B22D'},
    [ordered]@{id='CARRIER_CONTRACT_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT_V2.md';bytes=2498;sha256='96A54E088A588338059AF902FD69C4B66A79C9E1FAA92A47A66692236D978ED8'},
    [ordered]@{id='PROPERTY_WRITER';path='08_REVIEWS/B51R1_NativeDocumentTextPropertyWriter.dll';bytes=9216;sha256='A0E45A57C734894D638AD13F8895E7CEAE189993998D32518FA4260CB1E47D88'},
    [ordered]@{id='READINESS_PROBE';path='08_REVIEWS/B51R1_SR03_ExistingSolidWorksProbe.dll';bytes=5632;sha256='DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'},
    [ordered]@{id='BATCH_TOOL_SOURCE';path='08_REVIEWS/B51R1_S03B_S04B_BatchCarrierTool.cs';bytes=34173;sha256='3C44DB78868FC6A4AF75919CB5ECF6D4443CD80A3C39A4EDE7765F6A3D09C61F'},
    [ordered]@{id='BATCH_TOOL_BINARY';path='08_REVIEWS/B51R1_S03B_S04B_BatchCarrierTool.dll';bytes=29696;sha256='9C6F4300834EBCB30692843495C598CA287BB4924C98E921F67F672665486A13'},
    [ordered]@{id='S03B_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S03B/B51R1_S03B_BATCH_CARRIER_CREATE_RECEIPT.json';bytes=(Get-Item $s03bReceipt).Length;sha256=Get-Sha $s03bReceipt},
    [ordered]@{id='S03B_GATE';path='07_VERIFICATION/AUTONOMOUS/S03B/B51R1_S03B_REMAINING_NINE_CARRIER_GATE.json';bytes=(Get-Item $s03bGate).Length;sha256=Get-Sha $s03bGate},
    [ordered]@{id='S04B_ACTIVATION';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V18_POOL_A_A07_S04B_ACTIVATION.yaml';bytes=(Get-Item $activation).Length;sha256=Get-Sha $activation}
)
foreach ($item in $lockedItems) { Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id) }
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SolidWorks executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SolidWorks interop'

[IO.Directory]::CreateDirectory($sessionRoot) | Out-Null
Write-JsonCreateNew $manifest ([ordered]@{schema='B51R1_S04B_CARRIER_MANIFEST_V1';generated_at=[DateTimeOffset]::Now.ToString('o');status='PASS_TEN_CARRIER_HASHES_LOCKED_FOR_READ_ONLY_COLD_REOPEN';parts=$parts})

$session = [ordered]@{
    schema='B51R1_S04B_SESSION_RECEIPT_V1';session_id='S04B'
    started_at=[DateTimeOffset]::Now.ToString('o');status='S04B_FAIL_CLOSED_NOT_STARTED'
    force_termination_path_present=$false;save_api_call_count_allowed=0
}
$launchHandle=$null
$launchedPid=$null
$exitCode=1
try {
    Add-Type -Path $interop
    $launchHandle=Start-Process -FilePath $solidworksExe -PassThru
    $session['launch_request_process_id']=$launchHandle.Id
    $deadline=[DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline -and $null -eq $launchedPid) {
        Start-Sleep -Milliseconds 500
        $processes=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $candidate=$processes[0];$candidate.Refresh()
        if ($candidate.Responding -and $candidate.MainWindowHandle -ne [IntPtr]::Zero) { $launchedPid=$candidate.Id }
    }
    if ($null -eq $launchedPid) { throw 'Visible responsive SolidWorks process was not ready within three minutes' }
    $quietStart=[DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd=[DateTimeOffset]::Now
    $processes=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'S04B lost the sole SolidWorks process during zero-COM window' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding -or $processes[0].MainWindowHandle -eq [IntPtr]::Zero) { throw 'S04B SolidWorks process was not stable after zero-COM window' }
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $readinessResult=[B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid,$readinessReceipt)
    if ($readinessResult -ne 0) { throw "S04B readiness probe returned $readinessResult" }
    $readiness=Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($readiness.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') { throw 'S04B readiness did not pass' }
    $runtimeItems=@($lockedItems)+@([ordered]@{id='CARRIER_MANIFEST';path='07_VERIFICATION/AUTONOMOUS/S04B/B51R1_S04B_CARRIER_MANIFEST.json';bytes=(Get-Item $manifest).Length;sha256=Get-Sha $manifest},[ordered]@{id='READINESS_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S04B/B51R1_S04B_READINESS_RECEIPT.json';bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt})
    $lock=[ordered]@{
        schema='B51R1_S04B_INPUT_LOCK_V1';generated_at=[DateTimeOffset]::Now.ToString('o');status='PASS_S04B_INPUTS_HASH_LOCKED';session_id='S04B'
        runtime_boundary=[ordered]@{solidworks_process_id=$launchedPid;solidworks_process_count=1;visible=$true;responsive=$true;startup_completed=$true;document_count=0;zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds;readiness_probe_call_count=1}
        transaction=[ordered]@{operation='SILENT_READ_ONLY_COLD_REOPEN_ALL_TEN_CARRIERS';part_count=10;save_api_call_count_allowed=0;force_termination_allowed=$false}
        carrier_hashes=$parts;locked_items=$runtimeItems;locked_item_count=$runtimeItems.Count
        claim_limit='TEN_CARRIER_PERSISTENCE_ONLY_NO_ASSEMBLY_JOINT_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $writerDll).Path)
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result=[B51R1S03BS04BBatchCarrierTool]::Verify($launchedPid,$manifest,$receipt,$progress)
    if ($result -ne 0) { throw "S04B verifier returned $result" }
    $verified=Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($verified.status -ne 'S04B_10_OF_10_NATIVE_CARRIERS_COLD_REOPEN_PASS' -or $verified.verified_part_count -ne 10 -or $verified.save_api_call_count -ne 0) { throw 'S04B receipt did not satisfy the 10/10 Gate' }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SolidWorks remains after S04B normal ExitApp' }
    foreach ($part in $parts) { if ((Get-Sha $part.path) -ne $part.sha256) { throw "Carrier changed after S04B: $($part.link)" } }
    foreach ($item in $lockedItems) { Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id) }
    $gateData=[ordered]@{
        schema='B51R1_S04B_ALL_TEN_CARRIER_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
        status='S04B_10_OF_10_NATIVE_CARRIERS_COLD_REOPEN_PASS';verified_part_count=10
        manifest=[ordered]@{path='07_VERIFICATION/AUTONOMOUS/S04B/B51R1_S04B_CARRIER_MANIFEST.json';bytes=(Get-Item $manifest).Length;sha256=Get-Sha $manifest}
        cold_reopen_receipt=[ordered]@{path='07_VERIFICATION/AUTONOMOUS/S04B/B51R1_S04B_ALL_CARRIER_COLD_REOPEN_RECEIPT.json';bytes=(Get-Item $receipt).Length;sha256=Get-Sha $receipt}
        parts=$parts
        checks=[ordered]@{five_property_no_ops_each=$true;source_urdf_hash_exact=$true;all_controlled_frames_exact=$true;all_joint_reference_features_exact=$true;zero_bodies=$true;zero_cad_mass=$true;mass_api_status_no_body=$true;zero_external_references=$true;hashes_stable=$true;save_api_call_count=0;normal_application_exit=$true;protected_inputs_unchanged=$true}
        s05_joint_assembly_authorized=$true
        claim_limit='TEN_NATIVE_REFERENCE_ONLY_CARRIERS_PERSISTED_NO_JOINT_T005_STRUCTURAL_MANUFACTURING_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $gate $gateData
    $activationText=@"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V19_POOL_A_A08_S05_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: POOL_A_A08_S05_NATIVE_CARRIER_CHAIN_ASSEMBLY_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S04B/B51R1_S04B_ALL_TEN_CARRIER_GATE.json
activated_slot:
  id: A08_S05
  output: 03_CAD/20_NATIVE_ASSEMBLY/B51R1_CARRIER_CHAIN_NATIVE.SLDASM
  joint_sequence: J00-J09
  required_topology: 6R+1_FIXED+2_INDEPENDENT_P
  incremental_gate_required: true
t005_authorized: false
exit_gate: S05_NATIVE_CARRIER_CHAIN_ASSEMBLY_PASS
next_required_slot: A09_T005_A0
"@
    Write-TextCreateNew $s05Activation $activationText
    $session['status']='PASS_S04B_10_OF_10_NATIVE_CARRIERS_COLD_REOPEN'
    $session['solidworks_process_id']=$launchedPid
    $session['zero_com_quiet_window_seconds']=($quietEnd-$quietStart).TotalSeconds
    $session['input_lock_sha256']=Get-Sha $inputLock
    $session['cold_reopen_receipt_sha256']=Get-Sha $receipt
    $session['gate_sha256']=Get-Sha $gate
    $session['normal_application_exit']=$true
    $exitCode=0
}
catch {
    $session['status']='S04B_FAIL_CLOSED';$session['error_type']=$_.Exception.GetType().FullName
    $session['error_message']=$_.Exception.Message;$session['failed_at']=[DateTimeOffset]::Now.ToString('o')
}
finally {
    $remaining=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    foreach ($process in $remaining) {
        $process.Refresh()
        if ($process.Responding -and $process.MainWindowHandle -ne [IntPtr]::Zero) { try { [void]$process.CloseMainWindow() } catch {} }
    }
    for ($attempt=0;$attempt -lt 60;$attempt++) {
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    $session['completed_at']=[DateTimeOffset]::Now.ToString('o')
    $session['solidworks_process_count_after']=@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
    if (-not (Test-Path -LiteralPath $sessionReceipt)) { Write-JsonCreateNew $sessionReceipt $session }
    if ($null -ne $launchHandle) { $launchHandle.Dispose() }
}

$session | ConvertTo-Json -Depth 20
exit $exitCode
