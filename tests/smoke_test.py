import os
import sys
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_startup():
    app = QApplication(sys.argv)
    from main import AppCoordinator
    coordinator = AppCoordinator(is_minimized=True)
    print("SUCCESS: AppCoordinator initialized without errors!")
    coordinator.exit_app()

if __name__ == "__main__":
    test_startup()
