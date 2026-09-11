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
    if not pid: return False
    try:
        if IS_WINDOWS:
            cp=subprocess.run(["tasklist","/FI",f"PID eq {pid}","/NH"],capture_output=True,text=True,
                              creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            return str(pid) in cp.stdout
        os.kill(pid,0); return True
    except Exception: return False

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
        # Retrouve aussi WOPR si le fichier PID a disparu : uniquement Python/pythonw
        # dont la ligne de commande contient exactement ce public\app.py.
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
            errors.append("WOPR n'a retourné aucun résultat de sauvegarde.")
            continue
        if lines[-1] == "UNCHANGED":
            log("Sauvegarde de fermeture ignorée : base inchangée.")
            return None
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
    log("Serveur arrêté PID=" + ",".join(map(str,pids)))
    backup=create_shutdown_backup(status)
    if backup:
        status(f"WOPR arrêté • sauvegarde {backup.name}")
    else:
        status("WOPR arrêté • base inchangée, sauvegarde inutile")
    return backup

def db_desc():
    if not DB_FILE.exists(): return "Base : introuvable"
    s=DB_FILE.stat()
    return f"Base : {datetime.fromtimestamp(s.st_mtime):%d/%m/%Y %H:%M:%S}  •  {s.st_size/1048576:.2f} Mo"

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WOPR")
        self.geometry("520x280"); self.resizable(False,False)
        tk.Label(self,text="WOPR",font=("TkDefaultFont",24,"bold")).pack(pady=(22,2))
        tk.Label(self,text="Workflow d’Organisation et de Pilotage des Réparations").pack()
        self.status=tk.StringVar(value="Vérification…")
        tk.Label(self,textvariable=self.status,font=("TkDefaultFont",11,"bold")).pack(pady=(22,4))
        self.db=tk.StringVar(value=db_desc()); tk.Label(self,textvariable=self.db).pack(pady=(0,14))
        fr=tk.Frame(self); fr.pack()
        self.openb=tk.Button(fr,text="DÉMARRER WOPR",width=17,command=self.open_wopr); self.openb.grid(row=0,column=0,padx=5)
        self.stopb=tk.Button(fr,text="ARRÊTER WOPR",width=17,command=self.stop_wopr); self.stopb.grid(row=0,column=1,padx=5)
        tk.Button(fr,text="ACTUALISER",width=12,command=self.refresh).grid(row=0,column=2,padx=5)
        tk.Label(self,text=str(WOPR_DIR),wraplength=480,fg="#666",font=("TkDefaultFont",8)).pack(pady=(18,0))
        self.after(100,self.refresh); self.after(3000,self.tick)
    def set_status(self,t): self.after(0,self.status.set,t)
    def refresh(self):
        run=alive()
        self.status.set("● WOPR ACTIF" if run else "○ WOPR ARRÊTÉ")
        self.db.set(db_desc())
        self.openb.config(text="OUVRIR WOPR" if run else "DÉMARRER WOPR")
        self.stopb.config(state="normal" if run or process_exists(read_pid()) else "disabled")
    def tick(self):
        self.refresh(); self.after(3000,self.tick)
    def open_wopr(self):
        if alive(): webbrowser.open(APP_URL); return
        def job():
            try: start_server(self.set_status); webbrowser.open(APP_URL)
            except Exception as e: self.after(0,messagebox.showerror,"WOPR",str(e))
            finally: self.after(0,self.refresh)
        threading.Thread(target=job,daemon=True).start()
    def stop_wopr(self):
        def job():
            try: stop_server(self.set_status)
            except Exception as e: self.after(0,messagebox.showerror,"WOPR",str(e))
            finally: self.after(0,self.refresh)
        threading.Thread(target=job,daemon=True).start()

if __name__=="__main__":
    ensure_dirs()
    log(f"Lanceur unifié démarré ({platform.system()} {platform.release()})")
    Launcher().mainloop()
