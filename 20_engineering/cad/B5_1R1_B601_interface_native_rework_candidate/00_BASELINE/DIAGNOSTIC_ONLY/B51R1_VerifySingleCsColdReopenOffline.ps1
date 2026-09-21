[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$diagnosticDirectory = $PSScriptRoot
$candidateRoot = [IO.Path]::GetFullPath(
    (Join-Path $diagnosticDirectory '..\..'))
$sldWorksInteropPath =
    'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$swConstInteropPath =
    'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.swconst.dll'
$cscPath =
    'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$webExtensionsPath =
    'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Web.Extensions.dll'
$coreSource = Join-Path $diagnosticDirectory `
    'B51R1_SingleCsColdReopen.cs'
$runnerSource = Join-Path $diagnosticDirectory `
    'B51R1_SingleCsColdReopenRunner.cs'
$corePath = Join-Path $diagnosticDirectory `
    'B51R1_SingleCsColdReopen.Core.dll'
$runnerPath = Join-Path $diagnosticDirectory `
    'B51R1_SingleCsColdReopenRunner.exe'
$reportPath = Join-Path $candidateRoot `
    '07_VERIFICATION\B51R1_SINGLE_CS_COLD_REOPEN_TOOL_OFFLINE_VERIFICATION_R2.json'
$targetPath = Join-Path $diagnosticDirectory `
    'B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT'
$stageAPath = Join-Path $candidateRoot `
    '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$runtimeOutputs = @(
    (Join-Path $candidateRoot '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_COLD_REOPEN.json'),
    (Join-Path $candidateRoot '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $candidateRoot '07_VERIFICATION\B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_FAIL_CLOSED.json'),
    (Join-Path $candidateRoot '08_REVIEWS\B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_PROGRESS.log')
)
$expectedTargetHash =
    '6B571B49D440BBDC723566FA97224C69AFABCBA6BAC34DCF4036A5F4037E120C'
$expectedStageAHash =
    '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'

foreach ($requiredPath in @(
    $sldWorksInteropPath,
    $swConstInteropPath,
    $cscPath,
    $webExtensionsPath,
    $coreSource,
    $runnerSource,
    $targetPath,
    $stageAPath
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file missing: $requiredPath"
    }
}

if (Test-Path -LiteralPath $reportPath) {
    throw "Immutable offline report already exists; overwrite refused: $reportPath"
}

foreach ($runtimeOutput in $runtimeOutputs) {
    if (Test-Path -LiteralPath $runtimeOutput) {
        throw "Runtime output already exists; cold-reopen tool must remain unrun: $runtimeOutput"
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

$solidWorksProcessCountBefore =
    @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
if ($solidWorksProcessCountBefore -ne 0) {
    throw 'Offline verification refused because a SolidWorks process is running'
}

$targetHashBefore = Get-Sha256 $targetPath
$stageAHashBefore = Get-Sha256 $stageAPath
if ($targetHashBefore -ne $expectedTargetHash) {
    throw 'Diagnostic target hash drifted before offline build'
}
if ($stageAHashBefore -ne $expectedStageAHash) {
    throw 'Protected Stage A hash drifted before offline build'
}

$coreCompileOutput = @(
    & $cscPath `
        /nologo `
        /target:library `
        /platform:x64 `
        /optimize+ `
        "/out:$corePath" `
        "/reference:$sldWorksInteropPath" `
        "/reference:$swConstInteropPath" `
        "/reference:$webExtensionsPath" `
        $coreSource 2>&1
)
$coreCompileExitCode = $LASTEXITCODE
if ($coreCompileExitCode -ne 0) {
    throw "Core compilation failed: $($coreCompileOutput -join [Environment]::NewLine)"
}

$runnerCompileOutput = @(
    & $cscPath `
        /nologo `
        /target:exe `
        /platform:x64 `
        /optimize+ `
        "/out:$runnerPath" `
        $runnerSource 2>&1
)
$runnerCompileExitCode = $LASTEXITCODE
if ($runnerCompileExitCode -ne 0) {
    throw "Runner compilation failed: $($runnerCompileOutput -join [Environment]::NewLine)"
}

$sldInterop = [Reflection.Assembly]::LoadFrom($sldWorksInteropPath)
$null = [Reflection.Assembly]::LoadFrom($swConstInteropPath)
$sldWorksType =
    $sldInterop.GetType('SolidWorks.Interop.sldworks.ISldWorks', $true)
$modelType =
    $sldInterop.GetType('SolidWorks.Interop.sldworks.IModelDoc2', $true)
