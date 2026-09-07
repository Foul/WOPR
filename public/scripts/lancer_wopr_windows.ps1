$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublicDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$WoprDir = (Resolve-Path (Join-Path $PublicDir "..")).Path
$PrivateDir = Join-Path $WoprDir "private"
$DataDir = Join-Path $PrivateDir "data"
$VenvDir = Join-Path $PrivateDir ".venv-win"
$PidFile = Join-Path $DataDir "wopr.pid"
$LauncherLog = Join-Path $DataDir "wopr-launcher.log"
$ServerOutLog = Join-Path $DataDir "wopr-server.log"
$ServerErrLog = Join-Path $DataDir "wopr-server-error.log"
$LockFile = Join-Path $DataDir "wopr-launcher.lock"
$DepsStamp = Join-Path $VenvDir ".requirements.sha256"
$Requirements = Join-Path $PublicDir "requirements.txt"
$AppPath = Join-Path $PublicDir "app.py"
$Url = "http://127.0.0.1:5000"

function Show-WoprMessage {
    param([string]$Text, [string]$Icon = "Information")
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($Text, "WOPR", "OK", $Icon) | Out-Null
}

function Write-LauncherLog {
    param([string]$Text)
    try {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Text" | Add-Content -Path $LauncherLog -Encoding UTF8
    } catch {}
}

function Show-Status {
    param([string]$Text)
    Write-Host ""
    Write-Host "WOPR > $Text"
}

