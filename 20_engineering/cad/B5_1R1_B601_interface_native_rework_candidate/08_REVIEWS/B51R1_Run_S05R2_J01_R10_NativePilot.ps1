[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Create','ColdVerify')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10'
$carrierDir = Join-Path $root '03_CAD\12_DRIVER_READY_CARRIERS'
$pilotDir = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT'
$checkpointDir = Join-Path $pilotDir 'CHECKPOINTS'
$assemblyTemplate = 'C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_assembly.asmdot'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$softwareOglArgument = '/ForceSoftwareOGL'
$softwareOglRegistryPath = 'HKCU:\Software\SolidWorks\SOLIDWORKS 2024\General'
$softwareOglRegistryName = 'Use Software OGL'
$readinessDll = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$toolSource = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R10_NativePilotTool.cs'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R10_NativePilotTool.dll'
$toolRunner = Join-Path $PSScriptRoot 'B51R1_Run_S05R2_J01_R10_NativePilot.ps1'
$toolSourceBytes = 130028
$toolSourceSha256 = 'C1879161A3C3E36BFDED53D5D2D380DD9B9901F02BB0490E82C7120922E66751'
$toolDllBytes = 81408
$toolDllSha256 = '77A7A528768399D66F7A34CCC6AB2F099BA744537634FEB9875613C49C39E2F0'
$toolCompiler = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\MSBuild\Current\Bin\Roslyn\csc.exe'
$toolCompilerBytes = 64808
$toolCompilerSha256 = 'CF9B364171B07822F5AFA44391AE4FB4A4418D2056A5C5A018CE64F62173AB2C'
$r10StaticRelease = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R10_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r10CreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R13A_POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r10ColdActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R14A_POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION.json'

$mr2PilotGate = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R1_MR2_PILOT_COLD_REOPEN_GATE.json'
$mr2PilotReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R1_PILOT_COLD_REOPEN_RECEIPT.json'
$mr2PilotGateBytes = 1793
$mr2PilotGateSha256 = '358A42B42802CE53D83C9550E47E6526641D1FAD92E598190ABC4BC0FBBDC11B'
$mr2PilotReceiptBytes = 6065
$mr2PilotReceiptSha256 = 'DDC9C05EB489FA43F41F91F2CFA3E8ADDBDC8E880F7A55EC9E0601698D068314'
$baseCarrier = Join-Path $carrierDir 'B51R1_CARRIER_MR2_base_link.SLDPRT'
$link1Carrier = Join-Path $carrierDir 'B51R1_CARRIER_MR2_link1.SLDPRT'
$baseCarrierBytes = 104556
$baseCarrierSha256 = 'E8695447480FDD11B9C87B81E280334E47A68BECA780C4366DBA3F06279C8DFB'
$link1CarrierBytes = 107161
$link1CarrierSha256 = '4E3EDF2D494119F4A4C29E02D16A83CF559BE99ECA57113FE95BE8036721163E'
$hp01DirectReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_PC_R1\B51R1_S05R2_PC_R2_DIRECT_PART_VERIFY_RECEIPT.json'
$hp01DirectReceiptBytes = 6065
$hp01DirectReceiptSha256 = '4F1D9DC591F2F4F7F00E122EEF9E561414A43765131B93B9DD168E6C9215D883'
$r1ContextFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R1\B51R1_S05R2_J01_R1_CREATE_RECEIPT.json'
$r1ContextFailReceiptBytes = 1433
$r1ContextFailReceiptSha256 = 'AD078FF86F4924C833703F8FEC5360DBAC66279C3944E6C99A0269D2786C2448'
$r2RcwFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R2\B51R1_S05R2_J01_R2_CREATE_RECEIPT.json'
$r2RcwFailReceiptBytes = 3679
$r2RcwFailReceiptSha256 = '70CB5779F930F41FF208FDD7152E95BB4BAE6681096356CB70BFE975C4FC989B'
$r3EntityTypeFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R3\B51R1_S05R2_J01_R3_CREATE_RECEIPT.json'
$r3EntityTypeFailReceiptBytes = 3386
$r3EntityTypeFailReceiptSha256 = 'F6FC18BC5154B19F1BCACADBC5B8BD840A4B8C4EAE5E50274C6291DB121F3B0C'
$r4IncorrectSelectionsFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R4\B51R1_S05R2_J01_R4_CREATE_RECEIPT.json'
$r4IncorrectSelectionsFailReceiptBytes = 3693
$r4IncorrectSelectionsFailReceiptSha256 = 'A6A6F08C8FEE27BF6A971945007AD3384F36720C19EE3C3FD8CA0DEC005062E1'
$r5CorrespondingSpecificFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R5\B51R1_S05R2_J01_R5_CREATE_RECEIPT.json'
$r5CorrespondingSpecificFailReceiptBytes = 9810
$r5CorrespondingSpecificFailReceiptSha256 = '206717E6B52B2480EF167DB2C02E6EF4267E51292B4ED41F02D51474D5AEA525'
$r6SelectionConsumptionFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R6\B51R1_S05R2_J01_R6_CREATE_RECEIPT.json'
$r6SelectionConsumptionFailReceiptBytes = 14613
$r6SelectionConsumptionFailReceiptSha256 = 'C7CF8FDDA786BB959ACA3AA9A86DE3B40FBCBD6F4687BF8278AC442CBF9CE96E'
$r7OpenDocRpcFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_CREATE_RECEIPT.json'
$r7OpenDocRpcFailReceiptBytes = 1586
$r7OpenDocRpcFailReceiptSha256 = 'CAEA4F649697D94657286B269ABCA108DDF2487FBA09174F71BFAABC74629A04'
$r7OpenDocRpcFailInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_CREATE_INPUT_LOCK.json'
$r7OpenDocRpcFailInputLockBytes = 12815
$r7OpenDocRpcFailInputLockSha256 = '7951B9B90E0B8EEB9B192FDF046F7B2203020ECEAFE03F06147D68CB69ED5305'
$r7OpenDocRpcFailReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_CREATE_READINESS_RECEIPT.json'
$r7OpenDocRpcFailReadinessBytes = 470
$r7OpenDocRpcFailReadinessSha256 = 'E79777E4839AB669C842EF2C4ACB50E12D359D613DD98CF320F812CCA3D80D4D'
$r7OpenDocRpcFailProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_CREATE_PROGRESS.log'
$r7OpenDocRpcFailProgressBytes = 50
$r7OpenDocRpcFailProgressSha256 = '7DBE6C66EF87FA2328B9330DB658E683428D651075112D6261A213D446C2012F'
$r7StaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R7_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r7StaticReleaseBytes = 5636
$r7StaticReleaseSha256 = 'D4F04D036E981136433C95A8368FA18234C9E24796677A1B43C20268F37ADB42'
$r7Activation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R9A_POOL_A_A08R2_J01_R7_CREATE_MATE_POSTCONDITION_NATIVE_1R_PILOT_CREATE_ACTIVATION.yaml'
$r7ActivationBytes = 3156
$r7ActivationSha256 = '7D148A1F4536A489AA6CAC368BA2C8758B06951BBAC99FB109C70C351E569474'
$r7GraphicsIncident = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_NVIDIA_OPENGL_OOM_FAIL_CLOSED_INCIDENT.json'
$r7GraphicsIncidentBytes = 2851
$r7GraphicsIncidentSha256 = '509C7CB94E76C3BAE104FAC3A987000704E06545C3FE69E3373288B8B6DA60C8'
$r7AbsentOutputs = @(
    (Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R7.SLDASM'),
    (Join-Path $pilotDir 'B51R1_CARRIER_J01_R7_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R7\B51R1_S05R2_J01_R7_CREATE_GATE.json')
)
$r8DefinitionIdentityFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_CREATE_RECEIPT.json'
$r8DefinitionIdentityFailReceiptBytes = 14694
$r8DefinitionIdentityFailReceiptSha256 = 'A4EFFF67B31025409A7E2A2FB17D8B9AA867B94E96A60DD86485248A87441755'
$r8DefinitionIdentityFailInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_CREATE_INPUT_LOCK.json'
$r8DefinitionIdentityFailInputLockBytes = 17952
$r8DefinitionIdentityFailInputLockSha256 = '6B99F20CDE1D7F4A58E7D5C8A7D1FC708A2C9B5505B47385CE54E07D1BCD4B0B'
$r8DefinitionIdentityFailReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_CREATE_READINESS_RECEIPT.json'
$r8DefinitionIdentityFailReadinessBytes = 470
$r8DefinitionIdentityFailReadinessSha256 = 'ABDBE411A3D34BEEA75A0EB63C5845548EC718BA4F8642D260ED10C1BC565939'
$r8DefinitionIdentityFailProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_CREATE_PROGRESS.log'
$r8DefinitionIdentityFailProgressBytes = 129
$r8DefinitionIdentityFailProgressSha256 = 'A3326F3C4737AC9DAD79D5B8538C708B7781D3709D5B149E2925D8E2911DD173'
$r8StaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R8_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r8StaticReleaseBytes = 6915
$r8StaticReleaseSha256 = 'D83FBCDE6485AB8359C62CD9FB3AD4537DA1A230ED64B18BD33B82A1B81BB30A'
$r8Activation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R10A_POOL_A_A08R2_J01_R8_SOFTWARE_OGL_NATIVE_1R_PILOT_CREATE_ACTIVATION.yaml'
$r8ActivationBytes = 4483
$r8ActivationSha256 = 'FDD4B62C220EA8C78B03F9A9F2EC666AADD83E4173F42E2BAFA891D720A7892C'
$r8Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R8_NativePilotTool.cs'
$r8SourceBytes = 111906
$r8SourceSha256 = '1D28FBC97F1960E03A2207EEBB3A2E8E8B336ECA76FCFCBEAF776AE14301388A'
$r8Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R8_NativePilot.ps1'
$r8RunnerBytes = 72037
$r8RunnerSha256 = 'C34AFBFEFFDB9C0AC86E004B5A7C9E7FCD216FA257EC164D671477930A354BCA'
$r8Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R8_NativePilotTool.dll'
$r8BinaryBytes = 72192
$r8BinarySha256 = 'C2804F99F4890CBFC4E9D4753F95DDB57A3299A40071C5E371235D8C84AD4D09'
$r8AbsentOutputs = @(
    (Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R8.SLDASM'),
    (Join-Path $pilotDir 'B51R1_CARRIER_J01_R8_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_CREATE_GATE.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_COLD_REOPEN_PROGRESS.log'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R8\B51R1_S05R2_J01_R8_NATIVE_1R_GATE.json')
)
$r9SemanticLedgerFailReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_RECEIPT.json'
$r9SemanticLedgerFailReceiptBytes = 17126
$r9SemanticLedgerFailReceiptSha256 = '10683F5602D358CEC423B7D2723AD6BBEB7CC163F1BD1B5AD3481A29CAE091C8'
$r9SemanticLedgerFailInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_INPUT_LOCK.json'
$r9SemanticLedgerFailInputLockBytes = 28537
$r9SemanticLedgerFailInputLockSha256 = '0B8E6A152BF7BF121C638D2441DE574C9EB3D0CDD706E2D031F535594BAEE83A'
$r9SemanticLedgerFailReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_READINESS_RECEIPT.json'
$r9SemanticLedgerFailReadinessBytes = 470
$r9SemanticLedgerFailReadinessSha256 = 'A7787A94C10DCD0A031F087ED58DEA3DB745AAE5AB04671A1144C3B2FD918086'
$r9SemanticLedgerFailProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_PROGRESS.log'
$r9SemanticLedgerFailProgressBytes = 138
$r9SemanticLedgerFailProgressSha256 = '89761FABD1B8965B8D74358297409E67689EE262D79CA952CA7697B42648AA22'
$r9StaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R9_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r9StaticReleaseBytes = 5788
$r9StaticReleaseSha256 = 'A26E028C76EB0E7527A2F867CAFEA8C0641EF875FE07385EBFC230FC0EE453BB'
$r9Activation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R11A_POOL_A_A08R2_J01_R9_SEMANTIC_IDENTITY_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r9ActivationBytes = 3965
$r9ActivationSha256 = 'AD96B5CD54BD2C2482FCE3394BA73C7ADB0C73756FD98613EF0278828E3E84F1'
$r9Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R9_NativePilotTool.cs'
$r9SourceBytes = 126383
$r9SourceSha256 = 'B34FC21C36A670DE69FFB60903959C17D238747861BD821918D51867BFEB2A40'
$r9Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R9_NativePilot.ps1'
$r9RunnerBytes = 97383
$r9RunnerSha256 = 'DBDE5008AB2EC20B1CBC7905F521A5A2F9E60DE6A13FB6B1E56A5A4B04491EC0'
$r9Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R9_NativePilotTool.dll'
$r9BinaryBytes = 79360
$r9BinarySha256 = 'CC241657185E4FEF24EDFB69E5100C62CA4BE41C72AA78C6B4459EB29B3FF637'
$r9AbsentOutputs = @(
    (Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R9.SLDASM'),
    (Join-Path $pilotDir 'B51R1_CARRIER_J01_R9_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_GATE.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_COLD_REOPEN_PROGRESS.log'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_NATIVE_1R_GATE.json')
)
$j00Assembly = Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R10.SLDASM'
$pilotAssembly = Join-Path $pilotDir 'B51R1_CARRIER_J01_R10_NATIVE_PILOT.SLDASM'
$j00Checkpoint = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_J00_BASELINE_CHECKPOINT.json'
$createReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_CREATE_RECEIPT.json'
$createProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_CREATE_PROGRESS.log'
$createGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_CREATE_GATE.json'
$coldReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_COLD_REOPEN_RECEIPT.json'
$coldProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_COLD_REOPEN_PROGRESS.log'
$finalGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R10_NATIVE_1R_GATE.json'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-File([string]$Path, [long]$Bytes, [string]$Sha256, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label missing: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -ne $Bytes) { throw "$Label byte count mismatch" }
    if ((Get-Sha $Path) -ne $Sha256.ToUpperInvariant()) { throw "$Label SHA-256 mismatch" }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) { throw "Append-only JSON exists: $Path" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $utf8 = New-Object Text.UTF8Encoding($false)
    $payload = $utf8.GetBytes((($Value | ConvertTo-Json -Depth 100 -Compress) + [Environment]::NewLine))
    $stream = [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $stream.Write($payload,0,$payload.Length) }
    finally { $stream.Dispose() }
}

function Get-PersistentSoftwareOglValue {
    $item = Get-ItemProperty -LiteralPath $softwareOglRegistryPath -Name $softwareOglRegistryName -ErrorAction Stop
    $property = $item.PSObject.Properties[$softwareOglRegistryName]
    if ($null -eq $property) { throw 'Persistent Use Software OGL registry value is absent' }
    return [long]$property.Value
}

function Get-ModeActivation([string]$RequestedMode) {
    $activationPath = if ($RequestedMode -eq 'Create') { $r10CreateActivation } else { $r10ColdActivation }
    if (-not (Test-Path -LiteralPath $activationPath -PathType Leaf)) {
        throw "J01 R10 $RequestedMode has no independent activation: $activationPath"
    }
    $activation = Get-Content -Raw -Encoding UTF8 -LiteralPath $activationPath | ConvertFrom-Json
    $expectedSchema = if ($RequestedMode -eq 'Create') {
        'B51R1_AUTONOMOUS_SESSION_PLAN_V22R13A_POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION_V1'
    } else {
        'B51R1_AUTONOMOUS_SESSION_PLAN_V22R14A_POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION_V1'
    }
    $expectedStatus = if ($RequestedMode -eq 'Create') {
        'POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATED'
    } else {
        'POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATED'
    }
    $expectedActivationMode = if ($RequestedMode -eq 'Create') { 'CREATE_ONLY' } else { 'COLD_VERIFY_ONLY' }
    if ($activation.schema -ne $expectedSchema -or $activation.status -ne $expectedStatus -or
        $activation.activation_mode -ne $expectedActivationMode -or $activation.gate_pass -ne $true -or
        [IO.Path]::GetFullPath([string]$activation.static_release.path) -ne [IO.Path]::GetFullPath($r10StaticRelease)) {
        throw "J01 R10 $RequestedMode activation contract mismatch"
    }
    Assert-File $r10StaticRelease ([long]$activation.static_release.bytes) ([string]$activation.static_release.sha256) 'J01 R10 static release bound by activation'
    $release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10StaticRelease | ConvertFrom-Json
    if ($release.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $release.status -ne 'STATIC_RELEASE_PASS' -or $release.gate_pass -ne $true -or
        $release.runtime_executed -ne $false -or [long]$release.recovery_prerequisite_count -ne 10 -or
        [long]$release.source.bytes -ne $toolSourceBytes -or [string]$release.source.sha256 -ne $toolSourceSha256 -or
        [long]$release.runner.bytes -ne (Get-Item -LiteralPath $toolRunner).Length -or
        [string]$release.runner.sha256 -ne (Get-Sha $toolRunner) -or
        [long]$release.binary.bytes -ne $toolDllBytes -or [string]$release.binary.sha256 -ne $toolDllSha256 -or
        $release.binary.double_compile_byte_identical -ne $true -or
        $release.create_activation_authorized -ne $true -or
        $release.cold_verify_activation_authorized -ne $false -or
        $release.formal_s05_output_allowed -ne $false -or $release.t005_authorized -ne $false) {
        throw 'J01 R10 static release semantic contract mismatch'
    }
    if ([IO.Path]::GetFullPath([string]$activation.tool.source.path) -ne [IO.Path]::GetFullPath($toolSource) -or
        [long]$activation.tool.source.bytes -ne $toolSourceBytes -or [string]$activation.tool.source.sha256 -ne $toolSourceSha256 -or
        [IO.Path]::GetFullPath([string]$activation.tool.runner.path) -ne [IO.Path]::GetFullPath($toolRunner) -or
        [long]$activation.tool.runner.bytes -ne (Get-Item -LiteralPath $toolRunner).Length -or
        [string]$activation.tool.runner.sha256 -ne (Get-Sha $toolRunner) -or
        [IO.Path]::GetFullPath([string]$activation.tool.binary.path) -ne [IO.Path]::GetFullPath($toolDll) -or
        [long]$activation.tool.binary.bytes -ne $toolDllBytes -or [string]$activation.tool.binary.sha256 -ne $toolDllSha256) {
        throw "J01 R10 $RequestedMode activation tool binding mismatch"
    }
    if ($RequestedMode -eq 'Create') {
        if ($activation.create_authorized -ne $true -or $activation.cold_verify_authorized -ne $false -or
            [IO.Path]::GetFullPath([string]$activation.predecessor_failure.path) -ne [IO.Path]::GetFullPath($r9SemanticLedgerFailReceipt) -or
            [long]$activation.predecessor_failure.bytes -ne $r9SemanticLedgerFailReceiptBytes -or
            [string]$activation.predecessor_failure.sha256 -ne $r9SemanticLedgerFailReceiptSha256) {
            throw 'J01 R10 Create activation scope/predecessor binding mismatch'
        }
    } else {
        if ($activation.create_authorized -ne $false -or $activation.cold_verify_authorized -ne $true -or
            [IO.Path]::GetFullPath([string]$activation.create_gate.path) -ne [IO.Path]::GetFullPath($createGate) -or
            [IO.Path]::GetFullPath([string]$activation.create_receipt.path) -ne [IO.Path]::GetFullPath($createReceipt) -or
            [IO.Path]::GetFullPath([string]$activation.pilot_output.path) -ne [IO.Path]::GetFullPath($pilotAssembly)) {
            throw 'J01 R10 ColdVerify activation scope/path binding mismatch'
        }
        Assert-File $createGate ([long]$activation.create_gate.bytes) ([string]$activation.create_gate.sha256) 'J01 R10 Cold activation Create Gate'
        Assert-File $createReceipt ([long]$activation.create_receipt.bytes) ([string]$activation.create_receipt.sha256) 'J01 R10 Cold activation Create receipt'
        Assert-File $pilotAssembly ([long]$activation.pilot_output.bytes) ([string]$activation.pilot_output.sha256) 'J01 R10 Cold activation pilot output'
    }
    if ($activation.formal_s05_authorized -ne $false -or $activation.t005_authorized -ne $false) {
        throw "J01 R10 $RequestedMode activation exceeds Pilot scope"
    }
    return [ordered]@{
        id="J01_R10_$($RequestedMode.ToUpperInvariant())_ACTIVATION"
        path=$activationPath;bytes=(Get-Item -LiteralPath $activationPath).Length;sha256=Get-Sha $activationPath
        status=[string]$activation.status;activation_mode=[string]$activation.activation_mode
    }
}

function Get-Mr2PilotInputs {
    Assert-File $mr2PilotGate $mr2PilotGateBytes $mr2PilotGateSha256 'MR2 Pilot R1 accepted cold-reopen Gate'
    Assert-File $mr2PilotReceipt $mr2PilotReceiptBytes $mr2PilotReceiptSha256 'MR2 Pilot R1 accepted cold-reopen receipt'
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $mr2PilotGate | ConvertFrom-Json
    if ($gate.schema -ne 'B51R1_S05R2_PC_R1_GATE_V1' -or
        $gate.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or $gate.gate_pass -ne $true) {
        throw 'MR2 Pilot R1 cold-reopen Gate is not PASS'
    }
    if ([IO.Path]::GetFullPath([string]$gate.receipt.path) -ne [IO.Path]::GetFullPath($mr2PilotReceipt)) {
        throw 'MR2 Pilot R1 cold-reopen receipt path mismatch'
    }
    if ([long]$gate.receipt.bytes -ne $mr2PilotReceiptBytes -or
        [string]$gate.receipt.sha256 -ne $mr2PilotReceiptSha256) {
        throw 'MR2 Pilot R1 Gate receipt binding differs from the accepted receipt'
    }
    $receiptState = Get-Content -Raw -Encoding UTF8 -LiteralPath $mr2PilotReceipt | ConvertFrom-Json
    if ($receiptState.schema -ne 'B51R1_S05R2_R1_DRIVER_READY_COLD_REOPEN_V3' -or
        $receiptState.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or
        [long]$receiptState.verified_part_count -ne 2 -or $receiptState.normal_application_exit -ne $true) {
        throw 'MR2 Pilot R1 accepted cold-reopen receipt contract mismatch'
    }
    $parts = @($gate.parts)
    if ($parts.Count -ne 2 -or @($parts.link | Select-Object -Unique).Count -ne 2) {
        throw 'MR2 Pilot Gate does not contain two unique Carrier parts'
    }
    $result = @()
    foreach ($link in @('base_link','link1')) {
        $part = @($parts | Where-Object { $_.link -eq $link })
        if ($part.Count -ne 1) { throw "MR2 Gate part is not unique: $link" }
        $expectedPath = if ($link -eq 'base_link') { $baseCarrier } else { $link1Carrier }
        if ([IO.Path]::GetFullPath([string]$part[0].path) -ne [IO.Path]::GetFullPath($expectedPath)) {
            throw "MR2 Gate path mismatch: $link"
        }
        $expectedBytes = if ($link -eq 'base_link') { $baseCarrierBytes } else { $link1CarrierBytes }
        $expectedSha = if ($link -eq 'base_link') { $baseCarrierSha256 } else { $link1CarrierSha256 }
        $expectedFeatures = if ($link -eq 'base_link') { 27 } else { 29 }
        if ([long]$part[0].bytes -ne $expectedBytes -or [string]$part[0].sha256 -ne $expectedSha -or
            [long]$part[0].feature_count -ne $expectedFeatures -or [long]$part[0].body_count -ne 0 -or
            [long]$part[0].external_reference_count -ne 0) {
            throw "MR2 Gate accepted part binding is invalid: $link"
        }
        $receiptPart = @($receiptState.parts | Where-Object { $_.link -eq $link })
        if ($receiptPart.Count -ne 1 -or [long]$receiptPart[0].feature_count -ne $expectedFeatures -or
            [long]$receiptPart[0].body_count -ne 0 -or [long]$receiptPart[0].external_reference_count -ne 0 -or
            [string]$receiptPart[0].sha256_before_after -ne $expectedSha) {
            throw "MR2 accepted receipt part binding is invalid: $link"
        }
        Assert-File $expectedPath $expectedBytes $expectedSha "MR2_ACCEPTED_$link"
        $result += [ordered]@{link=$link;path=$expectedPath;bytes=$expectedBytes;sha256=$expectedSha;feature_count=$expectedFeatures;body_count=0;external_reference_count=0}
    }
    return $result
}

function Get-RecoveryPrerequisites {
    Assert-File $hp01DirectReceipt $hp01DirectReceiptBytes $hp01DirectReceiptSha256 'J01 R10 direct-open health receipt'
    Assert-File $r1ContextFailReceipt $r1ContextFailReceiptBytes $r1ContextFailReceiptSha256 'J01 R1 context failure receipt'
    Assert-File $r2RcwFailReceipt $r2RcwFailReceiptBytes $r2RcwFailReceiptSha256 'J01 R2 RCW failure receipt'
    Assert-File $r3EntityTypeFailReceipt $r3EntityTypeFailReceiptBytes $r3EntityTypeFailReceiptSha256 'J01 R3 mate-entity type failure receipt'
    Assert-File $r4IncorrectSelectionsFailReceipt $r4IncorrectSelectionsFailReceiptBytes $r4IncorrectSelectionsFailReceiptSha256 'J01 R4 incorrect-selections failure receipt'
    Assert-File $r5CorrespondingSpecificFailReceipt $r5CorrespondingSpecificFailReceiptBytes $r5CorrespondingSpecificFailReceiptSha256 'J01 R5 corresponding-specific failure receipt'
    Assert-File $r6SelectionConsumptionFailReceipt $r6SelectionConsumptionFailReceiptBytes $r6SelectionConsumptionFailReceiptSha256 'J01 R6 CreateMate selection-consumption failure receipt'

    $direct = Get-Content -Raw -Encoding UTF8 -LiteralPath $hp01DirectReceipt | ConvertFrom-Json
    if ($direct.schema -ne 'B51R1_S05R2_R1_DRIVER_READY_COLD_REOPEN_V3' -or
        $direct.status -ne 'S05R2_PC_R1_BASE_AND_LINK1_MR2_COLD_REOPEN_PASS' -or
        [long]$direct.verified_part_count -ne 2 -or $direct.normal_document_close -ne $true -or
        $direct.normal_application_exit -ne $true -or [long]$direct.save3_call_count -ne 0 -or
        [long]$direct.save_as_call_count -ne 0) {
        throw 'J01 R10 direct-open health receipt contract mismatch'
    }
    $directParts = @($direct.parts)
    if ($directParts.Count -ne 2 -or @($directParts.link | Select-Object -Unique).Count -ne 2) {
        throw 'J01 R10 direct-open health receipt does not bind two unique parts'
    }
    foreach ($link in @('base_link','link1')) {
        $part = @($directParts | Where-Object { $_.link -eq $link })
        if ($part.Count -ne 1) { throw "J01 R10 direct-open part is not unique: $link" }
        $expectedPath = if ($link -eq 'base_link') { $baseCarrier } else { $link1Carrier }
        $expectedBytes = if ($link -eq 'base_link') { $baseCarrierBytes } else { $link1CarrierBytes }
        $expectedSha = if ($link -eq 'base_link') { $baseCarrierSha256 } else { $link1CarrierSha256 }
        if ([IO.Path]::GetFullPath([string]$part[0].path) -ne [IO.Path]::GetFullPath($expectedPath) -or
            [long]$part[0].bytes -ne $expectedBytes -or [string]$part[0].sha256_before_after -ne $expectedSha -or
            [long]$part[0].body_count -ne 0 -or [long]$part[0].external_reference_count -ne 0) {
            throw "J01 R10 direct-open health binding mismatch: $link"
        }
    }

    $failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r1ContextFailReceipt | ConvertFrom-Json
    if ($failed.schema -ne 'B51R1_S05R2_J01_R1_NATIVE_PILOT_CREATE_V1' -or
        $failed.status -ne 'S05R2_J01_R1_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $failed.gate_pass -isnot [bool] -or $failed.gate_pass -ne $false -or
        [string]$failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$failed.exception -notmatch 'errors=2097152') {
        throw 'J01 R1 context failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','mate_preselection_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$failed.$field -ne 0) { throw "J01 R1 failure was not zero-action at $field" }
    }
    if ([string]$failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$failed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R1 context failure receipt does not preserve MR2 input hashes'
    }

    $rcwFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r2RcwFailReceipt | ConvertFrom-Json
    if ($rcwFailed.schema -ne 'B51R1_S05R2_J01_R2_NATIVE_PILOT_CREATE_V1' -or
        $rcwFailed.status -ne 'S05R2_J01_R2_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $rcwFailed.gate_pass -isnot [bool] -or $rcwFailed.gate_pass -ne $false -or
        [string]$rcwFailed.exception_type -ne 'System.Runtime.InteropServices.InvalidComObjectException' -or
        [string]$rcwFailed.exception -notmatch 'IAssemblyDoc.AddComponent5') {
        throw 'J01 R2 RCW failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','mate_preselection_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$rcwFailed.$field -ne 0) { throw "J01 R2 failure was not zero-action at $field" }
    }
    $rcwPreloads = @($rcwFailed.preload_operations)
    if ($rcwPreloads.Count -ne 2 -or [long]$rcwFailed.document_count_before_new_assembly -ne 2 -or
        [long]$rcwFailed.document_count_after_new_assembly -ne 3) {
        throw 'J01 R2 RCW failure did not complete the strict two-part preload transition'
    }
    foreach ($preload in $rcwPreloads) {
        if ($preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
            $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
            [long]$preload.open_errors -ne 0 -or [long]$preload.open_warnings -ne 0) {
            throw 'J01 R2 RCW failure did not preserve strict preload health evidence'
        }
    }
    if ([string]$rcwFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$rcwFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R2 RCW failure receipt does not preserve MR2 input hashes'
    }

    $entityFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r3EntityTypeFailReceipt | ConvertFrom-Json
    if ($entityFailed.schema -ne 'B51R1_S05R2_J01_R3_NATIVE_PILOT_CREATE_V1' -or
        $entityFailed.status -ne 'S05R2_J01_R3_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $entityFailed.gate_pass -isnot [bool] -or $entityFailed.gate_pass -ne $false -or
        [string]$entityFailed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$entityFailed.exception -notmatch 'CreateMate returned no Feature: J00_ROOT_X_COINCIDENT' -or
        [string]$entityFailed.exception -notmatch 'CreateCoincidentMate') {
        throw 'J01 R3 mate-entity type failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','add_mate5_call_count',
        'mate_preselection_call_count','transform2_call_count','set_transform_and_solve_call_count',
        'move_component_call_count')) {
        if ([long]$entityFailed.$field -ne 0) { throw "J01 R3 mate-entity failure contains a prohibited/save call at $field" }
    }
    if ([long]$entityFailed.create_mate_data_call_count -ne 0 -or [long]$entityFailed.create_mate_call_count -ne 0) {
        throw 'J01 R3 frozen receipt no longer matches its known inaccurate Mate counters'
    }
    $entityPreloads = @($entityFailed.preload_operations)
    if ($entityPreloads.Count -ne 2 -or [long]$entityFailed.document_count_before_new_assembly -ne 2 -or
        [long]$entityFailed.document_count_after_new_assembly -ne 3 -or
        $entityPreloads[0].add_component5_succeeded -isnot [bool] -or
        $entityPreloads[0].add_component5_succeeded -ne $true) {
        throw 'J01 R3 mate-entity failure did not reach the first root Mate after strict preload/base insertion'
    }
    if ([string]$entityFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$entityFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R3 mate-entity failure receipt does not preserve MR2 input hashes'
    }

    $selectionFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r4IncorrectSelectionsFailReceipt | ConvertFrom-Json
    if ($selectionFailed.schema -ne 'B51R1_S05R2_J01_R4_NATIVE_PILOT_CREATE_V1' -or
        $selectionFailed.status -ne 'S05R2_J01_R4_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $selectionFailed.gate_pass -isnot [bool] -or $selectionFailed.gate_pass -ne $false -or
        [string]$selectionFailed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$selectionFailed.exception -notmatch 'J00_ROOT_X_COINCIDENT, ErrorStatus=4') {
        throw 'J01 R4 incorrect-selections failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','add_mate5_call_count',
        'mate_preselection_call_count','transform2_call_count','set_transform_and_solve_call_count',
        'move_component_call_count')) {
        if ([long]$selectionFailed.$field -ne 0) { throw "J01 R4 incorrect-selections failure contains a prohibited/save call at $field" }
    }
    if ([long]$selectionFailed.create_mate_data_call_count -ne 1 -or
        [long]$selectionFailed.create_mate_call_count -ne 1) {
        throw 'J01 R4 Mate call ledger does not contain the one known failed CreateMate call'
    }
    $selectionAttempts = @($selectionFailed.mate_api_attempts)
    if ($selectionAttempts.Count -ne 1 -or
        [string]$selectionAttempts[0].name -ne 'J00_ROOT_X_COINCIDENT' -or
        [long]$selectionAttempts[0].create_mate_error_status -ne 4 -or
        $selectionAttempts[0].feature_returned -isnot [bool] -or
        $selectionAttempts[0].feature_returned -ne $false) {
        throw 'J01 R4 failure does not bind ErrorStatus=4 to the first root mate'
    }
    if ([string]$selectionFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$selectionFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R4 incorrect-selections failure receipt does not preserve MR2 input hashes'
    }

    $correspondingFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r5CorrespondingSpecificFailReceipt | ConvertFrom-Json
    if ($correspondingFailed.schema -ne 'B51R1_S05R2_J01_R5_NATIVE_PILOT_CREATE_V1' -or
        $correspondingFailed.status -ne 'S05R2_J01_R5_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $correspondingFailed.gate_pass -isnot [bool] -or $correspondingFailed.gate_pass -ne $false -or
        [string]$correspondingFailed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$correspondingFailed.exception -notmatch 'Direct corresponding specific object has the wrong runtime interface: J00_ROOT_X_COINCIDENT_BASE_PLANE') {
        throw 'J01 R5 corresponding-specific failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','transform2_call_count','set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$correspondingFailed.$field -ne 0) { throw "J01 R5 failure contains a prohibited/save/Mate call at $field" }
    }
    if ([long]$correspondingFailed.mate_preselection_call_count -ne 1 -or
        [long]$correspondingFailed.document_count_before_new_assembly -ne 2 -or
        [long]$correspondingFailed.document_count_after_new_assembly -ne 3) {
        throw 'J01 R5 failure did not stop after the first assembly-root SelectByID2 call'
    }
    $correspondingPreloads = @($correspondingFailed.preload_operations)
    if ($correspondingPreloads.Count -ne 2 -or
        $correspondingPreloads[0].add_component5_succeeded -isnot [bool] -or
        $correspondingPreloads[0].add_component5_succeeded -ne $true) {
        throw 'J01 R5 failure did not preserve the strict preload/base insertion transition'
    }
    foreach ($preload in $correspondingPreloads) {
        if ($preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
            $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
            [long]$preload.open_errors -ne 0 -or [long]$preload.open_warnings -ne 0) {
            throw 'J01 R5 failure did not preserve strict preload health evidence'
        }
    }
    $correspondingAttempts = @($correspondingFailed.mate_api_attempts)
    $correspondingSelections = @($correspondingFailed.mate_preselection_attempts)
    if ($correspondingAttempts.Count -ne 1 -or [string]$correspondingAttempts[0].name -ne 'J00_ROOT_X_COINCIDENT' -or
        @($correspondingAttempts[0].entity_selections).Count -ne 2 -or $correspondingSelections.Count -ne 2) {
        throw 'J01 R5 failure selection ledger shape mismatch'
    }
    $rootSelection = $correspondingSelections[0]
    $componentSelection = $correspondingSelections[1]
    if ([string]$rootSelection.role -ne 'J00_ROOT_X_COINCIDENT_ASSEMBLY_PLANE' -or
        $rootSelection.identity_gate_pass -isnot [bool] -or $rootSelection.identity_gate_pass -ne $true -or
        [long]$rootSelection.select_by_id2_call_index -ne 1 -or
        $rootSelection.select_by_id2_returned -isnot [bool] -or $rootSelection.select_by_id2_returned -ne $true -or
        [string]$componentSelection.role -ne 'J00_ROOT_X_COINCIDENT_BASE_PLANE' -or
        $componentSelection.identity_gate_pass -isnot [bool] -or $componentSelection.identity_gate_pass -ne $false -or
        [string]$componentSelection.failure_type -ne 'System.InvalidOperationException' -or
        [string]$componentSelection.failure -ne 'Direct corresponding specific object has the wrong runtime interface: J00_ROOT_X_COINCIDENT_BASE_PLANE') {
        throw 'J01 R5 failure is not localized to the component direct-specific diagnostic gate'
    }
    if ([string]$correspondingFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$correspondingFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R5 corresponding-specific failure receipt does not preserve MR2 input hashes'
    }

    $selectionConsumptionFailed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r6SelectionConsumptionFailReceipt | ConvertFrom-Json
    if ($selectionConsumptionFailed.schema -ne 'B51R1_S05R2_J01_R6_NATIVE_PILOT_CREATE_V1' -or
        $selectionConsumptionFailed.status -ne 'S05R2_J01_R6_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $selectionConsumptionFailed.gate_pass -isnot [bool] -or $selectionConsumptionFailed.gate_pass -ne $false -or
        [string]$selectionConsumptionFailed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$selectionConsumptionFailed.exception -notmatch 'Coincident selection did not persist through CreateMate return: J00_ROOT_X_COINCIDENT') {
        throw 'J01 R6 CreateMate selection-consumption failure receipt contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','add_mate5_call_count',
        'transform2_call_count','set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$selectionConsumptionFailed.$field -ne 0) { throw "J01 R6 failure contains a prohibited/save call at $field" }
    }
    if ([long]$selectionConsumptionFailed.mate_preselection_call_count -ne 2 -or
        [long]$selectionConsumptionFailed.create_mate_data_call_count -ne 1 -or
        [long]$selectionConsumptionFailed.create_mate_call_count -ne 1 -or
        [long]$selectionConsumptionFailed.document_count_before_new_assembly -ne 2 -or
        [long]$selectionConsumptionFailed.document_count_after_new_assembly -ne 3) {
        throw 'J01 R6 failure did not stop after the first successful CreateMate consumed the selections'
    }
    $r6Preloads = @($selectionConsumptionFailed.preload_operations)
    if ($r6Preloads.Count -ne 2 -or
        $r6Preloads[0].add_component5_succeeded -isnot [bool] -or $r6Preloads[0].add_component5_succeeded -ne $true) {
        throw 'J01 R6 failure did not preserve the strict preload/base insertion transition'
    }
    foreach ($preload in $r6Preloads) {
        if ($preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
            $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
            [long]$preload.open_errors -ne 0 -or [long]$preload.open_warnings -ne 0) {
            throw 'J01 R6 failure did not preserve strict preload health evidence'
        }
    }
    $r6Attempts = @($selectionConsumptionFailed.mate_api_attempts)
    $r6Selections = @($selectionConsumptionFailed.mate_preselection_attempts)
    if ($r6Attempts.Count -ne 1 -or $r6Selections.Count -ne 2) {
        throw 'J01 R6 failure Mate/selection ledger shape mismatch'
    }
    $r6Attempt = $r6Attempts[0]
    if ([string]$r6Attempt.name -ne 'J00_ROOT_X_COINCIDENT' -or [long]$r6Attempt.mate_type -ne 0 -or
        @($r6Attempt.entity_selections).Count -ne 2 -or
        [long]$r6Attempt.preselection_count_before_create_mate_data -ne 2 -or
        [long]$r6Attempt.create_mate_data_call_index -ne 1 -or
        [long]$r6Attempt.create_mate_call_index -ne 1 -or
        $r6Attempt.mate_data_returned -isnot [bool] -or $r6Attempt.mate_data_returned -ne $true -or
        [long]$r6Attempt.create_mate_error_status -ne 1 -or
        $r6Attempt.feature_returned -isnot [bool] -or $r6Attempt.feature_returned -ne $true -or
        [long]$r6Attempt.selection_count_at_create_mate_return -ne 0 -or
        $r6Attempt.PSObject.Properties.Name -contains 'selection_count_after_post_create_clear') {
        throw 'J01 R6 failure does not prove a successful first CreateMate consumed the selection set'
    }
    $r6RootSelection = $r6Selections[0]
    $r6ComponentSelection = $r6Selections[1]
    if ([string]$r6RootSelection.role -ne 'J00_ROOT_X_COINCIDENT_ASSEMBLY_PLANE' -or
        [long]$r6RootSelection.select_by_id2_call_index -ne 1 -or
        $r6RootSelection.select_by_id2_returned -isnot [bool] -or $r6RootSelection.select_by_id2_returned -ne $true -or
        $r6RootSelection.identity_gate_pass -isnot [bool] -or $r6RootSelection.identity_gate_pass -ne $true -or
        $r6RootSelection.direct_corresponding_specific_has_expected_type -ne $true -or
        $r6RootSelection.direct_corresponding_specific_diagnostic_only -ne $false -or
        $r6RootSelection.selected_specific_matches_direct_corresponding_specific -ne $true -or
        $null -ne $r6RootSelection.selected_owner_component -or $null -ne $r6RootSelection.selected_owner_path) {
        throw 'J01 R6 assembly-root selection evidence mismatch'
    }
    if ([string]$r6ComponentSelection.role -ne 'J00_ROOT_X_COINCIDENT_BASE_PLANE' -or
        [long]$r6ComponentSelection.select_by_id2_call_index -ne 2 -or
        $r6ComponentSelection.select_by_id2_returned -isnot [bool] -or $r6ComponentSelection.select_by_id2_returned -ne $true -or
        $r6ComponentSelection.identity_gate_pass -isnot [bool] -or $r6ComponentSelection.identity_gate_pass -ne $true -or
        $r6ComponentSelection.direct_corresponding_specific_diagnostic_only -ne $true -or
        [string]$r6ComponentSelection.mate_entity_authority -ne 'ISelectionMgr.GetSelectedObject6' -or
        [long]$r6ComponentSelection.selected_object_type -ne 4 -or [long]$r6ComponentSelection.selected_object_mark -ne 1 -or
        [IO.Path]::GetFullPath([string]$r6ComponentSelection.selected_owner_path) -ne [IO.Path]::GetFullPath($baseCarrier)) {
        throw 'J01 R6 component SelectionMgr authority/owner/type/mark evidence mismatch'
    }
    if ([string]$selectionConsumptionFailed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$selectionConsumptionFailed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R6 selection-consumption failure receipt does not preserve MR2 input hashes'
    }

    Assert-File $r7OpenDocRpcFailReceipt $r7OpenDocRpcFailReceiptBytes $r7OpenDocRpcFailReceiptSha256 'J01 R7 OpenDoc6 RPC failure receipt'
    Assert-File $r7OpenDocRpcFailInputLock $r7OpenDocRpcFailInputLockBytes $r7OpenDocRpcFailInputLockSha256 'J01 R7 OpenDoc6 RPC failure input lock'
    Assert-File $r7OpenDocRpcFailReadiness $r7OpenDocRpcFailReadinessBytes $r7OpenDocRpcFailReadinessSha256 'J01 R7 OpenDoc6 RPC failure readiness'
    Assert-File $r7OpenDocRpcFailProgress $r7OpenDocRpcFailProgressBytes $r7OpenDocRpcFailProgressSha256 'J01 R7 OpenDoc6 RPC failure progress'
    Assert-File $r7StaticRelease $r7StaticReleaseBytes $r7StaticReleaseSha256 'J01 R7 static release'
    Assert-File $r7Activation $r7ActivationBytes $r7ActivationSha256 'J01 R7 Create-only activation'
    Assert-File $r7GraphicsIncident $r7GraphicsIncidentBytes $r7GraphicsIncidentSha256 'J01 R7 NVIDIA OpenGL OOM incident'
    foreach ($path in $r7AbsentOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R7 unexpectedly produced a mechanical output: $path" }
    }
    $r7Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r7OpenDocRpcFailReceipt | ConvertFrom-Json
    if ($r7Failed.schema -ne 'B51R1_S05R2_J01_R7_NATIVE_PILOT_CREATE_V1' -or
        $r7Failed.status -ne 'S05R2_J01_R7_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r7Failed.gate_pass -isnot [bool] -or $r7Failed.gate_pass -ne $false -or
        [long]$r7Failed.expected_process_id -ne 29056 -or
        [string]$r7Failed.exception_type -ne 'System.Runtime.InteropServices.COMException' -or
        [string]$r7Failed.exception -notmatch '0x800706BE' -or
        [string]$r7Failed.exception -notmatch 'ISldWorks.OpenDoc6' -or
        [string]$r7Failed.exception -notmatch 'PreloadPart' -or
        [string]$r7Failed.exception -notmatch 'NativePilotTool.Create') {
        throw 'J01 R7 first-OpenDoc6 RPC failure contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','create_mate_data_call_count','create_mate_call_count',
        'add_mate5_call_count','mate_preselection_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r7Failed.$field -ne 0) { throw "J01 R7 failure was not zero-action at $field" }
    }
    if (@($r7Failed.preload_operations).Count -ne 0 -or @($r7Failed.mate_api_attempts).Count -ne 0 -or
        @($r7Failed.mate_preselection_attempts).Count -ne 0 -or
        [string]$r7Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r7Failed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R7 failure did not preserve the strict zero-action/MR2 boundary'
    }
    $r7Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r7OpenDocRpcFailInputLock | ConvertFrom-Json
    $r7Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r7OpenDocRpcFailReadiness | ConvertFrom-Json
    if ($r7Lock.schema -ne 'B51R1_S05R2_J01_R7_CREATE_INPUT_LOCK_V1' -or
        $r7Lock.status -ne 'PASS_S05R2_J01_R7_CREATE_INPUTS_HASH_LOCKED' -or
        [long]$r7Lock.runtime_boundary.solidworks_process_id -ne 29056 -or
        [long]$r7Lock.runtime_boundary.process_count -ne 1 -or
        [long]$r7Lock.runtime_boundary.document_count -ne 0 -or
        [double]$r7Lock.runtime_boundary.zero_com_quiet_window_seconds -lt 60 -or
        @($r7Lock.recovery_prerequisites).Count -ne 7 -or
        $r7Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r7Ready.expected_process_id -ne 29056 -or [long]$r7Ready.observed_process_id -ne 29056 -or
        [long]$r7Ready.document_count -ne 0 -or $r7Ready.active_document_present -ne $false) {
        throw 'J01 R7 readiness/input-lock boundary mismatch'
    }
    $r7ProgressText = (Get-Content -Raw -Encoding UTF8 -LiteralPath $r7OpenDocRpcFailProgress).Trim()
    if ($r7ProgressText -notmatch '^J01_R7_CREATE_START 2026-08-03T17:55:46\.5662309Z$') {
        throw 'J01 R7 progress no longer proves failure before preload completion'
    }
    $r7Incident = Get-Content -Raw -Encoding UTF8 -LiteralPath $r7GraphicsIncident | ConvertFrom-Json
    if ($r7Incident.schema -ne 'B51R1_S05R2_J01_R7_NVIDIA_OPENGL_OOM_FAIL_CLOSED_INCIDENT_V1' -or
        $r7Incident.status -ne 'R7_RPC_FAILURE_GRAPHICS_CAUSE_FROZEN' -or
        $r7Incident.gate_pass -isnot [bool] -or $r7Incident.gate_pass -ne $true -or
        [string]$r7Incident.windows_application_event.provider -ne 'NVIDIA OpenGL Driver' -or
        [long]$r7Incident.windows_application_event.event_id -ne 2 -or
        [long]$r7Incident.windows_application_event.record_id -ne 1473144 -or
        [string]$r7Incident.windows_application_event.time_created_utc -ne '2026-08-03T17:56:09.2150199Z' -or
        [long]$r7Incident.windows_application_event.system_execution_process_id -ne 29056 -or
        [string]$r7Incident.windows_application_event.message -notmatch 'out of memory error' -or
        [string]$r7Incident.r7_failure_receipt.sha256 -ne $r7OpenDocRpcFailReceiptSha256 -or
        [string]$r7Incident.authorized_recovery.argument -ne $softwareOglArgument -or
        $r7Incident.authorized_recovery.sw_disable_exit_app_argument_allowed -ne $false -or
        $r7Incident.authorized_recovery.persistent_registry_change_allowed -ne $false) {
        throw 'J01 R7 frozen NVIDIA OpenGL out-of-memory incident prerequisite mismatch'
    }

    Assert-File $r8DefinitionIdentityFailReceipt $r8DefinitionIdentityFailReceiptBytes $r8DefinitionIdentityFailReceiptSha256 'J01 R8 definition identity failure receipt'
    Assert-File $r8DefinitionIdentityFailInputLock $r8DefinitionIdentityFailInputLockBytes $r8DefinitionIdentityFailInputLockSha256 'J01 R8 definition identity failure input lock'
    Assert-File $r8DefinitionIdentityFailReadiness $r8DefinitionIdentityFailReadinessBytes $r8DefinitionIdentityFailReadinessSha256 'J01 R8 definition identity failure readiness'
    Assert-File $r8DefinitionIdentityFailProgress $r8DefinitionIdentityFailProgressBytes $r8DefinitionIdentityFailProgressSha256 'J01 R8 definition identity failure progress'
    Assert-File $r8StaticRelease $r8StaticReleaseBytes $r8StaticReleaseSha256 'J01 R8 static release'
    Assert-File $r8Activation $r8ActivationBytes $r8ActivationSha256 'J01 R8 Create-only activation'
    Assert-File $r8Source $r8SourceBytes $r8SourceSha256 'J01 R8 source'
    Assert-File $r8Runner $r8RunnerBytes $r8RunnerSha256 'J01 R8 runner'
    Assert-File $r8Binary $r8BinaryBytes $r8BinarySha256 'J01 R8 binary'
    foreach ($path in $r8AbsentOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R8 unexpectedly produced a mechanical output: $path" }
    }

    $r8Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r8DefinitionIdentityFailReceipt | ConvertFrom-Json
    if ($r8Failed.schema -ne 'B51R1_S05R2_J01_R8_NATIVE_PILOT_CREATE_V1' -or
        $r8Failed.status -ne 'S05R2_J01_R8_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r8Failed.gate_pass -isnot [bool] -or $r8Failed.gate_pass -ne $false -or
        [long]$r8Failed.expected_process_id -ne 56288 -or
        [string]$r8Failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$r8Failed.exception -notmatch 'Coincident entity readback mismatch: J00_ROOT_X_COINCIDENT' -or
        [string]$r8Failed.exception -notmatch 'CreateCoincidentMate') {
        throw 'J01 R8 first-coincident definition identity failure contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','add_mate5_call_count',
        'transform2_call_count','set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r8Failed.$field -ne 0) { throw "J01 R8 failure crossed a prohibited action boundary at $field" }
    }
    if ([long]$r8Failed.mate_preselection_call_count -ne 2 -or
        [long]$r8Failed.create_mate_data_call_count -ne 1 -or [long]$r8Failed.create_mate_call_count -ne 1 -or
        [long]$r8Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r8Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r8Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r8Failed.link1_hash_after_failure -ne $link1CarrierSha256) {
        throw 'J01 R8 failure action count, document transition, or MR2 boundary mismatch'
    }

    $r8Preloads = @($r8Failed.preload_operations)
    $r8Attempts = @($r8Failed.mate_api_attempts)
    $r8Selections = @($r8Failed.mate_preselection_attempts)
    if ($r8Preloads.Count -ne 2 -or $r8Attempts.Count -ne 1 -or $r8Selections.Count -ne 2) {
        throw 'J01 R8 failure ledger cardinality mismatch'
    }
    $r8BasePreload = @($r8Preloads | Where-Object { $_.role -eq 'BASE_MR2' })
    $r8LinkPreload = @($r8Preloads | Where-Object { $_.role -eq 'LINK1_MR2' })
    if ($r8BasePreload.Count -ne 1 -or $r8LinkPreload.Count -ne 1) {
        throw 'J01 R8 preload roles are not unique'
    }
    if ([IO.Path]::GetFullPath([string]$r8BasePreload[0].path) -ne [IO.Path]::GetFullPath($baseCarrier) -or
        [long]$r8BasePreload[0].bytes -ne $baseCarrierBytes -or
        [string]$r8BasePreload[0].sha256_before -ne $baseCarrierSha256 -or
        [string]$r8BasePreload[0].sha256_after_open -ne $baseCarrierSha256 -or
        [string]$r8BasePreload[0].open_options -ne 'SILENT_READ_ONLY' -or
        $r8BasePreload[0].opened_read_only -ne $true -or $r8BasePreload[0].model_returned -ne $true -or
        [long]$r8BasePreload[0].open_errors -ne 0 -or [long]$r8BasePreload[0].open_warnings -ne 0 -or
        [long]$r8BasePreload[0].document_count_before -ne 0 -or [long]$r8BasePreload[0].document_count_after -ne 1 -or
        $r8BasePreload[0].held_loaded_until_add_component5 -ne $true -or
        $r8BasePreload[0].add_component5_succeeded -ne $true -or
        [long]$r8BasePreload[0].document_count_after_standalone_close -ne 3) {
        throw 'J01 R8 BASE_MR2 read-only preload evidence mismatch'
    }
    if ([IO.Path]::GetFullPath([string]$r8LinkPreload[0].path) -ne [IO.Path]::GetFullPath($link1Carrier) -or
        [long]$r8LinkPreload[0].bytes -ne $link1CarrierBytes -or
        [string]$r8LinkPreload[0].sha256_before -ne $link1CarrierSha256 -or
        [string]$r8LinkPreload[0].sha256_after_open -ne $link1CarrierSha256 -or
        [string]$r8LinkPreload[0].open_options -ne 'SILENT_READ_ONLY' -or
        $r8LinkPreload[0].opened_read_only -ne $true -or $r8LinkPreload[0].model_returned -ne $true -or
        [long]$r8LinkPreload[0].open_errors -ne 0 -or [long]$r8LinkPreload[0].open_warnings -ne 0 -or
        [long]$r8LinkPreload[0].document_count_before -ne 1 -or [long]$r8LinkPreload[0].document_count_after -ne 2 -or
        $r8LinkPreload[0].held_loaded_until_add_component5 -ne $true -or
        $r8LinkPreload[0].standalone_title_closed -ne $false) {
        throw 'J01 R8 LINK1_MR2 read-only preload evidence mismatch'
    }

    $r8Attempt = $r8Attempts[0]
    if ([string]$r8Attempt.name -ne 'J00_ROOT_X_COINCIDENT' -or [long]$r8Attempt.mate_type -ne 0 -or
        [string]$r8Attempt.entity_contract -ne 'IRefPlane/IRefPlane' -or
        [long]$r8Attempt.preselection_count_before_create_mate_data -ne 2 -or
        [long]$r8Attempt.create_mate_data_call_index -ne 1 -or $r8Attempt.mate_data_returned -ne $true -or
        [long]$r8Attempt.create_mate_call_index -ne 1 -or [long]$r8Attempt.create_mate_error_status -ne 1 -or
        $r8Attempt.feature_returned -ne $true -or
        [long]$r8Attempt.selection_count_at_create_mate_return -ne 0 -or
        $r8Attempt.selection_count_at_create_mate_return_is_diagnostic_only -ne $true -or
        [long]$r8Attempt.selection_count_after_post_create_clear -ne 0) {
        throw 'J01 R8 first CreateMate success/post-clear evidence mismatch'
    }
    $r8RootSelection = @($r8Selections | Where-Object { $_.role -eq 'J00_ROOT_X_COINCIDENT_ASSEMBLY_PLANE' })
    $r8BaseSelection = @($r8Selections | Where-Object { $_.role -eq 'J00_ROOT_X_COINCIDENT_BASE_PLANE' })
    if ($r8RootSelection.Count -ne 1 -or $r8BaseSelection.Count -ne 1 -or
        [long]$r8RootSelection[0].select_by_id2_call_index -ne 1 -or $r8RootSelection[0].append -ne $false -or
        [long]$r8BaseSelection[0].select_by_id2_call_index -ne 2 -or $r8BaseSelection[0].append -ne $true -or
        $r8RootSelection[0].identity_gate_pass -ne $true -or $r8BaseSelection[0].identity_gate_pass -ne $true -or
        $r8RootSelection[0].select_by_id2_returned -ne $true -or $r8BaseSelection[0].select_by_id2_returned -ne $true -or
        [long]$r8RootSelection[0].selected_object_type -ne 4 -or [long]$r8BaseSelection[0].selected_object_type -ne 4 -or
        [long]$r8RootSelection[0].selected_object_mark -ne 1 -or [long]$r8BaseSelection[0].selected_object_mark -ne 1 -or
        $null -ne $r8RootSelection[0].selected_owner_component -or $null -ne $r8RootSelection[0].selected_owner_path -or
        [IO.Path]::GetFullPath([string]$r8BaseSelection[0].selected_owner_path) -ne [IO.Path]::GetFullPath($baseCarrier) -or
        $r8RootSelection[0].selected_feature_matches_context_feature -ne $true -or
        $r8BaseSelection[0].selected_feature_matches_context_feature -ne $true -or
        $r8RootSelection[0].selected_owner_matches_expected_component -ne $true -or
        $r8BaseSelection[0].selected_owner_matches_expected_component -ne $true) {
        throw 'J01 R8 SelectionMgr semantic identity/owner ledger mismatch'
    }

    $r8Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r8DefinitionIdentityFailInputLock | ConvertFrom-Json
    $r8Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r8DefinitionIdentityFailReadiness | ConvertFrom-Json
    if ($r8Lock.schema -ne 'B51R1_S05R2_J01_R8_CREATE_INPUT_LOCK_V1' -or
        $r8Lock.status -ne 'PASS_S05R2_J01_R8_CREATE_INPUTS_HASH_LOCKED' -or $r8Lock.mode -ne 'Create' -or
        [long]$r8Lock.runtime_boundary.solidworks_process_id -ne 56288 -or
        [long]$r8Lock.runtime_boundary.launch_handle_process_id -ne 56288 -or
        $r8Lock.runtime_boundary.launch_handle_matches_sole_process -ne $true -or
        [long]$r8Lock.runtime_boundary.process_count -ne 1 -or [long]$r8Lock.runtime_boundary.document_count -ne 0 -or
        [double]$r8Lock.runtime_boundary.zero_com_quiet_window_seconds -lt 60 -or
        [string]$r8Lock.runtime_boundary.launch_mode -ne 'ONE_SESSION_FORCE_SOFTWARE_OPENGL' -or
        @($r8Lock.runtime_boundary.requested_arguments).Count -ne 1 -or
        [string]$r8Lock.runtime_boundary.requested_arguments[0] -ne $softwareOglArgument -or
        $r8Lock.runtime_boundary.sw_disable_exit_app_requested -ne $false -or
        $r8Lock.runtime_boundary.swsafe_mode_requested -ne $false -or
        [long]$r8Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r8Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        $r8Lock.runtime_boundary.persistent_registry_modified -ne $false -or
        @($r8Lock.recovery_prerequisites).Count -ne 8 -or @($r8Lock.locked_items).Count -ne 18 -or
        [long]$r8Lock.tool_static_release.source.bytes -ne $r8SourceBytes -or
        [string]$r8Lock.tool_static_release.source.sha256 -ne $r8SourceSha256 -or
        [long]$r8Lock.tool_static_release.binary.bytes -ne $r8BinaryBytes -or
        [string]$r8Lock.tool_static_release.binary.sha256 -ne $r8BinarySha256) {
        throw 'J01 R8 readiness/input-lock runtime or tool boundary mismatch'
    }
    foreach ($field in @('transform2_allowed','move_component_allowed','set_transform_and_solve_allowed',
        'mate_controller_truth_allowed','source_carrier_save_allowed','persistent_registry_write_allowed',
        'formal_s05_output_allowed','t005_authorized')) {
        if ($r8Lock.transaction.$field -ne $false) { throw "J01 R8 input lock unexpectedly authorized $field" }
    }
    if ($r8Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r8Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r8Ready.expected_process_id -ne 56288 -or [long]$r8Ready.observed_process_id -ne 56288 -or
        $r8Ready.visible -ne $true -or $r8Ready.startup_process_completed -ne $true -or
        [long]$r8Ready.document_count -ne 0 -or $r8Ready.active_document_present -ne $false) {
        throw 'J01 R8 readiness receipt mismatch'
    }
    $r8ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r8DefinitionIdentityFailProgress).TrimEnd() -split '\r?\n')
    if ($r8ProgressLines.Count -ne 2 -or
        $r8ProgressLines[0] -ne 'J01_R8_CREATE_START 2026-08-03T18:49:44.2367382Z' -or
        $r8ProgressLines[1] -ne 'J01_R8_CREATE_FAIL Coincident entity readback mismatch: J00_ROOT_X_COINCIDENT') {
        throw 'J01 R8 progress no longer proves the exact first-mate readback failure'
    }
    $r8Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r8StaticRelease | ConvertFrom-Json
    if ($r8Release.schema -ne 'B51R1_S05R2_J01_R8_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r8Release.status -ne 'STATIC_RELEASE_PASS' -or $r8Release.gate_pass -ne $true -or
        $r8Release.runtime_executed -ne $false -or
        [long]$r8Release.runner.recovery_prerequisite_count -ne 8 -or
        [string]$r8Release.source.sha256 -ne $r8SourceSha256 -or
        [string]$r8Release.runner.sha256 -ne $r8RunnerSha256 -or
        [string]$r8Release.binary.sha256 -ne $r8BinarySha256 -or
        $r8Release.binary.double_compile_byte_identical -ne $true -or
        $r8Release.cold_verify_authorized -ne $false -or
        $r8Release.formal_s05_output_allowed -ne $false -or $r8Release.t005_authorized -ne $false) {
        throw 'J01 R8 static release contract mismatch'
    }

    Assert-File $r9SemanticLedgerFailReceipt $r9SemanticLedgerFailReceiptBytes $r9SemanticLedgerFailReceiptSha256 'J01 R9 semantic-ledger failure receipt'
    Assert-File $r9SemanticLedgerFailInputLock $r9SemanticLedgerFailInputLockBytes $r9SemanticLedgerFailInputLockSha256 'J01 R9 semantic-ledger failure input lock'
    Assert-File $r9SemanticLedgerFailReadiness $r9SemanticLedgerFailReadinessBytes $r9SemanticLedgerFailReadinessSha256 'J01 R9 semantic-ledger failure readiness'
    Assert-File $r9SemanticLedgerFailProgress $r9SemanticLedgerFailProgressBytes $r9SemanticLedgerFailProgressSha256 'J01 R9 semantic-ledger failure progress'
    Assert-File $r9StaticRelease $r9StaticReleaseBytes $r9StaticReleaseSha256 'J01 R9 static release'
    Assert-File $r9Activation $r9ActivationBytes $r9ActivationSha256 'J01 R9 Create-only activation'
    Assert-File $r9Source $r9SourceBytes $r9SourceSha256 'J01 R9 source'
    Assert-File $r9Runner $r9RunnerBytes $r9RunnerSha256 'J01 R9 runner'
    Assert-File $r9Binary $r9BinaryBytes $r9BinarySha256 'J01 R9 binary'
    foreach ($path in $r9AbsentOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R9 unexpectedly produced a mechanical output: $path" }
    }

    $r9Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r9SemanticLedgerFailReceipt | ConvertFrom-Json
    if ($r9Failed.schema -ne 'B51R1_S05R2_J01_R9_NATIVE_PILOT_CREATE_V1' -or
        $r9Failed.status -ne 'S05R2_J01_R9_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r9Failed.gate_pass -isnot [bool] -or $r9Failed.gate_pass -ne $false -or
        [long]$r9Failed.expected_process_id -ne 48992 -or
        [string]$r9Failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$r9Failed.exception -notmatch 'Coincident semantic entity readback mismatch: J00_ROOT_X_COINCIDENT' -or
        [string]$r9Failed.exception -notmatch 'CreateCoincidentMate') {
        throw 'J01 R9 semantic-ledger false-negative failure contract mismatch'
    }
    foreach ($field in @('save_as_call_count','save3_call_count','add_mate5_call_count',
        'transform2_call_count','set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r9Failed.$field -ne 0) { throw "J01 R9 failure crossed a prohibited action boundary at $field" }
    }
    if ([long]$r9Failed.mate_preselection_call_count -ne 2 -or
        [long]$r9Failed.create_mate_data_call_count -ne 1 -or [long]$r9Failed.create_mate_call_count -ne 1 -or
        [long]$r9Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r9Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r9Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r9Failed.link1_hash_after_failure -ne $link1CarrierSha256 -or
        @($r9Failed.preload_operations).Count -ne 2 -or @($r9Failed.mate_api_attempts).Count -ne 1 -or
        @($r9Failed.mate_preselection_attempts).Count -ne 2) {
        throw 'J01 R9 failure action, preload, document, or MR2 boundary mismatch'
    }
    $r9BasePreload = @($r9Failed.preload_operations | Where-Object { $_.role -eq 'BASE_MR2' })
    $r9LinkPreload = @($r9Failed.preload_operations | Where-Object { $_.role -eq 'LINK1_MR2' })
    if ($r9BasePreload.Count -ne 1 -or $r9LinkPreload.Count -ne 1 -or
        [string]$r9BasePreload[0].open_options -ne 'SILENT_READ_ONLY' -or
        [string]$r9LinkPreload[0].open_options -ne 'SILENT_READ_ONLY' -or
        [string]$r9BasePreload[0].sha256_before -ne $baseCarrierSha256 -or
        [string]$r9BasePreload[0].sha256_after_open -ne $baseCarrierSha256 -or
        [string]$r9LinkPreload[0].sha256_before -ne $link1CarrierSha256 -or
        [string]$r9LinkPreload[0].sha256_after_open -ne $link1CarrierSha256 -or
        [long]$r9BasePreload[0].open_errors -ne 0 -or [long]$r9BasePreload[0].open_warnings -ne 0 -or
        [long]$r9LinkPreload[0].open_errors -ne 0 -or [long]$r9LinkPreload[0].open_warnings -ne 0 -or
        $r9BasePreload[0].opened_read_only -ne $true -or $r9LinkPreload[0].opened_read_only -ne $true) {
        throw 'J01 R9 read-only preload evidence mismatch'
    }

    $r9Attempt = @($r9Failed.mate_api_attempts)[0]
    if ([string]$r9Attempt.name -ne 'J00_ROOT_X_COINCIDENT' -or [long]$r9Attempt.mate_type -ne 0 -or
        [long]$r9Attempt.preselection_count_before_create_mate_data -ne 2 -or
        [long]$r9Attempt.create_mate_data_call_index -ne 1 -or $r9Attempt.mate_data_returned -ne $true -or
        [long]$r9Attempt.create_mate_call_index -ne 1 -or [long]$r9Attempt.create_mate_error_status -ne 1 -or
        $r9Attempt.feature_returned -ne $true -or
        [long]$r9Attempt.selection_count_at_create_mate_return -ne 0 -or
        $r9Attempt.selection_count_at_create_mate_return_is_diagnostic_only -ne $true -or
        [long]$r9Attempt.selection_count_after_post_create_clear -ne 0 -or
        [long]$r9Attempt.definition_entity_count -ne 2 -or
        $r9Attempt.definition_iunknown_pair_match_diagnostic_only -ne $false -or
        $r9Attempt.definition_semantic_pair_match -ne $false -or
        [string]$r9Attempt.definition_identity_authority -ne 'IFeature.GetNameForSelection_PATH_TOKEN_NAME_TYPE') {
        throw 'J01 R9 successful first CreateMate/readback false-negative evidence mismatch'
    }
    $r9DefinitionPaths = @($r9Attempt.definition_entities | ForEach-Object { [string]$_.selection_path } | Sort-Object)
    $r9SelectionPaths = @($r9Attempt.entity_selections | ForEach-Object { [string]$_.assembly_context_selection_path } | Sort-Object)
    if ($r9DefinitionPaths.Count -ne 2 -or $r9SelectionPaths.Count -ne 2 -or
        @(Compare-Object -ReferenceObject $r9SelectionPaths -DifferenceObject $r9DefinitionPaths -CaseSensitive:$false).Count -ne 0 -or
        @($r9Attempt.definition_entities | Where-Object { $_.selection_token -ne 'PLANE' -or $_.feature_type -ne 'RefPlane' }).Count -ne 0) {
        throw 'J01 R9 GetDefinition entities no longer prove exact unordered selection-ledger equivalence'
    }

    $r9Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r9SemanticLedgerFailInputLock | ConvertFrom-Json
    $r9Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r9SemanticLedgerFailReadiness | ConvertFrom-Json
    if ($r9Lock.schema -ne 'B51R1_S05R2_J01_R9_CREATE_INPUT_LOCK_V1' -or
        $r9Lock.status -ne 'PASS_S05R2_J01_R9_CREATE_INPUTS_HASH_LOCKED' -or $r9Lock.mode -ne 'Create' -or
        [long]$r9Lock.runtime_boundary.solidworks_process_id -ne 48992 -or
        [long]$r9Lock.runtime_boundary.launch_handle_process_id -ne 48992 -or
        $r9Lock.runtime_boundary.launch_handle_matches_sole_process -ne $true -or
        [long]$r9Lock.runtime_boundary.process_count -ne 1 -or [long]$r9Lock.runtime_boundary.document_count -ne 0 -or
        [double]$r9Lock.runtime_boundary.zero_com_quiet_window_seconds -lt 60 -or
        [long]$r9Lock.runtime_boundary.predecessor_process_id -ne 56288 -or
        $r9Lock.runtime_boundary.predecessor_pid_present -ne $false -or
        [long]$r9Lock.runtime_boundary.prelaunch_sldworks_process_count -ne 0 -or
        [string]$r9Lock.runtime_boundary.launch_mode -ne 'ONE_SESSION_FORCE_SOFTWARE_OPENGL' -or
        @($r9Lock.runtime_boundary.requested_arguments).Count -ne 1 -or
        [string]$r9Lock.runtime_boundary.requested_arguments[0] -ne $softwareOglArgument -or
        $r9Lock.runtime_boundary.sw_disable_exit_app_requested -ne $false -or
        [long]$r9Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r9Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        $r9Lock.runtime_boundary.persistent_registry_modified -ne $false -or
        @($r9Lock.recovery_prerequisites).Count -ne 9 -or @($r9Lock.locked_items).Count -ne 28 -or
        [long]$r9Lock.mode_activation.bytes -ne $r9ActivationBytes -or
        [string]$r9Lock.mode_activation.sha256 -ne $r9ActivationSha256) {
        throw 'J01 R9 input-lock process, activation, or transaction boundary mismatch'
    }
    foreach ($field in @('transform2_allowed','move_component_allowed','set_transform_and_solve_allowed',
        'mate_controller_truth_allowed','source_carrier_save_allowed','persistent_registry_write_allowed',
        'formal_s05_output_allowed','t005_authorized')) {
        if ($r9Lock.transaction.$field -ne $false) { throw "J01 R9 input lock unexpectedly authorized $field" }
    }
    if ($r9Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r9Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r9Ready.expected_process_id -ne 48992 -or [long]$r9Ready.observed_process_id -ne 48992 -or
        $r9Ready.visible -ne $true -or $r9Ready.startup_process_completed -ne $true -or
        [long]$r9Ready.document_count -ne 0 -or $r9Ready.active_document_present -ne $false) {
        throw 'J01 R9 readiness receipt mismatch'
    }
    $r9ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r9SemanticLedgerFailProgress).TrimEnd() -split '\r?\n')
    if ($r9ProgressLines.Count -ne 2 -or
        $r9ProgressLines[0] -ne 'J01_R9_CREATE_START 2026-08-04T17:57:25.4083439Z' -or
        $r9ProgressLines[1] -ne 'J01_R9_CREATE_FAIL Coincident semantic entity readback mismatch: J00_ROOT_X_COINCIDENT') {
        throw 'J01 R9 progress no longer proves the exact semantic-ledger false negative'
    }
    $r9Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r9StaticRelease | ConvertFrom-Json
    $r9ActivationState = Get-Content -Raw -Encoding UTF8 -LiteralPath $r9Activation | ConvertFrom-Json
    if ($r9Release.schema -ne 'B51R1_S05R2_J01_R9_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r9Release.status -ne 'STATIC_RELEASE_PASS' -or $r9Release.gate_pass -ne $true -or
        $r9Release.runtime_executed -ne $false -or [long]$r9Release.recovery_prerequisite_count -ne 9 -or
        [string]$r9Release.source.sha256 -ne $r9SourceSha256 -or
        [string]$r9Release.runner.sha256 -ne $r9RunnerSha256 -or
        [string]$r9Release.binary.sha256 -ne $r9BinarySha256 -or
        $r9Release.binary.double_compile_byte_identical -ne $true -or
        $r9Release.cold_verify_activation_authorized -ne $false -or
        $r9ActivationState.activation_mode -ne 'CREATE_ONLY' -or
        $r9ActivationState.create_authorized -ne $true -or $r9ActivationState.cold_verify_authorized -ne $false -or
        $r9ActivationState.formal_s05_authorized -ne $false -or $r9ActivationState.t005_authorized -ne $false) {
        throw 'J01 R9 static release/Create-only activation contract mismatch'
    }

    return @(
        [ordered]@{id='HP01_DIRECT_OPEN_PASS_RECEIPT';path=$hp01DirectReceipt;bytes=$hp01DirectReceiptBytes;sha256=$hp01DirectReceiptSha256;status=[string]$direct.status},
        [ordered]@{id='J01_R1_CONTEXT_FAIL_RECEIPT';path=$r1ContextFailReceipt;bytes=$r1ContextFailReceiptBytes;sha256=$r1ContextFailReceiptSha256;status=[string]$failed.status;error_code=2097152},
        [ordered]@{id='J01_R2_RCW_FAIL_RECEIPT';path=$r2RcwFailReceipt;bytes=$r2RcwFailReceiptBytes;sha256=$r2RcwFailReceiptSha256;status=[string]$rcwFailed.status;exception_type=[string]$rcwFailed.exception_type},
        [ordered]@{id='J01_R3_MATE_ENTITY_TYPE_FAIL_RECEIPT';path=$r3EntityTypeFailReceipt;bytes=$r3EntityTypeFailReceiptBytes;sha256=$r3EntityTypeFailReceiptSha256;status=[string]$entityFailed.status;exception_type=[string]$entityFailed.exception_type;reported_mate_call_counters_known_inaccurate=$true;actual_execution_reached='IAssemblyDoc.CreateMate'},
        [ordered]@{id='J01_R4_INCORRECT_SELECTIONS_FAIL_RECEIPT';path=$r4IncorrectSelectionsFailReceipt;bytes=$r4IncorrectSelectionsFailReceiptBytes;sha256=$r4IncorrectSelectionsFailReceiptSha256;status=[string]$selectionFailed.status;error_status=4;actual_create_mate_call_count=1},
        [ordered]@{id='J01_R5_CORRESPONDING_SPECIFIC_FAIL_RECEIPT';path=$r5CorrespondingSpecificFailReceipt;bytes=$r5CorrespondingSpecificFailReceiptBytes;sha256=$r5CorrespondingSpecificFailReceiptSha256;status=[string]$correspondingFailed.status;select_by_id2_call_count=1;direct_specific_diagnostic_failure=$true},
        [ordered]@{id='J01_R6_CREATE_MATE_SELECTION_CONSUMPTION_FAIL_RECEIPT';path=$r6SelectionConsumptionFailReceipt;bytes=$r6SelectionConsumptionFailReceiptBytes;sha256=$r6SelectionConsumptionFailReceiptSha256;status=[string]$selectionConsumptionFailed.status;select_by_id2_call_count=2;create_mate_data_call_count=1;create_mate_call_count=1;create_mate_error_status=1;feature_returned=$true;selection_count_at_return=0},
        [ordered]@{
            id='J01_R7_FIRST_OPENDOC6_RPC_FAIL_WITH_NVIDIA_OPENGL_OOM';path=$r7OpenDocRpcFailReceipt
            bytes=$r7OpenDocRpcFailReceiptBytes;sha256=$r7OpenDocRpcFailReceiptSha256;status=[string]$r7Failed.status
            exception_type=[string]$r7Failed.exception_type;hresult='0x800706BE';failed_api='ISldWorks.OpenDoc6'
            action_counts_zero=$true;ledger_arrays_empty=$true;mr2_hashes_stable=$true;mechanical_outputs_absent=$true
            input_lock=[ordered]@{path=$r7OpenDocRpcFailInputLock;bytes=$r7OpenDocRpcFailInputLockBytes;sha256=$r7OpenDocRpcFailInputLockSha256}
            readiness=[ordered]@{path=$r7OpenDocRpcFailReadiness;bytes=$r7OpenDocRpcFailReadinessBytes;sha256=$r7OpenDocRpcFailReadinessSha256}
            progress=[ordered]@{path=$r7OpenDocRpcFailProgress;bytes=$r7OpenDocRpcFailProgressBytes;sha256=$r7OpenDocRpcFailProgressSha256}
            graphics_incident=[ordered]@{path=$r7GraphicsIncident;bytes=$r7GraphicsIncidentBytes;sha256=$r7GraphicsIncidentSha256}
            nvidia_opengl_event=[ordered]@{provider='NVIDIA OpenGL Driver';event_id=2;record_id=1473144;utc='2026-08-03T17:56:09.2150199Z';process_id=29056;failure='OPENGL_OUT_OF_MEMORY';source='FROZEN_APPEND_ONLY_INCIDENT'}
            recovery_action='ONE_SESSION_FORCE_SOFTWARE_OPENGL'
        },
        [ordered]@{
            id='J01_R8_FIRST_COINCIDENT_DEFINITION_IUNKNOWN_IDENTITY_FAIL_CLOSED';path=$r8DefinitionIdentityFailReceipt
            bytes=$r8DefinitionIdentityFailReceiptBytes;sha256=$r8DefinitionIdentityFailReceiptSha256;status=[string]$r8Failed.status
            exception_type=[string]$r8Failed.exception_type;failed_mate='J00_ROOT_X_COINCIDENT'
            create_mate_error_status=1;feature_returned=$true;post_clear_selection_count=0
            mr2_hashes_stable=$true;mechanical_outputs_absent=$true;historical_normal_exit_not_claimed=$true
            input_lock=[ordered]@{path=$r8DefinitionIdentityFailInputLock;bytes=$r8DefinitionIdentityFailInputLockBytes;sha256=$r8DefinitionIdentityFailInputLockSha256}
            readiness=[ordered]@{path=$r8DefinitionIdentityFailReadiness;bytes=$r8DefinitionIdentityFailReadinessBytes;sha256=$r8DefinitionIdentityFailReadinessSha256}
            progress=[ordered]@{path=$r8DefinitionIdentityFailProgress;bytes=$r8DefinitionIdentityFailProgressBytes;sha256=$r8DefinitionIdentityFailProgressSha256}
            static_release=[ordered]@{path=$r8StaticRelease;bytes=$r8StaticReleaseBytes;sha256=$r8StaticReleaseSha256}
            activation=[ordered]@{path=$r8Activation;bytes=$r8ActivationBytes;sha256=$r8ActivationSha256}
            tool=[ordered]@{
                source=[ordered]@{path=$r8Source;bytes=$r8SourceBytes;sha256=$r8SourceSha256}
                runner=[ordered]@{path=$r8Runner;bytes=$r8RunnerBytes;sha256=$r8RunnerSha256}
                binary=[ordered]@{path=$r8Binary;bytes=$r8BinaryBytes;sha256=$r8BinarySha256}
            }
            recovery_action='SEMANTIC_SELECTION_IDENTITY_READBACK_WITH_IUNKNOWN_DIAGNOSTIC_ONLY'
        },
        [ordered]@{
            id='J01_R9_SELECTION_SPECIFIC_CONTEXT_LOSS_FALSE_NEGATIVE_FAIL_CLOSED';path=$r9SemanticLedgerFailReceipt
            bytes=$r9SemanticLedgerFailReceiptBytes;sha256=$r9SemanticLedgerFailReceiptSha256;status=[string]$r9Failed.status
            exception_type=[string]$r9Failed.exception_type;failed_mate='J00_ROOT_X_COINCIDENT'
            create_mate_error_status=1;feature_returned=$true;post_clear_selection_count=0
            definition_and_selection_ledger_unordered_paths_equal=$true;iunknown_match_diagnostic_only=$false
            mr2_hashes_stable=$true;mechanical_outputs_absent=$true;historical_normal_exit_not_claimed=$true
            input_lock=[ordered]@{path=$r9SemanticLedgerFailInputLock;bytes=$r9SemanticLedgerFailInputLockBytes;sha256=$r9SemanticLedgerFailInputLockSha256}
            readiness=[ordered]@{path=$r9SemanticLedgerFailReadiness;bytes=$r9SemanticLedgerFailReadinessBytes;sha256=$r9SemanticLedgerFailReadinessSha256}
            progress=[ordered]@{path=$r9SemanticLedgerFailProgress;bytes=$r9SemanticLedgerFailProgressBytes;sha256=$r9SemanticLedgerFailProgressSha256}
            static_release=[ordered]@{path=$r9StaticRelease;bytes=$r9StaticReleaseBytes;sha256=$r9StaticReleaseSha256}
            activation=[ordered]@{path=$r9Activation;bytes=$r9ActivationBytes;sha256=$r9ActivationSha256}
            tool=[ordered]@{
                source=[ordered]@{path=$r9Source;bytes=$r9SourceBytes;sha256=$r9SourceSha256}
                runner=[ordered]@{path=$r9Runner;bytes=$r9RunnerBytes;sha256=$r9RunnerSha256}
                binary=[ordered]@{path=$r9Binary;bytes=$r9BinaryBytes;sha256=$r9BinarySha256}
            }
            recovery_action='COMPARE_GETDEFINITION_TO_FROZEN_ASSEMBLY_CONTEXT_SELECTION_LEDGER'
        }
    )
}

