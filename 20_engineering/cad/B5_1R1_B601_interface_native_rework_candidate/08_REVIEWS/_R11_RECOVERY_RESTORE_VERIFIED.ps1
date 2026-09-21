$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$sessionLog = 'C:\Users\stude\.codex\sessions\2026\08\05\rollout-2026-08-05T15-25-08-019fd0cf-d274-7132-ae2b-35ef1fe0c235.jsonl'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-SessionLine {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][int]$Number
    )

    $reader = [System.IO.File]::OpenText($Path)
    try {
        for ($lineNumber = 1; $lineNumber -lt $Number; $lineNumber++) {
            if ($null -eq $reader.ReadLine()) {
                throw "Session log ended before line $Number."
            }
        }
        return $reader.ReadLine()
    }
    finally {
        $reader.Dispose()
    }
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return -join ($sha256.ComputeHash($Bytes) | ForEach-Object { $_.ToString('X2') })
    }
    finally {
        $sha256.Dispose()
    }
}

function Assert-Bytes {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$ExpectedLength,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    $actualSha256 = Get-Sha256 -Bytes $Bytes
    if ($Bytes.Length -ne $ExpectedLength -or $actualSha256 -ne $ExpectedSha256) {
        throw "$Name failed verification: length=$($Bytes.Length), sha256=$actualSha256."
    }
}

function Write-VerifiedFile {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$ExpectedLength,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    Assert-Bytes -Name $Name -Bytes $Bytes -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256
    if (Test-Path -LiteralPath $Path) {
        $existingBytes = [System.IO.File]::ReadAllBytes($Path)
        Assert-Bytes -Name "$Name existing target" -Bytes $existingBytes -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256
        Write-Output "PRESENT_VERIFIED|$Name|$Path"
        return
    }

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    [System.IO.File]::WriteAllBytes($Path, $Bytes)
    $writtenBytes = [System.IO.File]::ReadAllBytes($Path)
    Assert-Bytes -Name "$Name written target" -Bytes $writtenBytes -ExpectedLength $ExpectedLength -ExpectedSha256 $ExpectedSha256
    Write-Output "RESTORED_VERIFIED|$Name|$Path"
}

function Get-LoggedOutputBytes {
    param(
        [Parameter(Mandatory = $true)][int]$Line,
        [Parameter(Mandatory = $true)][int]$OutputIndex,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $record = (Get-SessionLine -Path $sessionLog -Number $Line) | ConvertFrom-Json
    $raw = [string]$record.payload.output[$OutputIndex].text
    $marker = 'Output:'
    $start = $raw.IndexOf($marker, [System.StringComparison]::Ordinal)
    if ($start -lt 0) {
        throw "Output marker is missing at session line $Line, output index $OutputIndex."
    }
    $start += $marker.Length
    if ($start -lt $raw.Length -and [int]$raw[$start] -eq 13) {
        $start++
    }
    if ($start -lt $raw.Length -and [int]$raw[$start] -eq 10) {
        $start++
    }
    return $utf8NoBom.GetBytes($raw.Substring($start, $Length))
}

function Get-GitBlobBytes {
    param(
        [Parameter(Mandatory = $true)][string]$GitDirectory,
        [Parameter(Mandatory = $true)][string]$ObjectId
    )

    $git = (Get-Command git.exe -ErrorAction Stop).Source
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $git
    $startInfo.Arguments = '--git-dir="{0}" cat-file blob {1}' -f $GitDirectory, $ObjectId
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $memory = New-Object System.IO.MemoryStream
    try {
        if (-not $process.Start()) {
            throw 'Failed to start git cat-file.'
        }
        $process.StandardOutput.BaseStream.CopyTo($memory)
        $standardError = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            throw "git cat-file failed with exit code $($process.ExitCode): $standardError"
        }
        return $memory.ToArray()
    }
    finally {
        $memory.Dispose()
        $process.Dispose()
    }
}

function Get-OpenCodeAddedFileBytes {
    param(
        [Parameter(Mandatory = $true)][string]$SessionDiffPath,
        [Parameter(Mandatory = $true)][string]$RelativeFile
    )

    $diffs = Get-Content -LiteralPath $SessionDiffPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $matchingDiffs = @(@($diffs) | Where-Object { [string]$_.file -eq $RelativeFile -and [string]$_.status -eq 'added' })
    if ($matchingDiffs.Count -ne 1) {
        throw "Expected one added OpenCode session diff for $RelativeFile; found $($matchingDiffs.Count)."
    }

    $lines = ([string]$matchingDiffs[0].patch).Split([char]10)
    $hunkIndex = -1
    for ($index = 0; $index -lt $lines.Length; $index++) {
        if ($lines[$index].StartsWith('@@ ', [System.StringComparison]::Ordinal)) {
            $hunkIndex = $index
            break
        }
    }
    if ($hunkIndex -lt 0) {
        throw "OpenCode session diff hunk is missing for $RelativeFile."
    }

    $addedLines = New-Object System.Collections.Generic.List[string]
    $noFinalNewline = $false
    for ($index = $hunkIndex + 1; $index -lt $lines.Length; $index++) {
        $line = $lines[$index]
        if ($line -eq '\ No newline at end of file') {
            $noFinalNewline = $true
            continue
        }
        if ($index -eq $lines.Length - 1 -and $line.Length -eq 0) {
            continue
        }
        if (-not $line.StartsWith('+', [System.StringComparison]::Ordinal)) {
            throw "Unexpected non-addition line in OpenCode session diff for $RelativeFile."
        }
        $addedLines.Add($line.Substring(1))
    }

    $content = [string]::Join(([char]10).ToString(), $addedLines)
    if (-not $noFinalNewline) {
        $content += [char]10
    }
    return $utf8NoBom.GetBytes($content)
}

