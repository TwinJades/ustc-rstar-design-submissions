$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$fontSource = Join-Path $projectRoot 'assets\fonts\ZhiMangXing-Regular.ttf'
$fontDestination = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts\ZhiMangXing-Regular.ttf'
$fontRegistryPath = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$fontRegistryName = 'Zhi Mang Xing Regular (TrueType)'
if ((Get-FileHash -LiteralPath $fontDestination).Hash -ne (Get-FileHash -LiteralPath $fontSource).Hash) { throw '已安装字体与项目字体不同。' }
if ((Get-ItemPropertyValue -LiteralPath $fontRegistryPath -Name $fontRegistryName) -ne $fontDestination) { throw '字体登记路径验证失败。' }
Add-Type -AssemblyName System.Drawing
$installedFonts = [System.Drawing.Text.InstalledFontCollection]::new()
$matchingFamilies = @($installedFonts.Families | Where-Object { $_.Name -in @('Zhi Mang Xing', '钟齐志莽行书') } | Select-Object -ExpandProperty Name)
$installedFonts.Dispose()
if ($matchingFamilies.Count -eq 0) { throw 'Windows 已安装字体列表中没有找到志莽行书。' }
[pscustomobject]@{ InstalledFor = $env:USERNAME; Path = $fontDestination; Registered = $true; FontFamilies = $matchingFamilies; FileMatchesSource = $true } | ConvertTo-Json
