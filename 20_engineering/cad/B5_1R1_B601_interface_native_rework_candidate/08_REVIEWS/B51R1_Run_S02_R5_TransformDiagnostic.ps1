[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S02_R5'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_R1.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$readinessReceipt = Join-Path $sessionRoot 'B51R1_S02_R5_WAITING_READINESS_PROBE_RECEIPT.json'
$inputLock = Join-Path $sessionRoot 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_INPUT_LOCK.json'
$receipt = Join-Path $sessionRoot 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_RECEIPT.json'
$progress = Join-Path $sessionRoot 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_PROGRESS.log'
$sessionReceipt = Join-Path $sessionRoot 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT.json'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S02_R5_TransformConventionProbe_V3.dll'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_S02_R5_StrongTypedWaitingReadinessProbe.dll'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'

$expectedTarget = '7BE2D46AC5015ED9E318F3DD60C623F3B3B63015EA1E4CDBE100E1EB15363DFD'
$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'
$expectedSolidworksExe = '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60'
$expectedInterop = 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
    if ((Get-Item -LiteralPath $Path).Length -ne $Bytes) {
        throw "$Label byte count mismatch"
    }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) {
        throw "$Label SHA-256 mismatch"
    }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) {
        throw "Append-only output already exists: $Path"
    }
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText(
        $Path,
        (($Value | ConvertTo-Json -Depth 30) + [Environment]::NewLine),
        $utf8NoBom)
}

