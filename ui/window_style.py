import sys
import ctypes
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap


def apply_dark_titlebar(window, hex_color: str = "#161b22", hide_icon: bool = True):
    """Windows 11 기본 타이틀바를 다크 모드 + 지정 색상으로 바꾸고, 기본 아이콘을 깔끔하게 숨김"""
    if hide_icon:
        pixmap = QPixmap(1, 1)
        pixmap.fill(Qt.GlobalColor.transparent)
        window.setWindowIcon(QIcon(pixmap))

    if sys.platform != "win32":
        return

    try:
        hwnd = int(window.winId())
        dwmapi = ctypes.windll.dwmapi

        # 1. 다크 모드 활성화 (타이틀바 글씨 & 닫기/최소화 버튼 흰색 전환)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_mode = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_mode),
            ctypes.sizeof(dark_mode),
        )

        # 2. 타이틀바 배경색 지정 (Win32 COLORREF 포맷: 0x00BBGGRR)
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        colorref = ctypes.c_int((b << 16) | (g << 8) | r)
        DWMWA_CAPTION_COLOR = 35
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_CAPTION_COLOR,
            ctypes.byref(colorref),
            ctypes.sizeof(colorref),
        )
    except Exception:
        pass