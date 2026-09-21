param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$rootPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../..')).TrimEnd('\')
$auditPath = Split-Path $PSScriptRoot -Parent
if ($rootPath -ne 'F:\China Graduate Future Flight Vehicle Innovation Competition') { throw 'Unexpected workspace' }
$review = Get-Content -LiteralPath (Join-Path $auditPath 'LARGE_REDUNDANCY_REVIEW.json') -Raw | ConvertFrom-Json
$candidates = @($review.removal_candidates)
if ($candidates.Count -ne 3) { throw 'Unexpected candidate count' }
$allowed = @('servicer_service.step','servicer_released.step','servicer_parking.step')
function Get-CheckedFile([string]$relative) {
    $full = [IO.Path]::GetFullPath((Join-Path $rootPath $relative))
    if (-not $full.StartsWith($rootPath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Outside workspace' }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.PSIsContainer) { throw 'Expected file' }
    $cursor = $item
    while ($cursor.FullName -ne $rootPath) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse path rejected' }
        $cursor = Get-Item -LiteralPath (Split-Path $cursor.FullName -Parent) -Force
    }
    return $item
}
$connections = @(netstat -ano -p TCP)
if ($LASTEXITCODE -ne 0) { throw 'netstat failed' }
if (@($connections | Where-Object { $_ -match ':324[56]\s' }).Count -gt 0) { throw 'Viewer connection detected; preserve copies' }
$verified = @()
foreach ($row in $candidates) {
    $name = Split-Path $row.source -Leaf
    if ($allowed -notcontains $name -or $row.source -ne "40_evidence/artifacts/visualization/cad_showcase_20260916/$name" -or $row.canonical -ne "20_engineering/service_robot_wp03_spacecraft_body_r1/$name") { throw 'Not exact whitelist' }
    if (-not $row.byte_identical -or -not $row.approved_for_root_execution) { throw 'Review has not cleared duplicate' }
    $source = Get-CheckedFile $row.source
    $canonical = Get-CheckedFile $row.canonical
    if ($source.Length -ne $row.size_bytes -or $canonical.Length -ne $row.size_bytes) { throw 'Size changed' }
    $sourceHash = (Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $canonicalHash = (Get-FileHash -LiteralPath $canonical.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -ne $row.sha256 -or $canonicalHash -ne $row.sha256) { throw 'Hash changed' }
    $null = Get-CheckedFile $row.canonical_editable_source
    $verified += [pscustomobject][ordered]@{source=$row.source;canonical=$row.canonical;bytes=[long]$source.Length;sha256=$sourceHash;restore='Copy canonical bytes to the former source path and verify this hash'}
}
if (-not $Execute) {
    [ordered]@{verified=$verified.Count;bytes=($verified | Measure-Object -Property bytes -Sum).Sum;executed=$false} | ConvertTo-Json
    exit 0
}
$deleted = @()
foreach ($row in $verified) {
    Remove-Item -LiteralPath (Join-Path $rootPath $row.source)
    if (Test-Path -LiteralPath (Join-Path $rootPath $row.source)) { throw 'Removal not confirmed' }
    $deleted += $row
    [ordered]@{schema='EXACT_DISPLAY_DUPLICATE_CLEANUP_V1';generated_utc=[DateTime]::UtcNow.ToString('o');deleted_files=$deleted.Count;deleted_bytes=($deleted | Measure-Object -Property bytes -Sum).Sum;canonical_preserved=$true;recursive_delete_used=$false;viewer_ports_3245_3246_inactive_at_preflight=$true;files=$deleted} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $auditPath 'LARGE_DUPLICATE_CLEANUP_EXECUTED.json') -Encoding UTF8
}
[ordered]@{deleted_files=$deleted.Count;deleted_bytes=($deleted | Measure-Object -Property bytes -Sum).Sum} | ConvertTo-Json