$sourcePath = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NativePilotTool.cs'
$sourceBytes = [System.IO.File]::ReadAllBytes($sourcePath)
Write-VerifiedFile `
    -Name 'R11_SOURCE' `
    -Path $sourcePath `
    -Bytes $sourceBytes `
    -ExpectedLength 130647 `
    -ExpectedSha256 '424D6E8BDACE82B20EDDB134EA8A55260666D6810EDE2BE81F345EA1A17B78F3'

$runnerPath = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R11_NativePilot.ps1'
$runnerBytes = [System.IO.File]::ReadAllBytes($runnerPath)
Write-VerifiedFile `
    -Name 'R11_RUNNER' `
    -Path $runnerPath `
    -Bytes $runnerBytes `
    -ExpectedLength 125174 `
    -ExpectedSha256 '0EA669F9C5692607E62788557AF4137880D15D3B171606BF7FCC3CE29E59D854'

$staticBytes = Get-LoggedOutputBytes -Line 5789 -OutputIndex 8 -Length 6574
Write-VerifiedFile `
    -Name 'R11_STATIC_RELEASE' `
    -Path (Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json') `
    -Bytes $staticBytes `
    -ExpectedLength 6574 `
    -ExpectedSha256 '70CA724E4E560CBC0291F33BA59E4B23037D616AE1A1691C521A4632581ADBD1'

$activationBytes = Get-LoggedOutputBytes -Line 5806 -OutputIndex 8 -Length 4452
Write-VerifiedFile `
    -Name 'R11_CREATE_ACTIVATION' `
    -Path (Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R15A_POOL_A_A08R2_J01_R11_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json') `
    -Bytes $activationBytes `
    -ExpectedLength 4452 `
    -ExpectedSha256 'D2C6C6680E4E4AA17FFD7500E33A0D31445BBCBD4FCA0A14216E8274C854F802'

$readinessBytes = [System.Convert]::FromBase64String('eyJzY2hlbWEiOiJCNTFSMV9TUjAzX0VYSVNUSU5HX1NPTElEV09SS1NfUFJPQkVfVjEiLCJnZW5lcmF0ZWRfYXRfdXRjIjoiMjAyNi0wOC0wNVQwNzoxMToyMS41MjQ0ODg1WiIsInN0YXR1cyI6IlBBU1NfRVhJU1RJTkdfU0lOR0xFX1ZJU0lCTEVfUkVTUE9OU0lWRV9ET0NVTUVOVF9FTVBUWV9TRVNTSU9OIiwiZXhwZWN0ZWRfcHJvY2Vzc19pZCI6NTE3NDQsImF0dGFjaG1lbnRfcm91dGUiOiJDU0hBUlBfTUFSU0hBTF9HRVRBQ1RJVkVPQkpFQ1RfRVhJU1RJTkdfVVNFUl9PUEVORURfUFJPQ0VTUyIsInJlYWRfb25seV9wcmVmbGlnaHQiOnRydWUsIm9ic2VydmVkX3Byb2Nlc3NfaWQiOjUxNzQ0LCJ2aXNpYmxlIjp0cnVlLCJzdGFydHVwX3Byb2Nlc3NfY29tcGxldGVkIjp0cnVlLCJkb2N1bWVudF9jb3VudCI6MCwiYWN0aXZlX2RvY3VtZW50X3ByZXNlbnQiOmZhbHNlLCJzb2xpZHdvcmtzX3JldmlzaW9uIjoiMzIuNS4wIn0=')
Write-VerifiedFile `
    -Name 'R11_CREATE_READINESS' `
    -Path (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_READINESS_RECEIPT.json') `
    -Bytes $readinessBytes `
    -ExpectedLength 470 `
    -ExpectedSha256 'A60071AE3D31B57FFB843726A11395CB5BEDCE50ACFF78528ADA0E2C130D7626'

$progressBytes = [System.Convert]::FromBase64String('SjAxX1IxMV9DUkVBVEVfU1RBUlQgMjAyNi0wOC0wNVQwNzoxMToyMS44NjA0NzQyWg0KSjAxX1IxMV9DUkVBVEVfRkFJTCBDcmVhdGVNYXRlIHJldHVybmVkIG5vIEZlYXR1cmU6IEowMV9MSU1JVF9BTkdMRV9EUklWRVIsIEVycm9yU3RhdHVzPTQNCg==')
Write-VerifiedFile `
    -Name 'R11_CREATE_PROGRESS' `
    -Path (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_PROGRESS.log') `
    -Bytes $progressBytes `
    -ExpectedLength 142 `
    -ExpectedSha256 '004AC28A6DADE9E9BD289C06F1AFBD619B7F8CF9DE10F30C8B775E03843D7DB3'

$frozenDll = Join-Path $root '08_REVIEWS\_R11_DETERMINISM_A\B51R1_S05R2_J01_R11_NativePilotTool.dll'
$dllBytes = [System.IO.File]::ReadAllBytes($frozenDll)
Write-VerifiedFile `
    -Name 'R11_NATIVE_PILOT_DLL' `
    -Path (Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NativePilotTool.dll') `
    -Bytes $dllBytes `
    -ExpectedLength 81408 `
    -ExpectedSha256 'BBD8FA61860F3EE14B607485A7085D961E1F56E92F233D27E5AC46A7F76558C4'

$snapshotGitDirectory = 'C:\Users\stude\.local\share\opencode\snapshot\0a6df165f61ad99a66c740d4a5059ab6fabc082c\22c0669affad874e85b84739636aaedb92fc5b85'
$partialJ00Bytes = Get-GitBlobBytes `
    -GitDirectory $snapshotGitDirectory `
    -ObjectId '74295157e2629ab8cc53d1aa82f577ea26058b6c'
Write-VerifiedFile `
    -Name 'R11_PARTIAL_J00' `
    -Path (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\CHECKPOINTS\B51R1_CARRIER_J00_ROOT_PILOT_R11.SLDASM') `
    -Bytes $partialJ00Bytes `
    -ExpectedLength 44153 `
    -ExpectedSha256 'FE407C32E1D596DABA9C6B1290C1005D0D72ABC2BF04052F2C4F0E9A0A70FD10'

$sessionDiffPath = 'C:\Users\stude\.local\share\opencode\storage\session_diff\ses_03739af2fffeSVt05aUbCrjaax.json'
$inputLockRelativeFile = '20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/07_VERIFICATION/AUTONOMOUS/S05R2_J01_R11/B51R1_S05R2_J01_R11_CREATE_INPUT_LOCK.json'
$inputLockDiffBytes = Get-OpenCodeAddedFileBytes `
    -SessionDiffPath $sessionDiffPath `
    -RelativeFile $inputLockRelativeFile
Assert-Bytes `
    -Name 'R11_CREATE_INPUT_LOCK_SESSION_DIFF' `
    -Bytes $inputLockDiffBytes `
    -ExpectedLength 43594 `
    -ExpectedSha256 '03C33896B4DEDCE28C39EF94108E097B1D6A59C7C198A36E34BEDF80F9ECD1C1'
$inputLockBytes = Get-GitBlobBytes `
    -GitDirectory $snapshotGitDirectory `
    -ObjectId 'da1461b3a519c0b48fb0d765e9a76bc0fbb7fa24'
Write-VerifiedFile `
    -Name 'R11_CREATE_INPUT_LOCK' `
    -Path (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_INPUT_LOCK.json') `
    -Bytes $inputLockBytes `
    -ExpectedLength 43594 `
    -ExpectedSha256 '03C33896B4DEDCE28C39EF94108E097B1D6A59C7C198A36E34BEDF80F9ECD1C1'

$receiptRelativeFile = '20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/07_VERIFICATION/AUTONOMOUS/S05R2_J01_R11/B51R1_S05R2_J01_R11_CREATE_RECEIPT.json'
$receiptDiffBytes = Get-OpenCodeAddedFileBytes `
    -SessionDiffPath $sessionDiffPath `
    -RelativeFile $receiptRelativeFile
Assert-Bytes `
    -Name 'R11_CREATE_RECEIPT_SESSION_DIFF' `
    -Bytes $receiptDiffBytes `
    -ExpectedLength 102463 `
    -ExpectedSha256 '4578AB3A9405D3EC8EE62F579FAF2416E1CB03B0256676C894E4CC3F39EFCB3E'
$receiptBytes = Get-GitBlobBytes `
    -GitDirectory $snapshotGitDirectory `
    -ObjectId 'a4c076ffc17f262b1019e2e5e45df52b5b0a880f'
Write-VerifiedFile `
    -Name 'R11_CREATE_RECEIPT' `
    -Path (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_RECEIPT.json') `
    -Bytes $receiptBytes `
    -ExpectedLength 102463 `
    -ExpectedSha256 '4578AB3A9405D3EC8EE62F579FAF2416E1CB03B0256676C894E4CC3F39EFCB3E'

$forbiddenR11Outputs = @(
    (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\B51R1_CARRIER_J01_R11_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_GATE.json')
)
foreach ($forbiddenPath in $forbiddenR11Outputs) {
    if (Test-Path -LiteralPath $forbiddenPath) {
        throw "R11 forbidden completed output exists: $forbiddenPath"
    }
}

Write-Output 'R11_VERIFIED_RECOVERY_COMPLETE|transaction_closure_objects=10|closure_complete=true|forbidden_completed_outputs_absent=true'
