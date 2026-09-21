$ErrorActionPreference='Stop'
$auditPath=$PSScriptRoot
$rootPath=[IO.Path]::GetFullPath((Join-Path $auditPath '../../..'))
$publishPath=Join-Path $rootPath '20_engineering/SERVICE_STAR_PUBLICATION_20260921'
if ($publishPath -ne 'F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\SERVICE_STAR_PUBLICATION_20260921') { throw 'Unexpected publication directory' }
$expectedNew='359fa6cd1bc869bbcccdd9a2dedc73ee1a3cee0e'
$expectedOld='fe83adeb2c042568e3fe84a3a7a060a3966133d0'
$gitOptions=@('-c',('safe.directory='+$publishPath.Replace('\','/')),'-c','http.version=HTTP/1.1','-c','http.lowSpeedTime=120','-C',$publishPath)
$env:GIT_TERMINAL_PROMPT='0'
$env:GCM_INTERACTIVE='never'
$head=(& git @gitOptions rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $expectedNew) { throw 'Prepared commit changed' }
& python (Join-Path $publishPath '00_release/verify_package.py')
if ($LASTEXITCODE -ne 0) { throw 'Local file verification failed' }
$remoteLine=& git @gitOptions ls-remote origin refs/heads/main
if ($LASTEXITCODE -ne 0 -or -not $remoteLine) { throw 'Cannot determine remote main; no push attempted' }
$remoteSha=($remoteLine -split '\s+')[0]
if ($remoteSha -eq $expectedNew) {
    Write-Output 'Remote already contains the requested commit; skip push.'
} elseif ($remoteSha -eq $expectedOld) {
    & git @gitOptions push --progress --no-thin --porcelain "--force-with-lease=refs/heads/main:$expectedOld" origin HEAD:refs/heads/main
    if ($LASTEXITCODE -ne 0) { throw 'Push did not confirm success; recheck remote before retry' }
} else {
    throw "Remote main changed to $remoteSha; no overwrite performed"
}
& python (Join-Path $auditPath 'verify_remote_release.py')
if ($LASTEXITCODE -ne 0) { throw 'Remote whole-package verification did not pass' }
