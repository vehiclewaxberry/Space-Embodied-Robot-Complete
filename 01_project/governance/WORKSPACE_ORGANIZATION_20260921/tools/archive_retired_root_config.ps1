$ErrorActionPreference='Stop'
$auditRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskRoot=[IO.Path]::GetFullPath((Join-Path $auditRoot '..\..\..'))
$prefix=$taskRoot.TrimEnd('\')+'\'
$archiveRoot=[IO.Path]::GetFullPath((Join-Path $auditRoot 'local_private/root_config_archive'))
$source=[IO.Path]::GetFullPath((Join-Path $taskRoot '.mcp.json.retired-20260911-superseded-by-user-scope'))
$target=[IO.Path]::GetFullPath((Join-Path $archiveRoot ([IO.Path]::GetFileName($source))))
foreach($path in @($source,$target,$archiveRoot)){
    if(-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Outside workspace'}
    $cursor=$path
    while($cursor -and $cursor.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){
        if(Test-Path -LiteralPath $cursor){
            $item=Get-Item -LiteralPath $cursor -Force
            if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse point not allowed'}
        }
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
}
if(Test-Path -LiteralPath $target){throw 'Archive already exists; do not overwrite'}
$item=Get-Item -LiteralPath $source -Force
if($item.PSIsContainer){throw 'Expected exact retired file'}
$hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
# Only the explicitly named retired configuration is moved. Active configurations remain untouched.
Move-Item -LiteralPath $source -Destination $target
$after=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
if($after -ne $hash -or (Test-Path -LiteralPath $source)){throw 'Archive byte verification failed'}
'*' | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $archiveRoot) '.gitignore') -Encoding utf8
$emptyRoot=[IO.Path]::GetFullPath((Join-Path $taskRoot '.playwright-cli'))
$emptyRemoved=$false
if($emptyRoot.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $emptyRoot -PathType Container)){
    $emptyItem=Get-Item -LiteralPath $emptyRoot -Force
    if(($emptyItem.Attributes -band [IO.FileAttributes]::ReparsePoint)-ne 0){throw 'Reparse empty directory'}
    if(@(Get-ChildItem -LiteralPath $emptyRoot -Force).Count -eq 0){
        Remove-Item -LiteralPath $emptyRoot -Force  # Hidden empty directory; no recursive flag.
        $emptyRemoved=-not(Test-Path -LiteralPath $emptyRoot)
    }
}
$receipt=[ordered]@{
    schema='ROOT_RETIRED_CONFIGURATION_ARCHIVE_V1';generated_utc=[DateTime]::UtcNow.ToString('o')
    moved=[ordered]@{source='.mcp.json.retired-20260911-superseded-by-user-scope';target='01_project/governance/WORKSPACE_ORGANIZATION_20260921/local_private/root_config_archive/.mcp.json.retired-20260911-superseded-by-user-scope';bytes=$item.Length;sha256_before=$hash;sha256_after=$after;byte_identical=($hash -eq $after)}
    active_configuration_modified=$false;configuration_values_disclosed=$false;git_history_modified=$false
    prior_reference_check='No exact retired filename found in inspected active .claude/.codex/.agents and tool source/config files; prior audit paths remain historical references'
    empty_playwright_directory_removed=$emptyRemoved;recursive_move_or_delete_used=$false
    recovery='Move the archived exact file back to its recorded source only if the source remains absent; it remains a retired file, not an active configuration.'
}
$receipt|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $auditRoot 'ROOT_ARCHIVE_ACTIONS.json') -Encoding utf8
[ordered]@{archived_files=1;bytes=$item.Length;byte_identical=($hash -eq $after);empty_directory_removed=$emptyRemoved}|ConvertTo-Json -Compress