function Wait-ForSolidWorks([Diagnostics.Process]$LaunchHandle) {
    $deadline = [DateTimeOffset]::Now.AddMinutes(3)
    while ([DateTimeOffset]::Now -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
        if ($processes.Count -ne 1) { continue }
        $processes[0].Refresh()
        if ($processes[0].Id -eq $LaunchHandle.Id -and $processes[0].Responding -and
            $processes[0].MainWindowHandle -ne [IntPtr]::Zero) {
            return $processes[0].Id
        }
    }
    throw "SOLIDWORKS did not reach the sole visible responsive state; launch PID=$($LaunchHandle.Id)"
}

Assert-File $assemblyTemplate 34942 '37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC' 'Assembly template'
Assert-File $solidworksExe 707392 '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60' 'SOLIDWORKS executable'
Assert-File $interop 2773312 'FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB' 'SOLIDWORKS interop'
Assert-File $readinessDll 5632 'DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2' 'Readiness probe'
Assert-File $toolCompiler $toolCompilerBytes $toolCompilerSha256 'J01 R10 frozen-tool compiler provenance'
if ($toolDllBytes -le 0 -or $toolDllSha256 -eq ('0' * 64)) {
    throw 'J01 R10 is source-only: deterministic compile and append-only binary static freeze are required before execution'
}
Assert-File $toolSource $toolSourceBytes $toolSourceSha256 'J01 Pilot frozen source'
Assert-File $toolDll $toolDllBytes $toolDllSha256 'J01 Pilot frozen binary'
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "$Mode requires zero existing SLDWORKS processes"
}
$persistentSoftwareOglBefore = Get-PersistentSoftwareOglValue
if ($persistentSoftwareOglBefore -ne 0) {
    throw 'Persistent Use Software OGL must remain disabled; R10 authorizes only the one-session launch argument'
}

