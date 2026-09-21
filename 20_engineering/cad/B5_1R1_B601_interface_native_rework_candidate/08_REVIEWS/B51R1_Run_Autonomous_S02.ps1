[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedS01CurrentGateSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedTargetSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedSupplementalLockSha256,

    [string]$S01CurrentGatePath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$s02 = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S02'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
if ([string]::IsNullOrWhiteSpace($S01CurrentGatePath)) {
    $S01CurrentGatePath = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S01\B51R1_S01_CURRENT_GATE.json'
}
$receipt = Join-Path $s02 'B51R1_S02_GATE_RECEIPT.json'
$sessionReceipt = Join-Path $s02 'B51R1_S02_SESSION_EXECUTION_RECEIPT.json'
$ledgerPath = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json'
$g1bPath = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1B_STANDING_SESSION_ADMISSION.json'
$finalLockPath = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_PHASE2A_INPUT_LOCK_V3_FINAL.json'
$transitionMapV3 = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_GATE_TRANSITION_MAP_V3_SR03.csv'
$supplementalLock = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_PHASE2A_INPUT_LOCK_V3_S01_SUPPLEMENT_R2.json'
$verifier = Join-Path $PSScriptRoot 'B51R1_S02_MasterSkeletonColdReopenVerifier.dll'
$verifierSource = Join-Path $PSScriptRoot 'B51R1_S02_MasterSkeletonColdReopenVerifier.cs'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'

$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'
$expectedG1b = 'FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6'
$expectedFinalLock = 'AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214'
$expectedTransitionMapV3 = '3B1071670E0EAACF00DF1BC8A3D3F1129CF9A35A09F1DE81FC0C14FA4E502124'
$expectedSolidworksExe = '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
}

foreach ($required in @(
    [pscustomobject]@{Path=$target; Label='Final master skeleton'},
    [pscustomobject]@{Path=$stageA; Label='Protected Stage A'},
    [pscustomobject]@{Path=$S01CurrentGatePath; Label='Versioned S01 current gate'},
    [pscustomobject]@{Path=$ledgerPath; Label='Standing-session ledger'},
    [pscustomobject]@{Path=$g1bPath; Label='G1B standing-session admission'},
    [pscustomobject]@{Path=$finalLockPath; Label='Final V3 input lock'},
    [pscustomobject]@{Path=$transitionMapV3; Label='Versioned V3 transition map'},
    [pscustomobject]@{Path=$supplementalLock; Label='S01 supplemental input lock'},
    [pscustomobject]@{Path=$verifier; Label='S02 verifier DLL'},
    [pscustomobject]@{Path=$verifierSource; Label='S02 verifier source'},
    [pscustomobject]@{Path=$interop; Label='SolidWorks interop DLL'},
    [pscustomobject]@{Path=$solidworksExe; Label='SolidWorks executable'}
)) {
    Assert-File $required.Path $required.Label
}

if ((Get-Sha $target) -ne $ExpectedTargetSha256.ToUpperInvariant()) {
    throw 'Final master-skeleton hash differs from the S01-bound target hash'
}
if ((Get-Sha $stageA) -ne $expectedStageA) {
    throw 'Protected Stage A hash mismatch before S02 launch'
}
if ((Get-Sha $S01CurrentGatePath) -ne $ExpectedS01CurrentGateSha256.ToUpperInvariant()) {
    throw 'Versioned S01 current-gate hash mismatch before S02 launch'
}
if ((Get-Sha $g1bPath) -ne $expectedG1b) {
    throw 'G1B receipt hash mismatch before S02 launch'
}
if ((Get-Sha $finalLockPath) -ne $expectedFinalLock) {
    throw 'Final V3 input-lock hash mismatch before S02 launch'
}
if ((Get-Sha $transitionMapV3) -ne $expectedTransitionMapV3) {
    throw 'Versioned V3 transition-map hash mismatch before S02 launch'
}
if ((Get-Sha $supplementalLock) -ne $ExpectedSupplementalLockSha256.ToUpperInvariant()) {
    throw 'S01 supplemental-lock hash mismatch before S02 launch'
}
if ((Get-Sha $solidworksExe) -ne $expectedSolidworksExe) {
    throw 'SolidWorks executable hash mismatch before S02 launch'
}

