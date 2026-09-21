[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$base = $PSScriptRoot
$interopPath = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$librarySource = Join-Path $base 'B51R1_InsertCoordinateSystemSingleDiagnostic.cs'
$runnerSource = Join-Path $base 'B51R1_InsertCoordinateSystemDiagnosticRunner.cs'
$libraryPath = Join-Path $base 'B51R1_InsertCoordinateSystemSingleDiagnostic.dll'
$runnerPath = Join-Path $base 'B51R1_InsertCoordinateSystemDiagnosticRunner.exe'
$reportPath = Join-Path $base 'B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_OFFLINE_VERIFICATION.json'

foreach ($requiredPath in @(
    $interopPath,
    $librarySource,
    $runnerSource,
    $libraryPath,
    $runnerPath
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file missing: $requiredPath"
    }
}

function Get-Sha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Get-MethodSignature([Reflection.MethodInfo]$Method) {
    $parameters = @(
        $Method.GetParameters() | ForEach-Object {
            $parameterType = $_.ParameterType
            $prefix = ''
            if ($parameterType.IsByRef) {
                $prefix = 'ref '
                $parameterType = $parameterType.GetElementType()
            }
            "$prefix$($parameterType.FullName) $($_.Name)"
        }
    )
    "$($Method.ReturnType.FullName) $($Method.DeclaringType.FullName).$($Method.Name)($($parameters -join ', '))"
}

$interop = [Reflection.Assembly]::LoadFrom($interopPath)
$interopVersion = $interop.GetName().Version.ToString()
$interopFileVersion =
    [Diagnostics.FileVersionInfo]::GetVersionInfo($interopPath).FileVersion

$featureManagerType =
    $interop.GetType('SolidWorks.Interop.sldworks.IFeatureManager', $true)
$insertMethod = @(
    $featureManagerType.GetMethods() |
        Where-Object { $_.Name -eq 'InsertCoordinateSystem' }
)
if ($insertMethod.Count -ne 1) {
    throw "Expected one IFeatureManager.InsertCoordinateSystem overload"
}
$insertMethod = $insertMethod[0]

$selectionManagerType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISelectionMgr', $true)
$createSelectData = @(
    $selectionManagerType.GetMethods() |
        Where-Object { $_.Name -eq 'CreateSelectData' }
)
if ($createSelectData.Count -ne 1) {
    throw "Expected one ISelectionMgr.CreateSelectData overload"
}
$createSelectData = $createSelectData[0]

$selectDataType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISelectData', $true)
$markProperty = $selectDataType.GetProperty('Mark')

$sketchPointType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISketchPoint', $true)
$pointSelect4 = @(
    $sketchPointType.GetMethods() |
        Where-Object { $_.Name -eq 'Select4' }
)
if ($pointSelect4.Count -ne 1) {
    throw "Expected one ISketchPoint.Select4 overload"
}
$pointSelect4 = $pointSelect4[0]

$sketchSegmentType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISketchSegment', $true)
$segmentSelect4 = @(
    $sketchSegmentType.GetMethods() |
        Where-Object { $_.Name -eq 'Select4' }
)
if ($segmentSelect4.Count -ne 1) {
    throw "Expected one ISketchSegment.Select4 overload"
}
$segmentSelect4 = $segmentSelect4[0]

$modelDocType =
    $interop.GetType('SolidWorks.Interop.sldworks.IModelDoc2', $true)
$save3 = @(
    $modelDocType.GetMethods() |
        Where-Object { $_.Name -eq 'Save3' }
)
if ($save3.Count -ne 1) {
    throw "Expected one IModelDoc2.Save3 overload"
}
$save3 = $save3[0]

$sldWorksType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISldWorks', $true)
$getProcessId = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'GetProcessID' }
)
if ($getProcessId.Count -ne 1) {
    throw "Expected one ISldWorks.GetProcessID overload"
}
$getProcessId = $getProcessId[0]

