[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedAuthorizationSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedAdmissionSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedInputLockSupplementSha256,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$ExpectedProcessId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S01_CR01'
$source = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2.SLDPRT'
$work = Join-Path $sessionRoot 'WORK_S01_CR01\B51R1_MASTER_SKELETON_V2_CR01_WORK.SLDPRT'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_R1.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$authorization = Join-Path $sessionRoot 'B51R1_S01_CR01_S02_R1_OWNER_AUTHORIZATION.json'
$admission = Join-Path $sessionRoot 'B51R1_S01_CR01_ADMISSION_ADDENDUM.json'
$inputLock = Join-Path $sessionRoot 'B51R1_S01_CR01_INPUT_LOCK_SUPPLEMENT_V2.json'
$repairReceipt = Join-Path $sessionRoot 'B51R1_S01_CR01_PROPERTY_REPAIR_RECEIPT.json'
$sessionReceipt = Join-Path $sessionRoot 'B51R1_S01_CR01_SESSION_EXECUTION_RECEIPT.json'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S01_CR01_MasterSkeletonPropertyRepair_V2.dll'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'

$expectedSource = '71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA'
$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'
$expectedG1b = 'FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6'
$expectedFinalLock = 'AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214'
$expectedToolDll = '454B8C4CD6CA1CA1C492B61A62AE3079D6B8912DCEF9E64B419BB23E76576778'
$expectedSolidworksExe = '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
    $actual = Get-Sha $Path
    if ($actual -ne $Expected.ToUpperInvariant()) {
        throw "$Label SHA-256 mismatch: expected $Expected, observed $actual"
    }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) {
        throw "Append-only output already exists: $Path"
    }
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText(
        $Path,
        (($Value | ConvertTo-Json -Depth 20) + [Environment]::NewLine),
        $utf8NoBom)
}

foreach ($output in @($work, $target, $repairReceipt, $sessionReceipt)) {
    if (Test-Path -LiteralPath $output) {
        throw "S01_CR01 append-only output already exists; refusing overwrite: $output"
    }
}
$solidworksProcesses = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
if ($solidworksProcesses.Count -ne 1) {
    throw "S01_CR01 requires exactly one existing SLDWORKS process; observed $($solidworksProcesses.Count)"
}
$authorizedProcess = $solidworksProcesses[0]
$authorizedProcess.Refresh()
if ($authorizedProcess.Id -ne $ExpectedProcessId) {
    throw "Sole SLDWORKS PID $($authorizedProcess.Id) does not match authorized PID $ExpectedProcessId"
}
if (-not $authorizedProcess.Responding -or $authorizedProcess.MainWindowHandle -eq [IntPtr]::Zero) {
    throw 'Authorized SLDWORKS process is not visible and responsive'
}

Assert-Hash $authorization $ExpectedAuthorizationSha256 'Owner authorization'
Assert-Hash $admission $ExpectedAdmissionSha256 'S01_CR01 admission'
Assert-Hash $inputLock $ExpectedInputLockSupplementSha256 'S01_CR01 input-lock supplement'
Assert-Hash $source $expectedSource 'Protected source V2'
Assert-Hash $stageA $expectedStageA 'Protected Stage A'
Assert-Hash $toolDll $expectedToolDll 'Qualified repair DLL'
Assert-Hash $solidworksExe $expectedSolidworksExe 'SolidWorks executable'

$lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $inputLock | ConvertFrom-Json
if ($lock.status -ne 'PASS_S01_CR01_INPUTS_HASH_LOCKED') {
    throw "Input-lock supplement is not PASS: $($lock.status)"
}
foreach ($item in @($lock.locked_items)) {
    $lockedPath = Join-Path $root ([string]$item.path)
    Assert-Hash $lockedPath ([string]$item.sha256) ([string]$item.id)
    if ((Get-Item -LiteralPath $lockedPath).Length -ne [long]$item.bytes) {
        throw "Locked byte count mismatch for $($item.id)"
    }
}

