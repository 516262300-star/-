$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\lds\AppData\Local\Programs\Python\Python312\python.exe"
$LogDir = Join-Path $ProjectDir "debug"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location -LiteralPath $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "task_$Stamp.log"

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Start PDD Notion sync" | Tee-Object -FilePath $LogFile
$ErrorActionPreference = "Continue"
& $PythonExe (Join-Path $ProjectDir "main.py") --store all 2>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Exit code: $ExitCode" | Tee-Object -FilePath $LogFile -Append
exit $ExitCode