$signatureChecks = [ordered]@{
    interop_assembly_version_is_32_5_0_48 =
        ($interopVersion -eq '32.5.0.48')
    interop_file_version_is_32_5_0_48 =
        ($interopFileVersion -eq '32.5.0.48')
    insert_returns_feature =
        ($insertMethod.ReturnType.FullName -eq 'SolidWorks.Interop.sldworks.Feature')
    insert_has_three_boolean_parameters =
        (($insertMethod.GetParameters().Count -eq 3) -and
         (@($insertMethod.GetParameters() |
            Where-Object { $_.ParameterType -eq [bool] }).Count -eq 3))
    create_select_data_returns_select_data =
        ($createSelectData.ReturnType.FullName -eq
            'SolidWorks.Interop.sldworks.SelectData')
    mark_is_read_write_int32 =
        (($null -ne $markProperty) -and
         $markProperty.CanRead -and
         $markProperty.CanWrite -and
         ($markProperty.PropertyType -eq [int]))
    sketch_point_select4_signature =
        (($pointSelect4.ReturnType -eq [bool]) -and
         ($pointSelect4.GetParameters().Count -eq 2) -and
         ($pointSelect4.GetParameters()[0].ParameterType -eq [bool]) -and
         ($pointSelect4.GetParameters()[1].ParameterType.FullName -eq
            'SolidWorks.Interop.sldworks.SelectData'))
    sketch_segment_select4_signature =
        (($segmentSelect4.ReturnType -eq [bool]) -and
         ($segmentSelect4.GetParameters().Count -eq 2) -and
         ($segmentSelect4.GetParameters()[0].ParameterType -eq [bool]) -and
         ($segmentSelect4.GetParameters()[1].ParameterType.FullName -eq
            'SolidWorks.Interop.sldworks.SelectData'))
    save3_returns_boolean =
        (($save3.ReturnType -eq [bool]) -and
         ($save3.GetParameters().Count -eq 3))
    get_process_id_returns_int32 =
        (($getProcessId.ReturnType -eq [int]) -and
         ($getProcessId.GetParameters().Count -eq 0))
}

$libraryText = Get-Content -LiteralPath $librarySource -Raw -Encoding UTF8
$runnerText = Get-Content -LiteralPath $runnerSource -Raw -Encoding UTF8
$combinedToolText = "$libraryText`n$runnerText"

$forbiddenPatterns = [ordered]@{
    process_start = 'Process\s*\.\s*Start\s*\('
    activator_create_instance = 'Activator\s*\.\s*CreateInstance'
    sldworks_constructor = 'new\s+SldWorks\s*\('
    progid_activation = 'Type\s*\.\s*GetTypeFromProgID'
    solidworks_exit = '\.\s*ExitApp\s*\('
    protected_or_evidence_delete = 'File\s*\.\s*Delete\s*\('
}
$forbiddenHits = [ordered]@{}
foreach ($entry in $forbiddenPatterns.GetEnumerator()) {
    $forbiddenHits[$entry.Key] =
        [bool]([regex]::IsMatch(
            $combinedToolText,
            $entry.Value,
            [Text.RegularExpressions.RegexOptions]::IgnoreCase))
}

