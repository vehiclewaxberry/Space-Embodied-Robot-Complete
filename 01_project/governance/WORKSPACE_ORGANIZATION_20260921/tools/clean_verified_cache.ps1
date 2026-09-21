param([switch]$Execute)
$ErrorActionPreference='Stop'
$auditRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskRoot=[IO.Path]::GetFullPath((Join-Path $auditRoot '..\..\..'))
$prefix=$taskRoot.TrimEnd('\')+'\'
$plan=Get-Content -LiteralPath (Join-Path $auditRoot 'CACHE_CANDIDATES.json') -Raw -Encoding utf8 | ConvertFrom-Json
$rows=@($plan.candidates | Where-Object recommendation -eq 'DELETE_CANDIDATE')
if ($rows.Count -ne 267) { throw 'Unexpected approved set' }
function Checked-Path([string]$relative) {
    $full=[IO.Path]::GetFullPath((Join-Path $taskRoot $relative))
    if (-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Outside workspace' }
    $item=Get-Item -LiteralPath $full -Force
    $walk=$item
    while($walk -and $walk.FullName.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) {
        if (($walk.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse point not permitted' }
        if($walk.PSIsContainer){$walk=$walk.Parent}else{$walk=$walk.Directory}
    }
    return $full
}
$verified=@()
foreach($r in $rows){
    if($r.tracked -or $r.references.Count -ne 0){throw 'Referenced or tracked cache'}
    $rel=$r.path.Replace('\','/')
    if($rel -notmatch '^(01_project|10_research|20_engineering|30_simulation|40_evidence|50_literature|70_tools|80_third_party)/'){throw 'Wrong domain'}
    if($rel.Contains('/.git/') -or $rel.Contains('/SERVICE_STAR_HARDWARE_COMPACT_20260921/')){throw 'Protected scope'}
    $shape=($r.kind -eq 'PYTHON_BYTECODE' -and $rel.Contains('/__pycache__/') -and $rel.EndsWith('.pyc')) -or ($r.kind -eq 'STANDARD_PYTEST_CACHE' -and $rel.Contains('/.pytest_cache/v/cache/'))
    if(-not $shape){throw 'Unexpected file class'}
    $full=Checked-Path $r.path
    $item=Get-Item -LiteralPath $full
    if($item.PSIsContainer -or $item.Length -ne $r.bytes){throw 'Size/type mismatch'}
    $hash=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
    if($hash -ne $r.sha256){throw "Cache changed: $rel"}
    $source=Checked-Path $r.source
    $sourceHash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if($sourceHash -ne $r.source_sha256){throw "Regeneration source changed: $rel"}
    $verified+=[pscustomobject]@{path=$rel; full=$full; bytes=$r.bytes; sha256=$hash; source=$r.source; source_sha256=$sourceHash; kind=$r.kind}
}
$records=@()
foreach($r in $verified){
    if($Execute){
        Remove-Item -LiteralPath $r.full -Force
        if(Test-Path -LiteralPath $r.full){throw 'Deletion incomplete'}
    }
    $records+=[ordered]@{path=$r.path;bytes=$r.bytes;sha256=$r.sha256;source=$r.source;source_sha256=$r.source_sha256;kind=$r.kind;deleted=[bool]$Execute}
}
$receipt=[ordered]@{schema='WHOLE_WORKSPACE_EXACT_CACHE_CLEANUP_V1';generated_utc=[DateTime]::UtcNow.ToString('o');executed=[bool]$Execute;file_count=$records.Count;bytes=($verified|Measure-Object bytes -Sum).Sum;records=$records;recursive_delete_used=$false;git_history_modified=$false;source_design_or_gate_deleted=$false}
$name=if($Execute){'CACHE_CLEANUP_EXECUTED.json'}else{'CACHE_CLEANUP_PREFLIGHT.json'}
$receipt|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $auditRoot $name) -Encoding utf8
[ordered]@{executed=[bool]$Execute;files=$records.Count;bytes=$receipt.bytes;receipt=$name}|ConvertTo-Json -Compress