function Test-WOPR {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Get-RequirementsHash {
    if (-not (Test-Path $Requirements)) { return "" }
    return (Get-FileHash -Algorithm SHA256 -Path $Requirements).Hash
}

$lockStream = $null

try {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $PrivateDir "assets") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $PrivateDir "seeds") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $PrivateDir "signatures") | Out-Null

    $DocsDir = Join-Path $PrivateDir "documents"
    $PortableFactures = Join-Path $DocsDir "Factures"
    $PortableDevis = Join-Path $DocsDir "Devis"
    $PortableSuivi = Join-Path $DocsDir "Suivi de réparation"
    New-Item -ItemType Directory -Force -Path $PortableFactures | Out-Null
    New-Item -ItemType Directory -Force -Path $PortableDevis | Out-Null
    New-Item -ItemType Directory -Force -Path $PortableSuivi | Out-Null

    try {
        $lockStream = [System.IO.File]::Open(
            $LockFile,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch {
        Show-WoprMessage "Un démarrage de WOPR est déjà en cours.`n`nPatiente quelques secondes."
        exit 0
    }

    Write-LauncherLog "Démarrage du lanceur Windows."
    Show-Status "Préparation du démarrage..."

    $MigrationMarker = Join-Path $PrivateDir ".documents_portables_v23161"
    if (-not (Test-Path $MigrationMarker)) {
        $ParentDir = (Resolve-Path (Join-Path $WoprDir "..")).Path
        $OldFactures = Join-Path $ParentDir "Factures"
        $OldDevis = Join-Path $ParentDir "Devis"
        if (Test-Path $OldFactures) {
            Copy-Item -Path (Join-Path $OldFactures "*") -Destination $PortableFactures -Recurse -Force:$false -ErrorAction SilentlyContinue
        }
        if (Test-Path $OldDevis) {
            Copy-Item -Path (Join-Path $OldDevis "*") -Destination $PortableDevis -Recurse -Force:$false -ErrorAction SilentlyContinue
        }
        New-Item -ItemType File -Force -Path $MigrationMarker | Out-Null
    }

    $SuivieMarker = Join-Path $PrivateDir ".documents_suivie_portable_v23162"
    if (-not (Test-Path $SuivieMarker)) {
        $ParentDir = (Resolve-Path (Join-Path $WoprDir "..")).Path
        foreach ($OldName in @("Suivie de réparation", "Suivi de réparation")) {
            $OldSuivie = Join-Path $ParentDir $OldName
            if (Test-Path $OldSuivie) {
                Get-ChildItem -LiteralPath $OldSuivie -Force -ErrorAction SilentlyContinue | ForEach-Object {
                    Copy-Item -LiteralPath $_.FullName -Destination $PortableSuivi -Recurse -Force:$false -ErrorAction SilentlyContinue
                }
            }
        }
        New-Item -ItemType File -Force -Path $SuivieMarker | Out-Null
    }

    if (Test-WOPR) {
        Write-LauncherLog "WOPR déjà actif."
        Show-Status "WOPR est déjà lancé. Ouverture du navigateur..."
        Start-Sleep -Milliseconds 400
        Start-Process $Url
        exit 0
    }

    if (Test-Path $PidFile) {
        $pidText = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        $oldPid = 0
        if ($pidText -and [int]::TryParse($pidText.Trim(), [ref]$oldPid)) {
            $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($oldProc) {
                for ($i = 0; $i -lt 120; $i++) {
                    if (Test-WOPR) {
                        Write-LauncherLog "WOPR disponible après attente."
                        Start-Process $Url
                        exit 0
                    }
                    if (-not (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { break }
                    Start-Sleep -Milliseconds 500
                }
            }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }

    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    $VenvPythonW = Join-Path $VenvDir "Scripts\pythonw.exe"

    if (-not (Test-Path $VenvPython)) {
        $Launcher = $null
        $LauncherArgs = @()

        if (Get-Command py.exe -ErrorAction SilentlyContinue) {
            $Launcher = "py.exe"
            $LauncherArgs = @("-3")
        } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
            $Launcher = "python.exe"
        } elseif (Get-Command python3.exe -ErrorAction SilentlyContinue) {
            $Launcher = "python3.exe"
        }

        if (-not $Launcher) {
            Show-WoprMessage "Python 3 est nécessaire pour lancer WOPR sur cette machine.`n`nInstalle Python 3 puis relance WOPR." "Warning"
            exit 1
        }

        Show-WoprMessage "Premier lancement de WOPR sur Windows.`n`nL'environnement Python va être préparé automatiquement.`nCela peut prendre quelques minutes."

        Write-LauncherLog "Création de l'environnement Python."
        Show-Status "Création de l'environnement Python..."
        & $Launcher @LauncherArgs -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Impossible de créer l'environnement Python." }
    }

    $wantedHash = Get-RequirementsHash
    $installedHash = ""
    if (Test-Path $DepsStamp) {
        $installedHash = (Get-Content $DepsStamp -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    }

    $depsOk = $false
    if ($wantedHash -and $installedHash -eq $wantedHash) {
        $depsOk = $true
    } else {
        & $VenvPython -c "import flask, reportlab, qrcode; from google.oauth2.credentials import Credentials; from google_auth_oauthlib.flow import Flow; from googleapiclient.discovery import build" 1>$null 2>$null
        if ($LASTEXITCODE -eq 0 -and $wantedHash) {
            Set-Content -Path $DepsStamp -Value $wantedHash -Encoding ASCII
            $depsOk = $true
        }
    }

    if (-not $depsOk) {
        Show-WoprMessage "WOPR doit mettre à jour ses dépendances Python.`n`nL'opération peut prendre quelques minutes et ne sera pas répétée aux prochains démarrages."
        Write-LauncherLog "Installation / mise à jour des dépendances."
        Show-Status "Installation / mise à jour des dépendances Python..."
        & $VenvPython -m pip install -r $Requirements *>> $LauncherLog
        if ($LASTEXITCODE -ne 0) {
            Show-WoprMessage "L'installation des dépendances a échoué.`n`nDétail :`n$LauncherLog" "Error"
            exit 1
        }

        $wantedHash = Get-RequirementsHash
        if ($wantedHash) {
            Set-Content -Path $DepsStamp -Value $wantedHash -Encoding ASCII
        }
    }

    if (-not (Test-Path $AppPath)) { throw "public\app.py est introuvable." }

    Remove-Item $ServerOutLog -Force -ErrorAction SilentlyContinue
    Remove-Item $ServerErrLog -Force -ErrorAction SilentlyContinue

    $RunPython = if (Test-Path $VenvPythonW) { $VenvPythonW } else { $VenvPython }

    Write-LauncherLog "Lancement de WOPR avec $RunPython"
    Show-Status "Lancement du serveur WOPR..."

    $p = Start-Process `
        -FilePath $RunPython `
        -ArgumentList @("`"$AppPath`"") `
        -WorkingDirectory $PublicDir `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $ServerOutLog `
        -RedirectStandardError $ServerErrLog

    Set-Content -Path $PidFile -Value $p.Id -Encoding ASCII

    Show-Status "Initialisation de WOPR, merci de patienter..."

    for ($i = 0; $i -lt 180; $i++) {
        if (Test-WOPR) {
            Write-LauncherLog "WOPR prêt (PID $($p.Id))."
            Show-Status "WOPR est prêt. Ouverture du navigateur..."
            Start-Sleep -Milliseconds 700
            Start-Process $Url
            exit 0
        }

        if ($p.HasExited) {
            $detail = ""
            if (Test-Path $ServerErrLog) {
                $detail = (Get-Content $ServerErrLog -Tail 8 -ErrorAction SilentlyContinue) -join "`n"
            }
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            Write-LauncherLog "WOPR s'est arrêté pendant le démarrage."
            if ($detail) {
                Show-WoprMessage "WOPR n'a pas pu démarrer.`n`n$detail`n`nLog : $ServerErrLog" "Error"
            } else {
                Show-WoprMessage "WOPR n'a pas pu démarrer.`n`nConsulte :`n$LauncherLog`n$ServerErrLog" "Error"
            }
            exit 1
        }

        Start-Sleep -Milliseconds 500
        $p.Refresh()
    }

    Write-LauncherLog "Délai de démarrage dépassé."
    Show-WoprMessage "WOPR met trop de temps à démarrer.`n`nLe processus est toujours actif (PID $($p.Id)).`nConsulte les logs dans :`n$DataDir" "Warning"
    exit 1
}
catch {
    $message = $_.Exception.Message
    Write-LauncherLog "ERREUR : $message"
    try { Show-WoprMessage "Erreur au lancement de WOPR :`n`n$message`n`nDétail :`n$LauncherLog" "Error" } catch {}
    exit 1
}
finally {
    if ($lockStream) {
        try { $lockStream.Dispose() } catch {}
    }
}
