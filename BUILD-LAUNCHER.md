# WOPR Launcher

Le launcher WOPR utilise une source commune pour Linux et Windows :

```text
public/launcher/wopr_launcher.py
```

## Binaires officiels

```text
WOPR      -> Linux
WOPR.exe  -> Windows
```

Les binaires officiels sont placés à la racine du projet WOPR.

## Compilation Linux

Depuis la racine du projet :

```bash
python3 -m PyInstaller --onefile --windowed --name WOPR public/launcher/wopr_launcher.py
cp -f dist/WOPR ./WOPR
chmod +x ./WOPR
```

Test :

```bash
./WOPR
```

Nettoyage après compilation :

```bash
rm -rf build dist WOPR.spec
```

Le binaire `WOPR` copié à la racine est conservé.

## Compilation Windows

La version Windows est compilée directement avec l'environnement Python Windows de WOPR :

```text
private\.venv-win
```

Depuis la racine du projet :

```powershell
.\private\.venv-win\Scripts\python.exe -m PyInstaller --onefile --windowed --name WOPR --icon public\static\WOPR.ico public\launcher\wopr_launcher.py
```

Puis remplacer le binaire officiel à la racine :

```powershell
Copy-Item .\dist\WOPR.exe .\WOPR.exe -Force
```

Test :

```powershell
.\WOPR.exe
```

### Nettoyage après compilation Windows

Une fois `dist\WOPR.exe` copié en `WOPR.exe` à la racine, les fichiers temporaires générés par PyInstaller peuvent être supprimés :

```powershell
Remove-Item .\build,.\dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item .\WOPR.spec -Force -ErrorAction SilentlyContinue
```

À conserver :

```text
WOPR.exe
private\.venv-win
```

`private\.venv-win` reste nécessaire au fonctionnement de WOPR sous Windows et ne doit pas être supprimé.

## SQLCipher

WOPR utilise la même base SQLCipher sous Linux et Windows.

Les dépendances sont sélectionnées automatiquement par `public/requirements.txt` :

```text
sqlcipher3-binary==0.6.0; platform_system == "Linux"
sqlcipher3==0.6.2; platform_system == "Windows"
```

Le code Python conserve le même import sur les deux plateformes :

```python
from sqlcipher3 import dbapi2 as sqlcipher
```

## PyInstaller

PyInstaller est nécessaire uniquement pour reconstruire les launchers compilés.

Sous Windows, il peut être installé automatiquement via `public/requirements.txt` si la dépendance suivante y est présente :

```text
pyinstaller>=6.0; platform_system == "Windows"
```

## Remarque

Les anciens scripts de build et les anciens chemins de sortie sous :

```text
public/launcher/dist/
```

ne sont plus utilisés.

Le fichier source de référence à maintenir est :

```text
public/launcher/wopr_launcher.py
```

Après toute modification du launcher, recompiler le binaire correspondant :

```text
WOPR      -> Linux
WOPR.exe  -> Windows
```
