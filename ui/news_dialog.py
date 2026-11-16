from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt


class NewsCardWidget(QFrame):
    """계획서 3.2절의 파스텔 톤 뉴스 카드 (제목 + 날짜 + 가로선 + 요약 본문)"""

    def __init__(self, news_item: dict):
        super().__init__()
        category = news_item.get("category", "info")
        color_schemes = {
            "info": ("#fae17d", "#9a6700"),    # 노란색 카드
            "danger": ("#f28b96", "#a40e26"),  # 빨간색/분홍색 카드
            "story": ("#d99be6", "#6639ba")    # 보라색 카드
        }
        bg_color, border_color = color_schemes.get(category, ("#fae17d", "#9a6700"))

        self.setStyleSheet(f"""
            NewsCardWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        # 상단: 제목 + 우측 날짜
        header_row = QHBoxLayout()
        lbl_title = QLabel(news_item["title"])
        lbl_title.setStyleSheet("""
            background-color: transparent;
            font-size: 15px;
            font-weight: bold;
            color: #1f2328;
            border: none;
        """)

        lbl_date = QLabel(news_item["date"])
        lbl_date.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_date.setStyleSheet("""
            background-color: transparent;
            font-size: 13px;
            font-weight: bold;
            color: #24292f;
            border: none;
        """)

        header_row.addWidget(lbl_title, stretch=1)
        header_row.addWidget(lbl_date)
        layout.addLayout(header_row)

        # 중간 구분 실선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {border_color}; max-height: 1px; border: none;")
        layout.addWidget(line)

        # 하단 뉴스 본문
        lbl_content = QLabel(news_item["content"])
        lbl_content.setWordWrap(True)
        lbl_content.setStyleSheet("""
            background-color: transparent;
            font-size: 12px;
            color: #1f2328;
            border: none;
            line-height: 1.4;
        """)
        layout.addWidget(lbl_content)


class NewsDialog(QDialog):
    """계획서 3.2절 확장 팝업창 (최근 뉴스 / AI 활동 / 도감 탭 전환 지원)"""

    def __init__(self, game_state, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.setWindowTitle("AI 키우기 - 뉴스 및 도감")
        self.resize(760, 520)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

        self._init_ui()
        self._connect_signals()
        self.refresh_all()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 상단 헤더 바 (NEWS)
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #1f2328;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        self.lbl_header_title = QLabel("NEWS")
        self.lbl_header_title.setStyleSheet("background-color: transparent; font-size: 18px; font-weight: bold; color: #1f2328; border: none;")
        header_layout.addWidget(self.lbl_header_title)
        header_layout.addStretch()

        btn_close = QPushButton("닫기")
        btn_close.setFixedSize(60, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa; border: 1px solid #d0d7de;
                border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)
        main_layout.addWidget(header)

        # 2. 중앙 콘텐츠 스택 (0: 최근 뉴스, 1: AI 활동, 2: 도감)
        self.stack = QStackedWidget()

        # [탭 0] 최근 뉴스 스크롤 영역
        self.news_scroll = QScrollArea()
        self.news_scroll.setWidgetResizable(True)
        self.news_scroll.setStyleSheet("border: none; background-color: #ffffff;")
        self.news_container = QWidget()
        self.news_container.setStyleSheet("background-color: #ffffff;")
        self.news_list_layout = QVBoxLayout(self.news_container)
        self.news_list_layout.setContentsMargins(18, 16, 18, 16)
        self.news_list_layout.setSpacing(14)
        self.news_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.news_scroll.setWidget(self.news_container)
        self.stack.addWidget(self.news_scroll)

        # [탭 1] AI 활동 스크롤 영역
        self.activity_scroll = QScrollArea()
        self.activity_scroll.setWidgetResizable(True)
        self.activity_scroll.setStyleSheet("border: none; background-color: #ffffff;")
        self.activity_container = QWidget()
        self.activity_container.setStyleSheet("background-color: #ffffff;")
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(18, 16, 18, 16)
        self.activity_layout.setSpacing(12)
        self.activity_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.activity_scroll.setWidget(self.activity_container)
        self.stack.addWidget(self.activity_scroll)

        # [탭 2] 도감 스크롤 영역
        self.dex_scroll = QScrollArea()
        self.dex_scroll.setWidgetResizable(True)
        self.dex_scroll.setStyleSheet("border: none; background-color: #ffffff;")
        self.dex_container = QWidget()
        self.dex_container.setStyleSheet("background-color: #ffffff;")
        self.dex_layout = QVBoxLayout(self.dex_container)
        self.dex_layout.setContentsMargins(18, 16, 18, 16)
        self.dex_layout.setSpacing(12)
        self.dex_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dex_scroll.setWidget(self.dex_container)
        self.stack.addWidget(self.dex_scroll)

        main_layout.addWidget(self.stack, stretch=1)

        # 3. 하단 탭 바 (계획서 3.2절: 최근 뉴스 | AI 활동 | 도감)
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(46)
        bottom_bar.setStyleSheet("background-color: #ffffff; border-top: 2px solid #1f2328;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self.tab_buttons = []
        tab_names = ["최근 뉴스", "AI 활동", "도감"]
        for idx, name in enumerate(tab_names):
            btn = QPushButton(name)
            btn.setFixedHeight(44)
            btn.setFixedWidth(120)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            self.tab_buttons.append(btn)
            bottom_layout.addWidget(btn)

        bottom_layout.addStretch()
        main_layout.addWidget(bottom_bar)

        self._switch_tab(0)

    def _connect_signals(self):
        self.game_state.news_added.connect(lambda _: self.refresh_news())
        self.game_state.state_changed.connect(self.refresh_activities_and_dex)

    def _switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = ["NEWS", "AI ACTIVITY", "ENCYCLOPEDIA (도감)"]
        self.lbl_header_title.setText(titles[index])

        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #eaeef2;
                        border: none;
                        border-right: 2px solid #1f2328;
                        font-size: 14px;
                        font-weight: bold;
                        color: #0969da;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        border: none;
                        border-right: 2px solid #1f2328;
                        font-size: 14px;
                        font-weight: bold;
                        color: #1f2328;
                    }
                    QPushButton:hover { background-color: #f6f8fa; }
                """)
        self.refresh_all()

    def refresh_all(self):
        self.refresh_news()
        self.refresh_activities_and_dex()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_news(self):
        self._clear_layout(self.news_list_layout)
        for item in self.game_state.news_history:
            card = NewsCardWidget(item)
            self.news_list_layout.addWidget(card)

    def refresh_activities_and_dex(self):
        # AI 활동 갱신
        self._clear_layout(self.activity_layout)
        for act in self.game_state.ai_activities:
            box = QFrame()
            is_active = (act["status"] == "가동 중")
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#dafbe1' if is_active else '#f6f8fa'};
                    border: 1px solid {'#2da44e' if is_active else '#d0d7de'};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            row = QHBoxLayout(box)
            lbl_name = QLabel(f"● {act['name']}")
            lbl_name.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 14px; border: none;")
            lbl_rate = QLabel(f"[{act['status']}] {act['rate']}")
            lbl_rate.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; color: #0969da; border: none;")
            row.addWidget(lbl_name)
            row.addStretch()
            row.addWidget(lbl_rate)
            self.activity_layout.addWidget(box)

        # 도감 갱신
        self._clear_layout(self.dex_layout)
        unlocked_cnt = sum(1 for d in self.game_state.encyclopedia if d["unlocked"])
        total_cnt = len(self.game_state.encyclopedia)

        lbl_progress = QLabel(f"도감 수집률: {unlocked_cnt} / {total_cnt} ({int(unlocked_cnt / total_cnt * 100)}%) — 100% 달성 시 히든 엔딩 해금")
        lbl_progress.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #6639ba; margin-bottom: 6px;")
        self.dex_layout.addWidget(lbl_progress)

        for item in self.game_state.encyclopedia:
            card = QFrame()
            unlocked = item["unlocked"]
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#fbefff' if unlocked else '#eaeef2'};
                    border: 1px solid {'#8250df' if unlocked else '#afb8c1'};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            v_layout = QVBoxLayout(card)
            title_text = f"★ {item['name']}" if unlocked else "🔒 ??? (미해금 수집 요소)"
            desc_text = item["desc"] if unlocked else "게임을 진행하며 특정 조건을 달성하면 해금됩니다."

            lbl_t = QLabel(title_text)
            lbl_t.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 14px; border: none;")
            lbl_d = QLabel(desc_text)
            lbl_d.setStyleSheet("background-color: transparent; font-size: 12px; color: #424a53; border: none;")

            v_layout.addWidget(lbl_t)
            v_layout.addWidget(lbl_d)
            self.dex_layout.addWidget(card)