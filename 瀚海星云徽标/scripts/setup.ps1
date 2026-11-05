$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$npmProgram = (Get-Command npm.cmd -ErrorAction Stop).Source
$pythonProgram = (Get-Command python -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path 'assets\fonts','work\temp','output','.cache\pip','.cache\npm' | Out-Null
$env:TEMP = Join-Path $projectRoot 'work\temp'
$env:TMP = $env:TEMP
& $npmProgram install --cache '.cache\npm' --no-audit --no-fund --fetch-retries=1 --fetch-timeout=60000
if ($LASTEXITCODE -ne 0) { throw 'Node.js dependency installation failed.' }
if (-not (Test-Path -LiteralPath 'assets\fonts\ZhiMangXing-Regular.ttf')) {
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/google/fonts/main/ofl/zhimangxing/ZhiMangXing-Regular.ttf' -OutFile 'assets\fonts\ZhiMangXing-Regular.ttf'
}
if (-not (Test-Path -LiteralPath 'assets\fonts\OFL-ZhiMangXing.txt')) {
    Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/google/fonts/main/ofl/zhimangxing/OFL.txt' -OutFile 'assets\fonts\OFL-ZhiMangXing.txt'
}
if (-not (Test-Path -LiteralPath 'assets\P1-reference.png')) { throw 'Missing project reference image: assets\P1-reference.png.' }
$env:NO_PROXY = @($env:NO_PROXY, 'pypi.tuna.tsinghua.edu.cn', 'mirrors.tuna.tsinghua.edu.cn') -join ','
& $pythonProgram -m pip install --index-url 'https://pypi.tuna.tsinghua.edu.cn/simple' --target '.python-deps' --cache-dir '.cache\pip' --requirement 'requirements.txt' --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Write-Output 'Project dependencies, font and reference image are ready.'