$lockedItems = @(
    [ordered]@{id='R1_TARGET';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_R1.SLDPRT';bytes=232433;sha256=$expectedTarget},
    [ordered]@{id='PROTECTED_STAGE_A';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT';bytes=511198;sha256=$expectedStageA},
    [ordered]@{id='PROTECTED_V2';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT';bytes=232506;sha256='71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA'},
    [ordered]@{id='ACCEPTED_URDF';path='00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf';bytes=11321;sha256='1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164'},
    [ordered]@{id='S01_CR02_GATE';path='07_VERIFICATION/AUTONOMOUS/S01_CR02/B51R1_S01_CR02_PROPERTY_REPAIR_GATE.json';bytes=2602;sha256='3D6312974EC1AD4CE051053B1CC36DDAD6DADA888F5E2B202BACEEF03F0A22F8'},
    [ordered]@{id='S02_R2_FAILED_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S02_R2/B51R1_S02_R2_COLD_REOPEN_RECEIPT.json';bytes=2858;sha256='BA5CC9FE5EBE2322D7E77B68A52B72D2FA5EDFB605677BA6D52894F3051877C3'},
    [ordered]@{id='S02_R2_TRANSFORM_INCIDENT';path='07_VERIFICATION/AUTONOMOUS/S02_R2/B51R1_S02_R2_TRANSFORM_CONVENTION_ASSERTION_FAIL_CLOSED_INCIDENT.json';bytes=3248;sha256='DDFFAD3F0E40C5EB6077A0D311773B6FFCB2340C1DB8674D369CDCA49714616A'},
    [ordered]@{id='STEP_WITNESS_GATE';path='02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STEP_WITNESS_R2_GATE.json';bytes=3533;sha256='2C8467883555A3EABDFEA4F1A1C64CBF6B0D6F2EA6EFE38E52443B93309C339B'},
    [ordered]@{id='MECHANICAL_BASELINE';path='03_CAD/00_SYSTEM_ARCHITECTURE/B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1.yaml';bytes=4581;sha256='2E34789B194BC9F66B30552C8CEDFC15923DDE186ABF87D2A92DB6F67A7C1705'},
    [ordered]@{id='S02_R3_SESSION_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT.json';bytes=860;sha256='208C2D3F148B90E8C3FA9279507E8744DBD62CB4DB473F243BCDD09B8118F615'},
    [ordered]@{id='S02_R3_STARTUP_INCIDENT';path='07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_POWERSHELL_COM_STARTUP_BINDING_FAIL_CLOSED_INCIDENT.json';bytes=2195;sha256='E0E3E946D43E920199DFEAFC2FCF37A91C6A847358AAC804121F7975DB5008E3'},
    [ordered]@{id='S02_R4_READINESS_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S02_R4/B51R1_S02_R4_DOCUMENT_EMPTY_READINESS_PROBE_RECEIPT.json';bytes=550;sha256='27CDE40E3D151C1B3DF2CEB4770E3585D7933704D77EFFDD4AC6C51BEB94DD9D'},
    [ordered]@{id='S02_R4_SESSION_RECEIPT';path='07_VERIFICATION/AUTONOMOUS/S02_R4/B51R1_S02_R4_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT.json';bytes=828;sha256='85033F20F3E6D48BE74792BFFF7F2CB93F6F4C85091FBCFEA9297619DDEFA410'},
    [ordered]@{id='S02_R4_STARTUP_RACE_INCIDENT';path='07_VERIFICATION/AUTONOMOUS/S02_R4/B51R1_S02_R4_STARTUP_COMPLETION_RACE_FAIL_CLOSED_INCIDENT.json';bytes=2077;sha256='91246986D9470BE6944BA967FCE57929E8EA44A552002AA07DF40DF8485085A4'},
    [ordered]@{id='POOL_A_A16_EXTENSION';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V7_POOL_A_S02_R5_WAITING_READINESS_TRANSFORM_DIAGNOSTIC_EXTENSION.yaml';bytes=1655;sha256='EB600E9AE67BF9675A2560CCDB88B50598F392258201CE5E7A6222F08FB2F55B'},
    [ordered]@{id='S02_R5_AUTHORIZATION';path='07_VERIFICATION/AUTONOMOUS/S02_R5/B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_OWNER_AUTHORIZATION.json';bytes=1403;sha256='D9098884C49DA0C583F55D84F49335BA3B2C8A076D270F22EFA5DE52AB396350'},
    [ordered]@{id='S02_R5_ADMISSION';path='07_VERIFICATION/AUTONOMOUS/S02_R5/B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_ADMISSION.json';bytes=1229;sha256='0D48C69D479AEA60BE8DD0A8F5989FCA6C4B503D88104AD76677AD6B6D65E1D2'},
    [ordered]@{id='WAITING_READINESS_SOURCE';path='08_REVIEWS/B51R1_S02_R5_StrongTypedWaitingReadinessProbe.cs';bytes=7046;sha256='12B77138941CF4CDAB24D614EFEE85E73BC4F1C978554995BB86DB09A4AAAA7E'},
    [ordered]@{id='WAITING_READINESS_BINARY';path='08_REVIEWS/B51R1_S02_R5_StrongTypedWaitingReadinessProbe.dll';bytes=8192;sha256='6F00792C0366C64EB920B95E12670CCB382B83B9A44AD22DD84BCD6427A8282C'},
    [ordered]@{id='TRANSFORM_PROBE_SOURCE_V3';path='08_REVIEWS/B51R1_S02_R5_TransformConventionProbe_V3.cs';bytes=25944;sha256='9EF27633B7168262079353BAB5B8A0FBCD0D6E501BB1094CA2E121058651D1F3'},
    [ordered]@{id='TRANSFORM_PROBE_BINARY_V3';path='08_REVIEWS/B51R1_S02_R5_TransformConventionProbe_V3.dll';bytes=21504;sha256='E21AC73F9D654D92EEE673D73BC98DC7E8CEDC6AB103F9597F7382FABE364642'},
    [ordered]@{id='TOOL_STATIC_RELEASE_V3';path='08_REVIEWS/B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_TOOL_STATIC_RELEASE_V3.json';bytes=2325;sha256='0B1DBE796F81A9BCBA1E1D9DBD5435B4C377B56712A8CB06520C3BF00BD92C29'}
)

foreach ($output in @($readinessReceipt, $inputLock, $receipt, $progress, $sessionReceipt)) {
    if (Test-Path -LiteralPath $output) {
        throw "S02_R5 append-only output already exists: $output"
    }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw 'S02_R5 requires zero existing SLDWORKS processes before launch'
}
foreach ($item in $lockedItems) {
    Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) `
        ([string]$item.sha256) ([string]$item.id)
}
Assert-File $solidworksExe 707392 $expectedSolidworksExe 'SolidWorks executable'
Assert-File $interop 2773312 $expectedInterop 'SolidWorks interop'

$session = [ordered]@{
    schema = 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT_V1'
    session_id = 'S02_R5'
    started_at = [DateTimeOffset]::Now.ToString('o')
    status = 'S02_R5_FAIL_CLOSED_NOT_STARTED'
    save_api_call_count = 0
    force_termination_path_present = $false
}
$launchHandle = $null
$launchedPid = $null
$exitCode = 1
try {
    Add-Type -Path $interop
    $launchHandle = Start-Process -FilePath $solidworksExe -PassThru
    $session['launch_request_process_id'] = $launchHandle.Id
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    $osProcessReady = $false
    while ([DateTimeOffset]::Now -lt $deadline -and -not $osProcessReady) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $candidate = $processes[0]
        $candidate.Refresh()
        if (-not $candidate.Responding -or $candidate.MainWindowHandle -eq [IntPtr]::Zero) {
            continue
        }
        $launchedPid = $candidate.Id
        $osProcessReady = $true
    }
    if (-not $osProcessReady -or $null -eq $launchedPid) {
        throw 'Fresh visible responsive SolidWorks process did not become ready within three minutes'
    }

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $readinessResult = [B51R1S02R5StrongTypedWaitingReadinessProbe]::Run(
        $launchedPid, $readinessReceipt, 120000)
    if ($readinessResult -ne 0) {
        throw "S02_R5 waiting readiness probe returned $readinessResult"
    }
    $readiness = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt |
        ConvertFrom-Json
    if ($readiness.status -ne 'PASS_STRONG_TYPED_VISIBLE_RESPONSIVE_STARTUP_COMPLETE_DOCUMENT_EMPTY') {
        throw "S02_R5 waiting readiness probe did not pass: $($readiness.status)"
    }
    $revision = [string]$readiness.solidworks_revision
    $runtimeLockedItems = @($lockedItems) + @(
        [ordered]@{
            id = 'S02_R5_WAITING_READINESS_RECEIPT'
            path = '07_VERIFICATION/AUTONOMOUS/S02_R5/B51R1_S02_R5_WAITING_READINESS_PROBE_RECEIPT.json'
            bytes = (Get-Item -LiteralPath $readinessReceipt).Length
            sha256 = Get-Sha $readinessReceipt
        })
    $session['solidworks_process_id'] = $launchedPid
    $session['solidworks_revision'] = $revision
    $session['fresh_visible_responsive_document_empty'] = $true
    $session['readiness_probe_receipt_sha256'] = Get-Sha $readinessReceipt
    $lock = [ordered]@{
        schema = 'B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_INPUT_LOCK_V1'
        generated_at = [DateTimeOffset]::Now.ToString('o')
        status = 'PASS_S02_R5_TRANSFORM_DIAGNOSTIC_INPUTS_HASH_LOCKED'
        session_id = 'S02_R5'
        runtime_boundary = [ordered]@{
            solidworks_process_id = $launchedPid
            solidworks_process_count = 1
            solidworks_visible = $true
            solidworks_responsive = $true
            solidworks_startup_completed = $true
            solidworks_document_count = 0
            solidworks_active_document_present = $false
            solidworks_revision = $revision
            solidworks_executable_sha256 = $expectedSolidworksExe
        }
        transaction = [ordered]@{
            target = '02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_R1.SLDPRT'
            target_bytes = 232433
            target_sha256 = $expectedTarget
            target_last_write_time_utc = (Get-Item -LiteralPath $target).LastWriteTimeUtc.ToString('o')
            receipt = '07_VERIFICATION/AUTONOMOUS/S02_R5/B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_RECEIPT.json'
            progress_log = '07_VERIFICATION/AUTONOMOUS/S02_R5/B51R1_S02_R5_TRANSFORM_DIAGNOSTIC_PROGRESS.log'
            outputs_absent_at_lock = $true
            open_mode = 'SILENT_READ_ONLY'
            save_api_call_count_allowed = 0
            rebuild_call_count_allowed = 0
            configuration_activation_call_count_allowed = 0
        }
        locked_items = $runtimeLockedItems
        locked_item_count = $runtimeLockedItems.Count
        downstream_hold = [ordered]@{
            s02_pass = $true
            active_candidate_pointer = $true
            property_writer_qualification = $true
            s03 = $true
            carrier_creation = $true
        }
        claim_limit = 'S02_R5_DIAGNOSTIC_INPUT_LOCK_ONLY_NO_TRANSFORM_CLASSIFICATION_S02_PASS_ACTIVE_CANDIDATE_OR_S03_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock
    $session['input_lock_sha256'] = Get-Sha $inputLock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = [B51R1S02R5TransformConventionProbeV3]::Run(
        $target,
        $stageA,
        $receipt,
        $progress,
        $launchedPid,
        $expectedTarget,
        $expectedStageA)
    if ($result -ne 0) {
        throw "S02_R5 transform probe returned $result"
    }
    $probe = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($probe.status -ne 'PASS_READ_ONLY_TRANSFORM_CONVENTION_EVIDENCE_CAPTURED') {
        throw "S02_R5 transform probe did not pass evidence capture: $($probe.status)"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'SolidWorks remains after transform probe requested normal ExitApp'
    }
    Assert-File $target 232433 $expectedTarget 'R1 target after S02_R5'
    Assert-File $stageA 511198 $expectedStageA 'Protected Stage A after S02_R5'
    $session['status'] = 'PASS_S02_R5_TRANSFORM_CONVENTION_EVIDENCE_CAPTURED'
    $session['probe_receipt_sha256'] = Get-Sha $receipt
    $session['target_sha256_after'] = Get-Sha $target
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['normal_application_exit'] = $true
    $exitCode = 0
}
catch {
    $session['status'] = 'S02_R5_FAIL_CLOSED'
    $session['error_type'] = $_.Exception.GetType().FullName
    $session['error_message'] = $_.Exception.Message
    $session['failed_at'] = [DateTimeOffset]::Now.ToString('o')
}
finally {
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        foreach ($process in $processes) {
            $process.Refresh()
            if ($process.Responding -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
                try { [void]$process.CloseMainWindow() } catch { }
            }
        }
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
            Start-Sleep -Milliseconds 500
        }
    }
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    $session['solidworks_process_count_after'] =
        @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
    if (Test-Path -LiteralPath $target) {
        $session['target_sha256_final'] = Get-Sha $target
    }
    if (Test-Path -LiteralPath $stageA) {
        $session['protected_stage_a_sha256_final'] = Get-Sha $stageA
    }
    if (-not (Test-Path -LiteralPath $sessionReceipt)) {
        Write-JsonCreateNew $sessionReceipt $session
    }
    if ($null -ne $launchHandle) { $launchHandle.Dispose() }
}

$session | ConvertTo-Json -Depth 20
exit $exitCode