$requiredSourceTokens = [ordered]@{
    exactly_one_process = 'Process.GetProcessesByName("SLDWORKS")'
    process_responding = 'solidWorksProcess.Responding'
    visible_window = 'solidWorksProcess.MainWindowHandle != IntPtr.Zero'
    rot_attach_only = 'Marshal.GetActiveObject("SldWorks.Application")'
    attached_pid_match = 'swApp.GetProcessID()'
    empty_session_before = 'swApp.GetDocumentCount() == 0'
    disposable_copy = 'File.Copy(source, disposable, false)'
    protected_name_lock = 'ExpectedStageAFileName'
    no_direct_source_open = 'OPEN_DISPOSABLE_COPY_ONLY'
    origin_mark_1 = '((ISelectData)data).Mark = 1'
    x_axis_mark_2 = '((ISelectData)data).Mark = 2'
    y_axis_mark_4 = '((ISelectData)data).Mark = 4'
    insert_coordinate_system =
        'model.FeatureManager.InsertCoordinateSystem('
    save3 = 'model.Save3('
    close_before_hash = 'CLOSE_DISPOSABLE_COPY_BEFORE_HASH'
    hash_after_close = 'HASH_DISPOSABLE_COPY_AFTER_CLOSE'
    protected_hash_after = 'HASH_PROTECTED_STAGE_A_AFTER'
    authorization_token = '--authorized-attach-only'
    sta_worker = 'worker.SetApartmentState(ApartmentState.STA)'
    watchdog_timeout = 'WatchdogTimeoutMilliseconds = 120000'
    watchdog_self_termination = 'System.Environment.Exit(124)'
    watchdog_does_not_terminate_solidworks =
        '\"solidworks_process_termination_permitted\":false'
}
$requiredTokenChecks = [ordered]@{}
foreach ($entry in $requiredSourceTokens.GetEnumerator()) {
    $requiredTokenChecks[$entry.Key] =
        $combinedToolText.Contains([string]$entry.Value)
}

$orderedProgressLabels = @(
    'OPEN_3D_SKETCH',
    'CREATE_ORIGIN_POINT',
    'CREATE_X_AXIS_LINE',
    'CREATE_Y_AXIS_LINE',
    'CLOSE_3D_SKETCH',
    'SELECT_ORIGIN_MARK_1',
    'SELECT_X_AXIS_MARK_2',
    'SELECT_Y_AXIS_MARK_4',
    'CALL_FEATUREMANAGER_INSERT_COORDINATE_SYSTEM',
    'SAVE_DISPOSABLE_COPY_IN_PLACE',
    'CLOSE_DISPOSABLE_COPY_BEFORE_HASH',
    'HASH_DISPOSABLE_COPY_AFTER_CLOSE',
    'HASH_PROTECTED_STAGE_A_AFTER',
    'VERIFY_PROTECTED_STAGE_A_UNCHANGED'
)
$orderedIndices = @()
$searchFrom = 0
$orderedLabelsPass = $true
foreach ($label in $orderedProgressLabels) {
    $index = $libraryText.IndexOf(
        '"' + $label + '"',
        $searchFrom,
        [StringComparison]::Ordinal)
    $orderedIndices += $index
    if ($index -lt $searchFrom) {
        $orderedLabelsPass = $false
        break
    }
    $searchFrom = $index + $label.Length + 2
}

$compiledLibrary = [Reflection.Assembly]::LoadFrom($libraryPath)
$diagnosticType =
    $compiledLibrary.GetType(
        'B51R1.NativeCadDiagnostics.InsertCoordinateSystemSingleDiagnostic',
        $true)
$runMethod = $diagnosticType.GetMethod(
    'Run',
    [Reflection.BindingFlags]::Public -bor
    [Reflection.BindingFlags]::Static)
$compiledRunner = [Reflection.Assembly]::LoadFrom($runnerPath)
$runnerEntryPoint = $compiledRunner.EntryPoint

$compiledChecks = [ordered]@{
    library_run_returns_int32 =
        (($null -ne $runMethod) -and ($runMethod.ReturnType -eq [int]))
    library_run_has_four_string_parameters =
        (($null -ne $runMethod) -and
         ($runMethod.GetParameters().Count -eq 4) -and
         (@($runMethod.GetParameters() |
            Where-Object { $_.ParameterType -eq [string] }).Count -eq 4))
    runner_has_entry_point = ($null -ne $runnerEntryPoint)
    runner_entry_point_returns_int32 =
        (($null -ne $runnerEntryPoint) -and
         ($runnerEntryPoint.ReturnType -eq [int]))
}

