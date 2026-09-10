#!/usr/bin/env python3
from __future__ import annotations
import hashlib, os, platform, signal, subprocess, sys, threading, time, urllib.request, webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

APP_URL="http://127.0.0.1:5000"
IS_WINDOWS=os.name=="nt"

def base_dir():
    return Path(sys.executable if getattr(sys,"frozen",False) else __file__).resolve().parent

def find_root():
    here=base_dir()
    for c in (here, here.parent, here.parent.parent, Path.cwd()):
        if (c/"public"/"app.py").is_file():
            return c
    raise FileNotFoundError("Impossible de trouver WOPR/public/app.py autour du lanceur.")

WOPR_DIR=find_root()
PUBLIC_DIR=WOPR_DIR/"public"
PRIVATE_DIR=WOPR_DIR/"private"
DATA_DIR=PRIVATE_DIR/"data"
APP_PATH=PUBLIC_DIR/"app.py"
REQ=PUBLIC_DIR/"requirements.txt"
PID_FILE=DATA_DIR/"wopr.pid"
LOG=DATA_DIR/"wopr-launcher.log"
SERVER_OUT=DATA_DIR/"wopr-server.log"
SERVER_ERR=DATA_DIR/"wopr-server-error.log"
DB_FILE=DATA_DIR/"foulfix.db"
BACKUP_DIR=DATA_DIR/"backups"
VENV_DIR=PRIVATE_DIR/(".venv-win" if IS_WINDOWS else ".venv")
PY=VENV_DIR/("Scripts/python.exe" if IS_WINDOWS else "bin/python")
STAMP=VENV_DIR/".requirements.sha256"

def ensure_dirs():
    for p in (DATA_DIR,PRIVATE_DIR/"assets",PRIVATE_DIR/"seeds",PRIVATE_DIR/"signatures",
              PRIVATE_DIR/"documents"/"Factures",PRIVATE_DIR/"documents"/"Devis",
              PRIVATE_DIR/"documents"/"Suivi de réparation"):
        p.mkdir(parents=True,exist_ok=True)

