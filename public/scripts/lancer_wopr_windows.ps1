$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PublicDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$WoprDir = (Resolve-Path (Join-Path $PublicDir "..")).Path
$PrivateDir = Join-Path $WoprDir "private"
$DataDir = Join-Path $PrivateDir "data"
$VenvDir = Join-Path $PrivateDir ".venv-win"
$PidFile = Join-Path $DataDir "wopr.pid"
$LogFile = Join-Path $DataDir "wopr-launcher.log"
$Url = "http://127.0.0.1:5000"

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

# Migration sûre de l'ancienne disposition : copie uniquement, une fois.
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

# V2.3.163 : migration séparée de l'archive « Suivi de réparation ».
# Séparée du marker v2.3.161 pour fonctionner même si Factures/Devis ont déjà été migrés.
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

function Test-WOPR {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

if (Test-WOPR) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("WOPR est déjà lancé.", "WOPR") | Out-Null
    Start-Process $Url
    exit 0
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
        Add-Type -AssemblyName PresentationFramework
        $answer = [System.Windows.MessageBox]::Show(
            "Python 3 est nécessaire pour lancer WOPR sur cette machine.`n`nIl n'a pas été trouvé.`n`nOuvrir la page officielle de téléchargement de Python ?",
            "WOPR",
            "YesNo",
            "Warning"
        )
        if ($answer -eq "Yes") {
            Start-Process "https://www.python.org/downloads/windows/"
        }
        exit 1
    }

    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Premier lancement de WOPR sur Windows.`n`nL'environnement Python et les dépendances vont être préparés automatiquement.`nCela peut prendre quelques minutes.`n`nAucune fenêtre de console n'est nécessaire.",
        "WOPR",
        "OK",
        "Information"
    ) | Out-Null

    & $Launcher @LauncherArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Impossible de créer l'environnement Python." }

    & $VenvPython -m pip install --upgrade pip *>> $LogFile
    & $VenvPython -m pip install -r (Join-Path $PublicDir "requirements.txt") *>> $LogFile
    if ($LASTEXITCODE -ne 0) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "L'installation des dépendances a échoué.`n`nVérifie la connexion Internet puis relance WOPR.`nLe détail est enregistré dans WOPR\private\data\wopr-launcher.log",
            "WOPR",
            "OK",
            "Error"
        ) | Out-Null
        exit 1
    }

    [System.Windows.MessageBox]::Show(
        "WOPR est prêt sur cette machine.`n`nWOPR va maintenant démarrer.",
        "WOPR",
        "OK",
        "Information"
    ) | Out-Null
}

# Petite vérification des dépendances. Si nécessaire, on réinstalle requirements.txt.
$check = @'
import flask, reportlab, qrcode
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
'@
$check | & $VenvPython - 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install -r (Join-Path $PublicDir "requirements.txt") *>> $LogFile
}

$RunPython = if (Test-Path $VenvPythonW) { $VenvPythonW } else { $VenvPython }
$AppPath = Join-Path $PublicDir "app.py"

"===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - démarrage WOPR Windows =====" | Add-Content $LogFile

$p = Start-Process `
    -FilePath $RunPython `
    -ArgumentList @("`"$AppPath`"") `
    -WorkingDirectory $PublicDir `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $LogFile

Set-Content -Path $PidFile -Value $p.Id -Encoding ascii

for ($i = 0; $i -lt 50; $i++) {
    Start-Sleep -Milliseconds 250
    if (Test-WOPR) {
        Start-Process $Url
        exit 0
    }
    if ($p.HasExited) { break }
}

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
    "WOPR n'a pas démarré correctement.`nConsulte WOPR\private\data\wopr-launcher.log",
    "WOPR",
    "OK",
    "Error"
) | Out-Null
exit 1
