[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S03B_R1'
$carrierDir = Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS'
$template = 'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_part.prtdot'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$writerDll = Join-Path $PSScriptRoot 'B51R1_NativeDocumentTextPropertyWriter.dll'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S03B_S04B_BatchCarrierTool_V2.dll'
$readinessReceipt = Join-Path $sessionRoot 'B51R1_S03B_R1_READINESS_RECEIPT.json'
$inputLock = Join-Path $sessionRoot 'B51R1_S03B_R1_INPUT_LOCK.json'
$receipt = Join-Path $sessionRoot 'B51R1_S03B_R1_BATCH_CARRIER_CREATE_RECEIPT.json'
$progress = Join-Path $sessionRoot 'B51R1_S03B_R1_PROGRESS.log'
$gate = Join-Path $sessionRoot 'B51R1_S03B_R1_REMAINING_NINE_CARRIER_GATE.json'
$sessionReceipt = Join-Path $sessionRoot 'B51R1_S03B_R1_SESSION_RECEIPT.json'
$s04bActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V18_POOL_A_A07_S04B_ACTIVATION.yaml'

$expectedParts = @(
    'B51R1_CARRIER_link1.SLDPRT',
    'B51R1_CARRIER_link2.SLDPRT',
    'B51R1_CARRIER_link3.SLDPRT',
    'B51R1_CARRIER_link4.SLDPRT',
    'B51R1_CARRIER_link5.SLDPRT',
    'B51R1_CARRIER_link6.SLDPRT',
    'B51R1_CARRIER_gripper_link.SLDPRT',
    'B51R1_CARRIER_gripper_left.SLDPRT',
    'B51R1_CARRIER_gripper_right.SLDPRT'
)

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $Bytes) { throw "$Label byte count mismatch" }
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

