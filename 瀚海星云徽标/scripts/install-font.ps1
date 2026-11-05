$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$fontSource = Join-Path $projectRoot 'assets\fonts\ZhiMangXing-Regular.ttf'
$fontDirectory = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$fontDestination = Join-Path $fontDirectory 'ZhiMangXing-Regular.ttf'
$fontRegistryPath = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
$fontRegistryName = 'Zhi Mang Xing Regular (TrueType)'
$sourceHash = (Get-FileHash -LiteralPath $fontSource).Hash
if (Test-Path -LiteralPath $fontDestination) {
    if ((Get-FileHash -LiteralPath $fontDestination).Hash -ne $sourceHash) {
        throw '目标位置已存在内容不同的字体文件。'
    }
}
$fontRegistry = Get-Item -LiteralPath $fontRegistryPath
$registeredPath = $fontRegistry.GetValue($fontRegistryName, $null)
if ($null -ne $registeredPath -and $registeredPath -ne $fontDestination) {
    throw '当前用户已经登记了路径不同的同名字体。'
}
New-Item -ItemType Directory -Force -Path $fontDirectory | Out-Null
if (-not (Test-Path -LiteralPath $fontDestination)) {
    Copy-Item -LiteralPath $fontSource -Destination $fontDestination
}
New-ItemProperty -LiteralPath $fontRegistryPath -Name $fontRegistryName -Value $fontDestination -PropertyType String -Force | Out-Null
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class HanhaiFontInstall {
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int AddFontResourceExW(string path, uint flags, IntPtr reserved);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SendMessageTimeoutW(IntPtr window, uint message, UIntPtr wParam, IntPtr lParam, uint flags, uint timeout, out UIntPtr result);
}
'@
$fontCount = [HanhaiFontInstall]::AddFontResourceExW($fontDestination, 0, [IntPtr]::Zero)
if ($fontCount -le 0) { throw 'Windows 加载字体失败。' }
$notificationResult = [UIntPtr]::Zero
$notification = [HanhaiFontInstall]::SendMessageTimeoutW([IntPtr]65535, 29, [UIntPtr]::Zero, [IntPtr]::Zero, 2, 2000, [ref]$notificationResult)
if ($notification -eq [IntPtr]::Zero) { throw 'Windows 字体更新通知未完成。' }
if ((Get-FileHash -LiteralPath $fontDestination).Hash -ne $sourceHash) { throw '安装后的字体文件与源文件不同。' }
if ((Get-ItemPropertyValue -LiteralPath $fontRegistryPath -Name $fontRegistryName) -ne $fontDestination) { throw '字体登记路径验证失败。' }
$shellProgram = (Get-Process -Id $PID).Path
& $shellProgram -NoProfile -File (Join-Path $PSScriptRoot 'verify-font.ps1')
if ($LASTEXITCODE -ne 0) { throw '独立进程验证字体安装失败。' }
