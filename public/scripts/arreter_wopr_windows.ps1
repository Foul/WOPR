$ErrorActionPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublicDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$WoprDir = (Resolve-Path (Join-Path $PublicDir "..")).Path
$PrivateDir = Join-Path $WoprDir "private"
$PidFile = Join-Path $PrivateDir "data\wopr.pid"
$AppPath = Join-Path $PublicDir "app.py"

$pids = New-Object System.Collections.Generic.HashSet[int]

if (Test-Path $PidFile) {
    $pidText = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    $serverPid = 0
    if ([int]::TryParse($pidText, [ref]$serverPid)) {
        [void]$pids.Add($serverPid)
    }
}

# Filet de sécurité : uniquement Python/pythonw lançant exactement ce WOPR\public\app.py.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine.IndexOf($AppPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    } |
    ForEach-Object {
        [void]$pids.Add([int]$_.ProcessId)
    }

foreach ($processId in $pids) {
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

# Attend réellement la fin des processus avant de sauvegarder la base.
for ($i = 0; $i -lt 20; $i++) {
    $stillRunning = $false
    foreach ($processId in $pids) {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            $stillRunning = $true
            break
        }
    }
    if (-not $stillRunning) { break }
    Start-Sleep -Milliseconds 250
}

$backupOk = $false
$backupName = ""
if ($pids.Count -gt 0 -and (Test-Path $AppPath)) {
    $pythonExe = Join-Path $PrivateDir ".venv-win\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            $pythonExe = $pythonCmd.Source
        } else {
            $pythonExe = ""
        }
    }

    if ($pythonExe) {
        $backupOutput = & $pythonExe $AppPath --backup-arret 2>$null
        if ($LASTEXITCODE -eq 0 -and $backupOutput) {
            $backupPath = [string]($backupOutput | Select-Object -Last 1)
            if (Test-Path $backupPath) {
                $backupOk = $true
                $backupName = Split-Path -Leaf $backupPath
            }
        }
    }
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

Add-Type -AssemblyName PresentationFramework
if ($pids.Count -gt 0) {
    if ($backupOk) {
        [System.Windows.MessageBox]::Show("Toutes les instances WOPR ont été arrêtées.`nSauvegarde créée : $backupName", "WOPR") | Out-Null
    } else {
        [System.Windows.MessageBox]::Show("Toutes les instances WOPR ont été arrêtées, mais la sauvegarde de fermeture a échoué.", "WOPR") | Out-Null
    }
} else {
    [System.Windows.MessageBox]::Show("WOPR est déjà arrêté.", "WOPR") | Out-Null
}
exit 0
