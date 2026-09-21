param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$JournalPath
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$repoPrefix = $repo + '\'
$journal = New-Object System.Collections.ArrayList
$supplementDirectory = -join @([char]0x8865, [char]0x5145, [char]0x8BBA, [char]0x6587)
$rootDocName = (-join @([char]0x7A7A, [char]0x95F4, [char]0x673A, [char]0x68B0, [char]0x81C2)) + '.docx'

function Get-RepoPath([string]$RelativePath) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $repo ($RelativePath -replace '/', '\')))
    if (-not ($candidate.Equals($repo, [StringComparison]::OrdinalIgnoreCase) -or
              $candidate.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase))) {
        throw "Path escapes repository: $RelativePath -> $candidate"
    }
    return $candidate
}

function Save-Journal {
    $journal | Export-Csv -LiteralPath $JournalPath -NoTypeInformation -Encoding utf8
}

function Move-Safe([string]$SourceRelative, [string]$DestinationRelative) {
    $source = Get-RepoPath $SourceRelative
    $destination = Get-RepoPath $DestinationRelative
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Move source missing: $SourceRelative"
    }
    if (Test-Path -LiteralPath $destination) {
        throw "Move destination already exists: $DestinationRelative"
    }
    $parent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Move-Item -LiteralPath $source -Destination $destination
    [void]$journal.Add([pscustomobject]@{source=$SourceRelative;destination=$DestinationRelative})
    Save-Journal
}

function Remove-Empty([string]$RelativePath) {
    $path = Get-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path)) { return }
    if (@(Get-ChildItem -LiteralPath $path -Force).Count -ne 0) {
        throw "Directory is not empty: $RelativePath"
    }
    Remove-Item -LiteralPath $path
}

function Rollback-Moves {
    for ($index = $journal.Count - 1; $index -ge 0; $index--) {
        $entry = $journal[$index]
        $source = Get-RepoPath $entry.source
        $destination = Get-RepoPath $entry.destination
        if (-not (Test-Path -LiteralPath $destination)) { continue }
        if (Test-Path -LiteralPath $source) {
            throw "Rollback source already exists: $($entry.source)"
        }
        $parent = Split-Path -Parent $source
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Move-Item -LiteralPath $destination -Destination $source
    }
}

try {
    Move-Safe 'tools' '70_tools'
    Move-Safe 'research' '10_research'
    Move-Safe 'sim' '30_simulation'
    Move-Safe 'artifacts' '40_evidence/artifacts'
    Move-Safe 'cad' '20_engineering/cad'
    Move-Safe 'config' '20_engineering/config'

    Move-Safe 'docs/00_project_governance' '01_project/governance'
    Move-Safe 'docs/90_competition' '01_project/competition'
    Move-Safe 'docs/95_inbox' '01_project/inbox'
    Move-Safe 'docs/00_references' '50_literature/references'
    Move-Safe 'docs/20_system_design' '20_engineering/system_design'
    Move-Safe 'docs/stage1_spacecraft_layout' '20_engineering/stage1_spacecraft_layout'

    Move-Safe 'pdf' '50_literature/pdf'
    Move-Safe 'external' '80_third_party/external'
    Move-Safe 'vendor' '80_third_party/vendor'
    Move-Safe 'knowledge_base' '10_research/knowledge_base'

    Move-Safe 'e15_core_coverage' '30_simulation/e15_core_coverage'
    Move-Safe 'e15_ancf_certification' '30_simulation/e15_ancf_certification'
    Move-Safe 'e16_sync_capture' '30_simulation/e16_sync_capture'

    Move-Safe '30_simulation/asm_00_interface_preflight/README.md' '30_simulation/asm_00_interface_preflight/MIGRATION_NOTICE.md'
    $assemblySource = Get-RepoPath 'assembly_research/ASM-00_interface_ssot'
    foreach ($item in @(Get-ChildItem -LiteralPath $assemblySource -Force | Sort-Object Name)) {
        Move-Safe ("assembly_research/ASM-00_interface_ssot/" + $item.Name) ("30_simulation/asm_00_interface_preflight/" + $item.Name)
    }

    Move-Safe 'src/sim_09_grasp_evaluator' '30_simulation/sim_09_grasp_evaluator/src'
    Move-Safe 'tests/sim_09_grasp_evaluator' '30_simulation/sim_09_grasp_evaluator/tests'
    Move-Safe 'results/sim_09_grasp_evaluator' '30_simulation/sim_09_grasp_evaluator/results'
    Move-Safe 'figures/sim_09_grasp_evaluator' '30_simulation/sim_09_grasp_evaluator/figures'
    Move-Safe 'tables/sim_09_grasp_evaluator' '30_simulation/sim_09_grasp_evaluator/tables'

    Move-Safe 'src/visualization' '70_tools/project_visualization/src'
    Move-Safe 'tests/visualization' '70_tools/project_visualization/tests'
    Move-Safe 'figures/visualization' '40_evidence/artifacts/visualization/figures'
    Move-Safe 'tables/visualization' '40_evidence/artifacts/visualization/tables'
    Move-Safe 'videos/visualization' '40_evidence/artifacts/visualization/videos'

    foreach ($item in @(Get-ChildItem -LiteralPath (Get-RepoPath 'tables') -File | Sort-Object Name)) {
        Move-Safe ("tables/" + $item.Name) ("40_evidence/tables/" + $item.Name)
    }

    Move-Safe ($supplementDirectory + '/README.md') '50_literature/legacy_supplemental/README.md'
    Move-Safe $rootDocName ('01_project/inbox/source_documents/' + $rootDocName)

    foreach ($empty in @(
        'assembly_research/ASM-00_interface_ssot','assembly_research',
        'src','tests','results','figures','tables','videos',$supplementDirectory,'docs'
    )) {
        Remove-Empty $empty
    }

    Save-Journal
    Write-Output "REORG04_MOVE_COMPLETE moves=$($journal.Count)"
}
catch {
    $failure = $_
    try { Rollback-Moves } catch { Write-Error "Rollback failure: $($_.Exception.Message)" }
    throw "REORG04_MOVE_FAILED_AND_ROLLED_BACK: $($failure.Exception.Message)"
}
