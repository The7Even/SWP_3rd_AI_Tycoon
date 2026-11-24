import sys
import traceback
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.stderr.flush()
    sys.exit(1)


sys.excepthook = excepthook


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()