$modelExtensionType =
    $sldInterop.GetType('SolidWorks.Interop.sldworks.IModelDocExtension', $true)
$coordinateDataType = $sldInterop.GetType(
    'SolidWorks.Interop.sldworks.ICoordinateSystemFeatureData',
    $true)
$mathTransformType =
    $sldInterop.GetType('SolidWorks.Interop.sldworks.IMathTransform', $true)

$openDoc6 = @($sldWorksType.GetMethods() | Where-Object Name -eq 'OpenDoc6')
$save3 = @($modelType.GetMethods() | Where-Object Name -eq 'Save3')
$closeDoc = @($sldWorksType.GetMethods() | Where-Object Name -eq 'CloseDoc')
$exitApp = @($sldWorksType.GetMethods() | Where-Object Name -eq 'ExitApp')
$externalCount = @(
    $modelExtensionType.GetMethods() |
        Where-Object Name -eq 'ListExternalFileReferencesCount'
)
$coordinateTransform = $coordinateDataType.GetProperty('Transform')
$transformArray = $mathTransformType.GetProperty('ArrayData')

$reflectionChecks = [ordered]@{
    open_doc6_has_one_overload = ($openDoc6.Count -eq 1)
    save3_has_one_overload = ($save3.Count -eq 1)
    close_doc_has_one_overload = ($closeDoc.Count -eq 1)
    exit_app_has_one_overload = ($exitApp.Count -eq 1)
    external_reference_count_has_one_overload = ($externalCount.Count -eq 1)
    coordinate_transform_property_present = ($null -ne $coordinateTransform)
    transform_array_property_present = ($null -ne $transformArray)
    open_doc6_returns_model_doc2 =
        ($openDoc6[0].ReturnType.FullName -eq 'SolidWorks.Interop.sldworks.ModelDoc2')
    open_doc6_has_six_parameters =
        (@($openDoc6[0].GetParameters()).Count -eq 6)
    open_doc6_has_two_ref_int_outputs =
        (@(
            $openDoc6[0].GetParameters() |
                Where-Object {
                    $_.ParameterType.IsByRef -and
                    $_.ParameterType.GetElementType() -eq [int]
                }
        ).Count -eq 2)
    save3_returns_boolean = ($save3[0].ReturnType -eq [bool])
    save3_has_two_ref_int_outputs =
        (@(
            $save3[0].GetParameters() |
                Where-Object {
                    $_.ParameterType.IsByRef -and
                    $_.ParameterType.GetElementType() -eq [int]
                }
        ).Count -eq 2)
    external_reference_count_returns_int32 =
        ($externalCount[0].ReturnType -eq [int])
    coordinate_transform_returns_math_transform =
        ($coordinateTransform.PropertyType.FullName -eq
            'SolidWorks.Interop.sldworks.MathTransform')
    transform_array_returns_object =
        ($transformArray.PropertyType -eq [object])
}
if (@($reflectionChecks.Values | Where-Object { -not $_ }).Count -ne 0) {
    throw 'SolidWorks 2024 interop reflection contract failed'
}

