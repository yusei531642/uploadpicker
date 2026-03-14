param(
    [string]$CerPath = ''
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $CerPath) {
    $CerPath = Join-Path $ProjectRoot 'installer\certs\uploadpicker-codesign.cer'
}

if (-not (Test-Path $CerPath)) {
    throw "CER が見つかりません: $CerPath"
}

Import-Certificate -FilePath $CerPath -CertStoreLocation 'Cert:\CurrentUser\TrustedPeople' | Out-Null
Import-Certificate -FilePath $CerPath -CertStoreLocation 'Cert:\CurrentUser\TrustedPublisher' | Out-Null

Write-Output "Trusted: $CerPath"