$mr2Inputs = @(Get-Mr2PilotInputs)
$recoveryPrerequisites = @(Get-RecoveryPrerequisites)
if ($recoveryPrerequisites.Count -ne 10) {
    throw "J01 R10 recovery prerequisite count mismatch: $($recoveryPrerequisites.Count)"
}
$prelaunchSolidWorksCount = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
$r9PredecessorPidPresent = @(Get-Process -Id 48992 -ErrorAction SilentlyContinue).Count -ne 0
if ($prelaunchSolidWorksCount -ne 0 -or $r9PredecessorPidPresent) {
    throw 'J01 R10 predecessor process boundary is not clean immediately before launch'
}
$mr2LockedArtifacts = @(
    [ordered]@{id='MR2_PILOT_R1_COLD_GATE';path=$mr2PilotGate;bytes=$mr2PilotGateBytes;sha256=$mr2PilotGateSha256},
    [ordered]@{id='MR2_PILOT_R1_COLD_RECEIPT';path=$mr2PilotReceipt;bytes=$mr2PilotReceiptBytes;sha256=$mr2PilotReceiptSha256}
)
$r8ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R8_INPUT_LOCK';path=$r8DefinitionIdentityFailInputLock;bytes=$r8DefinitionIdentityFailInputLockBytes;sha256=$r8DefinitionIdentityFailInputLockSha256},
    [ordered]@{id='J01_R8_READINESS';path=$r8DefinitionIdentityFailReadiness;bytes=$r8DefinitionIdentityFailReadinessBytes;sha256=$r8DefinitionIdentityFailReadinessSha256},
    [ordered]@{id='J01_R8_PROGRESS';path=$r8DefinitionIdentityFailProgress;bytes=$r8DefinitionIdentityFailProgressBytes;sha256=$r8DefinitionIdentityFailProgressSha256},
    [ordered]@{id='J01_R8_STATIC_RELEASE';path=$r8StaticRelease;bytes=$r8StaticReleaseBytes;sha256=$r8StaticReleaseSha256},
    [ordered]@{id='J01_R8_ACTIVATION';path=$r8Activation;bytes=$r8ActivationBytes;sha256=$r8ActivationSha256},
    [ordered]@{id='J01_R8_SOURCE';path=$r8Source;bytes=$r8SourceBytes;sha256=$r8SourceSha256},
    [ordered]@{id='J01_R8_RUNNER';path=$r8Runner;bytes=$r8RunnerBytes;sha256=$r8RunnerSha256},
    [ordered]@{id='J01_R8_BINARY';path=$r8Binary;bytes=$r8BinaryBytes;sha256=$r8BinarySha256}
)
$r9ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R9_INPUT_LOCK';path=$r9SemanticLedgerFailInputLock;bytes=$r9SemanticLedgerFailInputLockBytes;sha256=$r9SemanticLedgerFailInputLockSha256},
    [ordered]@{id='J01_R9_READINESS';path=$r9SemanticLedgerFailReadiness;bytes=$r9SemanticLedgerFailReadinessBytes;sha256=$r9SemanticLedgerFailReadinessSha256},
    [ordered]@{id='J01_R9_PROGRESS';path=$r9SemanticLedgerFailProgress;bytes=$r9SemanticLedgerFailProgressBytes;sha256=$r9SemanticLedgerFailProgressSha256},
    [ordered]@{id='J01_R9_STATIC_RELEASE';path=$r9StaticRelease;bytes=$r9StaticReleaseBytes;sha256=$r9StaticReleaseSha256},
    [ordered]@{id='J01_R9_ACTIVATION';path=$r9Activation;bytes=$r9ActivationBytes;sha256=$r9ActivationSha256},
    [ordered]@{id='J01_R9_SOURCE';path=$r9Source;bytes=$r9SourceBytes;sha256=$r9SourceSha256},
    [ordered]@{id='J01_R9_RUNNER';path=$r9Runner;bytes=$r9RunnerBytes;sha256=$r9RunnerSha256},
    [ordered]@{id='J01_R9_BINARY';path=$r9Binary;bytes=$r9BinaryBytes;sha256=$r9BinarySha256}
)
$recoveryLockedArtifacts = @($recoveryPrerequisites) + @($r8ClosureLockedArtifacts) + @($r9ClosureLockedArtifacts)

