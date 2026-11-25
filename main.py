import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from ui.main_window import MainWindow


def get_resource_path(rel_path: str) -> str:
    """일반 실행 및 PyInstaller(--onefile) 빌드 환경 모두에서 리소스 경로 반환"""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, rel_path)


def load_custom_fonts(app: QApplication):
    """data/fonts/ 내 Pretendard 9종(.otf/.ttf)을 모두 등록하고 기본 UI 폰트 적용"""
    fonts_dir = get_resource_path(os.path.join("data", "fonts"))
    loaded_families: set[str] = set()

    if os.path.isdir(fonts_dir):
        for fname in sorted(os.listdir(fonts_dir)):
            if fname.lower().endswith((".ttf", ".otf")):
                font_path = os.path.join(fonts_dir, fname)
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    for fam in QFontDatabase.applicationFontFamilies(font_id):
                        loaded_families.add(fam)

    # 정확히 "Pretendard" 패밀리를 최우선 선택 (Black/Thin 등 서브 패밀리 오선택 방지)
    if "Pretendard" in loaded_families:
        base_font = QFont("Pretendard", 10)
        base_font.setWeight(QFont.Weight.Normal)
    elif loaded_families:
        base_font = QFont(sorted(loaded_families)[0], 10)
    else:
        base_font = QFont("Malgun Gothic", 10)

    # 폰트 렌더링 안티앨리어싱 선명도 보정
    base_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(base_font)


def main():
    app = QApplication(sys.argv)
    load_custom_fonts(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()