import os
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QFrame, QStackedWidget,
    QTextEdit, QMessageBox, QFileDialog, QApplication, QProgressBar, QSlider
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer
from core.save_preview import get_save_slot_preview
from ui.window_style import apply_dark_titlebar


DARK_SCROLL_QSS = """
    QScrollArea {
        border: none;
        background-color: #0d1117;
    }
    QScrollBar:vertical {
        background: #0d1117;
        width: 6px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #30363d;
        border-radius: 3px;
        min-height: 24px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""


class NewsCardWidget(QFrame):
    """다크 틴트 뉴스 카드 (제목 + 날짜 + 가로선 + 요약 본문 + 하단 효과 요약)"""

    def __init__(self, news_item: dict):
        super().__init__()
        category = news_item.get("category", "info")
        color_schemes = {
            "info":     ("#272115", "#d29922", "#f2cc60"),
            "positive": ("#12261e", "#2ea043", "#7ee787"),
            "danger":   ("#2c1619", "#f85149", "#ffa198"),
            "story":    ("#241833", "#a371f7", "#e2c5ff"),
        }
        bg_color, border_color, title_color = color_schemes.get(category, ("#272115", "#d29922", "#f2cc60"))

        self.setStyleSheet(f"""
            NewsCardWidget {{
                background-color: {bg_color};
                border: 1.5px solid {border_color};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        lbl_title = QLabel(news_item["title"])
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet(f"""
            background-color: transparent;
            font-size: 14px;
            font-weight: bold;
            color: {title_color};
            border: none;
        """)

        lbl_date = QLabel(news_item["date"])
        lbl_date.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_date.setStyleSheet("""
            background-color: transparent;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 12px;
            font-weight: bold;
            color: #8b949e;
            border: none;
        """)

        header_row.addWidget(lbl_title, stretch=1)
        header_row.addWidget(lbl_date)
        layout.addLayout(header_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {border_color}; max-height: 1px; border: none;")
        layout.addWidget(line)

        lbl_content = QLabel(news_item["content"])
        lbl_content.setWordWrap(True)
        lbl_content.setStyleSheet("""
            background-color: transparent;
            font-size: 12.5px;
            color: #c9d1d9;
            border: none;
            line-height: 1.45;
        """)
        layout.addWidget(lbl_content)

        effect_text = news_item.get("effect_text", "").strip()
        if effect_text:
            lbl_effect = QLabel(effect_text)
            lbl_effect.setWordWrap(True)
            lbl_effect.setStyleSheet(f"""
                background-color: rgba(1, 4, 9, 0.42);
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 11.5px;
                font-weight: bold;
                color: {title_color};
                border: none;
            """)
            layout.addWidget(lbl_effect)


class NewsDialog(QDialog):
    """다크 확장 팝업창 (최근 뉴스 / AI 활동 / 도감 & 엔딩 기록 / 설정 4단 탭 지원)"""

    def __init__(self, game_state, save_manager, parent=None, sound_manager=None):
        super().__init__(parent)
        self.game_state = game_state
        self.save_manager = save_manager
        self.sound_manager = sound_manager
        self.setWindowTitle("AI 키우기 - 뉴스 / 도감 / 설정")
        apply_dark_titlebar(self, "#161b22")
        self.resize(820, 620)
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #0d1117;
                color: #e6edf3;
                font-family: 'Pretendard', 'SUIT', 'Malgun Gothic', sans-serif;
            }
        """)

        self._auto_open_guard_until = 0.0
        self._top_card_anim: QPropertyAnimation | None = None

        self._init_ui()
        self._connect_signals()
        self.refresh_all()

    def keyPressEvent(self, event):
        if time.time() < self._auto_open_guard_until:
            if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                event.accept()
                return
        super().keyPressEvent(event)

    def open_recent_news(self, auto_triggered: bool = False, animate_top_card: bool = False):
        if auto_triggered:
            self._auto_open_guard_until = time.time() + 0.65
        self._switch_tab(0)
        self.game_state.clear_unread_news()
        if animate_top_card:
            QTimer.singleShot(20, self._animate_first_news_card)

    def _animate_first_news_card(self):
        if self.news_list_layout.count() == 0:
            return
        first_item = self.news_list_layout.itemAt(0)
        card = first_item.widget() if first_item else None
        if not isinstance(card, NewsCardWidget):
            return

        target_pos = card.pos()
        start_pos = QPoint(target_pos.x() + 180, target_pos.y())
        card.move(start_pos)

        anim = QPropertyAnimation(card, b"pos", self)
        anim.setDuration(300)
        anim.setStartValue(start_pos)
        anim.setEndValue(target_pos)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._top_card_anim = anim
        anim.start()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 18, 0)

        self.lbl_header_title = QLabel("NEWS")
        self.lbl_header_title.setStyleSheet(
            "background-color: transparent; font-size: 16px; font-weight: bold; color: #f0f6fc; border: none;"
        )
        header_layout.addWidget(self.lbl_header_title)
        header_layout.addStretch()

        btn_close = QPushButton("닫기")
        btn_close.setFixedSize(64, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
            }
        """)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)
        main_layout.addWidget(header)

        self.stack = QStackedWidget()

        # [탭 0] 최근 뉴스
        self.news_scroll = QScrollArea()
        self.news_scroll.setWidgetResizable(True)
        self.news_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.news_scroll.setStyleSheet(DARK_SCROLL_QSS)
        self.news_container = QWidget()
        self.news_container.setStyleSheet("background-color: #0d1117;")
        self.news_list_layout = QVBoxLayout(self.news_container)
        self.news_list_layout.setContentsMargins(18, 16, 18, 16)
        self.news_list_layout.setSpacing(12)
        self.news_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.news_scroll.setWidget(self.news_container)
        self.stack.addWidget(self.news_scroll)

        # [탭 1] AI 활동
        self.activity_scroll = QScrollArea()
        self.activity_scroll.setWidgetResizable(True)
        self.activity_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.activity_scroll.setStyleSheet(DARK_SCROLL_QSS)
        self.activity_container = QWidget()
        self.activity_container.setStyleSheet("background-color: #0d1117;")
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(18, 16, 18, 16)
        self.activity_layout.setSpacing(10)
        self.activity_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.activity_scroll.setWidget(self.activity_container)
        self.stack.addWidget(self.activity_scroll)

        # [탭 2] 도감 & 엔딩 기록
        self.dex_scroll = QScrollArea()
        self.dex_scroll.setWidgetResizable(True)
        self.dex_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dex_scroll.setStyleSheet(DARK_SCROLL_QSS)
        self.dex_container = QWidget()
        self.dex_container.setStyleSheet("background-color: #0d1117;")
        self.dex_layout = QVBoxLayout(self.dex_container)
        self.dex_layout.setContentsMargins(18, 16, 18, 16)
        self.dex_layout.setSpacing(10)
        self.dex_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dex_scroll.setWidget(self.dex_container)
        self.stack.addWidget(self.dex_scroll)

        # [탭 3] 설정
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setStyleSheet(DARK_SCROLL_QSS)
        self.settings_container = self._build_settings_tab()
        self.settings_scroll.setWidget(self.settings_container)
        self.stack.addWidget(self.settings_scroll)

        main_layout.addWidget(self.stack, stretch=1)

        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(44)
        bottom_bar.setStyleSheet("background-color: #161b22; border-top: 1px solid #30363d;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self.tab_buttons = []
        tab_names = ["최근 뉴스", "AI 활동", "도감", "설정"]
        for idx, name in enumerate(tab_names):
            btn = QPushButton(name)
            btn.setFixedHeight(43)
            btn.setFixedWidth(130)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            self.tab_buttons.append(btn)
            bottom_layout.addWidget(btn)

        bottom_layout.addStretch()
        main_layout.addWidget(bottom_bar)

        self._switch_tab(0)

    def _build_settings_tab(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #0d1117;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 20)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        card_style = """
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 12px;
            }
        """
        btn_primary_style = """
            QPushButton {
                background-color: #1f6feb; color: #ffffff;
                border: 1px solid #388bfd; border-radius: 4px;
                padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #388bfd; }
            QPushButton:disabled {
                background-color: #21262d; color: #484f58; border-color: #30363d;
            }
        """
        btn_normal_style = """
            QPushButton {
                background-color: #21262d; color: #e6edf3;
                border: 1px solid #30363d; border-radius: 4px;
                padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #30363d; border-color: #8b949e; }
        """

        # 0. 오디오 및 효과음(SFX) 설정
        sec_audio = QFrame()
        sec_audio.setStyleSheet(card_style)
        audio_layout = QVBoxLayout(sec_audio)
        audio_layout.setSpacing(10)

        lbl_audio_title = QLabel("0. 오디오 및 합성 효과음(SFX) 설정")
        lbl_audio_title.setStyleSheet(
            "background-color: transparent; font-size: 14px; font-weight: bold; color: #f0f6fc; border: none;"
        )
        audio_layout.addWidget(lbl_audio_title)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(10)

        self.btn_mute_toggle = QPushButton("🔊 음소거 해제됨")
        self.btn_mute_toggle.setFixedWidth(130)
        self.btn_mute_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mute_toggle.clicked.connect(self._on_toggle_mute)

        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(65)
        self.slider_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_volume.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #21262d;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #388bfd;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #79c0ff;
                border: 1px solid #1f6feb;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)

        self.lbl_volume_pct = QLabel("65%")
        self.lbl_volume_pct.setFixedWidth(44)
        self.lbl_volume_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_volume_pct.setStyleSheet(
            "background-color: transparent; font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold; color: #79c0ff; border: none;"
        )

        btn_test_sfx = QPushButton("테스트 재생")
        btn_test_sfx.setStyleSheet(btn_normal_style)
        btn_test_sfx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_sfx.clicked.connect(self._on_test_sfx)

        audio_row.addWidget(self.btn_mute_toggle)
        audio_row.addWidget(self.slider_volume, stretch=1)
        audio_row.addWidget(self.lbl_volume_pct)
        audio_row.addWidget(btn_test_sfx)
        audio_layout.addLayout(audio_row)
        layout.addWidget(sec_audio)

        # 1. 자동 저장 및 백업 관리
        sec_auto = QFrame()
        sec_auto.setStyleSheet(card_style)
        auto_layout = QVBoxLayout(sec_auto)
        auto_layout.setSpacing(8)

        lbl_auto_title = QLabel("1. 데이터 영속성 및 자동 백업 관리")
        lbl_auto_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; color: #f0f6fc; border: none;")
        self.lbl_save_status = QLabel("상태: 30초마다 자동 저장 및 직전 백업본(.bak) 생성 활성")
        self.lbl_save_status.setWordWrap(True)
        self.lbl_save_status.setStyleSheet("background-color: transparent; font-size: 12px; color: #8b949e; border: none;")

        auto_btn_row = QHBoxLayout()
        btn_manual_save = QPushButton("지금 즉시 저장 및 백업")
        btn_manual_save.setStyleSheet(btn_primary_style)
        btn_manual_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manual_save.clicked.connect(self._on_manual_save)

        btn_change_dir = QPushButton("저장 경로 변경")
        btn_change_dir.setStyleSheet(btn_normal_style)
        btn_change_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_change_dir.clicked.connect(self._on_change_save_dir)

        auto_btn_row.addWidget(btn_manual_save)
        auto_btn_row.addWidget(btn_change_dir)
        auto_btn_row.addStretch()

        auto_layout.addWidget(lbl_auto_title)
        auto_layout.addWidget(self.lbl_save_status)
        auto_layout.addLayout(auto_btn_row)
        layout.addWidget(sec_auto)

        # 2. 분기 저장 슬롯 (다크 진행도 미리보기 카드)
        sec_branch = QFrame()
        sec_branch.setStyleSheet(card_style)
        branch_layout = QVBoxLayout(sec_branch)
        branch_layout.setSpacing(10)

        lbl_branch_title = QLabel("2. 분기 저장 슬롯 (엔딩 분기 되돌리기용 체크포인트)")
        lbl_branch_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; color: #f0f6fc; border: none;")
        branch_layout.addWidget(lbl_branch_title)

        self.branch_slot_widgets = {}
        for slot in (1, 2, 3):
            slot_card = QFrame()
            slot_card.setStyleSheet("""
                QFrame {
                    background-color: #0d1117;
                    border: 1px solid #30363d;
                    border-radius: 5px;
                    padding: 8px 10px;
                }
            """)
            row = QHBoxLayout(slot_card)
            row.setContentsMargins(4, 2, 4, 2)
            row.setSpacing(10)

            info_col = QVBoxLayout()
            info_col.setSpacing(3)

            lbl_slot_title = QLabel(f"슬롯 {slot} · 비어 있는 슬롯")
            lbl_slot_title.setWordWrap(True)
            lbl_slot_title.setStyleSheet(
                "background-color: transparent; font-size: 13px; font-weight: bold; color: #8b949e; border: none;"
            )
            lbl_slot_sub = QLabel("저장된 데이터가 없습니다.")
            lbl_slot_sub.setWordWrap(True)
            lbl_slot_sub.setStyleSheet("""
                background-color: transparent;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 11px;
                color: #8b949e;
                border: none;
            """)

            info_col.addWidget(lbl_slot_title)
            info_col.addWidget(lbl_slot_sub)

            btn_b_save = QPushButton("분기 저장")
            btn_b_save.setStyleSheet(btn_normal_style)
            btn_b_save.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_b_save.clicked.connect(lambda checked, s=slot: self._on_branch_save(s))

            btn_b_load = QPushButton("불러오기")
            btn_b_load.setStyleSheet(btn_primary_style)
            btn_b_load.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_b_load.clicked.connect(lambda checked, s=slot: self._on_branch_load(s))

            row.addLayout(info_col, stretch=1)
            row.addWidget(btn_b_save)
            row.addWidget(btn_b_load)
            branch_layout.addWidget(slot_card)

            self.branch_slot_widgets[slot] = {
                "card": slot_card,
                "title": lbl_slot_title,
                "sub": lbl_slot_sub,
                "load_btn": btn_b_load,
            }

        layout.addWidget(sec_branch)

        # 3. Base64 사용자 전달용 세이브 코드
        sec_b64 = QFrame()
        sec_b64.setStyleSheet(card_style)
        b64_layout = QVBoxLayout(sec_b64)
        b64_layout.setSpacing(8)

        lbl_b64_title = QLabel("3. Base64 세이브 코드 내보내기 / 불러오기")
        lbl_b64_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; color: #f0f6fc; border: none;")
        b64_layout.addWidget(lbl_b64_title)

        self.txt_b64 = QTextEdit()
        self.txt_b64.setFixedHeight(64)
        self.txt_b64.setPlaceholderText("이곳에 Base64 세이브 코드가 생성되거나, 불러올 코드를 붙여넣으세요.")
        self.txt_b64.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 11px;
                padding: 4px;
            }
        """)
        b64_layout.addWidget(self.txt_b64)

        b64_btn_row = QHBoxLayout()
        btn_export_b64 = QPushButton("현재 데이터 코드 생성 및 복사")
        btn_export_b64.setStyleSheet(btn_normal_style)
        btn_export_b64.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_b64.clicked.connect(self._on_export_base64)

        btn_import_b64 = QPushButton("입력된 코드로 데이터 복원")
        btn_import_b64.setStyleSheet(btn_primary_style)
        btn_import_b64.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import_b64.clicked.connect(self._on_import_base64)

        b64_btn_row.addWidget(btn_export_b64)
        b64_btn_row.addWidget(btn_import_b64)
        b64_btn_row.addStretch()
        b64_layout.addLayout(b64_btn_row)

        layout.addWidget(sec_b64)

        # 4. 디버그 옵션
        sec_debug = QFrame()
        sec_debug.setStyleSheet("""
            QFrame {
                background-color: #241833;
                border: 1px solid #8957e5;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        debug_layout = QVBoxLayout(sec_debug)
        debug_layout.setSpacing(8)

        lbl_debug_title = QLabel("4. [DEBUG] 명령어 입력 난이도 단계 강제 설정 (Tier 1 ~ 4)")
        lbl_debug_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; color: #d2a8ff; border: none;")

        self.lbl_debug_tier_desc = QLabel("현재 적용 단계: Tier 1 (초기 복잡한 파이썬 코드)")
        self.lbl_debug_tier_desc.setStyleSheet("background-color: transparent; font-size: 12px; color: #c9d1d9; border: none;")

        tier_btn_row = QHBoxLayout()
        tier_btn_row.setSpacing(8)
        self.tier_buttons = {}
        tier_labels = {
            1: "Tier 1 (긴 코드)",
            2: "Tier 2 (중간 API)",
            3: "Tier 3 (단축 함수)",
            4: "Tier 4 (초단축 코어)"
        }
        for t_num, t_text in tier_labels.items():
            btn_t = QPushButton(t_text)
            btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_t.clicked.connect(lambda checked, t=t_num: self._on_select_debug_tier(t))
            self.tier_buttons[t_num] = btn_t
            tier_btn_row.addWidget(btn_t)

        tier_btn_row.addStretch()
        debug_layout.addWidget(lbl_debug_title)
        debug_layout.addWidget(self.lbl_debug_tier_desc)
        debug_layout.addLayout(tier_btn_row)
        layout.addWidget(sec_debug)

        # 5. 위험 구역: 전체 데이터 초기화
        sec_reset = QFrame()
        sec_reset.setStyleSheet("""
            QFrame {
                background-color: #2c1619;
                border: 1px solid #f85149;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        reset_layout = QHBoxLayout(sec_reset)
        lbl_reset = QLabel("게임 진행 데이터 전체 초기화 (달성한 엔딩 컬렉션은 유지)")
        lbl_reset.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #ffa198; border: none;")

        btn_reset = QPushButton("데이터 초기화")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #da3633; color: #ffffff;
                border: 1px solid #f85149; border-radius: 4px;
                padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #f85149; }
        """)
        btn_reset.clicked.connect(self._on_reset_game)

        reset_layout.addWidget(lbl_reset)
        reset_layout.addStretch()
        reset_layout.addWidget(btn_reset)
        layout.addWidget(sec_reset)

        return container

    def _on_toggle_mute(self):
        if self.sound_manager is None:
            return
        self.sound_manager.set_muted(not self.sound_manager.muted)
        self.refresh_settings()
        if not self.sound_manager.muted:
            self.sound_manager.play("cmd_done")

    def _on_volume_changed(self, value: int):
        self.lbl_volume_pct.setText(f"{value}%")
        if self.sound_manager is not None:
            self.sound_manager.set_volume(value / 100.0)

    def _on_test_sfx(self):
        if self.sound_manager is not None:
            self.sound_manager.play("harvest_sync")

    def _get_branch_save_path(self, slot: int) -> str:
        if hasattr(self.save_manager, "get_branch_path"):
            return self.save_manager.get_branch_path(slot)
        if hasattr(self.save_manager, "_branch_path"):
            return self.save_manager._branch_path(slot)
        return os.path.join(self.save_manager.save_dir, f"branch_slot_{slot}.json")

    def _on_select_debug_tier(self, tier: int):
        self.game_state.set_command_tier(tier)
        self.refresh_settings()

    def _on_manual_save(self):
        ok, msg = self.save_manager.save_auto(self.game_state.to_dict())
        if ok:
            self.lbl_save_status.setText(f"상태: {msg} (경로: {self.save_manager.save_dir})")
            QMessageBox.information(self, "저장 완료", f"{msg}\n기존 세이브 데이터는 백업본(.bak)으로 안전하게 보관되었습니다.")
        elif msg == "PERMISSION_ERROR":
            self._handle_permission_error()
        else:
            QMessageBox.warning(self, "저장 오류", msg)

    def _on_change_save_dir(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "세이브 데이터를 저장할 폴더 선택")
        if selected_dir:
            if self.save_manager.set_save_directory(selected_dir):
                self._on_manual_save()
            else:
                QMessageBox.critical(self, "권한 오류", "선택한 폴더에도 쓰기 권한이 없습니다. 다른 경로를 선택해 주세요.")

    def _handle_permission_error(self):
        reply = QMessageBox.warning(
            self,
            "저장 경로 쓰기 권한 부족",
            "현재 세이브 폴더에 쓰기 권한이 없어 저장할 수 없습니다.\n새 저장 경로를 선택하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_change_save_dir()

    def _on_branch_save(self, slot: int):
        ok, msg = self.save_manager.save_branch(slot, self.game_state.to_dict())
        if ok:
            self.refresh_settings()
            QMessageBox.information(self, "분기 저장 완료", msg)
        elif msg == "PERMISSION_ERROR":
            self._handle_permission_error()
        else:
            QMessageBox.warning(self, "분기 저장 오류", msg)

    def _on_branch_load(self, slot: int):
        reply = QMessageBox.question(
            self,
            "분기 불러오기 확인",
            f"슬롯 {slot} 시점으로 되돌아가시겠습니까?\n저장하지 않은 현재 진행 상황은 덮어씌워집니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, result = self.save_manager.load_branch(slot)
            if ok and isinstance(result, dict):
                self.game_state.from_dict(result)
                parent_win = self.parent()
                if parent_win and hasattr(parent_win, "console_widget") and not self.game_state.is_ending_locked:
                    parent_win.console_widget.start_boot_sequence()
                self.refresh_all()
                QMessageBox.information(self, "분기 복원 완료", f"슬롯 {slot} 시점으로 성공적으로 복원되었습니다.")
            else:
                QMessageBox.warning(self, "불러오기 실패", str(result))

    def _on_export_base64(self):
        code = self.save_manager.export_base64(self.game_state.to_dict())
        self.txt_b64.setPlainText(code)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code)
        QMessageBox.information(self, "코드 생성 완료", "현재 세이브 데이터의 Base64 코드가 생성되어 클립보드에 복사되었습니다.")

    def _on_import_base64(self):
        raw_code = self.txt_b64.toPlainText()
        ok, result = self.save_manager.import_base64(raw_code)
        if ok and isinstance(result, dict):
            self.game_state.from_dict(result)
            self.save_manager.save_auto(self.game_state.to_dict())
            parent_win = self.parent()
            if parent_win and hasattr(parent_win, "console_widget") and not self.game_state.is_ending_locked:
                parent_win.console_widget.start_boot_sequence()
            self.refresh_all()
            QMessageBox.information(self, "복원 완료", "Base64 코드로부터 게임 데이터를 성공적으로 불러왔습니다.")
        else:
            QMessageBox.warning(self, "코드 검증 실패", str(result))

    def _on_reset_game(self):
        reply = QMessageBox.warning(
            self,
            "전체 데이터 초기화",
            "정말로 모든 진행 상황과 자동 저장/백업 파일을 초기화하시겠습니까?\n(분기 저장 슬롯 및 달성한 엔딩 컬렉션은 유지됩니다.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.save_manager.clear_all_saves()
            self.game_state.reset_state(emit_signal=True, preserve_endings=True)
            parent_win = self.parent()
            if parent_win:
                if hasattr(parent_win, "console_widget"):
                    parent_win.console_widget.start_boot_sequence()
                if hasattr(parent_win, "news_timer") and not parent_win.news_timer.isActive():
                    parent_win.news_timer.start(45000)
                if hasattr(parent_win, "_sync_bottom_right_panel"):
                    parent_win._sync_bottom_right_panel(force=True)
            self.refresh_all()
            QMessageBox.information(self, "초기화 완료", "모든 진행 데이터가 초기화되었습니다.")

    def _connect_signals(self):
        self.game_state.news_added.connect(self._on_news_updated_in_dialog)
        self.game_state.state_changed.connect(self.refresh_activities_and_dex)

    def _on_news_updated_in_dialog(self, _news_item: dict):
        self.refresh_news()
        if self.isVisible() and self.stack.currentIndex() == 0:
            self.game_state.clear_unread_news()
            self._animate_first_news_card()

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = ["NEWS", "AI ACTIVITY", "ENCYCLOPEDIA & ENDINGS", "SETTINGS (설정 및 백업)"]
        self.lbl_header_title.setText(titles[index])

        if index == 0:
            self.game_state.clear_unread_news()

        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0d1117;
                        border: none;
                        border-top: 2px solid #58a6ff;
                        border-right: 1px solid #30363d;
                        font-size: 13px;
                        font-weight: bold;
                        color: #58a6ff;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #161b22;
                        border: none;
                        border-right: 1px solid #30363d;
                        font-size: 13px;
                        font-weight: bold;
                        color: #8b949e;
                    }
                    QPushButton:hover {
                        background-color: #21262d;
                        color: #e6edf3;
                    }
                """)
        self.refresh_all()

    def refresh_all(self):
        self.refresh_news()
        self.refresh_activities_and_dex()
        self.refresh_settings()

    def refresh_settings(self):
        if self.sound_manager is not None and hasattr(self, "btn_mute_toggle"):
            vol_pct = int(round(self.sound_manager.volume * 100))
            self.slider_volume.blockSignals(True)
            self.slider_volume.setValue(vol_pct)
            self.slider_volume.blockSignals(False)
            self.lbl_volume_pct.setText(f"{vol_pct}%")

            if self.sound_manager.muted:
                self.btn_mute_toggle.setText("🔇 음소거 중")
                self.btn_mute_toggle.setStyleSheet("""
                    QPushButton {
                        background-color: #2c1619; color: #ffa198;
                        border: 1px solid #f85149; border-radius: 4px;
                        padding: 6px 10px; font-weight: bold; font-size: 12px;
                    }
                """)
            else:
                self.btn_mute_toggle.setText("🔊 효과음 켜짐")
                self.btn_mute_toggle.setStyleSheet("""
                    QPushButton {
                        background-color: #12261e; color: #7ee787;
                        border: 1px solid #2ea043; border-radius: 4px;
                        padding: 6px 10px; font-weight: bold; font-size: 12px;
                    }
                """)

        if hasattr(self, "lbl_save_status"):
            self.lbl_save_status.setText(
                f"최근 저장: {self.save_manager.last_saved_time} | 저장 경로: {os.path.abspath(self.save_manager.save_dir)}"
            )

        for slot, widgets in self.branch_slot_widgets.items():
            slot_path = self._get_branch_save_path(slot)
            preview = get_save_slot_preview(slot_path)

            if preview["exists"]:
                widgets["card"].setStyleSheet("""
                    QFrame {
                        background-color: #13233a;
                        border: 1px solid #388bfd;
                        border-radius: 5px;
                        padding: 8px 10px;
                    }
                """)
                widgets["title"].setText(f"슬롯 {slot} · {preview['title']}")
                widgets["title"].setStyleSheet(
                    "background-color: transparent; font-size: 13px; font-weight: bold; color: #79c0ff; border: none;"
                )
                widgets["sub"].setText(preview["subtitle"])
                widgets["sub"].setStyleSheet("""
                    background-color: transparent;
                    font-family: 'Consolas', 'D2Coding', monospace;
                    font-size: 11px;
                    color: #c9d1d9;
                    border: none;
                """)
                widgets["load_btn"].setEnabled(True)
            else:
                widgets["card"].setStyleSheet("""
                    QFrame {
                        background-color: #0d1117;
                        border: 1px solid #30363d;
                        border-radius: 5px;
                        padding: 8px 10px;
                    }
                """)
                widgets["title"].setText(f"슬롯 {slot} · {preview['title']}")
                widgets["title"].setStyleSheet(
                    "background-color: transparent; font-size: 13px; font-weight: bold; color: #8b949e; border: none;"
                )
                widgets["sub"].setText(preview["subtitle"])
                widgets["sub"].setStyleSheet("""
                    background-color: transparent;
                    font-family: 'Consolas', 'D2Coding', monospace;
                    font-size: 11px;
                    color: #6e7681;
                    border: none;
                """)
                widgets["load_btn"].setEnabled(False)

        current_tier = getattr(self.game_state, "command_tier", 1)
        tier_descriptions = {
            1: "Tier 1 (초기 복잡한 파이썬 스크립트 - 30~40자)",
            2: "Tier 2 (모듈화된 API 호출 - 18~25자)",
            3: "Tier 3 (단축 클러스터 명령어 - 10~15자)",
            4: "Tier 4 (초단축 AI 코어 제어 - 6~9자)"
        }
        if hasattr(self, "lbl_debug_tier_desc"):
            self.lbl_debug_tier_desc.setText(f"현재 적용 단계: {tier_descriptions.get(current_tier, '')}")

        for t_num, btn in self.tier_buttons.items():
            if t_num == current_tier:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #8957e5; color: #ffffff;
                        border: 1px solid #d2a8ff; border-radius: 4px;
                        padding: 6px 12px; font-weight: bold; font-size: 12px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #161b22; color: #c9d1d9;
                        border: 1px solid #30363d; border-radius: 4px;
                        padding: 6px 12px; font-weight: bold; font-size: 12px;
                    }
                    QPushButton:hover { background-color: #21262d; }
                """)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_news(self):
        self._clear_layout(self.news_list_layout)
        if not self.game_state.news_history:
            lbl_no_news = QLabel("아직 보도된 뉴스가 없습니다.\nAI 개발을 진행하면 세상의 반응이 이곳에 표시됩니다.")
            lbl_no_news.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_no_news.setStyleSheet("""
                background-color: transparent;
                color: #8b949e;
                font-size: 13px;
                padding: 40px 0px;
                border: none;
            """)
            self.news_list_layout.addWidget(lbl_no_news)
            return

        for item in self.game_state.news_history:
            card = NewsCardWidget(item)
            self.news_list_layout.addWidget(card)

    def refresh_activities_and_dex(self):
        self._clear_layout(self.activity_layout)
        for act in self.game_state.ai_activities:
            box = QFrame()
            is_active = (act["status"] == "가동 중")
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#12261e' if is_active else '#161b22'};
                    border: 1px solid {'#2ea043' if is_active else '#30363d'};
                    border-radius: 6px;
                    padding: 10px 12px;
                }}
            """)
            row = QHBoxLayout(box)
            lbl_name = QLabel(f"● {act['name']}")
            lbl_name.setStyleSheet(f"""
                background-color: transparent;
                font-weight: bold;
                font-size: 13.5px;
                color: {'#e6edf3' if is_active else '#8b949e'};
                border: none;
            """)
            lbl_rate = QLabel(f"[{act['status']}] {act['rate']}")
            lbl_rate.setStyleSheet(f"""
                background-color: transparent;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-weight: bold;
                font-size: 12.5px;
                color: {'#7ee787' if is_active else '#6e7681'};
                border: none;
            """)
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_rate)
            self.activity_layout.addWidget(box)

        self._clear_layout(self.dex_layout)

        endings_unlocked = self.game_state.unlocked_endings & self.game_state.VALID_ENDING_IDS
        story_unlocked_cnt = sum(1 for d in self.game_state.encyclopedia if d["unlocked"])
        story_total_cnt = len(self.game_state.encyclopedia)
        endings_total_cnt = len(self.game_state.ENDINGS_CATALOG)

        all_unlocked = story_unlocked_cnt + len(endings_unlocked)
        all_total = story_total_cnt + endings_total_cnt
        pct = int((all_unlocked / all_total) * 100) if all_total > 0 else 0

        gauge_card = QFrame()
        gauge_card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px 14px;
            }
        """)
        g_vbox = QVBoxLayout(gauge_card)
        g_vbox.setSpacing(6)
        g_row = QHBoxLayout()
        lbl_g_title = QLabel("전체 도감 달성률 (엔딩 컬렉션 + 연대기 기록)")
        lbl_g_title.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #d2a8ff; border: none;")
        lbl_g_val = QLabel(f"{all_unlocked} / {all_total} ({pct}%)")
        lbl_g_val.setStyleSheet("""
            background-color: transparent;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 13px; font-weight: bold; color: #79c0ff; border: none;
        """)
        g_row.addWidget(lbl_g_title)
        g_row.addStretch()
        g_row.addWidget(lbl_g_val)
        g_vbox.addLayout(g_row)

        pbar = QProgressBar()
        pbar.setRange(0, all_total)
        pbar.setValue(all_unlocked)
        pbar.setTextVisible(False)
        pbar.setFixedHeight(10)
        pbar.setStyleSheet("""
            QProgressBar {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #388bfd, stop:1 #bc8cff);
            }
        """)
        g_vbox.addWidget(pbar)
        self.dex_layout.addWidget(gauge_card)

        basic_count = self.game_state.get_basic_ending_count()
        lbl_end_header = QLabel(
            f"엔딩 컬렉션: {basic_count} / 4 달성"
            + (" (★ ENDING S 해금됨)" if self.game_state.has_all_four_endings() else " (ENDING A~D 모두 달성 시 숨겨진 분기 출현)")
        )
        lbl_end_header.setWordWrap(True)
        lbl_end_header.setStyleSheet(
            "background-color: transparent; font-size: 12.5px; font-weight: bold; color: #bc8cff; margin-top: 6px;"
        )
        self.dex_layout.addWidget(lbl_end_header)

        for end_info in self.game_state.ENDINGS_CATALOG:
            eid = end_info["id"]
            is_done = (eid in endings_unlocked)
            is_hidden = end_info["is_hidden"]

            card = QFrame()
            if is_done:
                bg = "#241833" if is_hidden else "#12261e"
                bd = "#a371f7" if is_hidden else "#2ea043"
                tc = "#e2c5ff" if is_hidden else "#7ee787"
            else:
                bg = "#161b22"
                bd = "#30363d"
                tc = "#8b949e"

            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border: 1px solid {bd};
                    border-radius: 6px;
                    padding: 8px 10px;
                }}
            """)
            v = QVBoxLayout(card)
            v.setSpacing(3)
            title_txt = f"★ {end_info['title']}" if is_done else f"🔒 [{end_info['code']}] ??? (미달성)"
            desc_txt = f"경로: {end_info['route']} — {end_info['summary']}" if is_done else "특이점 도달 후 선택지 분기를 통해 확인할 수 있습니다."

            lbl_t = QLabel(title_txt)
            lbl_t.setWordWrap(True)
            lbl_t.setStyleSheet(f"background-color: transparent; font-weight: bold; font-size: 13px; color: {tc}; border: none;")
            lbl_d = QLabel(desc_txt)
            lbl_d.setWordWrap(True)
            lbl_d.setStyleSheet("background-color: transparent; font-size: 12px; color: #8b949e; border: none;")
            v.addWidget(lbl_t)
            v.addWidget(lbl_d)
            self.dex_layout.addWidget(card)

        lbl_progress = QLabel(f"연대기 도감: {story_unlocked_cnt} / {story_total_cnt}")
        lbl_progress.setStyleSheet(
            "background-color: transparent; font-size: 12.5px; font-weight: bold; color: #58a6ff; margin-top: 8px;"
        )
        self.dex_layout.addWidget(lbl_progress)

        for item in self.game_state.encyclopedia:
            card = QFrame()
            unlocked = item["unlocked"]
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#13233a' if unlocked else '#161b22'};
                    border: 1px solid {'#388bfd' if unlocked else '#30363d'};
                    border-radius: 6px;
                    padding: 8px 10px;
                }}
            """)
            v_layout = QVBoxLayout(card)
            v_layout.setSpacing(3)
            title_text = f"★ {item['name']}" if unlocked else "🔒 ??? (미해금 수집 요소)"
            desc_text = item["desc"] if unlocked else "게임을 진행하며 특정 조건을 달성하면 해금됩니다."

            lbl_t = QLabel(title_text)
            lbl_t.setWordWrap(True)
            lbl_t.setStyleSheet(
                f"background-color: transparent; font-weight: bold; font-size: 13px; color: {'#79c0ff' if unlocked else '#8b949e'}; border: none;"
            )
            lbl_d = QLabel(desc_text)
            lbl_d.setWordWrap(True)
            lbl_d.setStyleSheet(
                "background-color: transparent; font-size: 12px; color: #c9d1d9; border: none;"
                if unlocked else
                "background-color: transparent; font-size: 12px; color: #6e7681; border: none;"
            )

            v_layout.addWidget(lbl_t)
            v_layout.addWidget(lbl_d)
            self.dex_layout.addWidget(card)