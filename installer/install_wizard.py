from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PATH = PROJECT_ROOT / ".venv"
PYTHON_EXE = VENV_PATH / "Scripts" / "python.exe"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
ENV_FILE = PROJECT_ROOT / ".env"
LAUNCH_SCRIPT = PROJECT_ROOT / "installer" / "LaunchUploadPicker.ps1"
DESKTOP_SHORTCUT = Path(os.path.expandvars(r"%USERPROFILE%\Desktop\UploadPicker.lnk"))
START_MENU_DIR = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\UploadPicker"))
START_MENU_SHORTCUT = START_MENU_DIR / "UploadPicker.lnk"


def escape_ps_single_quotes(value: str) -> str:
    return value.replace("'", "''")


class InstallerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("UploadPicker Installer")
        self.root.geometry("760x520")
        self.root.configure(bg="#141821")
        self.root.resizable(False, False)

        title = tk.Label(
            self.root,
            text="UploadPicker Installer",
            font=("Segoe UI", 20, "bold"),
            bg="#141821",
            fg="#ffffff",
        )
        title.pack(anchor="w", padx=24, pady=(20, 4))

        desc = tk.Label(
            self.root,
            text="Install / Repair 専用です。Python が無ければ winget で導入を試み、.venv 作成と依存インストールまで進めます。",
            font=("Segoe UI", 10),
            bg="#141821",
            fg="#c3cede",
        )
        desc.pack(anchor="w", padx=24, pady=(0, 16))

        controls = tk.Frame(self.root, bg="#141821")
        controls.pack(fill="x", padx=24)

        self.install_button = ttk.Button(controls, text="Install / Repair", command=self.start_install)
        self.install_button.pack(side="left")

        self.progress = ttk.Progressbar(controls, mode="indeterminate", length=220)
        self.progress.pack(side="left", padx=16)

        self.output = tk.Text(
            self.root,
            wrap="word",
            bg="#0e1016",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("Consolas", 10),
        )
        self.output.pack(fill="both", expand=True, padx=24, pady=24)

    def log(self, message: str) -> None:
        self.output.insert("end", f"{message}\n")
        self.output.see("end")
        self.root.update_idletasks()

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.install_button.configure(state="disabled")
            self.progress.start(10)
        else:
            self.install_button.configure(state="normal")
            self.progress.stop()

    def run_step(self, command: list[str], shell: bool = False) -> None:
        display = command if isinstance(command, str) else " ".join(command)
        self.log(f"> {display}")
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            shell=shell,
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.stdout:
            self.log(completed.stdout.strip())
        if completed.stderr:
            self.log(completed.stderr.strip())
        if completed.returncode != 0:
            raise RuntimeError(f"Command failed: {display}")

    def detect_python_command(self) -> str | None:
        candidates = [
            ["py", "-3.11", "--version"],
            ["py", "-3", "--version"],
            ["python", "--version"],
        ]
        for candidate in candidates:
            try:
                result = subprocess.run(candidate, check=False, capture_output=True, text=True)
            except OSError:
                continue
            if result.returncode == 0:
                return " ".join(candidate[:-1])
        return None

    def ensure_python(self) -> str:
        command = self.detect_python_command()
        if command:
            self.log(f"Python detected: {command}")
            return command
        self.log("Python not found. Installing Python 3.11 via winget...")
        if shutil.which("winget") is None:
            raise RuntimeError("winget が見つかりません。Python を先にインストールするか、winget を使える環境で実行してください。")
        self.run_step([
            "winget",
            "install",
            "--exact",
            "--id",
            "Python.Python.3.11",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ])
        command = self.detect_python_command()
        if not command:
            raise RuntimeError("Python のインストール後もコマンドが見つかりません。PowerShell を再起動して再実行してください。")
        self.log(f"Python installed: {command}")
        return command

    def create_shortcuts(self) -> None:
        START_MENU_DIR.mkdir(parents=True, exist_ok=True)
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if not powershell:
            raise RuntimeError("powershell が見つかりません。")
        arguments = f'-ExecutionPolicy Bypass -File "{LAUNCH_SCRIPT}"'
        ps_script = (
            "$WshShell = New-Object -ComObject WScript.Shell;"
            f"$Shortcut = $WshShell.CreateShortcut('{escape_ps_single_quotes(str(DESKTOP_SHORTCUT))}');"
            f"$Shortcut.TargetPath = '{escape_ps_single_quotes(powershell)}';"
            f"$Shortcut.Arguments = '{escape_ps_single_quotes(arguments)}';"
            f"$Shortcut.WorkingDirectory = '{escape_ps_single_quotes(str(PROJECT_ROOT))}';"
            "$Shortcut.Save();"
            f"$Shortcut2 = $WshShell.CreateShortcut('{escape_ps_single_quotes(str(START_MENU_SHORTCUT))}');"
            f"$Shortcut2.TargetPath = '{escape_ps_single_quotes(powershell)}';"
            f"$Shortcut2.Arguments = '{escape_ps_single_quotes(arguments)}';"
            f"$Shortcut2.WorkingDirectory = '{escape_ps_single_quotes(str(PROJECT_ROOT))}';"
            "$Shortcut2.Save();"
        )
        self.run_step(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script])
        self.log("Shortcuts created.")

    def install(self) -> None:
        python_command = self.ensure_python()
        if not VENV_PATH.exists():
            self.run_step(["cmd.exe", "/c", f"{python_command} -m venv \"{VENV_PATH}\""])
        else:
            self.log("Virtual environment already exists. Reusing it.")
        if ENV_EXAMPLE.exists() and not ENV_FILE.exists():
            shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
            self.log(".env created from .env.example")
        self.run_step([str(PYTHON_EXE), "-m", "pip", "install", "--upgrade", "pip"])
        self.run_step([str(PYTHON_EXE), "-m", "pip", "install", "-e", "."])
        self.create_shortcuts()
        self.log("Install completed.")

    def start_install(self) -> None:
        def worker() -> None:
            self.set_busy(True)
            try:
                self.install()
                self.root.after(0, lambda: messagebox.showinfo("UploadPicker", "Install completed."))
            except Exception as exc:
                self.log(str(exc))
                self.root.after(0, lambda: messagebox.showerror("UploadPicker Error", str(exc)))
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    InstallerApp().run()