def log(msg):
    try:
        ensure_dirs()
        with LOG.open("a",encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass

def alive():
    try:
        with urllib.request.urlopen(APP_URL,timeout=.7) as r:
            return 200 <= int(r.status) < 500
    except Exception:
        return False

def read_pid():
    try: return int(PID_FILE.read_text(encoding="ascii").strip())
    except Exception: return None

def process_exists(pid):
    if not pid:
        return False
    try:
        if IS_WINDOWS:
            cp=subprocess.run(
                ["tasklist","/FI",f"PID eq {pid}","/NH"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
            )
            return str(pid) in cp.stdout

        # Linux : un processus zombie possède encore un PID, mais il est déjà mort.
        # os.kill(pid, 0) seul le considérait à tort comme encore actif.
        stat_path=Path(f"/proc/{pid}/stat")
        if stat_path.is_file():
            try:
                stat=stat_path.read_text(encoding="utf-8",errors="ignore")
                # /proc/<pid>/stat : PID (comm) STATE ...
                end_comm=stat.rfind(")")
                if end_comm != -1:
                    fields=stat[end_comm+2:].split()
                    if fields and fields[0] == "Z":
                        return False
            except Exception:
                pass

        os.kill(pid,0)
        return True
    except Exception:
        return False

def req_hash():
    if not REQ.exists(): return ""
    return hashlib.sha256(REQ.read_bytes()).hexdigest()

def system_python():
    candidates=[["py","-3"],["python"],["python3"]] if IS_WINDOWS else [["python3"],["python"]]
    for cmd in candidates:
        try:
            cp=subprocess.run(cmd+["-c","import sys;print(sys.version_info[0])"],capture_output=True,text=True,
                              timeout=5,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if IS_WINDOWS else 0)
            if cp.returncode==0 and cp.stdout.strip()=="3": return cmd
        except Exception: pass
    return None

def ensure_venv(status):
    ensure_dirs()
    if not PY.exists():
        cmd=system_python()
        if not cmd: raise RuntimeError("Python 3 est introuvable.")
        status("Création de l'environnement Python…")
        cp=subprocess.run(cmd+["-m","venv",str(VENV_DIR)],capture_output=True,text=True)
        if cp.returncode: raise RuntimeError(cp.stderr or "Échec création venv.")
    wanted=req_hash()
    installed=STAMP.read_text(encoding="ascii").strip() if STAMP.exists() else ""
    if wanted and installed==wanted: return
    status("Vérification des dépendances…")
    cp=subprocess.run([str(PY),"-c","import flask,reportlab,qrcode"],cwd=PUBLIC_DIR,
                      capture_output=True,text=True)
    if cp.returncode==0 and wanted:
        STAMP.write_text(wanted,encoding="ascii"); return
    status("Installation / mise à jour des dépendances…")
    with LOG.open("a",encoding="utf-8") as f:
        cp=subprocess.run([str(PY),"-m","pip","install","-r",str(REQ)],cwd=PUBLIC_DIR,
                          stdout=f,stderr=subprocess.STDOUT,text=True)
    if cp.returncode: raise RuntimeError(f"Installation des dépendances échouée. Voir {LOG}")
    if wanted: STAMP.write_text(wanted,encoding="ascii")

def start_server(status):
    if alive(): return read_pid() or 0
    pid=read_pid()
    if pid and not process_exists(pid): PID_FILE.unlink(missing_ok=True)
    ensure_venv(status)
    status("Lancement du serveur WOPR…")
    out=SERVER_OUT.open("a",encoding="utf-8")
    err=SERVER_ERR.open("a",encoding="utf-8")
    kwargs=dict(cwd=str(PUBLIC_DIR),stdout=out,stderr=err,stdin=subprocess.DEVNULL)
    if IS_WINDOWS:
        kwargs["creationflags"]=getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
    else:
        kwargs["start_new_session"]=True
    p=subprocess.Popen([str(PY),str(APP_PATH)],**kwargs)
    PID_FILE.write_text(str(p.pid),encoding="ascii")
    log(f"Serveur lancé PID={p.pid}")
    end=time.monotonic()+90
    while time.monotonic()<end:
        if alive(): status("WOPR est prêt."); return p.pid
        if p.poll() is not None:
            PID_FILE.unlink(missing_ok=True)
            raise RuntimeError("WOPR s'est arrêté pendant le démarrage.")
        time.sleep(.5)
    raise RuntimeError(f"Délai dépassé. Voir les logs dans {DATA_DIR}")

def discover_app_pids():
    pids=set()
    pid=read_pid()
    if process_exists(pid):
        pids.add(pid)

    if IS_WINDOWS:
        app=str(APP_PATH).replace("'", "''")
        ps=(
            "$app='"+app+"'; "
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -and "
            "$_.CommandLine.IndexOf($app,[System.StringComparison]::OrdinalIgnoreCase) -ge 0 } | "
            "ForEach-Object { $_.ProcessId }"
        )
        try:
            cp=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",ps],
                              capture_output=True,text=True,timeout=8,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            for line in cp.stdout.splitlines():
                try:
                    candidate=int(line.strip())
                    if process_exists(candidate): pids.add(candidate)
                except Exception:
                    pass
        except Exception:
            pass
    else:
        app=str(APP_PATH)
        proc_root=Path("/proc")
        if proc_root.is_dir():
            for proc in proc_root.iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    cmd=(proc/"cmdline").read_bytes().replace(b"\x00",b" ").decode(errors="ignore")
                    if app in cmd:
                        candidate=int(proc.name)
                        if process_exists(candidate): pids.add(candidate)
                except Exception:
                    pass
    return sorted(pids)

def create_shutdown_backup(status):
    status("Création de la sauvegarde de fermeture…")
    commands=[]
    if PY.exists():
        commands.append([str(PY),str(APP_PATH),"--backup-arret"])
    sys_py=system_python()
    if sys_py:
        cmd=sys_py+[str(APP_PATH),"--backup-arret"]
        if cmd not in commands:
            commands.append(cmd)
    if not commands:
        raise RuntimeError("Python 3 introuvable pour créer la sauvegarde de fermeture.")

    errors=[]
    for command in commands:
        try:
            cp=subprocess.run(
                command,cwd=str(PUBLIC_DIR),capture_output=True,text=True,timeout=120,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if IS_WINDOWS else 0
            )
        except Exception as exc:
            errors.append(f"{' '.join(command[:1])}: {exc}")
            continue
        if cp.returncode:
            detail=(cp.stderr or cp.stdout or "").strip()
            errors.append(detail or f"code retour {cp.returncode}")
            continue
        lines=[x.strip() for x in cp.stdout.splitlines() if x.strip()]
        if not lines:
            errors.append("WOPR n'a retourné aucun fichier de sauvegarde.")
            continue
        backup=Path(lines[-1])
        if not backup.is_file():
            errors.append(f"Sauvegarde annoncée mais introuvable : {backup}")
            continue
        log(f"Sauvegarde de fermeture créée : {backup.name}")
        return backup

    detail=" | ".join(x for x in errors if x)
    raise RuntimeError("Sauvegarde de fermeture impossible" + (f" : {detail}" if detail else "."))

def stop_server(status):
    pids=discover_app_pids()
    if not pids:
        PID_FILE.unlink(missing_ok=True)
        if alive():
            raise RuntimeError("WOPR répond encore, mais son processus n'a pas pu être identifié.")
        status("WOPR est déjà arrêté.")
        return None

    status("Arrêt de WOPR…")
    for pid in pids:
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill","/PID",str(pid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            else:
                os.kill(pid,signal.SIGTERM)
        except Exception:
            pass

    end=time.monotonic()+5
    while time.monotonic()<end and any(process_exists(pid) for pid in pids):
        time.sleep(.15)

    for pid in pids:
        if not process_exists(pid):
            continue
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill","/F","/PID",str(pid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            else:
                os.kill(pid,signal.SIGKILL)
        except Exception:
            pass

    end=time.monotonic()+3
    while time.monotonic()<end and any(process_exists(pid) for pid in pids):
        time.sleep(.15)
    remaining=[pid for pid in pids if process_exists(pid)]
    if remaining:
        raise RuntimeError("Impossible d'arrêter complètement WOPR (PID : " + ", ".join(map(str,remaining)) + ").")

    PID_FILE.unlink(missing_ok=True)
    log("Serveur arrêté PID="+",".join(map(str,pids)))
    backup=create_shutdown_backup(status)
    status(f"WOPR arrêté • sauvegarde {backup.name}")
    return backup

def db_desc():
    if not DB_FILE.exists(): return "Base : introuvable"
    s=DB_FILE.stat()
    return f"Base : {datetime.fromtimestamp(s.st_mtime):%d/%m/%Y %H:%M:%S}  •  {s.st_size/1048576:.2f} Mo"

class Launcher(tk.Tk):
    BG = "#070B10"
    PANEL = "#0D141C"
    PANEL_2 = "#101B25"
    GREEN = "#39FF88"
    CYAN = "#41DFFF"
    AMBER = "#FFCA58"
    RED = "#FF5F70"
    TEXT = "#D9F7E8"
    MUTED = "#6E8A7D"
    BORDER = "#173629"

    def __init__(self):
        super().__init__()

        self.title("WOPR // SYSTEM LAUNCHER")
        self.geometry("640x390")
        self.resizable(False, False)
        self.configure(bg=self.BG)

        mono = ("TkFixedFont", 10)
        mono_bold = ("TkFixedFont", 10, "bold")

        header = tk.Frame(self, bg=self.BG)
        header.pack(fill="x", padx=28, pady=(22, 0))

        tk.Label(
            header,
            text=">_ WOPR",
            bg=self.BG,
            fg=self.GREEN,
            font=("TkFixedFont", 28, "bold"),
        ).pack(anchor="w")

        tk.Label(
            header,
            text="WORKFLOW D'ORGANISATION ET DE PILOTAGE DES RÉPARATIONS",
            bg=self.BG,
            fg=self.CYAN,
            font=("TkFixedFont", 9, "bold"),
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            header,
            text="[ 100% GRATUIT • OPEN SOURCE ]",
            bg=self.BG,
            fg=self.AMBER,
            font=("TkFixedFont", 9, "bold"),
        ).pack(anchor="w", pady=(5, 0))

        console = tk.Frame(
            self,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        console.pack(fill="x", padx=28, pady=(20, 14))

        tk.Label(
            console,
            text=" SYSTEM STATUS",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("TkFixedFont", 8, "bold"),
        ).pack(anchor="w", padx=14, pady=(10, 2))

        self.status = tk.StringVar(value="[~] Vérification du système…")
        self.status_label = tk.Label(
            console,
            textvariable=self.status,
            bg=self.PANEL,
            fg=self.AMBER,
            font=("TkFixedFont", 12, "bold"),
        )
        self.status_label.pack(anchor="w", padx=14, pady=(2, 4))

        self.db = tk.StringVar(value=db_desc())
        tk.Label(
            console,
            textvariable=self.db,
            bg=self.PANEL,
            fg=self.TEXT,
            font=mono,
        ).pack(anchor="w", padx=14, pady=(0, 3))

        self.platform_text = tk.StringVar(
            value=f"OS   : {platform.system()} {platform.release()}"
        )
        tk.Label(
            console,
            textvariable=self.platform_text,
            bg=self.PANEL,
            fg=self.MUTED,
            font=mono,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        buttons = tk.Frame(self, bg=self.BG)
        buttons.pack(padx=28, pady=(0, 10), fill="x")

        def make_button(parent, text, command, fg):
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg=self.PANEL_2,
                fg=fg,
                activebackground=self.BORDER,
                activeforeground=fg,
                disabledforeground="#405048",
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=self.BORDER,
                cursor="hand2",
                font=mono_bold,
                padx=13,
                pady=9,
            )

        self.openb = make_button(
            buttons, "[▶] DÉMARRER WOPR", self.open_wopr, self.GREEN
        )
        self.openb.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stopb = make_button(
            buttons, "[■] ARRÊTER WOPR", self.stop_wopr, self.RED
        )
        self.stopb.pack(side="left", expand=True, fill="x", padx=6)

        self.refreshb = make_button(
            buttons, "[↻] ACTUALISER", self.refresh, self.CYAN
        )
        self.refreshb.pack(side="left", expand=True, fill="x", padx=(6, 0))

        footer = tk.Frame(self, bg=self.BG)
        footer.pack(fill="x", padx=28, pady=(8, 0))

        tk.Label(
            footer,
            text="root@wopr:",
            bg=self.BG,
            fg=self.GREEN,
            font=("TkFixedFont", 8, "bold"),
        ).pack(side="left")

        tk.Label(
            footer,
            text=str(WOPR_DIR),
            bg=self.BG,
            fg=self.MUTED,
            font=("TkFixedFont", 8),
            wraplength=520,
            justify="left",
        ).pack(side="left", padx=(5, 0))

        tk.Label(
            self,
            text="Foul-Fix // local-first repair management",
            bg=self.BG,
            fg="#30483D",
            font=("TkFixedFont", 8),
        ).pack(side="bottom", pady=(0, 12))

        self.after(100, self.refresh)
        self.after(3000, self.tick)

    def set_status(self, t):
        self.after(0, self.status.set, f"[~] {t}")

    def refresh(self):
        run = alive()

        if run:
            self.status.set("[●] WOPR ONLINE // 127.0.0.1:5000")
            self.status_label.config(fg=self.GREEN)
        else:
            self.status.set("[○] WOPR OFFLINE // READY")
            self.status_label.config(fg=self.RED)

        self.db.set(db_desc())
        self.openb.config(
            text="[↗] OUVRIR WOPR" if run else "[▶] DÉMARRER WOPR"
        )
        self.stopb.config(
            state="normal" if run or process_exists(read_pid()) else "disabled"
        )

    def tick(self):
        self.refresh()
        self.after(3000, self.tick)

    def open_wopr(self):
        if alive():
            webbrowser.open(APP_URL)
            return

        self.status.set("[~] BOOT SEQUENCE INITIALISÉE…")
        self.status_label.config(fg=self.AMBER)

        def job():
            try:
                start_server(self.set_status)
                webbrowser.open(APP_URL)
            except Exception as e:
                self.after(0, messagebox.showerror, "WOPR // ERROR", str(e))
            finally:
                self.after(0, self.refresh)

        threading.Thread(target=job, daemon=True).start()

    def stop_wopr(self):
        self.status.set("[~] SHUTDOWN SEQUENCE…")
        self.status_label.config(fg=self.AMBER)

        def job():
            try:
                stop_server(self.set_status)
            except Exception as e:
                self.after(0, messagebox.showerror, "WOPR // ERROR", str(e))
            finally:
                self.after(0, self.refresh)

        threading.Thread(target=job, daemon=True).start()


if __name__=="__main__":
    ensure_dirs()
    log(f"Lanceur unifié démarré ({platform.system()} {platform.release()})")
    Launcher().mainloop()
