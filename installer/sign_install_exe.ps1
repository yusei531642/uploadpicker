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
     throw "EXE not found: $ExePath"
 }
 if (-not (Test-Path $PfxPath)) {
     throw "PFX not found: $PfxPath"
 }
 
 $SecurePassword = ConvertTo-SecureString -String $Password -AsPlainText -Force
 $Imported = Import-PfxCertificate -FilePath $PfxPath -Password $SecurePassword -CertStoreLocation 'Cert:\CurrentUser\My'
 $Thumbprint = $Imported.Thumbprint
 $Certificate = Get-ChildItem 'Cert:\CurrentUser\My' | Where-Object { $_.Thumbprint -eq $Thumbprint } | Select-Object -First 1
 
 if (-not $Certificate) {
     throw "Certificate load failed. Thumbprint: $Thumbprint"
 }
 
 $Result = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $Certificate -HashAlgorithm SHA256
 if ($Result.Status -ne 'Valid') {
     throw "Signing failed: $($Result.Status) $($Result.StatusMessage)"
 }
 
 if ($Timestamp) {
     Write-Output "Self-signed timestamp does not avoid SmartScreen. Signing completed only."
 }
 
 Write-Output "Signed: $ExePath"
 Write-Output "Thumbprint: $Thumbprint"
