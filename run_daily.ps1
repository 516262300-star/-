$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\lds\AppData\Local\Programs\Python\Python312\python.exe"
$LogDir = Join-Path $ProjectDir "debug"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location -LiteralPath $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "task_$Stamp.log"
$SyncDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Start PDD Notion sync" | Tee-Object -FilePath $LogFile
$ErrorActionPreference = "Continue"
& $PythonExe (Join-Path $ProjectDir "main.py") --store all 2>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Exit code: $ExitCode" | Tee-Object -FilePath $LogFile -Append

if ($ExitCode -ne 0) {
    $LogText = Get-Content -LiteralPath $LogFile -Raw
    if ($LogText -match "ERP.*登录态已失效|LoginRequiredError") {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERP login expired; opening relogin window for $SyncDate" | Tee-Object -FilePath $LogFile -Append
        $ReloginCommand = "Set-Location '$ProjectDir'; & '$PythonExe' main.py --date $SyncDate --store all --relogin; Read-Host '运行结束，按回车关闭窗口'"
        Start-Process -FilePath powershell.exe -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $ReloginCommand)
    }
}

exit $ExitCode