$coreText = Get-Content -LiteralPath $coreSource -Raw -Encoding UTF8
$runnerText = Get-Content -LiteralPath $runnerSource -Raw -Encoding UTF8
$combinedText = $coreText + [Environment]::NewLine + $runnerText
$forbiddenPatterns = [ordered]@{
    no_process_start = (-not $combinedText.Contains('Process.Start'))
    no_process_kill = (-not $combinedText.Contains('.Kill('))
    no_file_copy = (-not $combinedText.Contains('File.Copy'))
    no_new_document = (-not $combinedText.Contains('.NewDocument('))
    no_insert_coordinate_system =
        (-not $combinedText.Contains('InsertCoordinateSystem'))
}
$staticChecks = [ordered]@{
    exact_authorization_token_present =
        $runnerText.Contains('--authorized-single-cs-cold-reopen-once')
    attach_via_rot_present =
        $coreText.Contains('Marshal.GetActiveObject(')
    sole_process_discovery_present =
        $coreText.Contains('Process.GetProcessesByName("SLDWORKS")')
    visible_responsive_checks_present =
        ($coreText.Contains('solidWorksProcess.Responding') -and
         $coreText.Contains('solidWorksProcess.MainWindowHandle'))
    empty_session_before_open_present =
        $coreText.Contains('swApp.GetDocumentCount() == 0 && swApp.ActiveDoc == null')
    exactly_one_open_doc6_call =
        ([regex]::Matches($coreText, '\bswApp\.OpenDoc6\s*\(').Count -eq 1)
    fixed_target_literal_present =
        $coreText.Contains('B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT')
    exactly_one_save3_call =
        ([regex]::Matches($coreText, '\bmodel\.Save3\s*\(').Count -eq 1)
    save_errors_and_warnings_zero_required =
        $coreText.Contains('saveErrors == 0 && saveWarnings == 0')
    coordinate_name_and_type_present =
        ($coreText.Contains('CS_DIAGNOSTIC_ONLY') -and
         $coreText.Contains('CoordSys'))
    transform_array_length_16_required =
        $coreText.Contains('values.Length == 16')
    identity_transform_tolerance_required =
        $coreText.Contains('maximumAbsoluteError <= tolerance')
    zero_external_references_required =
        $coreText.Contains('externalReferenceCount == 0')
    evidence_ready_marker_present =
        $coreText.Contains('READY_FOR_VISIBLE_EVIDENCE')
    exact_twenty_second_pause_present =
        ($coreText.Contains('EvidencePauseMilliseconds = 20000') -and
         $coreText.Contains('Thread.Sleep(EvidencePauseMilliseconds)'))
    current_title_close_present =
        ($coreText.Contains('currentTitle = model.GetTitle()') -and
         $coreText.Contains('swApp.CloseDoc(currentTitle)'))
    normal_exit_present = $coreText.Contains('swApp.ExitApp()')
    process_disappearance_is_primary =
        ($coreText.Contains('solidWorksProcess.WaitForExit(') -and
         $coreText.Contains('solidWorksProcess.HasExited') -and
         $coreText.Contains('remaining.Length == 0'))
    external_exit_code_unavailable_is_nonfatal =
        ($coreText.Contains('catch (InvalidOperationException ex)') -and
         $coreText.Contains('exitCodeEvidence = "UNAVAILABLE"') -and
         $coreText.Contains('if (exitCodeAvailable)') -and
         $coreText.Contains('availableExitCode == 0'))
    immutable_json_writes_present =
        $coreText.Contains('FileMode.CreateNew')
    success_status_present =
        $coreText.Contains('SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS')
    stage_a_hash_protection_present =
        $coreText.Contains($expectedStageAHash)
    target_preopen_hash_lock_present =
        $coreText.Contains($expectedTargetHash)
}
if (@($forbiddenPatterns.Values | Where-Object { -not $_ }).Count -ne 0) {
    throw 'A forbidden runtime capability is present in the cold-reopen source'
}
if (@($staticChecks.Values | Where-Object { -not $_ }).Count -ne 0) {
    throw 'Required cold-reopen static contract failed'
}

$coreAssembly = [Reflection.Assembly]::LoadFrom($corePath)
$coreType = $coreAssembly.GetType(
    'B51R1.NativeCadDiagnostics.SingleCsColdReopen',
    $true)
$runMethod = $coreType.GetMethod(
    'Run',
    [Reflection.BindingFlags]'Public, Static')
if (($null -eq $runMethod) -or ($runMethod.ReturnType -ne [int])) {
    throw 'Compiled strong-typed core does not expose public static int Run()'
}

$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$unauthorizedOutput = @(& $runnerPath 2>&1)
$unauthorizedExitCode = $LASTEXITCODE
$ErrorActionPreference = $savedErrorActionPreference
if ($unauthorizedExitCode -ne 64) {
    throw 'Runner did not fail closed without the exact authorization token'
}

$solidWorksProcessCountAfter =
    @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
$targetHashAfter = Get-Sha256 $targetPath
$stageAHashAfter = Get-Sha256 $stageAPath
if ($solidWorksProcessCountAfter -ne 0) {
    throw 'Offline verification caused or observed an unexpected SolidWorks process'
}
if (($targetHashAfter -ne $targetHashBefore) -or
    ($stageAHashAfter -ne $stageAHashBefore)) {
    throw 'Offline verification changed a protected CAD input'
}
foreach ($runtimeOutput in $runtimeOutputs) {
    if (Test-Path -LiteralPath $runtimeOutput) {
        throw "Offline verification created a runtime evidence file: $runtimeOutput"
    }
}

