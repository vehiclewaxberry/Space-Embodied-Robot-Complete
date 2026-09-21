$ErrorActionPreference = 'Stop'

$root = 'F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION'
$directivePath = Join-Path $root 'design\NATIVE_MECH_REAL_01_STAGE2_RECOVERY_DIRECTIVE.md'
$claudeExe = 'C:\Users\stude\.bun\bin\claude.exe'

Set-Location -LiteralPath $root

$solidWorks = @(Get-Process SLDWORKS -ErrorAction SilentlyContinue)
if ($solidWorks.Count -ne 1 -or -not $solidWorks[0].Responding) {
    throw 'Recovery writer not started: exactly one responding SolidWorks process is required.'
}

$directive = Get-Content -LiteralPath $directivePath -Raw -Encoding UTF8
$prompt = @"
You are a fresh, bounded SolidWorks CAD writer. Do not continue or infer any
unfinished action from another Claude session. Read and obey the directive
below literally. The directive is the entire authorized task.

$directive

Before any CAD or process action, repeat the forbidden-action list internally
and verify there is exactly one responding SLDWORKS.exe. Never terminate,
restart, or launch SolidWorks. If any precondition or API call fails, write the
required HOLD evidence and stop.
"@

& $claudeExe `
    --print `
    $prompt `
    --output-format stream-json `
    --verbose `
    --permission-mode bypassPermissions

exit $LASTEXITCODE