$currentGate = Get-Content -Raw -Encoding UTF8 -LiteralPath $S01CurrentGatePath |
    ConvertFrom-Json
if ($currentGate.status -ne 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED' -or
    -not [bool]$currentGate.pass -or
    -not [bool]$currentGate.current -or
    $currentGate.execution_session_id -ne 'SR03') {
    throw 'Versioned S01 current gate does not carry the effective SR03 PASS'
}
if ($currentGate.native_target.sha256 -ne $ExpectedTargetSha256.ToUpperInvariant() -or
    $currentGate.protected_stage_a.sha256 -ne $expectedStageA -or
    $currentGate.g1b_sha256 -ne $expectedG1b -or
    $currentGate.input_lock_sha256 -ne $expectedFinalLock -or
    $currentGate.supersession_chain.sha256 -ne
        'D32002928965A27FA023398361943E3BA45D74CDBD554237365A552472CBA197' -or
    $currentGate.prior_hold_receipt.sha256 -ne
        'DF31F5A674E093F7BF4F6CCDCDBC3DE9ACD3B9DA76992D0E2155620C6DB10E74' -or
    $currentGate.pass_gate_receipt.sha256 -ne
        'AEA36DB81918607615BB56BE77C5981AAD33CFEDAF5A4CEE5F4619CBA21F5CA2' -or
    $currentGate.session_execution_receipt.sha256 -ne
        'B58618FB701000A97063B59C10FD00C2643ED290AD48259512098BC65587863F') {
    throw 'Versioned S01 current gate has an invalid embedded hash binding'
}
if (-not [bool]$currentGate.cold_reopen_required -or
    $currentGate.next_gate_candidate -ne 'S02') {
    throw 'Versioned S01 current gate does not admit S02 cold reopen'
}

$transitionRows = Import-Csv -LiteralPath $transitionMapV3
$s02Transition = @($transitionRows | Where-Object { $_.session_id -eq 'S02' })
if ($s02Transition.Count -ne 1 -or
    $s02Transition[0].required_receipt_pattern -ne
        '07_VERIFICATION/AUTONOMOUS/S01/B51R1_S01_CURRENT_GATE.json' -or
    $s02Transition[0].required_status -ne
        'S01_PASS_NATIVE_MASTER_SKELETON_CREATED' -or
    $s02Transition[0].required_receipt_sha256 -ne
        $ExpectedS01CurrentGateSha256.ToUpperInvariant()) {
    throw 'Versioned V3 transition-map S02 row is not bound to the current S01 PASS'
}

$supplement = Get-Content -Raw -Encoding UTF8 -LiteralPath $supplementalLock |
    ConvertFrom-Json
if ($supplement.status -ne 'PASS_S01_SUPPLEMENTAL_HASH_LOCKED' -or
    $supplement.parent_final_input_lock.sha256 -ne $expectedFinalLock -or
    $supplement.effective_current_gate.sha256 -ne
        $ExpectedS01CurrentGateSha256.ToUpperInvariant() -or
    $supplement.effective_transition_map.sha256 -ne $expectedTransitionMapV3) {
    throw 'S01 supplemental lock does not admit the effective S01/V3 composition'
}
foreach ($toolSpec in @(
    [pscustomobject]@{Id='S02_VERIFIER_SOURCE'; Path=$verifierSource},
    [pscustomobject]@{Id='S02_VERIFIER_DLL'; Path=$verifier},
    [pscustomobject]@{Id='S02_RUNNER'; Path=$PSCommandPath}
)) {
    $locked = @($supplement.locked_items | Where-Object { $_.id -eq $toolSpec.Id })
    if ($locked.Count -ne 1 -or $locked[0].sha256 -ne (Get-Sha $toolSpec.Path)) {
        throw "Supplemental lock mismatch for $($toolSpec.Id)"
    }
}

foreach ($output in @($receipt, $sessionReceipt)) {
    if (Test-Path -LiteralPath $output) {
        throw "S02 output already exists; refusing ambiguous rerun: $output"
    }
}

$existing = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
if ($existing.Count -ne 0) {
    throw "S02 requires zero SLDWORKS processes before cold launch; found $($existing.Count)"
}

