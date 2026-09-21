$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$runnerR11 = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R11_NativePilot.ps1'
$runnerR12 = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R12_NativePilot.ps1'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false, $true)

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

if (Test-Path -LiteralPath $runnerR12) {
    throw "R12 runner target already exists: $runnerR12"
}

$r11Bytes = [System.IO.File]::ReadAllBytes($runnerR11)
$r11Sha256 = Get-Sha256 -Bytes $r11Bytes
if ($r11Bytes.Length -ne 125174 -or
    $r11Sha256 -ne '0EA669F9C5692607E62788557AF4137880D15D3B171606BF7FCC3CE29E59D854') {
    throw "R11 runner identity mismatch: length=$($r11Bytes.Length), sha256=$r11Sha256."
}

$r11Text = $utf8NoBom.GetString($r11Bytes)
$sentinel = '__R9_ACTIVATION_REVISION_SENTINEL__'
if ($r11Text.Contains($sentinel) -or [regex]::Matches($r11Text, 'V22R11A').Count -ne 1) {
    throw 'R9 activation revision protection anchor mismatch.'
}

$r12Text = $r11Text.Replace('V22R11A', $sentinel)
$r12Text = $r12Text.Replace('R11', 'R12').Replace('r11', 'r12')
$r12Text = $r12Text.Replace($sentinel, 'V22R11A')
$r12Text = $r12Text.Replace('V22R15A', 'V22R17A').Replace('V22R16A', 'V22R18A')
$r12Text = $r12Text.Replace('$toolSourceBytes = 130647', '$toolSourceBytes = 130525')
$r12Text = $r12Text.Replace(
    '$toolSourceSha256 = ''424D6E8BDACE82B20EDDB134EA8A55260666D6810EDE2BE81F345EA1A17B78F3''',
    '$toolSourceSha256 = ''31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A''')
$r12Text = $r12Text.Replace(
    '$toolDllSha256 = ''BBD8FA61860F3EE14B607485A7085D961E1F56E92F233D27E5AC46A7F76558C4''',
    '$toolDllSha256 = ''24F44E11FB1CFE761BFC9F7908F29D6FFF96F9D7CDBD89385ADA1D96783A7BB8''')

if ([regex]::Matches($r12Text, 'R11').Count -ne 1 -or
    [regex]::Matches($r12Text, 'V22R11A').Count -ne 1 -or
    [regex]::Matches($r12Text, 'r11').Count -ne 0 -or
    [regex]::Matches($r12Text, 'V22R17A').Count -ne 2 -or
    [regex]::Matches($r12Text, 'V22R18A').Count -ne 2) {
    throw 'R12 runner base generation anchors are inconsistent.'
}
if (-not $r12Text.Contains('$toolSourceBytes = 130525') -or
    -not $r12Text.Contains('$toolSourceSha256 = ''31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A''') -or
    -not $r12Text.Contains('$toolDllSha256 = ''24F44E11FB1CFE761BFC9F7908F29D6FFF96F9D7CDBD89385ADA1D96783A7BB8''')) {
    throw 'R12 runner base tool identity replacement failed.'
}

$r12Bytes = $utf8NoBom.GetBytes($r12Text)
[System.IO.File]::WriteAllBytes($runnerR12, $r12Bytes)
Write-Output "CREATED_UNFROZEN|R12_RUNNER_BASE|bytes=$($r12Bytes.Length)|sha256=$(Get-Sha256 -Bytes $r12Bytes)|path=$runnerR12"
