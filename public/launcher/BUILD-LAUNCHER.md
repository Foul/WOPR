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
python3 -m PyInstaller --noconfirm --clean --onefile --windowed --name WOPR public/launcher/wopr_launcher.py
cp -f dist/WOPR ./WOPR
chmod +x ./WOPR
rm -rf build dist WOPR.spec
```

## Compilation Windows

Depuis la racine du projet :

```powershell
.\private\.venv-win\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name WOPR --icon .\public\static\WOPR.ico --distpath . .\public\launcher\wopr_launcher.py
```

Si `WOPR.exe` est encore verrouillé alors qu'aucun processus WOPR n'est actif, renommer l'ancien exécutable puis relancer la compilation.

## SQLCipher

Les dépendances sont sélectionnées automatiquement selon la plateforme :

```text
sqlcipher3-binary==0.6.0; platform_system == "Linux"
sqlcipher3==0.6.2; platform_system == "Windows"
```

Sous Windows, `PRAGMA cipher_memory_security = ON` n'est volontairement pas activé avec `sqlcipher3 0.6.2` / Python 3.14, car il provoquait un stack overflow natif à la première lecture de la base.

Après toute modification de `wopr_launcher.py`, recompiler le binaire concerné avant une release officielle.

Si le source du launcher n'a pas changé depuis les binaires déjà validés, une recompilation n'est pas nécessaire pour un simple changement de version de WOPR.
