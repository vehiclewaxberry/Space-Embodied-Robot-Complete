param([switch]$Execute)
$ErrorActionPreference = 'Stop'
$auditDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspaceDirectory = [System.IO.Path]::GetFullPath((Join-Path $auditDirectory '..\..\..'))
$workspacePrefix = $workspaceDirectory.TrimEnd('\') + '\'
$review = Get-Content -LiteralPath (Join-Path $auditDirectory 'CLEANUP_CANDIDATES.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$checked = @()
foreach ($candidate in $review.candidates) {
    if ($candidate.recommendation -ne 'DELETE_CANDIDATE') { throw 'Unapproved candidate' }
    $absolute = [System.IO.Path]::GetFullPath((Join-Path $workspaceDirectory $candidate.path))
    if (-not $absolute.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Target outside workspace' }
    $relative = $candidate.path.Replace('\','/')
    $installer = $relative -eq '70_tools/runtime_wp09_kicad/kicad-10.0.6-x86_64.exe'
    $cache = $relative.StartsWith('20_engineering/SERVICE_STAR_') -and ($relative.Contains('/__pycache__/') -or $relative.Contains('/_generated_com/'))
    if (-not ($installer -or $cache)) { throw "Unexpected deletion scope: $relative" }
    $item = Get-Item -LiteralPath $absolute -Force
    if ($item.PSIsContainer) { throw 'Directories are not deletion targets' }
    $walk = $item
    while ($walk -and $walk.FullName.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        if (($walk.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse point not allowed' }
        if ($walk.PSIsContainer) { $walk = $walk.Parent } else { $walk = $walk.Directory }
    }
    $hash = (Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $candidate.sha256 -or $item.Length -ne $candidate.bytes) { throw "Candidate changed: $relative" }
    $regenerationSource = [System.IO.Path]::GetFullPath((Join-Path $workspaceDirectory $candidate.source_path))
    if (-not $regenerationSource.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Source outside workspace' }
    $sourceHash = (Get-FileHash -LiteralPath $regenerationSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceHash -ne $candidate.source_sha256) { throw "Regeneration evidence changed: $relative" }
    foreach ($property in $candidate.current_reference_checks.PSObject.Properties) {
        if ($property.Value) { throw 'Current dependency found' }
    }
    if ($candidate.mechanical_manifest_reference_paths.Count -ne 0) { throw 'Protected manifest reference found' }
    $checked += [pscustomobject]@{ path=$relative; absolute=$absolute; bytes=$item.Length; sha256=$hash; tracked=$candidate.tracked; kind=$candidate.kind; restoration=$candidate.regenerate_reason; source=$candidate.source_path }
}
if ($checked.Count -ne 30) { throw 'Expected exactly 30 independently reviewed files' }
$runtime = Join-Path $workspaceDirectory '70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) { throw 'Retained KiCad executable missing' }

$protectedPaths = @(
    '20_engineering/SERVICE_STAR_CORE_INSTALLATION_LATEST.json',
    '20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json',
    '20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM',
    '20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/SOURCE_DEPENDENCIES_SHA256.csv',
    '20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/PACKAGE_SHA256.csv',
    '20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920/PACKAGE_SHA256.csv'
)
$before = @{}
foreach ($path in $protectedPaths) { $before[$path] = (Get-FileHash -LiteralPath (Join-Path $workspaceDirectory $path) -Algorithm SHA256).Hash }
$records = @()
foreach ($row in $checked) {
    if ($Execute) {
        # Exact literal file, no wildcard, recursive delete or shell handoff.
        Remove-Item -LiteralPath $row.absolute -Force
        if (Test-Path -LiteralPath $row.absolute) { throw 'Deletion did not complete' }
    }
    $records += [ordered]@{ path=$row.path; bytes=$row.bytes; sha256=$row.sha256; tracked=$row.tracked; kind=$row.kind; source=$row.source; restoration=$row.restoration; deleted=[bool]$Execute }
}
$checks = @()
foreach ($path in $protectedPaths) {
    $after = (Get-FileHash -LiteralPath (Join-Path $workspaceDirectory $path) -Algorithm SHA256).Hash
    $checks += [ordered]@{ path=$path; sha256_before=$before[$path].ToLowerInvariant(); sha256_after=$after.ToLowerInvariant(); unchanged=($before[$path] -eq $after) }
    if ($before[$path] -ne $after) { throw 'Protected design changed during cleanup' }
}
$receipt = [ordered]@{
    schema='HARDWARE_EXACT_FILE_CLEANUP_V1'; generated_utc=[DateTime]::UtcNow.ToString('o'); executed=[bool]$Execute
    files=$records; file_count=$records.Count; bytes=($checked | Measure-Object -Property bytes -Sum).Sum
    protected_design_checks=$checks; portable_kicad_retained=(Test-Path -LiteralPath $runtime -PathType Leaf)
    recursive_deletion_used=$false; git_history_modified=$false; research_control_directories_modified=$false
    warning='Working-copy cleanup only; tracked installer remains in original Git history. No CAD/source/gate deleted.'
}
$outputName = if ($Execute) {'CLEANUP_EXECUTION.json'} else {'CLEANUP_PREFLIGHT.json'}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $auditDirectory $outputName) -Encoding UTF8
[ordered]@{executed=[bool]$Execute; files=$records.Count; bytes=$receipt.bytes; protected_checks=$checks.Count; receipt=$outputName} | ConvertTo-Json -Compress