$session = [ordered]@{
    schema = 'B51R1_S01_CR01_SESSION_EXECUTION_RECEIPT_V1'
    session_id = 'S01_CR01'
    started_at = [DateTimeOffset]::Now.ToString('o')
    status = 'S01_CR01_FAIL_CLOSED_NOT_STARTED'
    authorization_sha256 = (Get-Sha $authorization)
    admission_sha256 = (Get-Sha $admission)
    input_lock_supplement_sha256 = (Get-Sha $inputLock)
    source_sha256_before = (Get-Sha $source)
    protected_stage_a_sha256_before = (Get-Sha $stageA)
    repair_tool_sha256 = (Get-Sha $toolDll)
    solidworks_process_count_at_admission = 1
    solidworks_process_id = $ExpectedProcessId
    attach_existing_visible_process = $true
    launch_new_visible_process = $false
    force_termination_path_present = $false
}

$exitCode = 1
try {
    $session['solidworks_visible_and_responding'] = $true
    Write-Host "S01_CR01: existing process precondition ready (PID $ExpectedProcessId)."

    Add-Type -Path $interop
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    $result = [B51R1S01CR01MasterSkeletonPropertyRepairV2]::Run(
        $source,
        $work,
        $target,
        $stageA,
        $repairReceipt,
        $ExpectedProcessId,
        $expectedSource,
        $expectedStageA,
        $expectedG1b,
        $expectedFinalLock)
    if ($result -ne 0) {
        throw "S01_CR01 repair tool returned $result"
    }
    if (-not (Test-Path -LiteralPath $repairReceipt -PathType Leaf)) {
        throw 'S01_CR01 repair receipt was not created'
    }
    $repair = Get-Content -Raw -Encoding UTF8 -LiteralPath $repairReceipt | ConvertFrom-Json
    if ($repair.status -ne 'S01_CR01_PASS_APPEND_ONLY_PROPERTY_REPAIR_REVISION_CREATED') {
        throw "S01_CR01 repair receipt did not pass: $($repair.status)"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'SolidWorks remains after repair-tool requested normal ExitApp'
    }
    Assert-Hash $source $expectedSource 'Protected source V2 after S01_CR01'
    Assert-Hash $stageA $expectedStageA 'Protected Stage A after S01_CR01'
    if ((Get-Sha $work) -ne $expectedSource) {
        throw 'Isolated work copy is not the preserved byte-identical V2 input'
    }

    $session['status'] = 'S01_CR01_PASS_APPEND_ONLY_PROPERTY_REPAIR_REVISION_CREATED'
    $session['repair_receipt_sha256'] = Get-Sha $repairReceipt
    $session['target_revision_path'] = $target
    $session['target_revision_sha256'] = Get-Sha $target
    $session['target_revision_bytes'] = (Get-Item -LiteralPath $target).Length
    $session['source_sha256_after'] = Get-Sha $source
    $session['isolated_work_sha256_after'] = Get-Sha $work
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['normal_application_exit'] = $true
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    $exitCode = 0
}
catch {
    $session['status'] = 'S01_CR01_FAIL_CLOSED'
    $session['error_type'] = $_.Exception.GetType().FullName
    $session['error_message'] = $_.Exception.Message
    $session['failed_at'] = [DateTimeOffset]::Now.ToString('o')
    $session['solidworks_processes_remaining'] = @(
        Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue |
            ForEach-Object {
                [ordered]@{
                    pid = $_.Id
                    responding = $_.Responding
                    main_window_handle = $_.MainWindowHandle.ToInt64()
                }
            })
}
finally {
    if (Test-Path -LiteralPath $source) {
        $session['source_sha256_final'] = Get-Sha $source
    }
    if (Test-Path -LiteralPath $stageA) {
        $session['protected_stage_a_sha256_final'] = Get-Sha $stageA
    }
    if (Test-Path -LiteralPath $target) {
        $session['target_revision_sha256_final'] = Get-Sha $target
    }
    Write-JsonCreateNew $sessionReceipt $session
}

exit $exitCode