$report = [ordered]@{
    schema = 'B51R1_SINGLE_CS_COLD_REOPEN_TOOL_OFFLINE_VERIFICATION_V2'
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    status = 'PASS_OFFLINE_TOOL_READY_NOT_RUN'
    supersedes_offline_report =
        '07_VERIFICATION\B51R1_SINGLE_CS_COLD_REOPEN_TOOL_OFFLINE_VERIFICATION.json'
    scope = 'Compile, reflect, and statically verify cold-reopen tool only'
    runtime_execution_status = 'NOT_RUN'
    solidworks_launch_or_attach_performed = $false
    solidworks_process_count_before = $solidWorksProcessCountBefore
    solidworks_process_count_after = $solidWorksProcessCountAfter
    target = [ordered]@{
        path = [IO.Path]::GetFullPath($targetPath)
        bytes = (Get-Item -LiteralPath $targetPath).Length
        sha256_before = $targetHashBefore
        sha256_after = $targetHashAfter
        unchanged = ($targetHashBefore -eq $targetHashAfter)
    }
    protected_stage_a = [ordered]@{
        path = [IO.Path]::GetFullPath($stageAPath)
        bytes = (Get-Item -LiteralPath $stageAPath).Length
        sha256_before = $stageAHashBefore
        sha256_after = $stageAHashAfter
        unchanged = ($stageAHashBefore -eq $stageAHashAfter)
    }
    compiler = [ordered]@{
        path = $cscPath
        core_exit_code = $coreCompileExitCode
        core_output = @($coreCompileOutput | ForEach-Object { "$_" })
        runner_exit_code = $runnerCompileExitCode
        runner_output = @($runnerCompileOutput | ForEach-Object { "$_" })
        platform = 'x64'
    }
    interop = [ordered]@{
        sldworks_path = $sldWorksInteropPath
        sldworks_sha256 = Get-Sha256 $sldWorksInteropPath
        sldworks_assembly_version = $sldInterop.GetName().Version.ToString()
        sldworks_file_version =
            [Diagnostics.FileVersionInfo]::GetVersionInfo($sldWorksInteropPath).FileVersion
        swconst_path = $swConstInteropPath
        swconst_sha256 = Get-Sha256 $swConstInteropPath
        open_doc6_signature = Get-MethodSignature $openDoc6[0]
        save3_signature = Get-MethodSignature $save3[0]
        close_doc_signature = Get-MethodSignature $closeDoc[0]
        exit_app_signature = Get-MethodSignature $exitApp[0]
        external_reference_count_signature =
            Get-MethodSignature $externalCount[0]
        reflection_checks = $reflectionChecks
    }
    static_contract = [ordered]@{
        required_checks = $staticChecks
        forbidden_capability_checks = $forbiddenPatterns
        open_doc6_source_call_count =
            [regex]::Matches($coreText, '\bswApp\.OpenDoc6\s*\(').Count
        save3_source_call_count =
            [regex]::Matches($coreText, '\bmodel\.Save3\s*\(').Count
    }
    compiled_artifacts = @(
        [ordered]@{
            path = [IO.Path]::GetFullPath($corePath)
            bytes = (Get-Item -LiteralPath $corePath).Length
            sha256 = Get-Sha256 $corePath
        },
        [ordered]@{
            path = [IO.Path]::GetFullPath($runnerPath)
            bytes = (Get-Item -LiteralPath $runnerPath).Length
            sha256 = Get-Sha256 $runnerPath
        }
    )
    unauthorized_runner_probe = [ordered]@{
        exit_code = $unauthorizedExitCode
        expected_exit_code = 64
        output = @($unauthorizedOutput | ForEach-Object { "$_" })
        pass = ($unauthorizedExitCode -eq 64)
    }
    fixed_runtime_outputs = @(
        $runtimeOutputs | ForEach-Object { [IO.Path]::GetFullPath($_) }
    )
    authorization_token = '--authorized-single-cs-cold-reopen-once'
    execution_command =
        "& '$runnerPath' --authorized-single-cs-cold-reopen-once"
    claim_limit =
        'TOOL READY ONLY; SINGLE-CS PERSISTENCE NOT YET PROVED; NO SOLIDWORKS LAUNCH OR ATTACH; NO MASTER-SKELETON CARRIER H10 T005 CONTROL-RELEASE MANUFACTURING OR FLIGHT CREDIT'
}

$json = $report | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText(
    $reportPath,
    $json + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false))

$reportHash = Get-Sha256 $reportPath
Write-Output "PASS_OFFLINE_TOOL_READY_NOT_RUN"
Write-Output "REPORT=$reportPath"
Write-Output "REPORT_SHA256=$reportHash"
Write-Output "CORE=$corePath"
Write-Output "CORE_SHA256=$(Get-Sha256 $corePath)"
Write-Output "RUNNER=$runnerPath"
Write-Output "RUNNER_SHA256=$(Get-Sha256 $runnerPath)"
Write-Output "COMMAND=& '$runnerPath' --authorized-single-cs-cold-reopen-once"