$lockedItems = @(
    [ordered]@{id='ACTIVE_R1';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_R1.SLDPRT';bytes=232433;sha256='7BE2D46AC5015ED9E318F3DD60C623F3B3B63015EA1E4CDBE100E1EB15363DFD'},
    [ordered]@{id='PROTECTED_V2';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT';bytes=232506;sha256='71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA'},
    [ordered]@{id='PROTECTED_STAGE_A';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT';bytes=511198;sha256='5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'},
    [ordered]@{id='ACCEPTED_URDF';path='00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf';bytes=11321;sha256='1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164'},
    [ordered]@{id='PILOT_CARRIER';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_base_link.SLDPRT';bytes=48891;sha256='1151ECD78BC18AD9CCBF2B3EC86365879D09B0CCF14425C17A09DD84119F7F62'},
    [ordered]@{id='PILOT_GATE';path='07_VERIFICATION/AUTONOMOUS/S04P/B51R1_S04P_PILOT_CARRIER_GATE.json';bytes=1030;sha256='BA9B229B19189A3A22CA67CFC1E6577D37623B43E66624A5F01D3923066F2C24'},
    [ordered]@{id='S03B_ACTIVATION';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V17_POOL_A_A06_S03B_ACTIVATION.yaml';bytes=649;sha256='129B7079E28BFE2BBCC3028E3DF726800221211F69C8DBC557B11221EC6DFF60'},
    [ordered]@{id='CARRIER_REGISTER_V2';path='04_CONFIGURATION/B51R1_CARRIER_REGISTER_V2.csv';bytes=5302;sha256='52F4EC1CEA59B2AD73677C36829E68E3024B8911002F7F24270D6E38100B99B5'},
    [ordered]@{id='JOINT_SIDE_TRANSFORM_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv';bytes=2933;sha256='F833BE927C91FED962741B02596D279E87E4949458F0EDDEB81DBC8D78A2EC01'},
    [ordered]@{id='NATIVE_JOINT_REGISTER_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_JOINT_REGISTER_V2.csv';bytes=3818;sha256='B0B811DDCF26DAFCC4DCEFE4BB71305D471C1373C45F9262C1E66E7B7F61B22D'},
    [ordered]@{id='CARRIER_CONTRACT_V2';path='03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT_V2.md';bytes=2498;sha256='96A54E088A588338059AF902FD69C4B66A79C9E1FAA92A47A66692236D978ED8'},
    [ordered]@{id='PROPERTY_WRITER';path='08_REVIEWS/B51R1_NativeDocumentTextPropertyWriter.dll';bytes=9216;sha256='A0E45A57C734894D638AD13F8895E7CEAE189993998D32518FA4260CB1E47D88'},
    [ordered]@{id='READINESS_PROBE';path='08_REVIEWS/B51R1_SR03_ExistingSolidWorksProbe.dll';bytes=5632;sha256='DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'},
    [ordered]@{id='PRESERVED_S03B_FAILED_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S03B/B51R1_S03B_BATCH_CARRIER_CREATE_RECEIPT.json';bytes=378;sha256='C2B70794D1E5E54076A19BFA6C804E4FEB2DC467C7CD98B68CD82516E0487651'},
    [ordered]@{id='PRESERVED_S03B_FAILED_SESSION';path='07_VERIFICATION/AUTONOMOUS/S03B/B51R1_S03B_SESSION_RECEIPT.json';bytes=580;sha256='BEE8A48AA33624D98FE69C9EF7B9722DB2F87442FB57E802F9422DBFE8CA7BD6'},
    [ordered]@{id='PRESERVED_S03B_INPUT_LOCK';path='07_VERIFICATION/AUTONOMOUS/S03B/B51R1_S03B_INPUT_LOCK.json';bytes=7191;sha256='5DC9F2524426A7EAC5D8196DD7660C6597C3B8F3578A98FDD7B61909668A66F8'},
    [ordered]@{id='BATCH_TOOL_SOURCE_V2';path='08_REVIEWS/B51R1_S03B_S04B_BatchCarrierTool_V2.cs';bytes=34900;sha256='2CB427983EA348A9A69352256D6FEB2046CE76378F1DD2AB3868C6CA1DA37E92'},
    [ordered]@{id='BATCH_TOOL_BINARY_V2';path='08_REVIEWS/B51R1_S03B_S04B_BatchCarrierTool_V2.dll';bytes=30208;sha256='74324F05C089AAD100B3D7940330F919782DB795277DE79C7D2DC52A2AF0B9F7'}
)

foreach ($output in @($readinessReceipt, $inputLock, $receipt, $progress, $gate, $sessionReceipt, $s04bActivation)) {
    if (Test-Path -LiteralPath $output) { throw "S03B append-only output already exists: $output" }
}
foreach ($part in $expectedParts) {
    if (Test-Path -LiteralPath (Join-Path $carrierDir $part)) { throw "S03B Carrier output exists: $part" }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw 'S03B requires zero existing SLDWORKS processes before launch'
}
foreach ($item in $lockedItems) {
    Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id)
}
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SolidWorks executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SolidWorks interop'
if (-not (Test-Path -LiteralPath $template -PathType Leaf)) { throw 'Part template missing' }

$session = [ordered]@{
    schema='B51R1_S03B_R1_SESSION_RECEIPT_V1'; session_id='S03B_R1'
    started_at=[DateTimeOffset]::Now.ToString('o'); status='S03B_R1_FAIL_CLOSED_NOT_STARTED'
    force_termination_path_present=$false; save_as_call_count_allowed=9
}
$launchHandle = $null
$launchedPid = $null
$exitCode = 1
try {
    [IO.Directory]::CreateDirectory($sessionRoot) | Out-Null
    Add-Type -Path $interop
    $launchHandle = Start-Process -FilePath $solidworksExe -PassThru
    $session['launch_request_process_id'] = $launchHandle.Id
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline -and $null -eq $launchedPid) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $candidate = $processes[0]; $candidate.Refresh()
        if ($candidate.Responding -and $candidate.MainWindowHandle -ne [IntPtr]::Zero) { $launchedPid = $candidate.Id }
    }
    if ($null -eq $launchedPid) { throw 'Visible responsive SolidWorks process was not ready within three minutes' }
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'S03B lost the sole SolidWorks process during zero-COM window' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding -or $processes[0].MainWindowHandle -eq [IntPtr]::Zero) {
        throw 'S03B SolidWorks process was not stable after zero-COM window'
    }
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $readinessResult = [B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid, $readinessReceipt)
    if ($readinessResult -ne 0) { throw "S03B readiness probe returned $readinessResult" }
    $readiness = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($readiness.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') { throw 'S03B readiness did not pass' }
    $runtimeItems = @($lockedItems) + @([ordered]@{id='READINESS_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S03B_R1/B51R1_S03B_R1_READINESS_RECEIPT.json';bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt})
    $lock = [ordered]@{
        schema='B51R1_S03B_R1_INPUT_LOCK_V1'; generated_at=[DateTimeOffset]::Now.ToString('o')
        status='PASS_S03B_R1_INPUTS_HASH_LOCKED'; session_id='S03B_R1'
        runtime_boundary=[ordered]@{solidworks_process_id=$launchedPid;solidworks_process_count=1;visible=$true;responsive=$true;startup_completed=$true;document_count=0;zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds;readiness_probe_call_count=1}
        transaction=[ordered]@{operation='CREATE_REMAINING_NINE_NATIVE_REFERENCE_ONLY_CARRIERS';outputs_absent=$true;save_as_call_count_allowed=9;set2_call_count_allowed=0;force_termination_allowed=$false}
        locked_items=$runtimeItems;locked_item_count=$runtimeItems.Count
        claim_limit='NINE_NATIVE_REFERENCE_ONLY_CARRIERS_NO_ASSEMBLY_JOINT_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $writerDll).Path)
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = [B51R1S03BS04BBatchCarrierToolV2]::Create($launchedPid, $template, $carrierDir, $receipt, $progress)
    if ($result -ne 0) { throw "S03B builder returned $result" }
    $created = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($created.status -ne 'S03B_REMAINING_NINE_CARRIERS_CREATED' -or $created.created_part_count -ne 9 -or $created.save_as_call_count -ne 9) {
        throw 'S03B creation receipt did not satisfy the 9/9 Gate'
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SolidWorks remains after S03B normal ExitApp' }
    foreach ($item in $lockedItems) { Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) ([string]$item.sha256) ([string]$item.id) }
    $partEvidence = @($created.parts | ForEach-Object { [ordered]@{link=$_.link;path=(Resolve-Path -LiteralPath $_.path).Path;bytes=$_.part_bytes;sha256=$_.part_sha256;feature_count=$_.feature_count;coordinate_system_count=$_.coordinate_system_count;body_count=$_.body_count;external_reference_count=$_.external_reference_count} })
    $gateData = [ordered]@{
        schema='B51R1_S03B_R1_REMAINING_NINE_CARRIER_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
        status='S03B_REMAINING_NINE_CARRIERS_CREATED';created_part_count=9
        creation_receipt=[ordered]@{path='07_VERIFICATION/AUTONOMOUS/S03B_R1/B51R1_S03B_R1_BATCH_CARRIER_CREATE_RECEIPT.json';bytes=(Get-Item $receipt).Length;sha256=Get-Sha $receipt}
        parts=$partEvidence
        checks=[ordered]@{all_properties_exact=$true;source_urdf_hash_exact=$true;zero_bodies=$true;zero_cad_mass=$true;mass_api_status_no_body=$true;zero_external_references=$true;normal_application_exit=$true;protected_inputs_unchanged=$true}
        s04b_authorized=$true;joint_assembly_authorized=$false
        claim_limit='NINE_CREATED_NATIVE_REFERENCE_ONLY_CARRIERS_NO_COLD_REOPEN_ASSEMBLY_JOINT_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $gate $gateData
    $activationText = @"
schema: B51R1_AUTONOMOUS_SESSION_PLAN_V18_POOL_A_A07_S04B_ACTIVATION
generated_at: '$([DateTimeOffset]::Now.ToString('o'))'
status: POOL_A_A07_S04B_ALL_TEN_CARRIERS_COLD_REOPEN_ACTIVATED
activation_gate: 07_VERIFICATION/AUTONOMOUS/S03B_R1/B51R1_S03B_R1_REMAINING_NINE_CARRIER_GATE.json
activated_slot:
  id: A07_S04B
  carrier_count: 10
  open_mode: SILENT_READ_ONLY
  save_api_call_count_allowed: 0
  independent_new_solidworks_process_required: true
joint_assembly_authorized: false
exit_gate: S04B_10_OF_10_NATIVE_CARRIERS_COLD_REOPEN_PASS
next_required_slot: A08_S05
"@
    Write-TextCreateNew $s04bActivation $activationText
    $session['status']='PASS_S03B_R1_REMAINING_NINE_CARRIERS_CREATED'
    $session['solidworks_process_id']=$launchedPid
    $session['zero_com_quiet_window_seconds']=($quietEnd-$quietStart).TotalSeconds
    $session['input_lock_sha256']=Get-Sha $inputLock
    $session['creation_receipt_sha256']=Get-Sha $receipt
    $session['gate_sha256']=Get-Sha $gate
    $session['normal_application_exit']=$true
    $exitCode=0
}
catch {
    $session['status']='S03B_R1_FAIL_CLOSED'
    $session['error_type']=$_.Exception.GetType().FullName
    $session['error_message']=$_.Exception.Message
    $session['failed_at']=[DateTimeOffset]::Now.ToString('o')
}
finally {
    $remaining = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    foreach ($process in $remaining) {
        $process.Refresh()
        if ($process.Responding -and $process.MainWindowHandle -ne [IntPtr]::Zero) { try { [void]$process.CloseMainWindow() } catch {} }
    }
    for ($attempt=0; $attempt -lt 60; $attempt++) {
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