$allSignatureChecksPass =
    (@($signatureChecks.Values | Where-Object { -not $_ }).Count -eq 0)
$allRequiredTokensPresent =
    (@($requiredTokenChecks.Values | Where-Object { -not $_ }).Count -eq 0)
$noForbiddenCalls =
    (@($forbiddenHits.Values | Where-Object { $_ }).Count -eq 0)
$allCompiledChecksPass =
    (@($compiledChecks.Values | Where-Object { -not $_ }).Count -eq 0)
$allChecksPass =
    $allSignatureChecksPass -and
    $allRequiredTokensPresent -and
    $noForbiddenCalls -and
    $orderedLabelsPass -and
    $allCompiledChecksPass

$solidWorksProcessCountAtOfflineVerification =
    @(Get-Process -Name 'SLDWORKS' -ErrorAction SilentlyContinue).Count

$report = [ordered]@{
    schema =
        'SER_B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_OFFLINE_VERIFICATION_V1'
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    status = if ($allChecksPass) {
        'PASS_OFFLINE_COMPILE_REFLECTION_AND_STATIC_ATTACH_ONLY_CHECKS'
    }
    else {
        'FAIL_OFFLINE_VERIFICATION'
    }
    runtime_diagnostic_status =
        'NOT_RUN_REQUIRES_FRESH_EXPLICIT_VISIBLE_LAUNCH_AUTHORIZATION'
    solidworks_runtime_operations_executed = $false
    solidworks_process_count_observed_read_only =
        $solidWorksProcessCountAtOfflineVerification
    interop = [ordered]@{
        path = $interopPath
        bytes = (Get-Item -LiteralPath $interopPath).Length
        sha256 = Get-Sha256 $interopPath
        assembly_version = $interopVersion
        file_version = $interopFileVersion
    }
    reflected_signatures = @(
        Get-MethodSignature $insertMethod
        Get-MethodSignature $createSelectData
        'System.Int32 SolidWorks.Interop.sldworks.ISelectData.Mark { get; set; }'
        Get-MethodSignature $pointSelect4
        Get-MethodSignature $segmentSelect4
        Get-MethodSignature $save3
        Get-MethodSignature $getProcessId
    )
    signature_checks = $signatureChecks
    required_source_token_checks = $requiredTokenChecks
    forbidden_launch_or_destructive_call_hits = $forbiddenHits
    ordered_progress_labels = $orderedProgressLabels
    ordered_progress_label_indices = $orderedIndices
    ordered_progress_labels_pass = $orderedLabelsPass
    compiled_api_checks = $compiledChecks
    all_checks_pass = $allChecksPass
    artifacts = @(
        [ordered]@{
            path = $librarySource
            bytes = (Get-Item -LiteralPath $librarySource).Length
            sha256 = Get-Sha256 $librarySource
        }
        [ordered]@{
            path = $runnerSource
            bytes = (Get-Item -LiteralPath $runnerSource).Length
            sha256 = Get-Sha256 $runnerSource
        }
        [ordered]@{
            path = $libraryPath
            bytes = (Get-Item -LiteralPath $libraryPath).Length
            sha256 = Get-Sha256 $libraryPath
        }
        [ordered]@{
            path = $runnerPath
            bytes = (Get-Item -LiteralPath $runnerPath).Length
            sha256 = Get-Sha256 $runnerPath
        }
    )
    claim_limit =
        'OFFLINE_TOOLCHAIN_READINESS_ONLY_NO_SOLIDWORKS_ATTACH_OR_CAD_EXECUTION_NO_MASTER_SKELETON_GATE_H10_T005_LOAD_PATH_MANUFACTURING_OR_FLIGHT_CREDIT'
}

$json = $report | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText(
    $reportPath,
    $json + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))

if (-not $allChecksPass) {
    throw "Offline diagnostic verification failed; see $reportPath"
}

Write-Output $reportPath