$readinessReceipt = Join-Path $sessionRoot "B51R1_S05R2_J01_R10_$($Mode.ToUpperInvariant())_READINESS_RECEIPT.json"
$inputLock = Join-Path $sessionRoot "B51R1_S05R2_J01_R10_$($Mode.ToUpperInvariant())_INPUT_LOCK.json"
$modeOutputs = if ($Mode -eq 'Create') {
    @($readinessReceipt,$inputLock,$j00Assembly,$pilotAssembly,$j00Checkpoint,$createReceipt,$createProgress,$createGate)
} else {
    @($readinessReceipt,$inputLock,$coldReceipt,$coldProgress,$finalGate)
}
foreach ($path in $modeOutputs) {
    if (Test-Path -LiteralPath $path) { throw "Append-only $Mode output exists: $path" }
}

$coldLockedArtifacts = @()
if ($Mode -eq 'ColdVerify') {
    if (-not (Test-Path -LiteralPath $createGate -PathType Leaf)) { throw "J01 Create Gate missing: $createGate" }
    $created = Get-Content -Raw -Encoding UTF8 -LiteralPath $createGate | ConvertFrom-Json
    if ($created.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_1R_CREATE_GATE_V1' -or
        $created.status -ne 'S05R2_J01_R10_NATIVE_1R_PILOT_CREATE_PASS' -or
        $created.gate_pass -isnot [bool] -or $created.gate_pass -ne $true) {
        throw 'J01 R10 Create Gate is not PASS'
    }
    if ($created.cold_reopen_authorized -isnot [bool] -or $created.cold_reopen_authorized -ne $false) {
        throw 'J01 R10 Create Gate improperly self-authorizes cold reopen'
    }
    if ([IO.Path]::GetFullPath([string]$created.receipt.path) -ne [IO.Path]::GetFullPath($createReceipt)) {
        throw 'J01 Create Gate receipt path mismatch'
    }
    if ([IO.Path]::GetFullPath([string]$created.output.path) -ne [IO.Path]::GetFullPath($pilotAssembly)) {
        throw 'J01 Create Gate output path mismatch'
    }
    Assert-File $createReceipt ([long]$created.receipt.bytes) ([string]$created.receipt.sha256) 'J01 Create receipt'
    Assert-File $pilotAssembly ([long]$created.output.bytes) ([string]$created.output.sha256) 'J01 Pilot assembly'
    $createdReceipt = Get-Content -Raw -Encoding UTF8 -LiteralPath $createReceipt | ConvertFrom-Json
    if ($createdReceipt.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_CREATE_V1' -or
        $createdReceipt.status -ne 'S05R2_J01_R10_NATIVE_1R_PILOT_CREATE_PASS' -or
        $createdReceipt.gate_pass -isnot [bool] -or $createdReceipt.gate_pass -ne $true) {
        throw 'J01 R10 Create receipt is not PASS'
    }
    if ([IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath($pilotAssembly) -or
        [IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath([string]$created.output.path) -or
        [long]$createdReceipt.output.bytes -ne [long]$created.output.bytes -or
        [string]$createdReceipt.output.sha256 -ne [string]$created.output.sha256) {
        throw 'J01 Create receipt output binding differs from the Create Gate output'
    }
    $coldLockedArtifacts = @(
        [ordered]@{id='J01_R10_CREATE_GATE';path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate},
        [ordered]@{id='J01_R10_CREATE_RECEIPT';path=$createReceipt;bytes=[long]$created.receipt.bytes;sha256=[string]$created.receipt.sha256},
        [ordered]@{id='J01_R10_PILOT_ASSEMBLY';path=$pilotAssembly;bytes=[long]$created.output.bytes;sha256=[string]$created.output.sha256}
    )
}
$modeActivationLockedArtifacts = @(Get-ModeActivation $Mode)
[IO.Directory]::CreateDirectory($sessionRoot) | Out-Null

$launchHandle = $null
$launchedPid = $null
$exitCode = 1
try {
    $launchHandle = Start-Process -FilePath $solidworksExe -ArgumentList @($softwareOglArgument) -PassThru
    $launchStartInfoArguments = [string]$launchHandle.StartInfo.Arguments
    if ($launchStartInfoArguments -notmatch '(?i)(^|\s)/ForceSoftwareOGL($|\s)') {
        throw 'SOLIDWORKS launch handle does not retain the requested /ForceSoftwareOGL argument'
    }
    $launchedPid = Wait-ForSolidWorks $launchHandle
    $quietStart = [DateTimeOffset]::Now
    Start-Sleep -Seconds 60
    $quietEnd = [DateTimeOffset]::Now
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    if ($processes.Count -ne 1) { throw 'J01 Pilot lost the sole SOLIDWORKS process' }
    $processes[0].Refresh()
    if ($processes[0].Id -ne $launchedPid -or -not $processes[0].Responding -or $processes[0].MainWindowHandle -eq [IntPtr]::Zero) {
        throw 'J01 Pilot process was not stable after the zero-COM window'
    }
    $observedProcessPath = $processes[0].MainModule.FileName
    if ([IO.Path]::GetFullPath($observedProcessPath) -ne [IO.Path]::GetFullPath($solidworksExe)) {
        throw 'J01 Pilot process path differs from the frozen SOLIDWORKS executable'
    }
    $persistentSoftwareOglAfterLaunch = Get-PersistentSoftwareOglValue
    if ($persistentSoftwareOglAfterLaunch -ne 0) {
        throw 'R10 one-session Software OpenGL launch changed the persistent registry value'
    }
    Assert-File $toolSource $toolSourceBytes $toolSourceSha256 'J01 Pilot frozen source after zero-COM window'
    Assert-File $toolDll $toolDllBytes $toolDllSha256 'J01 Pilot frozen binary after zero-COM window'
    foreach ($item in $mr2LockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_LOCK_$($item.id)"
    }
    foreach ($item in $recoveryLockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "RECOVERY_LOCK_$($item.id)"
    }
    foreach ($item in $coldLockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "COLD_LOCK_$($item.id)"
    }
    foreach ($item in $modeActivationLockedArtifacts) {
        Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "ACTIVATION_LOCK_$($item.id)"
    }

    Add-Type -Path $interop
    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $readinessDll).Path)
    $readyCode = [B51R1SR03ExistingSolidWorksProbe]::Run($launchedPid,$readinessReceipt)
    if ($readyCode -ne 0) { throw "Readiness probe returned $readyCode" }
    $ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $readinessReceipt | ConvertFrom-Json
    if ($ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') {
        throw 'J01 Pilot readiness did not pass'
    }

    $lockedItems = @(
        [ordered]@{id='CONTRACT_V4';path=(Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md');bytes=(Get-Item (Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md')).Length;sha256=Get-Sha (Join-Path $carrierDir 'B51R1_CARRIER_ARCHITECTURE_CONTRACT_V4.md')},
        [ordered]@{id='NATIVE_DRIVER_MAPPING_V2';path=(Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv');bytes=(Get-Item (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv')).Length;sha256=Get-Sha (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_DRIVER_MAPPING_V2.csv')},
        [ordered]@{id='NATIVE_JOINT_REGISTER_V2';path=(Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv');bytes=(Get-Item (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv')).Length;sha256=Get-Sha (Join-Path $root '03_CAD\10_KINEMATIC_CARRIERS\B51R1_NATIVE_JOINT_REGISTER_V2.csv')},
        [ordered]@{id='TOLERANCE_AUTHORITY';path=(Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml');bytes=(Get-Item (Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml')).Length;sha256=Get-Sha (Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml')},
        [ordered]@{id='J01_TOOL_SOURCE';path=$toolSource;bytes=$toolSourceBytes;sha256=$toolSourceSha256},
        [ordered]@{id='J01_TOOL_BINARY';path=$toolDll;bytes=$toolDllBytes;sha256=$toolDllSha256},
        [ordered]@{id='J01_TOOL_COMPILER';path=$toolCompiler;bytes=$toolCompilerBytes;sha256=$toolCompilerSha256},
        [ordered]@{id='READINESS_RECEIPT';path=$readinessReceipt;bytes=(Get-Item $readinessReceipt).Length;sha256=Get-Sha $readinessReceipt}
    )
    $lockedItems += $mr2LockedArtifacts
    $lockedItems += $recoveryLockedArtifacts
    if ($Mode -eq 'ColdVerify') { $lockedItems += $coldLockedArtifacts }
    $lockedItems += $modeActivationLockedArtifacts
    $lock = [ordered]@{
        schema="B51R1_S05R2_J01_R10_$($Mode.ToUpperInvariant())_INPUT_LOCK_V1"
        generated_at=[DateTimeOffset]::Now.ToString('o')
        status="PASS_S05R2_J01_R10_$($Mode.ToUpperInvariant())_INPUTS_HASH_LOCKED"
        mode=$Mode
        runtime_boundary=[ordered]@{
            solidworks_process_id=$launchedPid;launch_handle_process_id=$launchHandle.Id
            launch_handle_matches_sole_process=($launchHandle.Id -eq $launchedPid);process_count=1;document_count=0
            predecessor_process_id=48992;predecessor_pid_present=$r9PredecessorPidPresent
            prelaunch_sldworks_process_count=$prelaunchSolidWorksCount
            zero_com_quiet_window_seconds=($quietEnd-$quietStart).TotalSeconds
            executable_path=$observedProcessPath;launch_mode='ONE_SESSION_FORCE_SOFTWARE_OPENGL'
            requested_arguments=@($softwareOglArgument);launch_start_info_arguments=$launchStartInfoArguments
            sw_disable_exit_app_requested=$false;swsafe_mode_requested=$false
            persistent_use_software_ogl_before=$persistentSoftwareOglBefore
            persistent_use_software_ogl_after_launch=$persistentSoftwareOglAfterLaunch
            persistent_registry_modified=$false
        }
        transaction=[ordered]@{transform2_allowed=$false;move_component_allowed=$false;set_transform_and_solve_allowed=$false;mate_controller_truth_allowed=$false;source_carrier_save_allowed=$false;persistent_registry_write_allowed=$false;formal_s05_output_allowed=$false;t005_authorized=$false}
        tool_static_release=[ordered]@{
            source=[ordered]@{path=$toolSource;bytes=$toolSourceBytes;sha256=$toolSourceSha256}
            binary=[ordered]@{path=$toolDll;bytes=$toolDllBytes;sha256=$toolDllSha256}
            compiler=[ordered]@{path=$toolCompiler;bytes=$toolCompilerBytes;sha256=$toolCompilerSha256;arguments='/nologo /target:library /platform:x64 /optimize+ /deterministic+'}
            interop=[ordered]@{path=$interop;bytes=2773312;sha256='FA85C4E9B26D0BA996C53362E95AFE42AB563C96F27D87CD6809D262F3D3C4CB'}
        }
        mr2_inputs=$mr2Inputs
        recovery_prerequisites=$recoveryPrerequisites
        mode_activation=$modeActivationLockedArtifacts[0]
        locked_items=$lockedItems
        claim_limit='J01_R10_ONE_SESSION_SOFTWARE_OPENGL_TYPED_MATE_ENTITY_RECOVERY_NATIVE_1R_PILOT_ONLY_NO_FORMAL_S05_G4_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    if ($Mode -eq 'Create') {
        $result = [B51R1S05R2J01R10NativePilotTool]::Create(
            $launchedPid,$assemblyTemplate,$baseCarrier,$link1Carrier,$j00Assembly,
            $pilotAssembly,$j00Checkpoint,$createReceipt,$createProgress)
        if ($result -ne 0) { throw "J01 Create tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $createReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_CREATE_V1' -or
            $data.status -ne 'S05R2_J01_R10_NATIVE_1R_PILOT_CREATE_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R10 Create receipt is not PASS'
        }
        if ($data.transform2_call_count -ne 0 -or $data.set_transform_and_solve_call_count -ne 0 -or
            $data.move_component_call_count -ne 0 -or $data.save_as_call_count -ne 2 -or $data.save3_call_count -ne 0 -or
            $data.create_mate_data_call_count -ne 5 -or $data.create_mate_call_count -ne 5 -or
            $data.add_mate5_call_count -ne 0 -or $data.mate_preselection_call_count -ne 13) {
            throw 'J01 Create prohibited API/save count mismatch'
        }
        $mateAttempts = @($data.mate_api_attempts)
        $selectionLedger = @($data.mate_preselection_attempts)
        if ($mateAttempts.Count -ne 5 -or @($data.native_mate_creation).Count -ne 5 -or
            $selectionLedger.Count -ne 13) {
            throw 'J01 R10 Mate API call ledger count mismatch'
        }
        $expectedMateSelectionCounts = @(2,2,2,4,3)
        foreach ($index in 0..4) {
            $attempt = $mateAttempts[$index]
            if ([long]$attempt.create_mate_data_call_index -ne ($index + 1) -or
                [long]$attempt.create_mate_call_index -ne ($index + 1) -or
                $attempt.mate_data_returned -isnot [bool] -or $attempt.mate_data_returned -ne $true -or
                $attempt.feature_returned -isnot [bool] -or $attempt.feature_returned -ne $true -or
                [long]$attempt.create_mate_error_status -ne 1 -or
                [long]$attempt.mate_alignment_requested -ne 0 -or
                [string]$attempt.mate_alignment_name -ne 'ALIGNED' -or
                @($attempt.entity_selections).Count -ne $expectedMateSelectionCounts[$index] -or
                [long]$attempt.preselection_count_before_create_mate_data -ne $expectedMateSelectionCounts[$index] -or
                $attempt.selection_count_at_create_mate_return_is_diagnostic_only -isnot [bool] -or
                $attempt.selection_count_at_create_mate_return_is_diagnostic_only -ne $true -or
                [long]$attempt.selection_count_at_create_mate_return -lt 0 -or
                [long]$attempt.selection_count_at_create_mate_return -gt $expectedMateSelectionCounts[$index] -or
                [long]$attempt.selection_count_after_post_create_clear -ne 0) {
                throw "J01 R10 Mate API call ledger mismatch at index $index"
            }
        }
        $expectedTypes = @(4,4,4,4,4,4,5,5,4,4,4,4,5)
        $expectedMarks = @(1,1,1,1,1,1,1,1,32768,32768,1,1,67108864)
        $expectedAppend = @($false,$true,$false,$true,$false,$true,$false,$true,$true,$true,$false,$true,$true)
        $expectedGlobalIndexes = @(1,2,1,2,1,2,1,2,3,4,1,2,3)
        $expectedMarkedIndexes = @(1,2,1,2,1,2,1,2,1,2,1,2,1)
        foreach ($index in 0..12) {
            $selection = $selectionLedger[$index]
            $expectedToken = if ($expectedTypes[$index] -eq 4) { 'PLANE' } else { 'AXIS' }
            if ([long]$selection.select_by_id2_call_index -ne ($index + 1) -or
                [long]$selection.expected_selection_type -ne $expectedTypes[$index] -or
                [long]$selection.selected_object_type -ne $expectedTypes[$index] -or
                [string]$selection.expected_selection_token -ne $expectedToken -or
                [string]$selection.selection_type_token -ne $expectedToken -or
                [long]$selection.mark -ne $expectedMarks[$index] -or
                [long]$selection.selected_object_mark -ne $expectedMarks[$index] -or
                [long]$selection.selected_object_global_index -ne $expectedGlobalIndexes[$index] -or
                [long]$selection.selected_object_index_for_mark -ne $expectedMarkedIndexes[$index] -or
                [long]$selection.selection_count_before -ne ($expectedGlobalIndexes[$index] - 1) -or
                [long]$selection.selection_count_after -ne $expectedGlobalIndexes[$index] -or
                [long]$selection.marked_selection_count_before -ne ($expectedMarkedIndexes[$index] - 1) -or
                [long]$selection.marked_selection_count_after -ne $expectedMarkedIndexes[$index] -or
                $selection.append -isnot [bool] -or $selection.append -ne $expectedAppend[$index] -or
                $selection.select_by_id2_returned -isnot [bool] -or $selection.select_by_id2_returned -ne $true -or
                $selection.identity_gate_pass -isnot [bool] -or $selection.identity_gate_pass -ne $true -or
                $selection.direct_corresponding_specific_has_expected_type -isnot [bool] -or
                $selection.direct_corresponding_specific_diagnostic_only -isnot [bool] -or
                [string]$selection.mate_entity_authority -ne 'ISelectionMgr.GetSelectedObject6' -or
                $selection.selected_specific_matches_direct_corresponding_specific -isnot [bool] -or
                $selection.selected_owner_matches_expected_component -isnot [bool] -or
                $selection.selected_owner_matches_expected_component -ne $true -or
                [string]::IsNullOrWhiteSpace([string]$selection.assembly_context_selection_path)) {
                throw "J01 R10 selection identity/mark ledger mismatch at index $index"
            }
            $isAssemblyRoot = $index -in @(0,2,4)
            if ($isAssemblyRoot) {
                if ($selection.direct_corresponding_specific_diagnostic_only -ne $false -or
                    $selection.direct_corresponding_specific_has_expected_type -ne $true -or
                    $selection.selected_specific_matches_direct_corresponding_specific -ne $true -or
                    $null -ne $selection.expected_owner_component -or $null -ne $selection.expected_owner_path -or
                    $null -ne $selection.selected_owner_component -or $null -ne $selection.selected_owner_path) {
                    throw "J01 R10 assembly-root selection unexpectedly has a component owner at index $index"
                }
            }
            else {
                $expectedOwnerPath = if ($index -in @(1,3,5,6,8,10,12)) { $baseCarrier } else { $link1Carrier }
                if ($selection.direct_corresponding_specific_diagnostic_only -ne $true -or
                    [string]::IsNullOrWhiteSpace([string]$selection.expected_owner_component) -or
                    [string]$selection.selected_owner_component -ne [string]$selection.expected_owner_component -or
                    [IO.Path]::GetFullPath([string]$selection.expected_owner_path) -ne [IO.Path]::GetFullPath($expectedOwnerPath) -or
                    [IO.Path]::GetFullPath([string]$selection.selected_owner_path) -ne [IO.Path]::GetFullPath($expectedOwnerPath)) {
                    throw "J01 R10 selected owner binding mismatch at index $index"
                }
            }
            if ($null -ne $selection.selected_feature_matches_context_feature -and
                ($selection.selected_feature_matches_context_feature -isnot [bool] -or
                 $selection.selected_feature_matches_context_feature -ne $true)) {
                throw "J01 R10 selected context-Feature identity mismatch at index $index"
            }
        }
        $preloads = @($data.preload_operations)
        if ($preloads.Count -ne 2 -or [long]$data.document_count_before_new_assembly -ne 2 -or
            [long]$data.document_count_after_new_assembly -ne 3) {
            throw 'J01 R10 preload count or assembly document-count transition mismatch'
        }
        foreach ($index in 0..1) {
            $expectedRole = if ($index -eq 0) { 'BASE_MR2' } else { 'LINK1_MR2' }
            $expectedPath = if ($index -eq 0) { $baseCarrier } else { $link1Carrier }
            $expectedBytes = if ($index -eq 0) { $baseCarrierBytes } else { $link1CarrierBytes }
            $expectedSha = if ($index -eq 0) { $baseCarrierSha256 } else { $link1CarrierSha256 }
            $preload = $preloads[$index]
            if ([string]$preload.role -ne $expectedRole -or
                [IO.Path]::GetFullPath([string]$preload.path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [IO.Path]::GetFullPath([string]$preload.model_path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [long]$preload.bytes -ne $expectedBytes -or [string]$preload.sha256_before -ne $expectedSha -or
                [string]$preload.sha256_after_open -ne $expectedSha -or [long]$preload.open_errors -ne 0 -or
                [long]$preload.open_warnings -ne 0 -or [long]$preload.document_count_before -ne $index -or
                [long]$preload.document_count_after -ne ($index + 1) -or
                $preload.model_returned -isnot [bool] -or $preload.model_returned -ne $true -or
                $preload.opened_read_only -isnot [bool] -or $preload.opened_read_only -ne $true -or
                $preload.held_loaded_until_add_component5 -isnot [bool] -or $preload.held_loaded_until_add_component5 -ne $true -or
                $preload.add_component5_succeeded -isnot [bool] -or $preload.add_component5_succeeded -ne $true -or
                $preload.standalone_title_closed -isnot [bool] -or $preload.standalone_title_closed -ne $true) {
                throw "J01 R10 strict preload evidence mismatch: $expectedRole"
            }
        }
        foreach ($item in $lockedItems) {
            Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "CREATE_POST_$($item.id)"
        }
        Assert-File $pilotAssembly ([long]$data.output.bytes) ([string]$data.output.sha256) 'J01 Pilot output'
        foreach ($item in $mr2Inputs) { Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_$($item.link)_POST" }
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SOLIDWORKS remains after J01 Create normal exit' }
        $gate = [ordered]@{
            schema='B51R1_S05R2_J01_R10_NATIVE_1R_CREATE_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R10_NATIVE_1R_PILOT_CREATE_PASS';gate_pass=$true
            receipt=[ordered]@{path=$createReceipt;bytes=(Get-Item $createReceipt).Length;sha256=Get-Sha $createReceipt}
            j00_checkpoint=[ordered]@{path=$j00Checkpoint;bytes=(Get-Item $j00Checkpoint).Length;sha256=Get-Sha $j00Checkpoint}
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{preloaded_before_new_assembly=$true;strict_preload_errors_and_warnings_zero=$true;preloaded_read_only_state_verified=$true;repair_error_bit_not_relaxed=$true;standalone_titles_closed_after_insertion=$true;typed_refplane_refaxis_mate_entities=$true;specific_object_get_corresponding_before_selection=$true;get_name_for_selection_and_select_by_id2=$true;selectionmgr_identity_and_owner_gate=$true;select_by_id2_call_count=13;selection_marks_exact=$true;mate_alignment_aligned=$true;mate_api_call_ledger_at_call_sites=$true;j00_three_root_plane_mates=$true;automatic_fix_removed=$true;j01_native_hinge_angle_selection_false=$true;j01_limit_angle_reference_axis_bound=$true;native_create_mate_data_readback_pass=$true;unique_native_limit_angle_driver=$true;native_limits_0_to_5p6_rad=$true;remaining_dof_exactly_one_rotation=$true;canonical_plus_minus_one_degree_pass=$true;enhanced_branch_and_endpoint_sweep_pass=$true;ten_q0_reset_cycles_pass=$true;returned_to_q0=$true;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            cold_reopen_authorized=$false;separate_cold_verify_activation_required=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R10_SELECTIONMGR_BOUND_TYPED_MATE_ENTITY_RECOVERY_CREATE_AND_SAME_DOCUMENT_DRIVER_EVIDENCE_ONLY_PENDING_INDEPENDENT_COLD_REOPEN'
        }
        Write-JsonCreateNew $createGate $gate
        Write-Output $createGate
    }
    else {
        $result = [B51R1S05R2J01R10NativePilotTool]::ColdVerify(
            $launchedPid,$pilotAssembly,
            $baseCarrier,$baseCarrierBytes,$baseCarrierSha256,
            $link1Carrier,$link1CarrierBytes,$link1CarrierSha256,
            $coldReceipt,$coldProgress)
        if ($result -ne 0) { throw "J01 ColdVerify tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $coldReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_COLD_REOPEN_V1' -or
            $data.status -ne 'S05R2_J01_R10_NATIVE_1R_PILOT_COLD_REOPEN_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R10 ColdVerify receipt is not PASS'
        }
        if ($data.transform2_call_count -ne 0 -or $data.set_transform_and_solve_call_count -ne 0 -or
            $data.move_component_call_count -ne 0 -or $data.save_as_call_count -ne 0 -or $data.save3_call_count -ne 0 -or
            $data.create_mate_data_call_count -ne 0 -or $data.create_mate_call_count -ne 0 -or
            $data.add_mate5_call_count -ne 0 -or $data.mate_preselection_call_count -ne 0 -or
            $data.get_components_call_count -ne 1 -or $data.open_errors -ne 0 -or $data.open_warnings -ne 0 -or
            [string]$data.open_options -ne 'SILENT_READ_ONLY' -or
            $data.opened_read_only -isnot [bool] -or $data.opened_read_only -ne $true) {
            throw 'J01 ColdVerify prohibited API/save count mismatch'
        }
        $resolution = @($data.component_resolution)
        $expectedIdentities = @($data.expected_component_identities)
        if ($resolution.Count -lt 2 -or $expectedIdentities.Count -ne 2 -or
            @($resolution | Where-Object { $_.matches_parent_identity -eq $true }).Count -ne 1 -or
            @($resolution | Where-Object { $_.matches_child_identity -eq $true }).Count -ne 1) {
            throw 'J01 R10 ColdVerify did not resolve parent and child uniquely in one component traversal'
        }
        foreach ($role in @('parent','child')) {
            $expectedPath = if ($role -eq 'parent') { $baseCarrier } else { $link1Carrier }
            $expectedBytes = if ($role -eq 'parent') { $baseCarrierBytes } else { $link1CarrierBytes }
            $expectedSha = if ($role -eq 'parent') { $baseCarrierSha256 } else { $link1CarrierSha256 }
            $identity = @($expectedIdentities | Where-Object { $_.role -eq $role })
            $match = if ($role -eq 'parent') {
                @($resolution | Where-Object { $_.matches_parent_identity -eq $true })
            } else {
                @($resolution | Where-Object { $_.matches_child_identity -eq $true })
            }
            if ($identity.Count -ne 1 -or $match.Count -ne 1 -or
                [IO.Path]::GetFullPath([string]$identity[0].canonical_path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [long]$identity[0].bytes -ne $expectedBytes -or [string]$identity[0].sha256 -ne $expectedSha -or
                [IO.Path]::GetFullPath([string]$match[0].canonical_path) -ne [IO.Path]::GetFullPath($expectedPath) -or
                [long]$match[0].bytes -ne $expectedBytes -or [string]$match[0].sha256 -ne $expectedSha) {
                throw "J01 R10 ColdVerify component identity mismatch: $role"
            }
        }
        foreach ($item in $lockedItems) {
            Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "COLD_POST_$($item.id)"
        }
        foreach ($item in $mr2Inputs) { Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_$($item.link)_POST_COLD" }
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SOLIDWORKS remains after J01 ColdVerify normal exit' }
        $create = Get-Content -Raw -Encoding UTF8 -LiteralPath $createGate | ConvertFrom-Json
        $coldReceiptBinding = [ordered]@{path=$coldReceipt;bytes=(Get-Item $coldReceipt).Length;sha256=Get-Sha $coldReceipt}
        $gate = [ordered]@{
            schema='B51R1_S05R2_J01_R10_NATIVE_1R_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R10_NATIVE_1R_PILOT_PASS';gate_pass=$true
            create_gate=[ordered]@{path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate}
            receipt=$coldReceiptBinding
            cold_reopen_receipt=$coldReceiptBinding
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{assembly_opened_read_only=$true;single_get_components_identity_traversal=$true;component_identity_full_path_bytes_sha256=$true;target_component_rcws_not_final_released=$true;native_hinge_and_limit_mates_persisted=$true;native_limit_reference_axis_and_q0_persisted=$true;remaining_dof_exactly_one_rotation=$true;base_and_link1_not_fixed=$true;ten_cold_q0_samples_pass=$true;cold_plus_minus_one_degree_pass=$true;cold_branch_witnesses_pass=$true;returned_to_q0_after_cold_drive=$true;assembly_hash_stable=$true;mr2_input_hashes_stable=$true;normal_application_exit=$true;save_api_call_count=0;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            mr2_batch_create_authorized=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R10_SELECTIONMGR_BOUND_TYPED_MATE_ENTITY_RECOVERY_NATIVE_1R_PILOT_GATE_ONLY_NO_COMPLETE_CHAIN_G4_T005_STRUCTURAL_MANUFACTURING_OR_FLIGHT_CREDIT'
        }
        Write-JsonCreateNew $finalGate $gate
        Write-Output $finalGate
    }
    $exitCode = 0
}
finally {
    $remaining = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    foreach ($process in $remaining) {
        $process.Refresh()
        if ($process.Responding -and $process.MainWindowHandle -ne [IntPtr]::Zero) {
            try { [void]$process.CloseMainWindow() } catch { }
        }
    }
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($null -ne $launchHandle) { $launchHandle.Dispose() }
}

exit $exitCode
