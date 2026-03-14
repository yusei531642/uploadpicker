param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [string]$TargetPid = ""
)

$ErrorActionPreference = "Stop"

$projectPath = (Resolve-Path $ProjectRoot).Path
$owner = "yusei531642"
$repo = "uploadpicker"
$branch = "main"
$downloadUrl = "https://github.com/$owner/$repo/archive/refs/heads/$branch.zip"

$tempRoot = Join-Path $env:TEMP ("uploadpicker-update-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "uploadpicker.zip"
$extractPath = Join-Path $tempRoot "extract"

try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $extractPath -Force | Out-Null

    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractPath -Force

    $sourceRoot = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    if (-not $sourceRoot) {
        throw "Downloaded archive could not be extracted."
    }

    Start-Sleep -Seconds 2

    if ($TargetPid) {
        Stop-Process -Id ([int]$TargetPid) -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    $folderNames = @("app", "installer")
    foreach ($folderName in $folderNames) {
        $sourceFolder = Join-Path $sourceRoot.FullName $folderName
        $targetFolder = Join-Path $projectPath $folderName
        if (Test-Path $sourceFolder) {
            New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
            robocopy $sourceFolder $targetFolder /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ | Out-Null
        }
    }

    $fileNames = @(
        ".env.example",
        ".gitignore",
        "Install UploadPicker.bat",
        "Start UploadPicker.bat",
        "Uninstall UploadPicker.bat",
        "Update UploadPicker.bat",
        "UploadPicker.bat",
        "README.md",
        "pyproject.toml",
        "yolov8n.pt"
    )
    foreach ($fileName in $fileNames) {
        $sourceFile = Join-Path $sourceRoot.FullName $fileName
        $targetFile = Join-Path $projectPath $fileName
        if (Test-Path $sourceFile) {
            Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force
        }
    }

    $installScript = Join-Path $projectPath "Install UploadPicker.bat"
    $installProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$installScript`" --no-pause" -WorkingDirectory $projectPath -Wait -PassThru
    if ($installProcess.ExitCode -ne 0) {
        throw "Install / Repair failed during update."
    }

    $startScript = Join-Path $projectPath "Start UploadPicker.bat"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$startScript`"" -WorkingDirectory $projectPath
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
