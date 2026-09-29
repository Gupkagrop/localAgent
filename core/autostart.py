"""
Модуль управления автозагрузкой приложения в Windows 11.
Использует системный реестр Windows (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
для безопасного запуска в фоновом режиме через pythonw.exe с ключом --minimized.
"""
import os
import sys
import winreg
from typing import Optional

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_APP_NAME = "AntigravityVoice"

def get_pythonw_executable() -> str:
    """
    Возвращает путь к pythonw.exe для скрытого запуска без окна консоли.
    Если pythonw.exe не найден, возвращает sys.executable.
    """
    base_dir = os.path.dirname(os.path.abspath(sys.executable))
    pythonw = os.path.join(base_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return sys.executable

def get_main_script_path() -> str:
    """Возвращает абсолютный путь к точке входа main.py."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(project_root, "main.py")

def build_autostart_command(start_minimized: bool = True) -> str:
    """Формирует строку команды для реестра автозапуска Windows."""
    exe_path = get_pythonw_executable()
    main_py = get_main_script_path()
    minimized_flag = " --minimized" if start_minimized else ""
    return f'"{exe_path}" "{main_py}"{minimized_flag}'

def set_windows_autostart(enable: bool, app_name: str = DEFAULT_APP_NAME, start_minimized: bool = True) -> bool:
    """
    Включает или отключает автозагрузку приложения в реестре Windows.
    :param enable: True для добавления в автозагрузку, False для удаления.
    :param app_name: Имя параметра в реестре.
    :param start_minimized: Запускать ли с ключом --minimized.
    :return: True при успешном изменении, False при ошибке.
    """
    try:
        access_rights = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, access_rights) as key:
            if enable:
                cmd = build_autostart_command(start_minimized=start_minimized)
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                return True
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
                return True
    except Exception as e:
        print(f"[Autostart Error] Не удалось изменить автозагрузку: {e}")
        return False

def is_windows_autostart_enabled(app_name: str = DEFAULT_APP_NAME) -> bool:
    """
    Проверяет, включена ли автозагрузка приложения в реестре Windows.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, app_name)
            return bool(val and str(val).strip())
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[Autostart Error] Ошибка проверки автозагрузки: {e}")
        return False

def get_autostart_command(app_name: str = DEFAULT_APP_NAME) -> Optional[str]:
    """
    Возвращает текущую команду автозагрузки из реестра или None.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, app_name)
            return str(val)
    except Exception:
        return None
