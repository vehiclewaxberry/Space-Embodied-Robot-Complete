$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
$sourceR11 = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NativePilotTool.cs'
$sourceR12 = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R12_NativePilotTool.cs'
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

function Assert-Identity {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$ExpectedLength,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    $actualSha256 = Get-Sha256 -Bytes $Bytes
    if ($Bytes.Length -ne $ExpectedLength -or $actualSha256 -ne $ExpectedSha256) {
        throw "$Name identity mismatch: length=$($Bytes.Length), sha256=$actualSha256."
    }
}

$r11Bytes = [System.IO.File]::ReadAllBytes($sourceR11)
Assert-Identity `
    -Name 'R11 source' `
    -Bytes $r11Bytes `
    -ExpectedLength 130647 `
    -ExpectedSha256 '424D6E8BDACE82B20EDDB134EA8A55260666D6810EDE2BE81F345EA1A17B78F3'

$r11Text = $utf8NoBom.GetString($r11Bytes)
$r11AnchorCount = [regex]::Matches($r11Text, 'R11').Count
if ($r11AnchorCount -ne 15) {
    throw "R11 source generation anchor count mismatch: $r11AnchorCount."
}

$entitiesToMateLine = '            data.EntitiesToMate = new object[] { parentLimit, childZero };' + [char]10
$referenceEntityLine = '            data.ReferenceEntity = parentAxis;' + [char]10
if ([regex]::Matches($r11Text, [regex]::Escape($entitiesToMateLine)).Count -ne 1) {
    throw 'R11 source EntitiesToMate deletion anchor is not unique.'
}
if ([regex]::Matches($r11Text, [regex]::Escape($referenceEntityLine)).Count -ne 1) {
    throw 'R11 source ReferenceEntity deletion anchor is not unique.'
}

$r12Text = $r11Text.Replace('R11', 'R12')
$r12Text = $r12Text.Replace($entitiesToMateLine, '')
$r12Text = $r12Text.Replace($referenceEntityLine, '')
$r12Bytes = $utf8NoBom.GetBytes($r12Text)
Assert-Identity `
    -Name 'R12 source candidate' `
    -Bytes $r12Bytes `
    -ExpectedLength 130525 `
    -ExpectedSha256 '31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A'

if ([regex]::Matches($r12Text, 'R11').Count -ne 0) {
    throw 'R12 source retains an R11 generation anchor.'
}
if ($r12Text.Contains('data.EntitiesToMate = new object[] { parentLimit, childZero };') -or
    $r12Text.Contains('data.ReferenceEntity = parentAxis;')) {
    throw 'R12 source retains a removed duplicate angle entity assignment.'
}

if (Test-Path -LiteralPath $sourceR12) {
    $existingBytes = [System.IO.File]::ReadAllBytes($sourceR12)
    Assert-Identity `
        -Name 'Existing R12 source' `
        -Bytes $existingBytes `
        -ExpectedLength 130525 `
        -ExpectedSha256 '31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A'
    Write-Output "PRESENT_VERIFIED|R12_SOURCE|$sourceR12"
}
else {
    [System.IO.File]::WriteAllBytes($sourceR12, $r12Bytes)
    $writtenBytes = [System.IO.File]::ReadAllBytes($sourceR12)
    Assert-Identity `
        -Name 'Written R12 source' `
        -Bytes $writtenBytes `
        -ExpectedLength 130525 `
        -ExpectedSha256 '31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A'
    Write-Output "CREATED_VERIFIED|R12_SOURCE|$sourceR12"
}
