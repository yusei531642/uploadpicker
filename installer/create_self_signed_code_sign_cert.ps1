param(
    [string]$Subject = 'CN=UploadPicker Local Code Signing',
    [string]$Password = 'uploadpicker-local',
    [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not $OutputDir) {
    $OutputDir = Join-Path $ProjectRoot 'installer\certs'
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$Cert = New-SelfSignedCertificate \
    -Subject $Subject \
    -Type CodeSigningCert \
    -CertStoreLocation 'Cert:\CurrentUser\My' \
    -KeyAlgorithm RSA \
    -KeyLength 4096 \
    -HashAlgorithm SHA256 \
    -NotAfter (Get-Date).AddYears(3)

$SecurePassword = ConvertTo-SecureString -String $Password -AsPlainText -Force
$PfxPath = Join-Path $OutputDir 'uploadpicker-codesign.pfx'
$CerPath = Join-Path $OutputDir 'uploadpicker-codesign.cer'

Export-PfxCertificate -Cert $Cert -FilePath $PfxPath -Password $SecurePassword | Out-Null
Export-Certificate -Cert $Cert -FilePath $CerPath | Out-Null

Write-Output "Thumbprint: $($Cert.Thumbprint)"
Write-Output "PFX: $PfxPath"
Write-Output "CER: $CerPath"
Write-Output "Password: $Password"
