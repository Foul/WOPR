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

## Compilation Windows

La version Windows est compilée sous Windows, par exemple dans une VM Windows 11.

Depuis la racine du projet, en une seule ligne :

```powershell
py -m PyInstaller --onefile --windowed --name WOPR --icon public\static\WOPR.ico public\launcher\wopr_launcher.py
```

Puis remplacer le binaire officiel à la racine :

```powershell
copy /Y dist\WOPR.exe WOPR.exe
```

Test :

```powershell
WOPR.exe
```

## Nettoyage PyInstaller

Linux :

```bash
rm -rf build dist WOPR.spec
```

Windows :

```powershell
rmdir /S /Q build & del /Q WOPR.spec & rmdir /S /Q dist
```

## Remarque

Les anciens scripts de build et les anciens chemins de sortie sous
`public/launcher/dist/` ne sont plus utilisés.

Le fichier de référence à maintenir est :

```text
public/launcher/wopr_launcher.py
```

Après toute modification du launcher, recompiler les deux binaires officiels :

```text
WOPR
WOPR.exe
```