$ledger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath | ConvertFrom-Json
if ($ledger.status -ne 'ACTIVE_G1B_STANDING_SESSION_POOL' -or
    [int]$ledger.budget -ne 20 -or
    [int]$ledger.consumed_since_activation -ne 4 -or
    [int]$ledger.remaining -ne 16) {
    throw 'Standing-session ledger is not in the exact pre-S02 budget state'
}
if ($null -ne $ledger.PSObject.Properties['next_session_authorized'] -and
    -not [bool]$ledger.next_session_authorized) {
    throw 'Standing-session ledger does not authorize the next session'
}
if ($null -ne $ledger.PSObject.Properties['next_session_id'] -and
    -not [string]::IsNullOrWhiteSpace([string]$ledger.next_session_id) -and
    [string]$ledger.next_session_id -ne 'S02') {
    throw "Standing-session ledger authorizes $($ledger.next_session_id), not S02"
}
if (@($ledger.entries | Where-Object { $_.session_id -eq 'S02' }).Count -ne 0) {
    throw 'S02 ledger entry already exists; refusing duplicate execution'
}

New-Item -ItemType Directory -Path $s02 -Force | Out-Null
$utf8NoBom = New-Object Text.UTF8Encoding($false)
$started = [DateTimeOffset]::Now.ToString('o')
$session = [ordered]@{
    schema = 'B51R1_S02_SESSION_EXECUTION_RECEIPT_V1'
    session_id = 'S02'
    started_at = $started
    status = 'S02_FAIL_CLOSED_NOT_STARTED'
    s01_current_gate_path = $S01CurrentGatePath
    s01_current_gate_sha256 = $ExpectedS01CurrentGateSha256.ToUpperInvariant()
    s01_supplemental_lock_sha256 = $ExpectedSupplementalLockSha256.ToUpperInvariant()
    transition_map_v3_sha256 = $expectedTransitionMapV3
    target_path = $target
    target_sha256_before = $ExpectedTargetSha256.ToUpperInvariant()
    protected_stage_a_sha256_before = $expectedStageA
    g1b_sha256 = $expectedG1b
    final_input_lock_sha256 = $expectedFinalLock
    verifier_source_sha256 = Get-Sha $verifierSource
    verifier_dll_sha256 = Get-Sha $verifier
    runner_sha256 = Get-Sha $PSCommandPath
    launch_mode = 'NEW_UNIQUE_VISIBLE_SOLIDWORKS_PROCESS'
    open_mode = 'READ_ONLY'
    save_permitted = $false
}
$launchedPid = $null
$exitCode = 1
try {
    [void][Reflection.Assembly]::LoadFrom($interop)
    [void][Reflection.Assembly]::LoadFrom($verifier)

    $launched = Start-Process -FilePath $solidworksExe -PassThru
    $launchedPid = $launched.Id
    $session['process_id'] = $launchedPid

    $responsive = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        $candidate = Get-Process -Id $launchedPid -ErrorAction SilentlyContinue
        if ($null -ne $candidate -and $candidate.Responding -and $candidate.MainWindowHandle -ne 0) {
            $responsive = $true
            break
        }
    }
    if (-not $responsive) {
        throw 'A visible responsive SolidWorks main window did not appear within 60 seconds'
    }
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction Stop)
    if ($processes.Count -ne 1) {
        throw "Expected one SLDWORKS process after launch; found $($processes.Count)"
    }
    if ($processes[0].Id -ne $launchedPid) {
        throw "The sole SLDWORKS PID differs from launched PID $launchedPid"
    }
    if (-not $processes[0].Responding -or $processes[0].MainWindowHandle -eq 0) {
        throw 'The sole launched SLDWORKS process is not visible and responsive'
    }

    $result = [B51R1S02MasterSkeletonColdReopenVerifier]::Run(
        $target,
        $stageA,
        $receipt,
        $launchedPid,
        $S01CurrentGatePath,
        $ExpectedS01CurrentGateSha256.ToUpperInvariant(),
        $ExpectedTargetSha256.ToUpperInvariant(),
        $expectedStageA,
        $expectedG1b,
        $expectedFinalLock
    )
    $session['verifier_result'] = $result
    if ($result -ne 0) {
        throw "S02 cold-reopen verifier failed with code $result"
    }
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($gate.status -ne 'S02_PASS_MASTER_SKELETON_COLD_REOPEN') {
        throw "S02 receipt did not pass: $($gate.status)"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'SLDWORKS process remains after verifier-requested normal ExitApp'
    }
    if ((Get-Sha $target) -ne $ExpectedTargetSha256.ToUpperInvariant()) {
        throw 'Final master-skeleton hash changed during S02'
    }
    if ((Get-Sha $stageA) -ne $expectedStageA) {
        throw 'Protected Stage A hash changed during S02'
    }
    if ((Get-Sha $S01CurrentGatePath) -ne $ExpectedS01CurrentGateSha256.ToUpperInvariant()) {
        throw 'Versioned S01 current-gate hash changed during S02'
    }

    $session['status'] = 'S02_PASS_MASTER_SKELETON_COLD_REOPEN'
    $session['gate_receipt_sha256'] = Get-Sha $receipt
    $session['target_sha256_after'] = Get-Sha $target
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['normal_application_exit'] = $true
    $exitCode = 0
}
catch {
    $session['status'] = 'S02_FAIL_CLOSED'
    $session['error_type'] = $_.Exception.GetType().FullName
    $session['error_message'] = $_.Exception.Message
    $session['normal_application_exit'] =
        (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0)
    $exitCode = 1
}
finally {
    # No Terminate/Kill fallback is permitted. The verifier requests CloseDoc and ExitApp.
    # If startup failed before COM attachment, request only a graceful main-window close.
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0 -and
        $null -ne $launchedPid) {
        $process = Get-Process -Id $launchedPid -ErrorAction SilentlyContinue
        if ($null -ne $process -and $process.Responding) {
            try { [void]$process.CloseMainWindow() } catch { }
        }
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
            Start-Sleep -Milliseconds 500
        }
    }
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    $processCountAfter =
        @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
    $session['solidworks_process_count_after'] = $processCountAfter
    if ($session['status'] -eq 'S02_PASS_MASTER_SKELETON_COLD_REOPEN' -and
        $processCountAfter -ne 0) {
        $session['status'] = 'S02_HOLD_COLD_REOPEN_PROCESS_EXIT_PENDING'
        $session['normal_application_exit'] = $false
        $session['error_message'] =
            'S02 verification completed, but SolidWorks did not exit normally'
        $exitCode = 2
    }
    $session['final_target_exists'] = Test-Path -LiteralPath $target -PathType Leaf
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $session['target_sha256_final'] = Get-Sha $target
    }
    $session['protected_stage_a_sha256_final'] = Get-Sha $stageA
    $session['s01_current_gate_sha256_final'] = Get-Sha $S01CurrentGatePath
    [IO.File]::WriteAllText(
        $sessionReceipt,
        ($session | ConvertTo-Json -Depth 12) + "`n",
        $utf8NoBom)

    $ledger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath |
        ConvertFrom-Json
    $event = [pscustomobject]@{
        session_id = 'S02'
        bound_gate = 'S02'
        started_at = $started
        completed_at = $session['completed_at']
        status = $session['status']
        process_id = $launchedPid
        new_process_launched = $true
        receipt_path =
            '07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_SESSION_EXECUTION_RECEIPT.json'
        gate_receipt_path =
            '07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_GATE_RECEIPT.json'
        s01_current_gate_sha256 =
            $ExpectedS01CurrentGateSha256.ToUpperInvariant()
        supplemental_lock_sha256 =
            $ExpectedSupplementalLockSha256.ToUpperInvariant()
    }
    $ledger.entries = @($ledger.entries) + @($event)
    $ledger.consumed_since_activation = 5
    $ledger.remaining = 15
    $ledger.last_session_id = 'S02'
    $ledger.last_session_status = $session['status']
    $ledger.updated_at = $session['completed_at']
    if ($session['status'] -eq 'S02_PASS_MASTER_SKELETON_COLD_REOPEN' -and
        $processCountAfter -eq 0) {
        $ledger.status = 'ACTIVE_G1B_STANDING_SESSION_POOL'
        $ledger.next_session_authorized = $true
        $ledger.next_session_id = 'S03'
    }
    else {
        $ledger.status = 'BLOCKED_S02_COLD_REOPEN_FAIL_CLOSED'
        $ledger.next_session_authorized = $false
        $ledger.next_session_id = $null
    }
    [IO.File]::WriteAllText(
        $ledgerPath,
        ($ledger | ConvertTo-Json -Depth 12) + "`n",
        $utf8NoBom)
}

$session | ConvertTo-Json -Depth 12
exit $exitCode
