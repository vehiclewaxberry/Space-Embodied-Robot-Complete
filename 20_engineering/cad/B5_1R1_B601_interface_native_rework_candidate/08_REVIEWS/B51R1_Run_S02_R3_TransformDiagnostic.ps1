[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S02_R3'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_R1.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$inputLock = Join-Path $sessionRoot 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_INPUT_LOCK.json'
$receipt = Join-Path $sessionRoot 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_RECEIPT.json'
$progress = Join-Path $sessionRoot 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_PROGRESS.log'
$sessionReceipt = Join-Path $sessionRoot 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT.json'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S02_R3_TransformConventionProbe.dll'
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

function Release-Com($Value) {
    if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value) }
        catch { }
    }
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
    [ordered]@{id='POOL_A_A14_EXTENSION';path='04_CONFIGURATION/B51R1_AUTONOMOUS_SESSION_PLAN_V5_POOL_A_S02_R3_TRANSFORM_DIAGNOSTIC_EXTENSION.yaml';bytes=1315;sha256='5C81A07FABDD53326D951D550C0A257DD397983F074A7F11B080A51510EA637C'},
    [ordered]@{id='S02_R3_AUTHORIZATION';path='07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_OWNER_AUTHORIZATION.json';bytes=1312;sha256='37DB3E7F9456D3DAE8E65888F83744B43E8BD1A087BC2758D79B370AC4DCB2C1'},
    [ordered]@{id='S02_R3_ADMISSION';path='07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_ADMISSION.json';bytes=1385;sha256='334E123840BAF6006C48AA4D4C8F5AE5DB2EC4E23FE71E8B154A95C540E155CF'},
    [ordered]@{id='TRANSFORM_PROBE_SOURCE';path='08_REVIEWS/B51R1_S02_R3_TransformConventionProbe.cs';bytes=25942;sha256='E824F10A763EFEC41E457A0B8AA0170C8EC8A99B13AB9063E76D854AEE144937'},
    [ordered]@{id='TRANSFORM_PROBE_BINARY';path='08_REVIEWS/B51R1_S02_R3_TransformConventionProbe.dll';bytes=21504;sha256='597D828F30471CB085A3077F5E84F3F663FC80C73A18E880561D0E02695ED307'},
    [ordered]@{id='TRANSFORM_PROBE_STATIC_RELEASE';path='08_REVIEWS/B51R1_S02_R3_TRANSFORM_CONVENTION_PROBE_STATIC_RELEASE.json';bytes=1924;sha256='76B7F3D6DB24D80E27F31E996E17C09A3D1AC0BE1E6D9F51FD501BC29C2B3D25'}
)

foreach ($output in @($inputLock, $receipt, $progress, $sessionReceipt)) {
    if (Test-Path -LiteralPath $output) {
        throw "S02_R3 append-only output already exists: $output"
    }
}
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw 'S02_R3 requires zero existing SLDWORKS processes before launch'
}
foreach ($item in $lockedItems) {
    Assert-File (Join-Path $root ([string]$item.path)) ([long]$item.bytes) `
        ([string]$item.sha256) ([string]$item.id)
}
Assert-File $solidworksExe 707392 $expectedSolidworksExe 'SolidWorks executable'
Assert-File $interop 2773312 $expectedInterop 'SolidWorks interop'

$session = [ordered]@{
    schema = 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_SESSION_RECEIPT_V1'
    session_id = 'S02_R3'
    started_at = [DateTimeOffset]::Now.ToString('o')
    status = 'S02_R3_FAIL_CLOSED_NOT_STARTED'
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
    $startupReady = $false
    $revision = $null
    while ([DateTimeOffset]::Now -lt $deadline -and -not $startupReady) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $candidate = $processes[0]
        $candidate.Refresh()
        if (-not $candidate.Responding -or $candidate.MainWindowHandle -eq [IntPtr]::Zero) {
            continue
        }
        $app = $null
        try {
            $app = [Runtime.InteropServices.Marshal]::GetActiveObject('SldWorks.Application')
            if ($null -eq $app -or [int]$app.GetProcessID() -ne $candidate.Id -or
                -not [bool]$app.Visible -or -not [bool]$app.StartupProcessCompleted) {
                continue
            }
            if ([int]$app.GetDocumentCount() -ne 0 -or $null -ne $app.ActiveDoc) {
                throw 'Fresh SolidWorks process is not document-empty'
            }
            $launchedPid = $candidate.Id
            $revision = [string]$app.RevisionNumber()
            $startupReady = $true
        }
        finally {
            Release-Com $app
        }
    }
    if (-not $startupReady -or $null -eq $launchedPid) {
        throw 'Fresh visible document-empty SolidWorks process did not become ready within three minutes'
    }

    $session['solidworks_process_id'] = $launchedPid
    $session['solidworks_revision'] = $revision
    $session['fresh_visible_responsive_document_empty'] = $true
    $lock = [ordered]@{
        schema = 'B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_INPUT_LOCK_V1'
        generated_at = [DateTimeOffset]::Now.ToString('o')
        status = 'PASS_S02_R3_TRANSFORM_DIAGNOSTIC_INPUTS_HASH_LOCKED'
        session_id = 'S02_R3'
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
            receipt = '07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_RECEIPT.json'
            progress_log = '07_VERIFICATION/AUTONOMOUS/S02_R3/B51R1_S02_R3_TRANSFORM_DIAGNOSTIC_PROGRESS.log'
            outputs_absent_at_lock = $true
            open_mode = 'SILENT_READ_ONLY'
            save_api_call_count_allowed = 0
            rebuild_call_count_allowed = 0
            configuration_activation_call_count_allowed = 0
        }
        locked_items = $lockedItems
        locked_item_count = $lockedItems.Count
        downstream_hold = [ordered]@{
            s02_pass = $true
            active_candidate_pointer = $true
            property_writer_qualification = $true
            s03 = $true
            carrier_creation = $true
        }
        claim_limit = 'S02_R3_DIAGNOSTIC_INPUT_LOCK_ONLY_NO_TRANSFORM_CLASSIFICATION_S02_PASS_ACTIVE_CANDIDATE_OR_S03_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock
    $session['input_lock_sha256'] = Get-Sha $inputLock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = [B51R1S02R3TransformConventionProbe]::Run(
        $target,
        $stageA,
        $receipt,
        $progress,
        $launchedPid,
        $expectedTarget,
        $expectedStageA)
    if ($result -ne 0) {
        throw "S02_R3 transform probe returned $result"
    }
    $probe = Get-Content -Raw -Encoding UTF8 -LiteralPath $receipt | ConvertFrom-Json
    if ($probe.status -ne 'PASS_READ_ONLY_TRANSFORM_CONVENTION_EVIDENCE_CAPTURED') {
        throw "S02_R3 transform probe did not pass evidence capture: $($probe.status)"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'SolidWorks remains after transform probe requested normal ExitApp'
    }
    Assert-File $target 232433 $expectedTarget 'R1 target after S02_R3'
    Assert-File $stageA 511198 $expectedStageA 'Protected Stage A after S02_R3'
    $session['status'] = 'PASS_S02_R3_TRANSFORM_CONVENTION_EVIDENCE_CAPTURED'
    $session['probe_receipt_sha256'] = Get-Sha $receipt
    $session['target_sha256_after'] = Get-Sha $target
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['normal_application_exit'] = $true
    $exitCode = 0
}
catch {
    $session['status'] = 'S02_R3_FAIL_CLOSED'
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
