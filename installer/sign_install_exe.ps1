param(
    [string]$ExePath = '',
    [string]$PfxPath = '',
    [string]$Password = 'uploadpicker-local',
    [switch]$Timestamp
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $ExePath) {
    $ExePath = Join-Path $ProjectRoot 'dist\UploadPicker-Install.exe'
}
if (-not $PfxPath) {
    $PfxPath = Join-Path $ProjectRoot 'installer\certs\uploadpicker-codesign.pfx'
}

if (-not (Test-Path $ExePath)) {
    throw "EXE が見つかりません: $ExePath"
}
if (-not (Test-Path $PfxPath)) {
    throw "PFX が見つかりません: $PfxPath"
}

$SecurePassword = ConvertTo-SecureString -String $Password -AsPlainText -Force
$Cert = Get-PfxCertificate -FilePath $PfxPath
$Imported = Import-PfxCertificate -FilePath $PfxPath -Password $SecurePassword -CertStoreLocation 'Cert:\CurrentUser\My'
$Certificate = if ($Imported) { $Imported } else { $Cert }

$Result = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $Certificate -HashAlgorithm SHA256
if ($Result.Status -ne 'Valid') {
    throw "署名に失敗しました: $($Result.Status) $($Result.StatusMessage)"
}

if ($Timestamp) {
    Write-Output '自己署名では信頼タイムスタンプを付けても SmartScreen 回避にはなりません。署名のみ完了しています。'
}

Write-Output "Signed: $ExePath"
Write-Output "Thumbprint: $($Certificate.Thumbprint)"
