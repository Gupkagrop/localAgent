"""
Скрипт генерации ярлыка на рабочем столе Windows (Antigravity Voice.lnk).
Запускает приложение через pythonw.exe без всплывающего черного окна консоли.
"""
import os
import sys
import json
import win32com.client

def create_desktop_shortcut():
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    shortcut_path = os.path.join(desktop, "Antigravity Voice.lnk")

    project_dir = os.path.dirname(os.path.abspath(__file__))
    pythonw_path = os.path.join(project_dir, ".venv", "Scripts", "pythonw.exe")
    main_py_path = os.path.join(project_dir, "main.py")

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    # Учитываем настройку start_minimized
    args = f'"{main_py_path}"'
    config_path = os.path.join(project_dir, "config", "settings.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                sett = json.load(f)
                if sett.get("start_minimized", False):
                    args += " --minimized"
        except Exception:
            pass

    shortcut.Arguments = args
    shortcut.WorkingDirectory = project_dir
    shortcut.Description = "Antigravity Voice Assistant"
    
    # Иконка микрофона из Windows shell32
    shortcut.IconLocation = r"C:\Windows\System32\shell32.dll, 168"
    shortcut.save()

    print(f"Ярлык успешно создан: {shortcut_path}")

if __name__ == "__main__":
    create_desktop_shortcut()
