[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Create','ColdVerify')]
    [string]$Mode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$sessionRoot = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R14'
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
$toolSource = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R14_NativePilotTool.cs'
$toolDll = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R14_NativePilotTool.dll'
$toolRunner = Join-Path $PSScriptRoot 'B51R1_Run_S05R2_J01_R14_NativePilot.ps1'
$toolSourceBytes = 133772
$toolSourceSha256 = '2834458C2A77F30A255926C8C118B5DCD7E3080FC749D3601590D001064B0C56'
$toolDllBytes = 83968
$toolDllSha256 = '37E0DB2B4E954D896BF9903A881126424940C9CF65959C0AB5AB44FD4B69D0D6'
$toolCompiler = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\MSBuild\Current\Bin\Roslyn\csc.exe'
$toolCompilerBytes = 64808
$toolCompilerSha256 = 'CF9B364171B07822F5AFA44391AE4FB4A4418D2056A5C5A018CE64F62173AB2C'
$r14StaticRelease = Join-Path $PSScriptRoot 'B51R1_S05R2_J01_R14_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r14CreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R21A_POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r14ColdActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R22A_POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION.json'

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
$r10FailureReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_CREATE_RECEIPT.json'
$r10FailureReceiptBytes = 46312
$r10FailureReceiptSha256 = 'F664755F2CE8CD9370F6A5293A1F2BAA2D5D86B27CF62E30E3F94CB90634F7AE'
$r10FailureInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_CREATE_INPUT_LOCK.json'
$r10FailureInputLockBytes = 38206
$r10FailureInputLockSha256 = 'B14842885C6BB95A2A5ECC9F15FE4E58F32AB3E2D2609F1B0A1CA0AF27B6A5E0'
$r10FailureReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_CREATE_READINESS_RECEIPT.json'
$r10FailureReadinessBytes = 470
$r10FailureReadinessSha256 = 'CD5F2FCE0C88511C456C141818FF163D7D6DC97633D3A505F5E4B240AE5C4674'
$r10FailureProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_CREATE_PROGRESS.log'
$r10FailureProgressBytes = 366
$r10FailureProgressSha256 = '3DBA13E1A515280B8C1741C52CC69DD94CE8DFB3DDC4F1013BF187BAD0DAC150'
$r10PartialJ00Assembly = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\CHECKPOINTS\B51R1_CARRIER_J00_ROOT_PILOT_R10.SLDASM'
$r10PartialJ00AssemblyBytes = 43800
$r10PartialJ00AssemblySha256 = '470C349FE98C374B2D7415DCE8BE335DE9068E9A2150C9D318A6341B0EA57565'
$r10PredecessorStaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R10_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r10PredecessorStaticReleaseBytes = 6245
$r10PredecessorStaticReleaseSha256 = 'DB890F48CEE939B9B601EDB0B9177760AE3106E230F7F60AED5F318BED82009D'
$r10PredecessorCreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R13A_POOL_A_A08R2_J01_R10_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r10PredecessorCreateActivationBytes = 3980
$r10PredecessorCreateActivationSha256 = 'F7D6E25C4E90FB32372FE8C5BB1CC64AC53984A215243BC31DD382FD38858FB3'
$r10Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R10_NativePilotTool.cs'
$r10SourceBytes = 130028
$r10SourceSha256 = 'C1879161A3C3E36BFDED53D5D2D380DD9B9901F02BB0490E82C7120922E66751'
$r10Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R10_NativePilot.ps1'
$r10RunnerBytes = 113783
$r10RunnerSha256 = '2863F50DFB5AD0D13A2A48140FBF75026D65A0A59FE69F32B54425390274CD8C'
$r10Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R10_NativePilotTool.dll'
$r10BinaryBytes = 81408
$r10BinarySha256 = '77A7A528768399D66F7A34CCC6AB2F099BA744537634FEB9875613C49C39E2F0'
$r10AbsentOutputs = @(
    (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\B51R1_CARRIER_J01_R10_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R10\B51R1_S05R2_J01_R10_CREATE_GATE.json')
)
$r11FailureReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_RECEIPT.json'
$r11FailureReceiptBytes = 102463
$r11FailureReceiptSha256 = '4578AB3A9405D3EC8EE62F579FAF2416E1CB03B0256676C894E4CC3F39EFCB3E'
$r11FailureInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_INPUT_LOCK.json'
$r11FailureInputLockBytes = 43594
$r11FailureInputLockSha256 = '03C33896B4DEDCE28C39EF94108E097B1D6A59C7C198A36E34BEDF80F9ECD1C1'
$r11FailureReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_READINESS_RECEIPT.json'
$r11FailureReadinessBytes = 470
$r11FailureReadinessSha256 = 'A60071AE3D31B57FFB843726A11395CB5BEDCE50ACFF78528ADA0E2C130D7626'
$r11FailureProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_PROGRESS.log'
$r11FailureProgressBytes = 142
$r11FailureProgressSha256 = '004AC28A6DADE9E9BD289C06F1AFBD619B7F8CF9DE10F30C8B775E03843D7DB3'
$r11PartialJ00Assembly = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\CHECKPOINTS\B51R1_CARRIER_J00_ROOT_PILOT_R11.SLDASM'
$r11PartialJ00AssemblyBytes = 44153
$r11PartialJ00AssemblySha256 = 'FE407C32E1D596DABA9C6B1290C1005D0D72ABC2BF04052F2C4F0E9A0A70FD10'
$r11PredecessorStaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r11PredecessorStaticReleaseBytes = 6574
$r11PredecessorStaticReleaseSha256 = '70CA724E4E560CBC0291F33BA59E4B23037D616AE1A1691C521A4632581ADBD1'
$r11PredecessorCreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R15A_POOL_A_A08R2_J01_R11_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r11PredecessorCreateActivationBytes = 4452
$r11PredecessorCreateActivationSha256 = 'D2C6C6680E4E4AA17FFD7500E33A0D31445BBCBD4FCA0A14216E8274C854F802'
$r11Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NativePilotTool.cs'
$r11SourceBytes = 130647
$r11SourceSha256 = '424D6E8BDACE82B20EDDB134EA8A55260666D6810EDE2BE81F345EA1A17B78F3'
$r11Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R11_NativePilot.ps1'
$r11RunnerBytes = 125174
$r11RunnerSha256 = '0EA669F9C5692607E62788557AF4137880D15D3B171606BF7FCC3CE29E59D854'
$r11Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R11_NativePilotTool.dll'
$r11BinaryBytes = 81408
$r11BinarySha256 = 'BBD8FA61860F3EE14B607485A7085D961E1F56E92F233D27E5AC46A7F76558C4'
$r11AbsentOutputs = @(
    (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\B51R1_CARRIER_J01_R11_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R11\B51R1_S05R2_J01_R11_CREATE_GATE.json')
)
$r12FailureReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_CREATE_RECEIPT.json'
$r12FailureReceiptBytes = 102463
$r12FailureReceiptSha256 = 'E48300D870F73C3F3D36A215FADA239BAD038B8B6FFC019D3FFFF118CFCF8B98'
$r12FailureInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_CREATE_INPUT_LOCK.json'
$r12FailureInputLockBytes = 49076
$r12FailureInputLockSha256 = 'DCD4A2A00F029DF89625821FA38376CBAE4DB0171EA33029AB2270D0A0FA8F36'
$r12FailureReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_CREATE_READINESS_RECEIPT.json'
$r12FailureReadinessBytes = 470
$r12FailureReadinessSha256 = '2316B997BD9CC5E565262970EC02042F7F80641C47A59B52A873A015B7C5B532'
$r12FailureProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_CREATE_PROGRESS.log'
$r12FailureProgressBytes = 142
$r12FailureProgressSha256 = '5B30055AB93A18248A07B160364E93BA88EB116E0C2A1B39770657AAD895E5CC'
$r12PartialJ00Assembly = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\CHECKPOINTS\B51R1_CARRIER_J00_ROOT_PILOT_R12.SLDASM'
$r12PartialJ00AssemblyBytes = 43766
$r12PartialJ00AssemblySha256 = '6B0FC43F9ED8B1E50D02DBA1ED8EBF5668110EF372AA2A8AE5C49CBE30C41C3B'
$r12PredecessorStaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R12_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r12PredecessorStaticReleaseBytes = 7306
$r12PredecessorStaticReleaseSha256 = 'BC8306054C03E158A93D0E27C833E1EC8FDE22E8D35BAC07745F96CD4EC2CC8E'
$r12PredecessorCreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R17A_POOL_A_A08R2_J01_R12_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r12PredecessorCreateActivationBytes = 4789
$r12PredecessorCreateActivationSha256 = 'AA15D9FFD8AF2E16A619FEED69AD0E9C86FE6C8C9D872EE3899EE316898C5D5A'
$r12Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R12_NativePilotTool.cs'
$r12SourceBytes = 130525
$r12SourceSha256 = '31C9867F5A336275CA8D5E7FC6C66C67ABA4D9C2314EF2433832D3F99E9EDE0A'
$r12Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R12_NativePilot.ps1'
$r12RunnerBytes = 137815
$r12RunnerSha256 = 'DCA83243E63094D0AF7A248DE12DA8ED5D3EE285429D18A8149FE8943A3EF314'
$r12Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R12_NativePilotTool.dll'
$r12BinaryBytes = 81408
$r12BinarySha256 = '24F44E11FB1CFE761BFC9F7908F29D6FFF96F9D7CDBD89385ADA1D96783A7BB8'
$r13FailureReceipt = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_CREATE_RECEIPT.json'
$r13FailureReceiptBytes = 102765
$r13FailureReceiptSha256 = '55F23340CAABD9F52477E77708519DF360CF1E04C764006DB03279FAF5137B17'
$r13FailureInputLock = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_CREATE_INPUT_LOCK.json'
$r13FailureInputLockBytes = 54832
$r13FailureInputLockSha256 = '1AAF550CE09D07E34C9B9BC383975613D66E69514D558948BF1F0070AAA915DA'
$r13FailureReadiness = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_CREATE_READINESS_RECEIPT.json'
$r13FailureReadinessBytes = 470
$r13FailureReadinessSha256 = 'EE1364B7C7D7ECA413B8E6AE1B97B775BCF8DB51043C3226BCB0C3086E9D3A54'
$r13FailureProgress = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_CREATE_PROGRESS.log'
$r13FailureProgressBytes = 142
$r13FailureProgressSha256 = 'B66B9DB64D6D47EBC7E378FEFEC08B7D4F026A2D3801C1037886ABCDD7EDB60F'
$r13PartialJ00Assembly = Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\CHECKPOINTS\B51R1_CARRIER_J00_ROOT_PILOT_R13.SLDASM'
$r13PartialJ00AssemblyBytes = 43714
$r13PartialJ00AssemblySha256 = '6F9C56878ED0D1276F924F2936AC815533FCDE636F2ECC51D50174BF60B0E22C'
$r13PredecessorStaticRelease = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R13_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1.json'
$r13PredecessorStaticReleaseBytes = 7684
$r13PredecessorStaticReleaseSha256 = '222CECC5AD3223FEF4C86BA527EBDCEF02907093720A89A820B7867AA0FF1921'
$r13PredecessorCreateActivation = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R19A_POOL_A_A08R2_J01_R13_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION.json'
$r13PredecessorCreateActivationBytes = 4855
$r13PredecessorCreateActivationSha256 = 'F45A636571B295B73BEB5ACC8121EEF8FA33F15B22A70B69533CC454662C932B'
$r13Source = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R13_NativePilotTool.cs'
$r13SourceBytes = 131411
$r13SourceSha256 = 'BA11E7E49C3E1BB1455676798148E19DCB08A86E17FBEB44903B1267C3561339'
$r13Runner = Join-Path $root '08_REVIEWS\B51R1_Run_S05R2_J01_R13_NativePilot.ps1'
$r13RunnerBytes = 151933
$r13RunnerSha256 = '1C55EAD2F9F07F369DC6185A1E3FDA6F0C03D51857E92D1A6FD2346F6EB8B441'
$r13Binary = Join-Path $root '08_REVIEWS\B51R1_S05R2_J01_R13_NativePilotTool.dll'
$r13BinaryBytes = 82432
$r13BinarySha256 = '88295BA7DAB3A6211648C66A2CFC3392385C53ABAB4DF751E78B75104EF392C1'
$r13AbsentSuccessOutputs = @(
    (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\B51R1_CARRIER_J01_R13_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_CREATE_GATE.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_COLD_REOPEN_PROGRESS.log'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R13\B51R1_S05R2_J01_R13_NATIVE_1R_GATE.json'),
    (Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R20A_POOL_A_A08R2_J01_R13_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION.json')
)
$r12AbsentSuccessOutputs = @(
    (Join-Path $root '03_CAD\20_NATIVE_ASSEMBLY\PILOT\B51R1_CARRIER_J01_R12_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_CREATE_GATE.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_COLD_REOPEN_PROGRESS.log'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R12\B51R1_S05R2_J01_R12_NATIVE_1R_GATE.json'),
    (Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_SESSION_PLAN_V22R18A_POOL_A_A08R2_J01_R12_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION.json')
)
$r9AbsentOutputs = @(
    (Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R9.SLDASM'),
    (Join-Path $pilotDir 'B51R1_CARRIER_J01_R9_NATIVE_PILOT.SLDASM'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_J00_BASELINE_CHECKPOINT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_CREATE_GATE.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_COLD_REOPEN_RECEIPT.json'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_COLD_REOPEN_PROGRESS.log'),
    (Join-Path $root '07_VERIFICATION\AUTONOMOUS\S05R2_J01_R9\B51R1_S05R2_J01_R9_NATIVE_1R_GATE.json')
)
$j00Assembly = Join-Path $checkpointDir 'B51R1_CARRIER_J00_ROOT_PILOT_R14.SLDASM'
$pilotAssembly = Join-Path $pilotDir 'B51R1_CARRIER_J01_R14_NATIVE_PILOT.SLDASM'
$j00Checkpoint = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_J00_BASELINE_CHECKPOINT.json'
$createReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_CREATE_RECEIPT.json'
$createProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_CREATE_PROGRESS.log'
$createGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_CREATE_GATE.json'
$coldReceipt = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_COLD_REOPEN_RECEIPT.json'
$coldProgress = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_COLD_REOPEN_PROGRESS.log'
$finalGate = Join-Path $sessionRoot 'B51R1_S05R2_J01_R14_NATIVE_1R_GATE.json'

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
    $activationPath = if ($RequestedMode -eq 'Create') { $r14CreateActivation } else { $r14ColdActivation }
    if (-not (Test-Path -LiteralPath $activationPath -PathType Leaf)) {
        throw "J01 R14 $RequestedMode has no independent activation: $activationPath"
    }
    $activation = Get-Content -Raw -Encoding UTF8 -LiteralPath $activationPath | ConvertFrom-Json
    $expectedSchema = if ($RequestedMode -eq 'Create') {
        'B51R1_AUTONOMOUS_SESSION_PLAN_V22R21A_POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATION_V1'
    } else {
        'B51R1_AUTONOMOUS_SESSION_PLAN_V22R22A_POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATION_V1'
    }
    $expectedStatus = if ($RequestedMode -eq 'Create') {
        'POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_CREATE_ACTIVATED'
    } else {
        'POOL_A_A08R2_J01_R14_SELECTION_LEDGER_NATIVE_1R_PILOT_COLD_VERIFY_ACTIVATED'
    }
    $expectedActivationMode = if ($RequestedMode -eq 'Create') { 'CREATE_ONLY' } else { 'COLD_VERIFY_ONLY' }
    if ($activation.schema -ne $expectedSchema -or $activation.status -ne $expectedStatus -or
        $activation.activation_mode -ne $expectedActivationMode -or $activation.gate_pass -ne $true -or
        [IO.Path]::GetFullPath([string]$activation.static_release.path) -ne [IO.Path]::GetFullPath($r14StaticRelease)) {
        throw "J01 R14 $RequestedMode activation contract mismatch"
    }
    Assert-File $r14StaticRelease ([long]$activation.static_release.bytes) ([string]$activation.static_release.sha256) 'J01 R14 static release bound by activation'
    $release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r14StaticRelease | ConvertFrom-Json
    if ($release.schema -ne 'B51R1_S05R2_J01_R14_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $release.status -ne 'STATIC_RELEASE_PASS' -or $release.gate_pass -ne $true -or
        $release.runtime_executed -ne $false -or [long]$release.recovery_prerequisite_count -ne 14 -or
        [long]$release.source.bytes -ne $toolSourceBytes -or [string]$release.source.sha256 -ne $toolSourceSha256 -or
        [long]$release.runner.bytes -ne (Get-Item -LiteralPath $toolRunner).Length -or
        [string]$release.runner.sha256 -ne (Get-Sha $toolRunner) -or
        [long]$release.binary.bytes -ne $toolDllBytes -or [string]$release.binary.sha256 -ne $toolDllSha256 -or
        $release.binary.double_compile_byte_identical -ne $true -or
        [long]$release.runner.r13_transaction_closure_artifact_count -ne 10 -or
        [long]$release.runner.create_locked_item_count -ne 77 -or
        [long]$release.runner.cold_verify_locked_item_count -ne 80 -or
        $release.create_activation_authorized -ne $true -or
        $release.cold_verify_activation_authorized -ne $false -or
        $release.formal_s05_output_allowed -ne $false -or $release.t005_authorized -ne $false) {
        throw 'J01 R14 static release semantic contract mismatch'
    }
    if ([IO.Path]::GetFullPath([string]$activation.tool.source.path) -ne [IO.Path]::GetFullPath($toolSource) -or
        [long]$activation.tool.source.bytes -ne $toolSourceBytes -or [string]$activation.tool.source.sha256 -ne $toolSourceSha256 -or
        [IO.Path]::GetFullPath([string]$activation.tool.runner.path) -ne [IO.Path]::GetFullPath($toolRunner) -or
        [long]$activation.tool.runner.bytes -ne (Get-Item -LiteralPath $toolRunner).Length -or
        [string]$activation.tool.runner.sha256 -ne (Get-Sha $toolRunner) -or
        [IO.Path]::GetFullPath([string]$activation.tool.binary.path) -ne [IO.Path]::GetFullPath($toolDll) -or
        [long]$activation.tool.binary.bytes -ne $toolDllBytes -or [string]$activation.tool.binary.sha256 -ne $toolDllSha256) {
        throw "J01 R14 $RequestedMode activation tool binding mismatch"
    }
    if ($RequestedMode -eq 'Create') {
        if ($activation.create_authorized -ne $true -or $activation.cold_verify_authorized -ne $false -or
            [string]$activation.required_limit_angle_recovery -ne
                'CLEAR_SELECTION_AFTER_TYPED_ENTITY_LEDGER_THEN_ASSIGN_ENTITIES_TO_MATE_ONLY_WITH_REFERENCE_ENTITY_UNSET' -or
            [long]$activation.required_counts.recovery_prerequisites -ne 14 -or
            [long]$activation.required_counts.predecessor_transaction_closure_artifacts -ne 10 -or
            [long]$activation.required_counts.create_locked_items -ne 77 -or
            [IO.Path]::GetFullPath([string]$activation.predecessor_failure.path) -ne [IO.Path]::GetFullPath($r13FailureReceipt) -or
            [long]$activation.predecessor_failure.bytes -ne $r13FailureReceiptBytes -or
            [string]$activation.predecessor_failure.sha256 -ne $r13FailureReceiptSha256 -or
            [IO.Path]::GetFullPath([string]$activation.predecessor_failure.partial_j00_snapshot.path) -ne [IO.Path]::GetFullPath($r13PartialJ00Assembly) -or
            [long]$activation.predecessor_failure.partial_j00_snapshot.bytes -ne $r13PartialJ00AssemblyBytes -or
            [string]$activation.predecessor_failure.partial_j00_snapshot.sha256 -ne $r13PartialJ00AssemblySha256) {
            throw 'J01 R14 Create activation scope/predecessor binding mismatch'
        }
    } else {
        if ($activation.create_authorized -ne $false -or $activation.cold_verify_authorized -ne $true -or
            [IO.Path]::GetFullPath([string]$activation.create_gate.path) -ne [IO.Path]::GetFullPath($createGate) -or
            [IO.Path]::GetFullPath([string]$activation.create_receipt.path) -ne [IO.Path]::GetFullPath($createReceipt) -or
            [IO.Path]::GetFullPath([string]$activation.pilot_output.path) -ne [IO.Path]::GetFullPath($pilotAssembly)) {
            throw 'J01 R14 ColdVerify activation scope/path binding mismatch'
        }
        Assert-File $createGate ([long]$activation.create_gate.bytes) ([string]$activation.create_gate.sha256) 'J01 R14 Cold activation Create Gate'
        Assert-File $createReceipt ([long]$activation.create_receipt.bytes) ([string]$activation.create_receipt.sha256) 'J01 R14 Cold activation Create receipt'
        Assert-File $pilotAssembly ([long]$activation.pilot_output.bytes) ([string]$activation.pilot_output.sha256) 'J01 R14 Cold activation pilot output'
    }
    if ($activation.formal_s05_authorized -ne $false -or $activation.t005_authorized -ne $false) {
        throw "J01 R14 $RequestedMode activation exceeds Pilot scope"
    }
    return [ordered]@{
        id="J01_R14_$($RequestedMode.ToUpperInvariant())_ACTIVATION"
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
    Assert-File $hp01DirectReceipt $hp01DirectReceiptBytes $hp01DirectReceiptSha256 'J01 R14 direct-open health receipt'
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
        throw 'J01 R14 direct-open health receipt contract mismatch'
    }
    $directParts = @($direct.parts)
    if ($directParts.Count -ne 2 -or @($directParts.link | Select-Object -Unique).Count -ne 2) {
        throw 'J01 R14 direct-open health receipt does not bind two unique parts'
    }
    foreach ($link in @('base_link','link1')) {
        $part = @($directParts | Where-Object { $_.link -eq $link })
        if ($part.Count -ne 1) { throw "J01 R14 direct-open part is not unique: $link" }
        $expectedPath = if ($link -eq 'base_link') { $baseCarrier } else { $link1Carrier }
        $expectedBytes = if ($link -eq 'base_link') { $baseCarrierBytes } else { $link1CarrierBytes }
        $expectedSha = if ($link -eq 'base_link') { $baseCarrierSha256 } else { $link1CarrierSha256 }
        if ([IO.Path]::GetFullPath([string]$part[0].path) -ne [IO.Path]::GetFullPath($expectedPath) -or
            [long]$part[0].bytes -ne $expectedBytes -or [string]$part[0].sha256_before_after -ne $expectedSha -or
            [long]$part[0].body_count -ne 0 -or [long]$part[0].external_reference_count -ne 0) {
            throw "J01 R14 direct-open health binding mismatch: $link"
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

    Assert-File $r10FailureReceipt $r10FailureReceiptBytes $r10FailureReceiptSha256 'J01 R10 deferred-hash failure receipt'
    Assert-File $r10FailureInputLock $r10FailureInputLockBytes $r10FailureInputLockSha256 'J01 R10 deferred-hash failure input lock'
    Assert-File $r10FailureReadiness $r10FailureReadinessBytes $r10FailureReadinessSha256 'J01 R10 deferred-hash failure readiness'
    Assert-File $r10FailureProgress $r10FailureProgressBytes $r10FailureProgressSha256 'J01 R10 deferred-hash failure progress'
    Assert-File $r10PartialJ00Assembly $r10PartialJ00AssemblyBytes $r10PartialJ00AssemblySha256 'J01 R10 partial J00 assembly snapshot'
    Assert-File $r10PredecessorStaticRelease $r10PredecessorStaticReleaseBytes $r10PredecessorStaticReleaseSha256 'J01 R10 static release predecessor'
    Assert-File $r10PredecessorCreateActivation $r10PredecessorCreateActivationBytes $r10PredecessorCreateActivationSha256 'J01 R10 Create activation predecessor'
    Assert-File $r10Source $r10SourceBytes $r10SourceSha256 'J01 R10 source predecessor'
    Assert-File $r10Runner $r10RunnerBytes $r10RunnerSha256 'J01 R10 runner predecessor'
    Assert-File $r10Binary $r10BinaryBytes $r10BinarySha256 'J01 R10 binary predecessor'
    foreach ($path in $r10AbsentOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R10 unexpectedly produced a completed output: $path" }
    }
    $r10Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10FailureReceipt | ConvertFrom-Json
    if ($r10Failed.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_CREATE_V1' -or
        $r10Failed.status -ne 'S05R2_J01_R10_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r10Failed.gate_pass -isnot [bool] -or $r10Failed.gate_pass -ne $false -or
        [long]$r10Failed.expected_process_id -ne 47036 -or
        [string]$r10Failed.exception_type -ne 'System.IO.IOException' -or
        [string]$r10Failed.exception -notmatch 'Sha256' -or
        [string]$r10Failed.exception -notmatch 'B51R1_CARRIER_J00_ROOT_PILOT_R10\.SLDASM' -or
        [long]$r10Failed.save_as_call_count -ne 1 -or
        [long]$r10Failed.create_mate_data_call_count -ne 3 -or
        [long]$r10Failed.create_mate_call_count -ne 3 -or
        [long]$r10Failed.mate_preselection_call_count -ne 6 -or
        [long]$r10Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r10Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r10Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r10Failed.link1_hash_after_failure -ne $link1CarrierSha256 -or
        @($r10Failed.mate_api_attempts).Count -ne 3 -or
        @($r10Failed.mate_preselection_attempts).Count -ne 6) {
        throw 'J01 R10 deferred-hash failure boundary mismatch'
    }
    foreach ($field in @('save3_call_count','add_mate5_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r10Failed.$field -ne 0) { throw "J01 R10 failure crossed a prohibited action boundary at $field" }
    }
    foreach ($attempt in @($r10Failed.mate_api_attempts)) {
        if ($attempt.mate_data_returned -ne $true -or $attempt.feature_returned -ne $true -or
            [long]$attempt.create_mate_error_status -ne 1 -or
            $attempt.definition_semantic_pair_match -ne $true) {
            throw 'J01 R10 successful J00 semantic readback closure is invalid'
        }
    }
    $r10Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10FailureInputLock | ConvertFrom-Json
    $r10Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10FailureReadiness | ConvertFrom-Json
    if ($r10Lock.schema -ne 'B51R1_S05R2_J01_R10_CREATE_INPUT_LOCK_V1' -or
        $r10Lock.status -ne 'PASS_S05R2_J01_R10_CREATE_INPUTS_HASH_LOCKED' -or $r10Lock.mode -ne 'Create' -or
        [long]$r10Lock.runtime_boundary.solidworks_process_id -ne 47036 -or
        [long]$r10Lock.runtime_boundary.prelaunch_sldworks_process_count -ne 0 -or
        [long]$r10Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r10Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        @($r10Lock.recovery_prerequisites).Count -ne 10 -or
        $r10Lock.transaction.formal_s05_output_allowed -ne $false -or
        $r10Lock.transaction.t005_authorized -ne $false) {
        throw 'J01 R10 failure input-lock boundary mismatch'
    }
    if ($r10Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r10Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r10Ready.expected_process_id -ne 47036 -or [long]$r10Ready.observed_process_id -ne 47036 -or
        $r10Ready.visible -ne $true -or $r10Ready.startup_process_completed -ne $true -or
        [long]$r10Ready.document_count -ne 0 -or $r10Ready.active_document_present -ne $false) {
        throw 'J01 R10 failure readiness receipt mismatch'
    }
    $r10ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r10FailureProgress).TrimEnd() -split '\r?\n')
    if ($r10ProgressLines.Count -ne 2 -or
        $r10ProgressLines[0] -notmatch '^J01_R10_CREATE_START ' -or
        $r10ProgressLines[1] -notmatch '^J01_R10_CREATE_FAIL The process cannot access the file ') {
        throw 'J01 R10 deferred-hash progress does not prove the locked-file failure'
    }
    $r10Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10PredecessorStaticRelease | ConvertFrom-Json
    $r10ActivationState = Get-Content -Raw -Encoding UTF8 -LiteralPath $r10PredecessorCreateActivation | ConvertFrom-Json
    if ($r10Release.schema -ne 'B51R1_S05R2_J01_R10_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r10Release.status -ne 'STATIC_RELEASE_PASS' -or $r10Release.gate_pass -ne $true -or
        $r10Release.runtime_executed -ne $false -or [long]$r10Release.recovery_prerequisite_count -ne 10 -or
        $r10Release.create_activation_authorized -ne $true -or
        $r10Release.cold_verify_activation_authorized -ne $false -or
        $r10ActivationState.activation_mode -ne 'CREATE_ONLY' -or
        $r10ActivationState.create_authorized -ne $true -or $r10ActivationState.cold_verify_authorized -ne $false -or
        $r10ActivationState.formal_s05_authorized -ne $false -or $r10ActivationState.t005_authorized -ne $false) {
        throw 'J01 R10 predecessor static release/Create activation contract mismatch'
    }

    # R11 is an append-only failed successor. Bind its complete transaction
    # closure before permitting this R14 Create attempt.
    Assert-File $r11FailureReceipt $r11FailureReceiptBytes $r11FailureReceiptSha256 'J01 R11 failure receipt'
    Assert-File $r11FailureInputLock $r11FailureInputLockBytes $r11FailureInputLockSha256 'J01 R11 failure input lock'
    Assert-File $r11FailureReadiness $r11FailureReadinessBytes $r11FailureReadinessSha256 'J01 R11 failure readiness'
    Assert-File $r11FailureProgress $r11FailureProgressBytes $r11FailureProgressSha256 'J01 R11 failure progress'
    Assert-File $r11PartialJ00Assembly $r11PartialJ00AssemblyBytes $r11PartialJ00AssemblySha256 'J01 R11 partial J00 assembly'
    Assert-File $r11PredecessorStaticRelease $r11PredecessorStaticReleaseBytes $r11PredecessorStaticReleaseSha256 'J01 R11 static release predecessor'
    Assert-File $r11PredecessorCreateActivation $r11PredecessorCreateActivationBytes $r11PredecessorCreateActivationSha256 'J01 R11 Create activation predecessor'
    Assert-File $r11Source $r11SourceBytes $r11SourceSha256 'J01 R11 source predecessor'
    Assert-File $r11Runner $r11RunnerBytes $r11RunnerSha256 'J01 R11 runner predecessor'
    Assert-File $r11Binary $r11BinaryBytes $r11BinarySha256 'J01 R11 binary predecessor'
    foreach ($path in $r11AbsentOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R11 unexpectedly produced a completed output: $path" }
    }
    $r11Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r11FailureReceipt | ConvertFrom-Json
    if ($r11Failed.schema -ne 'B51R1_S05R2_J01_R11_NATIVE_PILOT_CREATE_V1' -or
        $r11Failed.status -ne 'S05R2_J01_R11_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r11Failed.gate_pass -isnot [bool] -or $r11Failed.gate_pass -ne $false -or
        [long]$r11Failed.expected_process_id -ne 51744 -or
        [string]$r11Failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$r11Failed.exception -notmatch 'J01_LIMIT_ANGLE_DRIVER' -or
        [string]$r11Failed.exception -notmatch 'ErrorStatus=4' -or
        [long]$r11Failed.save_as_call_count -ne 1 -or
        [long]$r11Failed.create_mate_data_call_count -ne 5 -or
        [long]$r11Failed.create_mate_call_count -ne 5 -or
        [long]$r11Failed.mate_preselection_call_count -ne 13 -or
        [long]$r11Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r11Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r11Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r11Failed.link1_hash_after_failure -ne $link1CarrierSha256 -or
        @($r11Failed.mate_api_attempts).Count -ne 5 -or
        @($r11Failed.mate_preselection_attempts).Count -ne 13) {
        throw 'J01 R11 Limit Angle incorrect-selection failure boundary mismatch'
    }
    foreach ($field in @('save3_call_count','add_mate5_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r11Failed.$field -ne 0) { throw "J01 R11 failure crossed a prohibited action boundary at $field" }
    }
    $r11Attempts = @($r11Failed.mate_api_attempts)
    if (@($r11Attempts | Where-Object { $_.feature_returned -eq $true -and [long]$_.create_mate_error_status -eq 1 }).Count -ne 4 -or
        [string]$r11Attempts[4].name -ne 'J01_LIMIT_ANGLE_DRIVER' -or
        $r11Attempts[4].feature_returned -ne $false -or
        [long]$r11Attempts[4].create_mate_error_status -ne 4) {
        throw 'J01 R11 successful-J00/Hinge and failed-Limit-Angle ledger mismatch'
    }
    $r11Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r11FailureInputLock | ConvertFrom-Json
    $r11Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r11FailureReadiness | ConvertFrom-Json
    if ($r11Lock.schema -ne 'B51R1_S05R2_J01_R11_CREATE_INPUT_LOCK_V1' -or
        $r11Lock.status -ne 'PASS_S05R2_J01_R11_CREATE_INPUTS_HASH_LOCKED' -or $r11Lock.mode -ne 'Create' -or
        [long]$r11Lock.runtime_boundary.solidworks_process_id -ne 51744 -or
        [long]$r11Lock.runtime_boundary.launch_handle_process_id -ne 51744 -or
        $r11Lock.runtime_boundary.launch_handle_matches_sole_process -ne $true -or
        [long]$r11Lock.runtime_boundary.process_count -ne 1 -or
        [long]$r11Lock.runtime_boundary.document_count -ne 0 -or
        [long]$r11Lock.runtime_boundary.prelaunch_sldworks_process_count -ne 0 -or
        [long]$r11Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r11Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        @($r11Lock.recovery_prerequisites).Count -ne 11 -or
        @($r11Lock.locked_items).Count -ne 47 -or
        $r11Lock.transaction.formal_s05_output_allowed -ne $false -or
        $r11Lock.transaction.t005_authorized -ne $false) {
        throw 'J01 R11 failure input-lock boundary mismatch'
    }
    if ($r11Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r11Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r11Ready.expected_process_id -ne 51744 -or [long]$r11Ready.observed_process_id -ne 51744 -or
        $r11Ready.visible -ne $true -or $r11Ready.startup_process_completed -ne $true -or
        [long]$r11Ready.document_count -ne 0 -or $r11Ready.active_document_present -ne $false) {
        throw 'J01 R11 failure readiness receipt mismatch'
    }
    $r11ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r11FailureProgress).TrimEnd() -split '\r?\n')
    if ($r11ProgressLines.Count -ne 2 -or
        $r11ProgressLines[0] -notmatch '^J01_R11_CREATE_START ' -or
        $r11ProgressLines[1] -notmatch '^J01_R11_CREATE_FAIL CreateMate returned no Feature: J01_LIMIT_ANGLE_DRIVER, ErrorStatus=4') {
        throw 'J01 R11 progress does not prove the Limit Angle fail-closed boundary'
    }
    $r11Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r11PredecessorStaticRelease | ConvertFrom-Json
    $r11ActivationState = Get-Content -Raw -Encoding UTF8 -LiteralPath $r11PredecessorCreateActivation | ConvertFrom-Json
    if ($r11Release.schema -ne 'B51R1_S05R2_J01_R11_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r11Release.status -ne 'STATIC_RELEASE_PASS' -or $r11Release.gate_pass -ne $true -or
        $r11Release.runtime_executed -ne $false -or [long]$r11Release.recovery_prerequisite_count -ne 11 -or
        $r11Release.create_activation_authorized -ne $true -or
        $r11Release.cold_verify_activation_authorized -ne $false -or
        $r11ActivationState.activation_mode -ne 'CREATE_ONLY' -or
        $r11ActivationState.create_authorized -ne $true -or $r11ActivationState.cold_verify_authorized -ne $false -or
        $r11ActivationState.formal_s05_authorized -ne $false -or $r11ActivationState.t005_authorized -ne $false) {
        throw 'J01 R11 predecessor static release/Create activation contract mismatch'
    }

    # R12 preserved the documented marks but used only the retained preselection
    # channel. Bind its entire failed transaction before testing the direct-property path.
    Assert-File $r12FailureReceipt $r12FailureReceiptBytes $r12FailureReceiptSha256 'J01 R12 failure receipt'
    Assert-File $r12FailureInputLock $r12FailureInputLockBytes $r12FailureInputLockSha256 'J01 R12 failure input lock'
    Assert-File $r12FailureReadiness $r12FailureReadinessBytes $r12FailureReadinessSha256 'J01 R12 failure readiness'
    Assert-File $r12FailureProgress $r12FailureProgressBytes $r12FailureProgressSha256 'J01 R12 failure progress'
    Assert-File $r12PartialJ00Assembly $r12PartialJ00AssemblyBytes $r12PartialJ00AssemblySha256 'J01 R12 partial J00 assembly'
    Assert-File $r12PredecessorStaticRelease $r12PredecessorStaticReleaseBytes $r12PredecessorStaticReleaseSha256 'J01 R12 static release predecessor'
    Assert-File $r12PredecessorCreateActivation $r12PredecessorCreateActivationBytes $r12PredecessorCreateActivationSha256 'J01 R12 Create activation predecessor'
    Assert-File $r12Source $r12SourceBytes $r12SourceSha256 'J01 R12 source predecessor'
    Assert-File $r12Runner $r12RunnerBytes $r12RunnerSha256 'J01 R12 runner predecessor'
    Assert-File $r12Binary $r12BinaryBytes $r12BinarySha256 'J01 R12 binary predecessor'
    foreach ($path in $r12AbsentSuccessOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R12 unexpectedly produced a success-state output: $path" }
    }
    $r12Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r12FailureReceipt | ConvertFrom-Json
    if ($r12Failed.schema -ne 'B51R1_S05R2_J01_R12_NATIVE_PILOT_CREATE_V1' -or
        $r12Failed.status -ne 'S05R2_J01_R12_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r12Failed.gate_pass -isnot [bool] -or $r12Failed.gate_pass -ne $false -or
        [long]$r12Failed.expected_process_id -ne 52196 -or
        [string]$r12Failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$r12Failed.exception -notmatch 'J01_LIMIT_ANGLE_DRIVER' -or
        [string]$r12Failed.exception -notmatch 'ErrorStatus=4' -or
        [long]$r12Failed.save_as_call_count -ne 1 -or
        [long]$r12Failed.create_mate_data_call_count -ne 5 -or
        [long]$r12Failed.create_mate_call_count -ne 5 -or
        [long]$r12Failed.mate_preselection_call_count -ne 13 -or
        [long]$r12Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r12Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r12Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r12Failed.link1_hash_after_failure -ne $link1CarrierSha256 -or
        @($r12Failed.mate_api_attempts).Count -ne 5 -or
        @($r12Failed.mate_preselection_attempts).Count -ne 13) {
        throw 'J01 R12 Limit Angle incorrect-selection failure boundary mismatch'
    }
    foreach ($field in @('save3_call_count','add_mate5_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r12Failed.$field -ne 0) { throw "J01 R12 failure crossed a prohibited action boundary at $field" }
    }
    $r12Attempts = @($r12Failed.mate_api_attempts)
    $r12AngleSelections = @($r12Attempts[4].entity_selections)
    if (@($r12Attempts | Where-Object { $_.feature_returned -eq $true -and [long]$_.create_mate_error_status -eq 1 }).Count -ne 4 -or
        [string]$r12Attempts[4].name -ne 'J01_LIMIT_ANGLE_DRIVER' -or
        [long]$r12Attempts[4].preselection_count_before_create_mate_data -ne 3 -or
        $r12Attempts[4].feature_returned -ne $false -or
        [long]$r12Attempts[4].create_mate_error_status -ne 4 -or
        $r12AngleSelections.Count -ne 3 -or
        [long]$r12AngleSelections[0].mark -ne 1 -or [long]$r12AngleSelections[1].mark -ne 1 -or
        [long]$r12AngleSelections[2].mark -ne 67108864) {
        throw 'J01 R12 marked-preselection Limit Angle ledger mismatch'
    }
    $r12Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r12FailureInputLock | ConvertFrom-Json
    $r12Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r12FailureReadiness | ConvertFrom-Json
    if ($r12Lock.schema -ne 'B51R1_S05R2_J01_R12_CREATE_INPUT_LOCK_V1' -or
        $r12Lock.status -ne 'PASS_S05R2_J01_R12_CREATE_INPUTS_HASH_LOCKED' -or $r12Lock.mode -ne 'Create' -or
        [long]$r12Lock.runtime_boundary.solidworks_process_id -ne 52196 -or
        [long]$r12Lock.runtime_boundary.launch_handle_process_id -ne 52196 -or
        $r12Lock.runtime_boundary.launch_handle_matches_sole_process -ne $true -or
        [long]$r12Lock.runtime_boundary.process_count -ne 1 -or
        [long]$r12Lock.runtime_boundary.document_count -ne 0 -or
        [long]$r12Lock.runtime_boundary.prelaunch_sldworks_process_count -ne 0 -or
        [long]$r12Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r12Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        @($r12Lock.recovery_prerequisites).Count -ne 12 -or
        @($r12Lock.locked_items).Count -ne 57 -or
        $r12Lock.transaction.formal_s05_output_allowed -ne $false -or
        $r12Lock.transaction.t005_authorized -ne $false) {
        throw 'J01 R12 failure input-lock boundary mismatch'
    }
    if ($r12Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r12Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r12Ready.expected_process_id -ne 52196 -or [long]$r12Ready.observed_process_id -ne 52196 -or
        $r12Ready.visible -ne $true -or $r12Ready.startup_process_completed -ne $true -or
        [long]$r12Ready.document_count -ne 0 -or $r12Ready.active_document_present -ne $false) {
        throw 'J01 R12 failure readiness receipt mismatch'
    }
    $r12ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r12FailureProgress).TrimEnd() -split '\r?\n')
    if ($r12ProgressLines.Count -ne 2 -or
        $r12ProgressLines[0] -notmatch '^J01_R12_CREATE_START ' -or
        $r12ProgressLines[1] -notmatch '^J01_R12_CREATE_FAIL CreateMate returned no Feature: J01_LIMIT_ANGLE_DRIVER, ErrorStatus=4') {
        throw 'J01 R12 progress does not prove the Limit Angle fail-closed boundary'
    }
    $r12Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r12PredecessorStaticRelease | ConvertFrom-Json
    $r12ActivationState = Get-Content -Raw -Encoding UTF8 -LiteralPath $r12PredecessorCreateActivation | ConvertFrom-Json
    if ($r12Release.schema -ne 'B51R1_S05R2_J01_R12_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r12Release.status -ne 'STATIC_RELEASE_PASS' -or $r12Release.gate_pass -ne $true -or
        $r12Release.runtime_executed -ne $false -or [long]$r12Release.recovery_prerequisite_count -ne 12 -or
        $r12Release.create_activation_authorized -ne $true -or
        $r12Release.cold_verify_activation_authorized -ne $false -or
        $r12ActivationState.activation_mode -ne 'CREATE_ONLY' -or
        $r12ActivationState.create_authorized -ne $true -or $r12ActivationState.cold_verify_authorized -ne $false -or
        $r12ActivationState.formal_s05_authorized -ne $false -or $r12ActivationState.t005_authorized -ne $false) {
        throw 'J01 R12 predecessor static release/Create activation contract mismatch'
    }

    # R13 proved that setting both direct properties still returns IncorrectSelections.
    # Freeze its receipt plus the remaining nine transaction artifacts before R14.
    Assert-File $r13FailureReceipt $r13FailureReceiptBytes $r13FailureReceiptSha256 'J01 R13 failure receipt'
    Assert-File $r13FailureInputLock $r13FailureInputLockBytes $r13FailureInputLockSha256 'J01 R13 failure input lock'
    Assert-File $r13FailureReadiness $r13FailureReadinessBytes $r13FailureReadinessSha256 'J01 R13 failure readiness'
    Assert-File $r13FailureProgress $r13FailureProgressBytes $r13FailureProgressSha256 'J01 R13 failure progress'
    Assert-File $r13PartialJ00Assembly $r13PartialJ00AssemblyBytes $r13PartialJ00AssemblySha256 'J01 R13 partial J00 assembly'
    Assert-File $r13PredecessorStaticRelease $r13PredecessorStaticReleaseBytes $r13PredecessorStaticReleaseSha256 'J01 R13 static release predecessor'
    Assert-File $r13PredecessorCreateActivation $r13PredecessorCreateActivationBytes $r13PredecessorCreateActivationSha256 'J01 R13 Create activation predecessor'
    Assert-File $r13Source $r13SourceBytes $r13SourceSha256 'J01 R13 source predecessor'
    Assert-File $r13Runner $r13RunnerBytes $r13RunnerSha256 'J01 R13 runner predecessor'
    Assert-File $r13Binary $r13BinaryBytes $r13BinarySha256 'J01 R13 binary predecessor'
    foreach ($path in $r13AbsentSuccessOutputs) {
        if (Test-Path -LiteralPath $path) { throw "J01 R13 unexpectedly produced a success-state output: $path" }
    }
    $r13Failed = Get-Content -Raw -Encoding UTF8 -LiteralPath $r13FailureReceipt | ConvertFrom-Json
    if ($r13Failed.schema -ne 'B51R1_S05R2_J01_R13_NATIVE_PILOT_CREATE_V1' -or
        $r13Failed.status -ne 'S05R2_J01_R13_NATIVE_1R_PILOT_CREATE_FAIL_CLOSED' -or
        $r13Failed.gate_pass -isnot [bool] -or $r13Failed.gate_pass -ne $false -or
        [long]$r13Failed.expected_process_id -ne 49640 -or
        [string]$r13Failed.exception_type -ne 'System.InvalidOperationException' -or
        [string]$r13Failed.exception -notmatch 'J01_LIMIT_ANGLE_DRIVER' -or
        [string]$r13Failed.exception -notmatch 'ErrorStatus=4' -or
        [long]$r13Failed.save_as_call_count -ne 1 -or
        [long]$r13Failed.create_mate_data_call_count -ne 5 -or
        [long]$r13Failed.create_mate_call_count -ne 5 -or
        [long]$r13Failed.mate_preselection_call_count -ne 13 -or
        [long]$r13Failed.document_count_before_new_assembly -ne 2 -or
        [long]$r13Failed.document_count_after_new_assembly -ne 3 -or
        [string]$r13Failed.base_hash_after_failure -ne $baseCarrierSha256 -or
        [string]$r13Failed.link1_hash_after_failure -ne $link1CarrierSha256 -or
        @($r13Failed.mate_api_attempts).Count -ne 5 -or
        @($r13Failed.mate_preselection_attempts).Count -ne 13) {
        throw 'J01 R13 direct-property Limit Angle failure boundary mismatch'
    }
    foreach ($field in @('save3_call_count','add_mate5_call_count','transform2_call_count',
        'set_transform_and_solve_call_count','move_component_call_count')) {
        if ([long]$r13Failed.$field -ne 0) { throw "J01 R13 failure crossed a prohibited action boundary at $field" }
    }
    $r13Attempts = @($r13Failed.mate_api_attempts)
    $r13AngleSelections = @($r13Attempts[4].entity_selections)
    if (@($r13Attempts | Where-Object { $_.feature_returned -eq $true -and [long]$_.create_mate_error_status -eq 1 }).Count -ne 4 -or
        [string]$r13Attempts[4].name -ne 'J01_LIMIT_ANGLE_DRIVER' -or
        [long]$r13Attempts[4].selection_count_before_direct_property_contract_clear -ne 3 -or
        [long]$r13Attempts[4].selection_count_after_direct_property_contract_clear -ne 0 -or
        [long]$r13Attempts[4].preselection_count_before_create_mate_data -ne 0 -or
        $r13Attempts[4].direct_property_entities_assigned -ne $true -or
        $r13Attempts[4].direct_property_reference_assigned -ne $true -or
        $r13Attempts[4].feature_returned -ne $false -or
        [long]$r13Attempts[4].create_mate_error_status -ne 4 -or
        $r13AngleSelections.Count -ne 3 -or
        [long]$r13AngleSelections[0].mark -ne 1 -or [long]$r13AngleSelections[1].mark -ne 1 -or
        [long]$r13AngleSelections[2].mark -ne 67108864) {
        throw 'J01 R13 direct-property Limit Angle ledger mismatch'
    }
    $r13Lock = Get-Content -Raw -Encoding UTF8 -LiteralPath $r13FailureInputLock | ConvertFrom-Json
    $r13Ready = Get-Content -Raw -Encoding UTF8 -LiteralPath $r13FailureReadiness | ConvertFrom-Json
    if ($r13Lock.schema -ne 'B51R1_S05R2_J01_R13_CREATE_INPUT_LOCK_V1' -or
        $r13Lock.status -ne 'PASS_S05R2_J01_R13_CREATE_INPUTS_HASH_LOCKED' -or $r13Lock.mode -ne 'Create' -or
        [long]$r13Lock.runtime_boundary.solidworks_process_id -ne 49640 -or
        [long]$r13Lock.runtime_boundary.launch_handle_process_id -ne 49640 -or
        $r13Lock.runtime_boundary.launch_handle_matches_sole_process -ne $true -or
        [long]$r13Lock.runtime_boundary.process_count -ne 1 -or
        [long]$r13Lock.runtime_boundary.document_count -ne 0 -or
        [long]$r13Lock.runtime_boundary.prelaunch_sldworks_process_count -ne 0 -or
        [long]$r13Lock.runtime_boundary.persistent_use_software_ogl_before -ne 0 -or
        [long]$r13Lock.runtime_boundary.persistent_use_software_ogl_after_launch -ne 0 -or
        @($r13Lock.recovery_prerequisites).Count -ne 13 -or
        @($r13Lock.locked_items).Count -ne 67 -or
        $r13Lock.transaction.formal_s05_output_allowed -ne $false -or
        $r13Lock.transaction.t005_authorized -ne $false) {
        throw 'J01 R13 failure input-lock boundary mismatch'
    }
    if ($r13Ready.schema -ne 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_V1' -or
        $r13Ready.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION' -or
        [long]$r13Ready.expected_process_id -ne 49640 -or [long]$r13Ready.observed_process_id -ne 49640 -or
        $r13Ready.visible -ne $true -or $r13Ready.startup_process_completed -ne $true -or
        [long]$r13Ready.document_count -ne 0 -or $r13Ready.active_document_present -ne $false) {
        throw 'J01 R13 failure readiness receipt mismatch'
    }
    $r13ProgressLines = @((Get-Content -Raw -Encoding UTF8 -LiteralPath $r13FailureProgress).TrimEnd() -split '\r?\n')
    if ($r13ProgressLines.Count -ne 2 -or
        $r13ProgressLines[0] -notmatch '^J01_R13_CREATE_START ' -or
        $r13ProgressLines[1] -notmatch '^J01_R13_CREATE_FAIL CreateMate returned no Feature: J01_LIMIT_ANGLE_DRIVER, ErrorStatus=4') {
        throw 'J01 R13 progress does not prove the Limit Angle fail-closed boundary'
    }
    $r13Release = Get-Content -Raw -Encoding UTF8 -LiteralPath $r13PredecessorStaticRelease | ConvertFrom-Json
    $r13ActivationState = Get-Content -Raw -Encoding UTF8 -LiteralPath $r13PredecessorCreateActivation | ConvertFrom-Json
    if ($r13Release.schema -ne 'B51R1_S05R2_J01_R13_NATIVE_PILOT_TOOL_STATIC_RELEASE_V1' -or
        $r13Release.status -ne 'STATIC_RELEASE_PASS' -or $r13Release.gate_pass -ne $true -or
        $r13Release.runtime_executed -ne $false -or [long]$r13Release.recovery_prerequisite_count -ne 13 -or
        [long]$r13Release.runner.r12_transaction_closure_artifact_count -ne 10 -or
        [long]$r13Release.runner.create_locked_item_count -ne 67 -or
        [long]$r13Release.runner.cold_verify_locked_item_count -ne 70 -or
        $r13Release.create_activation_authorized -ne $true -or
        $r13Release.cold_verify_activation_authorized -ne $false -or
        $r13ActivationState.activation_mode -ne 'CREATE_ONLY' -or
        [long]$r13ActivationState.required_counts.recovery_prerequisites -ne 13 -or
        [long]$r13ActivationState.required_counts.predecessor_transaction_closure_artifacts -ne 10 -or
        [long]$r13ActivationState.required_counts.create_locked_items -ne 67 -or
        $r13ActivationState.create_authorized -ne $true -or $r13ActivationState.cold_verify_authorized -ne $false -or
        $r13ActivationState.formal_s05_authorized -ne $false -or $r13ActivationState.t005_authorized -ne $false) {
        throw 'J01 R13 predecessor static release/Create activation contract mismatch'
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
        },
        [ordered]@{
            id='J01_R10_DEFERRED_ASSEMBLY_HASH_FAIL_CLOSED';path=$r10FailureReceipt
            bytes=$r10FailureReceiptBytes;sha256=$r10FailureReceiptSha256;status=[string]$r10Failed.status
            exception_type=[string]$r10Failed.exception_type;failed_boundary='POST_SAVEAS_SHA256_WHILE_DOCUMENT_LOCKED'
            j00_mates_created=3;save_as_call_count=1;mechanical_outputs_partial=$true
            partial_j00_snapshot=[ordered]@{path=$r10PartialJ00Assembly;bytes=$r10PartialJ00AssemblyBytes;sha256=$r10PartialJ00AssemblySha256}
            mr2_hashes_stable=$true;formal_s05_output_allowed=$false;t005_authorized=$false
            recovery_action='DEFER_ASSEMBLY_HASH_AND_CHECKPOINT_PERSISTENCE_UNTIL_NORMAL_APPLICATION_EXIT'
        },
        [ordered]@{
            id='J01_R11_LIMIT_ANGLE_INCORRECT_SELECTIONS_FAIL_CLOSED';path=$r11FailureReceipt
            bytes=$r11FailureReceiptBytes;sha256=$r11FailureReceiptSha256;status=[string]$r11Failed.status
            exception_type=[string]$r11Failed.exception_type;failed_mate='J01_LIMIT_ANGLE_DRIVER';error_status=4
            j00_mates_created=3;hinge_created=$true;save_as_call_count=1;mechanical_outputs_partial=$true
            partial_j00_snapshot=[ordered]@{path=$r11PartialJ00Assembly;bytes=$r11PartialJ00AssemblyBytes;sha256=$r11PartialJ00AssemblySha256}
            mr2_hashes_stable=$true;formal_s05_output_allowed=$false;t005_authorized=$false
            recovery_action='USE_MARKED_ENTITIES_AND_REFERENCE_OR_CONTRACT_WITHOUT_DUPLICATE_ANGLE_ASSIGNMENTS'
        },
        [ordered]@{
            id='J01_R12_LIMIT_ANGLE_PURE_PRESELECTION_INCORRECT_SELECTIONS_FAIL_CLOSED';path=$r12FailureReceipt
            bytes=$r12FailureReceiptBytes;sha256=$r12FailureReceiptSha256;status=[string]$r12Failed.status
            exception_type=[string]$r12Failed.exception_type;failed_mate='J01_LIMIT_ANGLE_DRIVER';error_status=4
            entity_marks=@(1,1,67108864);preselection_count_before_create_mate_data=3
            j00_mates_created=3;hinge_created=$true;save_as_call_count=1;mechanical_outputs_partial=$true
            partial_j00_snapshot=[ordered]@{path=$r12PartialJ00Assembly;bytes=$r12PartialJ00AssemblyBytes;sha256=$r12PartialJ00AssemblySha256}
            mr2_hashes_stable=$true;success_state_outputs_absent=$true
            formal_s05_output_allowed=$false;t005_authorized=$false
            recovery_action='CLEAR_SELECTION_AFTER_TYPED_ENTITY_LEDGER_THEN_ASSIGN_ANGLE_ENTITIES_AND_REFERENCE_DIRECTLY'
        },
        [ordered]@{
            id='J01_R13_LIMIT_ANGLE_DUAL_DIRECT_PROPERTY_INCORRECT_SELECTIONS_FAIL_CLOSED';path=$r13FailureReceipt
            bytes=$r13FailureReceiptBytes;sha256=$r13FailureReceiptSha256;status=[string]$r13Failed.status
            exception_type=[string]$r13Failed.exception_type;failed_mate='J01_LIMIT_ANGLE_DRIVER';error_status=4
            entity_marks=@(1,1,67108864);acquisition_selection_count=3;create_preselection_count=0
            entities_to_mate_assigned=$true;reference_entity_assigned=$true
            j00_mates_created=3;hinge_created=$true;save_as_call_count=1;mechanical_outputs_partial=$true
            partial_j00_snapshot=[ordered]@{path=$r13PartialJ00Assembly;bytes=$r13PartialJ00AssemblyBytes;sha256=$r13PartialJ00AssemblySha256}
            mr2_hashes_stable=$true;success_state_outputs_absent=$true
            formal_s05_output_allowed=$false;t005_authorized=$false
            recovery_action='KEEP_TYPED_IDENTITY_LEDGER_AND_ENTITIES_TO_MATE_BUT_LEAVE_REFERENCE_ENTITY_UNSET'
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
Assert-File $toolCompiler $toolCompilerBytes $toolCompilerSha256 'J01 R14 frozen-tool compiler provenance'
if ($toolDllBytes -le 0 -or $toolDllSha256 -eq ('0' * 64)) {
    throw 'J01 R14 is source-only: deterministic compile and append-only binary static freeze are required before execution'
}
Assert-File $toolSource $toolSourceBytes $toolSourceSha256 'J01 Pilot frozen source'
Assert-File $toolDll $toolDllBytes $toolDllSha256 'J01 Pilot frozen binary'
if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "$Mode requires zero existing SLDWORKS processes"
}
$persistentSoftwareOglBefore = Get-PersistentSoftwareOglValue
if ($persistentSoftwareOglBefore -ne 0) {
    throw 'Persistent Use Software OGL must remain disabled; R14 authorizes only the one-session launch argument'
}

$mr2Inputs = @(Get-Mr2PilotInputs)
$recoveryPrerequisites = @(Get-RecoveryPrerequisites)
if ($recoveryPrerequisites.Count -ne 14) {
    throw "J01 R14 recovery prerequisite count mismatch: $($recoveryPrerequisites.Count)"
}
$prelaunchSolidWorksCount = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
$r9PredecessorPidPresent = @(Get-Process -Id 48992 -ErrorAction SilentlyContinue).Count -ne 0
$r10PredecessorPidPresent = @(Get-Process -Id 47036 -ErrorAction SilentlyContinue).Count -ne 0
$r11PredecessorPidPresent = @(Get-Process -Id 51744 -ErrorAction SilentlyContinue).Count -ne 0
$r12PredecessorPidPresent = @(Get-Process -Id 52196 -ErrorAction SilentlyContinue).Count -ne 0
$r13PredecessorPidPresent = @(Get-Process -Id 49640 -ErrorAction SilentlyContinue).Count -ne 0
if ($prelaunchSolidWorksCount -ne 0 -or $r9PredecessorPidPresent -or $r10PredecessorPidPresent -or
    $r11PredecessorPidPresent -or $r12PredecessorPidPresent -or $r13PredecessorPidPresent) {
    throw 'J01 R14 predecessor process boundary is not clean immediately before launch'
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
$r10ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R10_INPUT_LOCK';path=$r10FailureInputLock;bytes=$r10FailureInputLockBytes;sha256=$r10FailureInputLockSha256},
    [ordered]@{id='J01_R10_READINESS';path=$r10FailureReadiness;bytes=$r10FailureReadinessBytes;sha256=$r10FailureReadinessSha256},
    [ordered]@{id='J01_R10_PROGRESS';path=$r10FailureProgress;bytes=$r10FailureProgressBytes;sha256=$r10FailureProgressSha256},
    [ordered]@{id='J01_R10_PARTIAL_J00_ASSEMBLY';path=$r10PartialJ00Assembly;bytes=$r10PartialJ00AssemblyBytes;sha256=$r10PartialJ00AssemblySha256},
    [ordered]@{id='J01_R10_STATIC_RELEASE';path=$r10PredecessorStaticRelease;bytes=$r10PredecessorStaticReleaseBytes;sha256=$r10PredecessorStaticReleaseSha256},
    [ordered]@{id='J01_R10_ACTIVATION';path=$r10PredecessorCreateActivation;bytes=$r10PredecessorCreateActivationBytes;sha256=$r10PredecessorCreateActivationSha256},
    [ordered]@{id='J01_R10_SOURCE';path=$r10Source;bytes=$r10SourceBytes;sha256=$r10SourceSha256},
    [ordered]@{id='J01_R10_RUNNER';path=$r10Runner;bytes=$r10RunnerBytes;sha256=$r10RunnerSha256},
    [ordered]@{id='J01_R10_BINARY';path=$r10Binary;bytes=$r10BinaryBytes;sha256=$r10BinarySha256}
)
$r11ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R11_INPUT_LOCK';path=$r11FailureInputLock;bytes=$r11FailureInputLockBytes;sha256=$r11FailureInputLockSha256},
    [ordered]@{id='J01_R11_READINESS';path=$r11FailureReadiness;bytes=$r11FailureReadinessBytes;sha256=$r11FailureReadinessSha256},
    [ordered]@{id='J01_R11_PROGRESS';path=$r11FailureProgress;bytes=$r11FailureProgressBytes;sha256=$r11FailureProgressSha256},
    [ordered]@{id='J01_R11_PARTIAL_J00_ASSEMBLY';path=$r11PartialJ00Assembly;bytes=$r11PartialJ00AssemblyBytes;sha256=$r11PartialJ00AssemblySha256},
    [ordered]@{id='J01_R11_STATIC_RELEASE';path=$r11PredecessorStaticRelease;bytes=$r11PredecessorStaticReleaseBytes;sha256=$r11PredecessorStaticReleaseSha256},
    [ordered]@{id='J01_R11_ACTIVATION';path=$r11PredecessorCreateActivation;bytes=$r11PredecessorCreateActivationBytes;sha256=$r11PredecessorCreateActivationSha256},
    [ordered]@{id='J01_R11_SOURCE';path=$r11Source;bytes=$r11SourceBytes;sha256=$r11SourceSha256},
    [ordered]@{id='J01_R11_RUNNER';path=$r11Runner;bytes=$r11RunnerBytes;sha256=$r11RunnerSha256},
    [ordered]@{id='J01_R11_BINARY';path=$r11Binary;bytes=$r11BinaryBytes;sha256=$r11BinarySha256}
)
$r12ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R12_INPUT_LOCK';path=$r12FailureInputLock;bytes=$r12FailureInputLockBytes;sha256=$r12FailureInputLockSha256},
    [ordered]@{id='J01_R12_READINESS';path=$r12FailureReadiness;bytes=$r12FailureReadinessBytes;sha256=$r12FailureReadinessSha256},
    [ordered]@{id='J01_R12_PROGRESS';path=$r12FailureProgress;bytes=$r12FailureProgressBytes;sha256=$r12FailureProgressSha256},
    [ordered]@{id='J01_R12_PARTIAL_J00_ASSEMBLY';path=$r12PartialJ00Assembly;bytes=$r12PartialJ00AssemblyBytes;sha256=$r12PartialJ00AssemblySha256},
    [ordered]@{id='J01_R12_STATIC_RELEASE';path=$r12PredecessorStaticRelease;bytes=$r12PredecessorStaticReleaseBytes;sha256=$r12PredecessorStaticReleaseSha256},
    [ordered]@{id='J01_R12_ACTIVATION';path=$r12PredecessorCreateActivation;bytes=$r12PredecessorCreateActivationBytes;sha256=$r12PredecessorCreateActivationSha256},
    [ordered]@{id='J01_R12_SOURCE';path=$r12Source;bytes=$r12SourceBytes;sha256=$r12SourceSha256},
    [ordered]@{id='J01_R12_RUNNER';path=$r12Runner;bytes=$r12RunnerBytes;sha256=$r12RunnerSha256},
    [ordered]@{id='J01_R12_BINARY';path=$r12Binary;bytes=$r12BinaryBytes;sha256=$r12BinarySha256}
)
$r13ClosureLockedArtifacts = @(
    [ordered]@{id='J01_R13_INPUT_LOCK';path=$r13FailureInputLock;bytes=$r13FailureInputLockBytes;sha256=$r13FailureInputLockSha256},
    [ordered]@{id='J01_R13_READINESS';path=$r13FailureReadiness;bytes=$r13FailureReadinessBytes;sha256=$r13FailureReadinessSha256},
    [ordered]@{id='J01_R13_PROGRESS';path=$r13FailureProgress;bytes=$r13FailureProgressBytes;sha256=$r13FailureProgressSha256},
    [ordered]@{id='J01_R13_PARTIAL_J00_ASSEMBLY';path=$r13PartialJ00Assembly;bytes=$r13PartialJ00AssemblyBytes;sha256=$r13PartialJ00AssemblySha256},
    [ordered]@{id='J01_R13_STATIC_RELEASE';path=$r13PredecessorStaticRelease;bytes=$r13PredecessorStaticReleaseBytes;sha256=$r13PredecessorStaticReleaseSha256},
    [ordered]@{id='J01_R13_ACTIVATION';path=$r13PredecessorCreateActivation;bytes=$r13PredecessorCreateActivationBytes;sha256=$r13PredecessorCreateActivationSha256},
    [ordered]@{id='J01_R13_SOURCE';path=$r13Source;bytes=$r13SourceBytes;sha256=$r13SourceSha256},
    [ordered]@{id='J01_R13_RUNNER';path=$r13Runner;bytes=$r13RunnerBytes;sha256=$r13RunnerSha256},
    [ordered]@{id='J01_R13_BINARY';path=$r13Binary;bytes=$r13BinaryBytes;sha256=$r13BinarySha256}
)
$recoveryLockedArtifacts = @($recoveryPrerequisites) + @($r8ClosureLockedArtifacts) +
    @($r9ClosureLockedArtifacts) + @($r10ClosureLockedArtifacts) + @($r11ClosureLockedArtifacts) +
    @($r12ClosureLockedArtifacts) + @($r13ClosureLockedArtifacts)

$readinessReceipt = Join-Path $sessionRoot "B51R1_S05R2_J01_R14_$($Mode.ToUpperInvariant())_READINESS_RECEIPT.json"
$inputLock = Join-Path $sessionRoot "B51R1_S05R2_J01_R14_$($Mode.ToUpperInvariant())_INPUT_LOCK.json"
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
    if ($created.schema -ne 'B51R1_S05R2_J01_R14_NATIVE_1R_CREATE_GATE_V1' -or
        $created.status -ne 'S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_PASS' -or
        $created.gate_pass -isnot [bool] -or $created.gate_pass -ne $true) {
        throw 'J01 R14 Create Gate is not PASS'
    }
    if ($created.cold_reopen_authorized -isnot [bool] -or $created.cold_reopen_authorized -ne $false) {
        throw 'J01 R14 Create Gate improperly self-authorizes cold reopen'
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
    if ($createdReceipt.schema -ne 'B51R1_S05R2_J01_R14_NATIVE_PILOT_CREATE_V1' -or
        $createdReceipt.status -ne 'S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_PASS' -or
        $createdReceipt.gate_pass -isnot [bool] -or $createdReceipt.gate_pass -ne $true) {
        throw 'J01 R14 Create receipt is not PASS'
    }
    if ([IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath($pilotAssembly) -or
        [IO.Path]::GetFullPath([string]$createdReceipt.output.path) -ne [IO.Path]::GetFullPath([string]$created.output.path) -or
        [long]$createdReceipt.output.bytes -ne [long]$created.output.bytes -or
        [string]$createdReceipt.output.sha256 -ne [string]$created.output.sha256) {
        throw 'J01 Create receipt output binding differs from the Create Gate output'
    }
    $coldLockedArtifacts = @(
        [ordered]@{id='J01_R14_CREATE_GATE';path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate},
        [ordered]@{id='J01_R14_CREATE_RECEIPT';path=$createReceipt;bytes=[long]$created.receipt.bytes;sha256=[string]$created.receipt.sha256},
        [ordered]@{id='J01_R14_PILOT_ASSEMBLY';path=$pilotAssembly;bytes=[long]$created.output.bytes;sha256=[string]$created.output.sha256}
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
        throw 'R14 one-session Software OpenGL launch changed the persistent registry value'
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
    $expectedLockedItemCount = if ($Mode -eq 'Create') { 77 } else { 80 }
    if ($lockedItems.Count -ne $expectedLockedItemCount) {
        throw "J01 R14 locked item count mismatch: expected=$expectedLockedItemCount actual=$($lockedItems.Count)"
    }
    $lock = [ordered]@{
        schema="B51R1_S05R2_J01_R14_$($Mode.ToUpperInvariant())_INPUT_LOCK_V1"
        generated_at=[DateTimeOffset]::Now.ToString('o')
        status="PASS_S05R2_J01_R14_$($Mode.ToUpperInvariant())_INPUTS_HASH_LOCKED"
        mode=$Mode
        runtime_boundary=[ordered]@{
            solidworks_process_id=$launchedPid;launch_handle_process_id=$launchHandle.Id
            launch_handle_matches_sole_process=($launchHandle.Id -eq $launchedPid);process_count=1;document_count=0
            predecessor_process_id=48992;predecessor_pid_present=$r9PredecessorPidPresent
            r10_predecessor_process_id=47036;r10_predecessor_pid_present=$r10PredecessorPidPresent
            r11_predecessor_process_id=51744;r11_predecessor_pid_present=$r11PredecessorPidPresent
            r12_predecessor_process_id=52196;r12_predecessor_pid_present=$r12PredecessorPidPresent
            r13_predecessor_process_id=49640;r13_predecessor_pid_present=$r13PredecessorPidPresent
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
        claim_limit='J01_R14_ONE_SESSION_SOFTWARE_OPENGL_TYPED_MATE_ENTITY_RECOVERY_NATIVE_1R_PILOT_ONLY_NO_FORMAL_S05_G4_T005_OR_FLIGHT_CREDIT'
    }
    Write-JsonCreateNew $inputLock $lock

    [void][Reflection.Assembly]::LoadFile((Resolve-Path -LiteralPath $toolDll).Path)
    if ($Mode -eq 'Create') {
        $result = [B51R1S05R2J01R14NativePilotTool]::Create(
            $launchedPid,$assemblyTemplate,$baseCarrier,$link1Carrier,$j00Assembly,
            $pilotAssembly,$j00Checkpoint,$createReceipt,$createProgress)
        if ($result -ne 0) { throw "J01 Create tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $createReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R14_NATIVE_PILOT_CREATE_V1' -or
            $data.status -ne 'S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R14 Create receipt is not PASS'
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
            throw 'J01 R14 Mate API call ledger count mismatch'
        }
        $expectedEntitySelectionCounts = @(2,2,2,4,3)
        $expectedCreateMatePreselectionCounts = @(2,2,2,4,0)
        foreach ($index in 0..4) {
            $attempt = $mateAttempts[$index]
            if ([long]$attempt.create_mate_data_call_index -ne ($index + 1) -or
                [long]$attempt.create_mate_call_index -ne ($index + 1) -or
                $attempt.mate_data_returned -isnot [bool] -or $attempt.mate_data_returned -ne $true -or
                $attempt.feature_returned -isnot [bool] -or $attempt.feature_returned -ne $true -or
                [long]$attempt.create_mate_error_status -ne 1 -or
                [long]$attempt.mate_alignment_requested -ne 0 -or
                [string]$attempt.mate_alignment_name -ne 'ALIGNED' -or
                @($attempt.entity_selections).Count -ne $expectedEntitySelectionCounts[$index] -or
                [long]$attempt.preselection_count_before_create_mate_data -ne $expectedCreateMatePreselectionCounts[$index] -or
                $attempt.selection_count_at_create_mate_return_is_diagnostic_only -isnot [bool] -or
                $attempt.selection_count_at_create_mate_return_is_diagnostic_only -ne $true -or
                [long]$attempt.selection_count_at_create_mate_return -lt 0 -or
                [long]$attempt.selection_count_at_create_mate_return -gt $expectedCreateMatePreselectionCounts[$index] -or
                [long]$attempt.selection_count_after_post_create_clear -ne 0) {
                throw "J01 R14 Mate API call ledger mismatch at index $index"
            }
        }
        $angleAttempt = $mateAttempts[4]
        if ([long]$angleAttempt.selection_count_before_direct_property_contract_clear -ne 3 -or
            [long]$angleAttempt.selection_count_after_direct_property_contract_clear -ne 0 -or
            [string]$angleAttempt.angle_input_channel -ne
                'DIRECT_ENTITIES_TO_MATE_ONLY_WITH_REFERENCE_ENTITY_UNSET_AFTER_SELECTION_LEDGER_ACQUISITION' -or
            $angleAttempt.direct_property_entities_assigned -isnot [bool] -or
            $angleAttempt.direct_property_entities_assigned -ne $true -or
            $angleAttempt.direct_property_reference_assigned -isnot [bool] -or
            $angleAttempt.direct_property_reference_assigned -ne $false -or
            [long]$angleAttempt.precreate_entities_to_mate_count -ne 2 -or
            @($angleAttempt.precreate_entities_to_mate).Count -ne 2 -or
            $angleAttempt.precreate_reference_entity_is_null -isnot [bool] -or
            $angleAttempt.precreate_reference_entity_is_null -ne $true -or
            [long]$angleAttempt.precreate_selection_count -ne 0 -or
            $angleAttempt.precreate_is_advanced_mate -ne $true -or
            [Math]::Abs([double]$angleAttempt.precreate_angle_rad - 2.8) -gt 1.0e-12 -or
            [double]$angleAttempt.precreate_minimum_angle_rad -ne 0.0 -or
            [Math]::Abs([double]$angleAttempt.precreate_maximum_angle_rad - 5.6) -gt 1.0e-12 -or
            [long]$angleAttempt.precreate_mate_alignment -ne 0 -or
            $angleAttempt.precreate_flip_dimension -ne $false -or
            $null -eq $angleAttempt.create_mate_return_object -or
            $angleAttempt.create_mate_return_object.is_feature -ne $true) {
            throw 'J01 R14 Limit Angle direct-property input-channel ledger mismatch'
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
                throw "J01 R14 selection identity/mark ledger mismatch at index $index"
            }
            $isAssemblyRoot = $index -in @(0,2,4)
            if ($isAssemblyRoot) {
                if ($selection.direct_corresponding_specific_diagnostic_only -ne $false -or
                    $selection.direct_corresponding_specific_has_expected_type -ne $true -or
                    $selection.selected_specific_matches_direct_corresponding_specific -ne $true -or
                    $null -ne $selection.expected_owner_component -or $null -ne $selection.expected_owner_path -or
                    $null -ne $selection.selected_owner_component -or $null -ne $selection.selected_owner_path) {
                    throw "J01 R14 assembly-root selection unexpectedly has a component owner at index $index"
                }
            }
            else {
                $expectedOwnerPath = if ($index -in @(1,3,5,6,8,10,12)) { $baseCarrier } else { $link1Carrier }
                if ($selection.direct_corresponding_specific_diagnostic_only -ne $true -or
                    [string]::IsNullOrWhiteSpace([string]$selection.expected_owner_component) -or
                    [string]$selection.selected_owner_component -ne [string]$selection.expected_owner_component -or
                    [IO.Path]::GetFullPath([string]$selection.expected_owner_path) -ne [IO.Path]::GetFullPath($expectedOwnerPath) -or
                    [IO.Path]::GetFullPath([string]$selection.selected_owner_path) -ne [IO.Path]::GetFullPath($expectedOwnerPath)) {
                    throw "J01 R14 selected owner binding mismatch at index $index"
                }
            }
            if ($null -ne $selection.selected_feature_matches_context_feature -and
                ($selection.selected_feature_matches_context_feature -isnot [bool] -or
                 $selection.selected_feature_matches_context_feature -ne $true)) {
                throw "J01 R14 selected context-Feature identity mismatch at index $index"
            }
        }
        $preloads = @($data.preload_operations)
        if ($preloads.Count -ne 2 -or [long]$data.document_count_before_new_assembly -ne 2 -or
            [long]$data.document_count_after_new_assembly -ne 3) {
            throw 'J01 R14 preload count or assembly document-count transition mismatch'
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
                throw "J01 R14 strict preload evidence mismatch: $expectedRole"
            }
        }
        foreach ($item in $lockedItems) {
            Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "CREATE_POST_$($item.id)"
        }
        Assert-File $pilotAssembly ([long]$data.output.bytes) ([string]$data.output.sha256) 'J01 Pilot output'
        foreach ($item in $mr2Inputs) { Assert-File ([string]$item.path) ([long]$item.bytes) ([string]$item.sha256) "MR2_$($item.link)_POST" }
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) { throw 'SOLIDWORKS remains after J01 Create normal exit' }
        $gate = [ordered]@{
            schema='B51R1_S05R2_J01_R14_NATIVE_1R_CREATE_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R14_NATIVE_1R_PILOT_CREATE_PASS';gate_pass=$true
            receipt=[ordered]@{path=$createReceipt;bytes=(Get-Item $createReceipt).Length;sha256=Get-Sha $createReceipt}
            j00_checkpoint=[ordered]@{path=$j00Checkpoint;bytes=(Get-Item $j00Checkpoint).Length;sha256=Get-Sha $j00Checkpoint}
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{preloaded_before_new_assembly=$true;strict_preload_errors_and_warnings_zero=$true;preloaded_read_only_state_verified=$true;repair_error_bit_not_relaxed=$true;standalone_titles_closed_after_insertion=$true;typed_refplane_refaxis_mate_entities=$true;specific_object_get_corresponding_before_selection=$true;get_name_for_selection_and_select_by_id2=$true;selectionmgr_identity_and_owner_gate=$true;select_by_id2_call_count=13;selection_marks_exact=$true;mate_alignment_aligned=$true;mate_api_call_ledger_at_call_sites=$true;j00_three_root_plane_mates=$true;automatic_fix_removed=$true;j01_native_hinge_angle_selection_false=$true;j01_limit_angle_two_plane_semantic_binding=$true;j01_limit_angle_reference_entity_diagnostic_only=$true;native_create_mate_data_readback_pass=$true;unique_native_limit_angle_driver=$true;native_limits_0_to_5p6_rad=$true;remaining_dof_exactly_one_rotation=$true;canonical_plus_minus_one_degree_pass=$true;enhanced_branch_and_endpoint_sweep_pass=$true;ten_q0_reset_cycles_pass=$true;returned_to_q0=$true;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            cold_reopen_authorized=$false;separate_cold_verify_activation_required=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R14_SELECTIONMGR_BOUND_TYPED_MATE_ENTITY_RECOVERY_CREATE_AND_SAME_DOCUMENT_DRIVER_EVIDENCE_ONLY_PENDING_INDEPENDENT_COLD_REOPEN'
        }
        Write-JsonCreateNew $createGate $gate
        Write-Output $createGate
    }
    else {
        $result = [B51R1S05R2J01R14NativePilotTool]::ColdVerify(
            $launchedPid,$pilotAssembly,
            $baseCarrier,$baseCarrierBytes,$baseCarrierSha256,
            $link1Carrier,$link1CarrierBytes,$link1CarrierSha256,
            $coldReceipt,$coldProgress)
        if ($result -ne 0) { throw "J01 ColdVerify tool returned $result" }
        $data = Get-Content -Raw -Encoding UTF8 -LiteralPath $coldReceipt | ConvertFrom-Json
        if ($data.schema -ne 'B51R1_S05R2_J01_R14_NATIVE_PILOT_COLD_REOPEN_V1' -or
            $data.status -ne 'S05R2_J01_R14_NATIVE_1R_PILOT_COLD_REOPEN_PASS' -or
            $data.gate_pass -isnot [bool] -or $data.gate_pass -ne $true) {
            throw 'J01 R14 ColdVerify receipt is not PASS'
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
            throw 'J01 R14 ColdVerify did not resolve parent and child uniquely in one component traversal'
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
                throw "J01 R14 ColdVerify component identity mismatch: $role"
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
            schema='B51R1_S05R2_J01_R14_NATIVE_1R_GATE_V1';generated_at=[DateTimeOffset]::Now.ToString('o')
            status='S05R2_J01_R14_NATIVE_1R_PILOT_PASS';gate_pass=$true
            create_gate=[ordered]@{path=$createGate;bytes=(Get-Item $createGate).Length;sha256=Get-Sha $createGate}
            receipt=$coldReceiptBinding
            cold_reopen_receipt=$coldReceiptBinding
            output=[ordered]@{path=$pilotAssembly;bytes=(Get-Item $pilotAssembly).Length;sha256=Get-Sha $pilotAssembly}
            checks=[ordered]@{assembly_opened_read_only=$true;single_get_components_identity_traversal=$true;component_identity_full_path_bytes_sha256=$true;target_component_rcws_not_final_released=$true;native_hinge_and_limit_mates_persisted=$true;native_hinge_axis_and_limit_plane_semantics_persisted=$true;native_limit_reference_entity_diagnostic_only=$true;native_limit_bounds_and_q0_persisted=$true;remaining_dof_exactly_one_rotation=$true;base_and_link1_not_fixed=$true;ten_cold_q0_samples_pass=$true;cold_plus_minus_one_degree_pass=$true;cold_branch_witnesses_pass=$true;returned_to_q0_after_cold_drive=$true;assembly_hash_stable=$true;mr2_input_hashes_stable=$true;normal_application_exit=$true;save_api_call_count=0;transform2_call_count=0;move_component_call_count=0;set_transform_and_solve_call_count=0}
            mr2_batch_create_authorized=$true;formal_s05_authorized=$false;t005_authorized=$false
            claim_limit='J01_R14_SELECTIONMGR_BOUND_TYPED_MATE_ENTITY_RECOVERY_NATIVE_1R_PILOT_GATE_ONLY_NO_COMPLETE_CHAIN_G4_T005_STRUCTURAL_MANUFACTURING_OR_FLIGHT_CREDIT'
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
