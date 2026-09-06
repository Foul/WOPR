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

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

Add-Type -AssemblyName PresentationFramework
if ($pids.Count -gt 0) {
    [System.Windows.MessageBox]::Show("Toutes les instances WOPR ont été arrêtées.", "WOPR") | Out-Null
} else {
    [System.Windows.MessageBox]::Show("WOPR est déjà arrêté.", "WOPR") | Out-Null
}
exit 0
