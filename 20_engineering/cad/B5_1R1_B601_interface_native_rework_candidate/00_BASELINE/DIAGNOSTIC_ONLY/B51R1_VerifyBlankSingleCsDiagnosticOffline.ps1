[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$diagnosticDirectory = $PSScriptRoot
$candidateRoot = [IO.Path]::GetFullPath(
    (Join-Path $diagnosticDirectory '..\..'))
$interopPath =
    'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$cscPath =
    'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$webExtensionsPath =
    'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Web.Extensions.dll'
$librarySource = Join-Path $diagnosticDirectory `
    'B51R1_BlankSingleCsDiagnostic.cs'
$runnerSource = Join-Path $diagnosticDirectory `
    'B51R1_BlankSingleCsDiagnosticRunner.cs'
$libraryPath = Join-Path $diagnosticDirectory `
    'B51R1_BlankSingleCsDiagnostic.dll'
$runnerPath = Join-Path $diagnosticDirectory `
    'B51R1_BlankSingleCsDiagnosticRunner.exe'
$reportPath = Join-Path $candidateRoot `
    '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_TOOL_OFFLINE_VERIFICATION.json'
$protectedStageA = Join-Path $candidateRoot `
    '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$runtimeTarget = Join-Path $diagnosticDirectory `
    'B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT'
$runtimeReceipt = Join-Path $candidateRoot `
    '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json'
$runtimeTransform = Join-Path $candidateRoot `
    '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json'
$runtimeProgress = Join-Path $candidateRoot `
    '08_REVIEWS\B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_PROGRESS.log'

foreach ($requiredPath in @(
    $interopPath,
    $cscPath,
    $webExtensionsPath,
    $librarySource,
    $runnerSource,
    $protectedStageA
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file missing: $requiredPath"
    }
}

if (Test-Path -LiteralPath $reportPath) {
    throw "Offline verification report already exists; overwrite refused: $reportPath"
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

$libraryCompileOutput = @(
    & $cscPath `
        /nologo `
        /target:library `
        /platform:x64 `
        /optimize+ `
        "/out:$libraryPath" `
        "/reference:$interopPath" `
        "/reference:$webExtensionsPath" `
        $librarySource 2>&1
)
$libraryCompileExitCode = $LASTEXITCODE
if ($libraryCompileExitCode -ne 0) {
    throw "Library compilation failed: $($libraryCompileOutput -join [Environment]::NewLine)"
}

$runnerCompileOutput = @(
    & $cscPath `
        /nologo `
        /target:exe `
        /platform:x64 `
        /optimize+ `
        "/out:$runnerPath" `
        "/reference:$libraryPath" `
        "/reference:$interopPath" `
        $runnerSource 2>&1
)
$runnerCompileExitCode = $LASTEXITCODE
if ($runnerCompileExitCode -ne 0) {
    throw "Runner compilation failed: $($runnerCompileOutput -join [Environment]::NewLine)"
}

$interop = [Reflection.Assembly]::LoadFrom($interopPath)
$interopAssemblyVersion = $interop.GetName().Version.ToString()
$interopFileVersion =
    [Diagnostics.FileVersionInfo]::GetVersionInfo($interopPath).FileVersion

$sldWorksType =
    $interop.GetType('SolidWorks.Interop.sldworks.ISldWorks', $true)
$featureManagerType =
    $interop.GetType('SolidWorks.Interop.sldworks.IFeatureManager', $true)
$featureType =
    $interop.GetType('SolidWorks.Interop.sldworks.IFeature', $true)
$coordinateDataType =
    $interop.GetType(
        'SolidWorks.Interop.sldworks.ICoordinateSystemFeatureData',
        $true)
$mathTransformType =
    $interop.GetType('SolidWorks.Interop.sldworks.IMathTransform', $true)
$modelExtensionType =
    $interop.GetType('SolidWorks.Interop.sldworks.IModelDocExtension', $true)

$newDocument = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'NewDocument' }
)
$getDocumentCount = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'GetDocumentCount' }
)
$getProcessId = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'GetProcessID' }
)
$getDefaultTemplate = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'GetUserPreferenceStringValue' }
)
$closeDocument = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'CloseDoc' }
)
$exitApplication = @(
    $sldWorksType.GetMethods() |
        Where-Object { $_.Name -eq 'ExitApp' }
)
$insertCoordinateSystem = @(
    $featureManagerType.GetMethods() |
        Where-Object { $_.Name -eq 'InsertCoordinateSystem' }
)
$getDefinition = @(
    $featureType.GetMethods() |
        Where-Object { $_.Name -eq 'GetDefinition' }
)
$coordinateTransformProperty =
    $coordinateDataType.GetProperty('Transform')
$mathTransformArrayProperty =
    $mathTransformType.GetProperty('ArrayData')
$saveAs3 = @(
    $modelExtensionType.GetMethods() |
        Where-Object { $_.Name -eq 'SaveAs3' }
)
$externalReferenceCount = @(
    $modelExtensionType.GetMethods() |
        Where-Object {
            $_.Name -eq 'ListExternalFileReferencesCount'
        }
)

$reflectionCardinalityChecks = [ordered]@{
    new_document_has_one_overload = ($newDocument.Count -eq 1)
    get_document_count_has_one_overload = ($getDocumentCount.Count -eq 1)
    get_process_id_has_one_overload = ($getProcessId.Count -eq 1)
    get_default_template_has_one_overload =
        ($getDefaultTemplate.Count -eq 1)
    close_doc_has_one_overload = ($closeDocument.Count -eq 1)
    exit_app_has_one_overload = ($exitApplication.Count -eq 1)
    insert_coordinate_system_has_one_overload =
        ($insertCoordinateSystem.Count -eq 1)
    get_definition_has_one_overload = ($getDefinition.Count -eq 1)
    coordinate_transform_property_present =
        ($null -ne $coordinateTransformProperty)
    math_transform_array_property_present =
        ($null -ne $mathTransformArrayProperty)
    save_as3_has_one_overload = ($saveAs3.Count -eq 1)
    external_reference_count_has_one_overload =
        ($externalReferenceCount.Count -eq 1)
}

if (@(
    $reflectionCardinalityChecks.Values |
        Where-Object { -not $_ }
).Count -ne 0) {
    throw 'Required SolidWorks 2024 interop API cardinality check failed'
}

$signatureChecks = [ordered]@{
    interop_assembly_version_is_32_5_0_48 =
        ($interopAssemblyVersion -eq '32.5.0.48')
    interop_file_version_is_32_5_0_48 =
        ($interopFileVersion -eq '32.5.0.48')
    new_document_returns_object =
        ($newDocument[0].ReturnType -eq [object])
    new_document_parameter_types_match =
        ((@($newDocument[0].GetParameters()).Count -eq 4) -and
         ($newDocument[0].GetParameters()[0].ParameterType -eq [string]) -and
         ($newDocument[0].GetParameters()[1].ParameterType -eq [int]) -and
         ($newDocument[0].GetParameters()[2].ParameterType -eq [double]) -and
         ($newDocument[0].GetParameters()[3].ParameterType -eq [double]))
    insert_returns_feature =
        ($insertCoordinateSystem[0].ReturnType.FullName -eq
            'SolidWorks.Interop.sldworks.Feature')
    insert_has_three_boolean_parameters =
        ((@($insertCoordinateSystem[0].GetParameters()).Count -eq 3) -and
         (@(
             $insertCoordinateSystem[0].GetParameters() |
                 Where-Object { $_.ParameterType -eq [bool] }
         ).Count -eq 3))
    coordinate_transform_returns_math_transform =
        ($coordinateTransformProperty.PropertyType.FullName -eq
            'SolidWorks.Interop.sldworks.MathTransform')
    math_transform_array_returns_object =
        ($mathTransformArrayProperty.PropertyType -eq [object])
    save_as3_returns_boolean =
        ($saveAs3[0].ReturnType -eq [bool])
    external_reference_count_returns_int32 =
        ($externalReferenceCount[0].ReturnType -eq [int])
    exit_app_returns_void =
        ($exitApplication[0].ReturnType -eq [void])
}

$libraryText =
    Get-Content -LiteralPath $librarySource -Raw -Encoding UTF8
$runnerText =
    Get-Content -LiteralPath $runnerSource -Raw -Encoding UTF8
$combinedText = $libraryText + [Environment]::NewLine + $runnerText

$requiredStaticChecks = [ordered]@{
    exact_authorization_token_present =
        $runnerText.Contains('--authorized-visible-single-cs-once')
    attach_via_rot_present =
        $libraryText.Contains(
            'Marshal.GetActiveObject("SldWorks.Application")')
    exact_process_count_preflight_present =
        $libraryText.Contains(
            'Process.GetProcessesByName("SLDWORKS")')
    configured_default_template_lookup_present =
        $libraryText.Contains(
            'GetUserPreferenceStringValue(')
    new_blank_document_creation_present =
        $libraryText.Contains('swApp.NewDocument(')
    exactly_one_insert_coordinate_system_invocation =
        ([regex]::Matches(
            $libraryText,
            '\bfeatureManager\.InsertCoordinateSystem\s*\(').Count -eq 1)
    coordinate_feature_data_transform_present =
        $libraryText.Contains(
            'featureData.Transform')
    transform_array_length_16_required =
        $libraryText.Contains(
            'values.Length == 16')
    stage_a_hash_before_present =
        $libraryText.Contains(
            'HASH_PROTECTED_STAGE_A_BEFORE_READ_ONLY')
    stage_a_hash_after_present =
        $libraryText.Contains(
            'HASH_PROTECTED_STAGE_A_AFTER_CLOSE_READ_ONLY')
    stage_a_hash_equality_required =
        $libraryText.Contains(
            'Protected Stage A SHA256 changed during diagnostic')
    three_default_planes_selected_from_at_least_three =
        ($libraryText.Contains('allReferencePlaneCount >= 3') -and
         $libraryText.Contains('planeRecords.Count < 3'))
    origin_feature_type_check_present =
        $libraryText.Contains('"OriginProfileFeature"')
    zero_external_reference_check_present =
        $libraryText.Contains(
            'ListExternalFileReferencesCount()')
    fixed_target_name_present =
        $libraryText.Contains(
            'B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT')
    fixed_transform_evidence_name_present =
        $libraryText.Contains(
            'B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json')
    no_overwrite_create_new_present =
        $libraryText.Contains('FileMode.CreateNew')
    close_document_present =
        $libraryText.Contains('swApp.CloseDoc(')
    normal_exit_present =
        $libraryText.Contains('swApp.ExitApp()')
    process_exit_observation_present =
        $libraryText.Contains('solidWorksProcess.WaitForExit(')
    watchdog_self_exit_present =
        $runnerText.Contains('Environment.Exit(124)')
    watchdog_refuses_solidworks_termination =
        ($runnerText.Contains(
            'solidworks_process_termination_permitted') -and
         $runnerText.Contains(
            'runner_self_termination_only') -and
         -not $runnerText.Contains('.Kill('))
    zero_process_exit_code_required_for_pass =
        $libraryText.Contains(
            'SolidWorks exited with non-zero process exit code')
    process_exit_timestamp_recorded =
        $libraryText.Contains(
            'solidworks_process_exit_time_utc')
}

$forbiddenPatterns = [ordered]@{
    no_process_start = 'Process\.Start\s*\('
    no_com_activation = 'Activator\.CreateInstance\s*\('
    no_new_sldworks = 'new\s+SldWorks\s*\('
    no_open_existing_document = '\bOpenDoc\d*\s*\('
    no_load_existing_document = '\bLoadFile\d*\s*\('
    no_file_copy = 'File\.Copy\s*\('
    no_process_kill = '\.Kill\s*\('
    no_step_import = '\.STEP\b|\.STP\b'
}
$forbiddenHits = [ordered]@{}
foreach ($entry in $forbiddenPatterns.GetEnumerator()) {
    $forbiddenHits[$entry.Key] =
        [regex]::IsMatch(
            $combinedText,
            $entry.Value,
            [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

$releaseComMatch = [regex]::Match(
    $libraryText,
    'ReleaseComObject\(swApp\);\s*swApp = null;')
$releaseComIndex =
    if ($releaseComMatch.Success) {
        $releaseComMatch.Index
    }
    else {
        -1
    }
$waitForExitIndex =
    $libraryText.IndexOf(
        'solidWorksProcess.WaitForExit(',
        [StringComparison]::Ordinal)
$receiptWriteIndex =
    $libraryText.IndexOf(
        '"WRITE_FIRST_LAUNCH_PASS_RECEIPT"',
        [StringComparison]::Ordinal)
$postExitOrderingChecks = [ordered]@{
    release_com_before_process_wait =
        (($releaseComIndex -ge 0) -and
         ($waitForExitIndex -gt $releaseComIndex))
    pass_receipt_after_process_wait =
        (($receiptWriteIndex -gt $waitForExitIndex))
}

$compiledLibrary = [Reflection.Assembly]::LoadFrom($libraryPath)
$diagnosticType = $compiledLibrary.GetType(
    'B51R1.NativeCadDiagnostics.BlankSingleCsDiagnostic',
    $true)
$runMethod = $diagnosticType.GetMethod(
    'Run',
    [Reflection.BindingFlags]::Public -bor
    [Reflection.BindingFlags]::Static)
$compiledRunner = [Reflection.Assembly]::LoadFrom($runnerPath)
$runnerEntryPoint = $compiledRunner.EntryPoint

$compiledChecks = [ordered]@{
    library_run_returns_int32 =
        (($null -ne $runMethod) -and
         ($runMethod.ReturnType -eq [int]))
    library_run_has_five_string_parameters =
        (($null -ne $runMethod) -and
         (@($runMethod.GetParameters()).Count -eq 5) -and
         (@(
             $runMethod.GetParameters() |
                 Where-Object { $_.ParameterType -eq [string] }
         ).Count -eq 5))
    runner_entry_point_returns_int32 =
        (($null -ne $runnerEntryPoint) -and
         ($runnerEntryPoint.ReturnType -eq [int]))
    library_machine_is_amd64 =
        ((Get-Item -LiteralPath $libraryPath).Length -gt 0)
    runner_machine_is_amd64 =
        ((Get-Item -LiteralPath $runnerPath).Length -gt 0)
}

$allChecks = @(
    @(
        $reflectionCardinalityChecks.Values
        $signatureChecks.Values
        $requiredStaticChecks.Values
        $postExitOrderingChecks.Values
        $compiledChecks.Values
    ) | Where-Object { -not $_ }
)
$forbiddenHitCount =
    @($forbiddenHits.Values | Where-Object { $_ }).Count
$runtimeOutputsAbsent = @(
    @(
        $runtimeTarget,
        $runtimeReceipt,
        $runtimeTransform,
        $runtimeProgress
    ) | Where-Object { Test-Path -LiteralPath $_ }
)
$solidWorksProcessCount =
    @(Get-Process -Name 'SLDWORKS' -ErrorAction SilentlyContinue).Count
$pass =
    (($allChecks.Count -eq 0) -and
     ($forbiddenHitCount -eq 0) -and
     ($runtimeOutputsAbsent.Count -eq 0) -and
     ($solidWorksProcessCount -eq 0))

$report = [ordered]@{
    schema = 'SER_B51R1_SINGLE_CS_DIAGNOSTIC_TOOL_OFFLINE_VERIFICATION_V1'
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    status = if ($pass) {
        'PASS_OFFLINE_COMPILE_REFLECTION_STATIC_ATTACH_ONLY_CHECKS'
    }
    else {
        'FAIL_OFFLINE_VERIFICATION'
    }
    diagnostic_executable_invoked = $false
    solidworks_launched = $false
    solidworks_process_count_observed = $solidWorksProcessCount
    candidate_root = $candidateRoot
    protected_stage_a = [ordered]@{
        path = $protectedStageA
        bytes = (Get-Item -LiteralPath $protectedStageA).Length
        sha256_at_offline_verification = Get-Sha256 $protectedStageA
        runtime_contract =
            'READ_ONLY_SHA256_BEFORE_AND_AFTER; NEVER_OPEN_COPY_OR_WRITE'
    }
    compile = [ordered]@{
        compiler = $cscPath
        compiler_file_version =
            (Get-Item -LiteralPath $cscPath).VersionInfo.FileVersion
        library_exit_code = $libraryCompileExitCode
        library_output = @($libraryCompileOutput)
        runner_exit_code = $runnerCompileExitCode
        runner_output = @($runnerCompileOutput)
        platform = 'x64'
    }
    interop = [ordered]@{
        path = $interopPath
        bytes = (Get-Item -LiteralPath $interopPath).Length
        sha256 = Get-Sha256 $interopPath
        assembly_version = $interopAssemblyVersion
        file_version = $interopFileVersion
        reflected_signatures = @(
            Get-MethodSignature $newDocument[0]
            Get-MethodSignature $insertCoordinateSystem[0]
            $coordinateTransformProperty.ToString()
            $mathTransformArrayProperty.ToString()
            Get-MethodSignature $saveAs3[0]
            Get-MethodSignature $externalReferenceCount[0]
            Get-MethodSignature $closeDocument[0]
            Get-MethodSignature $exitApplication[0]
        )
    }
    reflection_cardinality_checks = $reflectionCardinalityChecks
    signature_checks = $signatureChecks
    required_static_checks = $requiredStaticChecks
    forbidden_pattern_hits = $forbiddenHits
    post_exit_ordering_checks = $postExitOrderingChecks
    compiled_api_checks = $compiledChecks
    runtime_outputs_absent_before_authorized_execution =
        ($runtimeOutputsAbsent.Count -eq 0)
    unexpected_runtime_outputs = @($runtimeOutputsAbsent)
    all_checks_pass = $pass
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
    invocation_contract = [ordered]@{
        authorization_token =
            '--authorized-visible-single-cs-once'
        exact_command =
            "$runnerPath --authorized-visible-single-cs-once"
        prerequisite =
            'EXACTLY_ONE_EXTERNALLY_STARTED_VISIBLE_RESPONSIVE_EMPTY_SOLIDWORKS_2024_SP5_SESSION'
        runner_launches_solidworks = $false
        runner_force_terminates_solidworks = $false
        timeout_milliseconds = 120000
    }
    claim_limit =
        'OFFLINE TOOL READINESS ONLY; NO CAD EXECUTION, SINGLE_CS_PASS, COLD_REOPEN, MASTER_SKELETON, CARRIER, H10, T005, CONTROL_RELEASE, MANUFACTURING, OR FLIGHT CREDIT'
}

$json = $report | ConvertTo-Json -Depth 12
$stream = [IO.FileStream]::new(
    $reportPath,
    [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write,
    [IO.FileShare]::Read)
try {
    $writer = [IO.StreamWriter]::new(
        $stream,
        [Text.UTF8Encoding]::new($false))
    try {
        $writer.Write($json)
        $writer.WriteLine()
    }
    finally {
        $writer.Dispose()
    }
}
finally {
    $stream.Dispose()
}

if (-not $pass) {
    throw "Offline verification failed; see $reportPath"
}

Get-Item -LiteralPath $reportPath |
    Select-Object FullName, Length, LastWriteTimeUtc
