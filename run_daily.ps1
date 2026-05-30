$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\lds\AppData\Local\Programs\Python\Python312\python.exe"
$LogDir = Join-Path $ProjectDir "debug"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location -LiteralPath $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "task_$Stamp.log"

& $PythonExe (Join-Path $ProjectDir "main.py") *>&1 | Tee-Object -FilePath $LogFile
exit $LASTEXITCODE
