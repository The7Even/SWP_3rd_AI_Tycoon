from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from core.game_state import GameState
from core.number_format import format_number
from ui.console_widget import VirtualConsoleWidget
from ui.tree_widget import UpgradeTreeWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 키우기 - Prototype")
        self.resize(1150, 720)

        self.game_state = GameState()
        self._init_ui()
        self._connect_signals()

        # 0.1초(100ms) 주기 패시브 토큰 수급 타이머
        self.passive_timer = QTimer(self)
        self.passive_timer.timeout.connect(self._on_tick)
        self.passive_timer.start(100)

        self._update_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ================= [좌측 메인 영역 (72%)] =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. 상단 재화 표시 바
        top_bar = QFrame()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #d0d7de;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 5, 15, 5)

        self.lbl_tokens = QLabel("0 Token")
        self.lbl_tokens.setStyleSheet("color: #0969da; font-size: 20px; font-weight: bold;")

        self.lbl_rates = QLabel("24 Tk/Command\n6 Tk/s")
        self.lbl_rates.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_rates.setStyleSheet("color: #0969da; font-size: 13px; font-weight: bold;")

        top_layout.addWidget(self.lbl_tokens)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_rates)
        left_layout.addWidget(top_bar)

        # 2. 중앙 가상 콘솔 영역
        self.console_widget = VirtualConsoleWidget(self.game_state)
        left_layout.addWidget(self.console_widget, stretch=1)

        # 3. 하단 정보 영역 (좌: Specs / 우: NEWS)
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(155)
        bottom_bar.setStyleSheet("background-color: #ffffff; border-top: 2px solid #d0d7de;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        # 3-1. 하단 좌측: 하드웨어 스펙 및 벤치마크 점수
        specs_box = QWidget()
        specs_layout = QVBoxLayout(specs_box)
        specs_layout.setContentsMargins(12, 8, 12, 8)
        specs_layout.setSpacing(2)

        self.lbl_specs = QLabel()
        self.lbl_specs.setStyleSheet("color: #1f2328; font-size: 13px; font-weight: bold;")
        self.lbl_bench = QLabel()
        self.lbl_bench.setStyleSheet("color: #0969da; font-size: 14px; font-weight: bold;")

        specs_layout.addWidget(self.lbl_specs)
        specs_layout.addWidget(self.lbl_bench)
        bottom_layout.addWidget(specs_box, stretch=1)

        # 3-2. 하단 우측: 미니 NEWS 패널
        news_box = QFrame()
        news_box.setStyleSheet("border-left: 2px solid #d0d7de;")
        news_layout = QVBoxLayout(news_box)
        news_layout.setContentsMargins(10, 6, 10, 6)
        news_layout.setSpacing(6)

        news_header = QHBoxLayout()
        lbl_news_title = QLabel("NEWS")
        lbl_news_title.setStyleSheet("font-size: 15px; font-weight: bold; border: none;")
        btn_news_expand = QPushButton("↗")
        btn_news_expand.setFixedSize(26, 24)
        btn_news_expand.setToolTip("전체 뉴스 및 도감 보기 (구현 예정)")
        btn_news_expand.clicked.connect(self._show_news_popup)

        news_header.addWidget(lbl_news_title)
        news_header.addStretch()
        news_header.addWidget(btn_news_expand)
        news_layout.addLayout(news_header)

        self.lbl_news_1 = QLabel("OO, 개인 개발 AI 최초 수능 1등급..")
        self.lbl_news_1.setStyleSheet("""
            background-color: #fae17d; border: 1px solid #9a6700;
            border-radius: 4px; padding: 6px; font-size: 12px; font-weight: bold;
        """)

        self.lbl_news_2 = QLabel("InstantGram, AI 개발 우려 표명.. AI 산업 주춤")
        self.lbl_news_2.setStyleSheet("""
            background-color: #ff8182; border: 1px solid #cf222e;
            border-radius: 4px; padding: 6px; font-size: 12px; font-weight: bold;
        """)

        news_layout.addWidget(self.lbl_news_1)
        news_layout.addWidget(self.lbl_news_2)
        bottom_layout.addWidget(news_box, stretch=1)

        left_layout.addWidget(bottom_bar)
        root_layout.addWidget(left_panel, stretch=72)

        # ================= [우측 업그레이드 트리 영역 (28%)] =================
        self.tree_widget = UpgradeTreeWidget(self.game_state)
        root_layout.addWidget(self.tree_widget, stretch=28)

    def _connect_signals(self):
        self.game_state.state_changed.connect(self._update_ui)
        self.game_state.news_added.connect(self._on_news_added)

    def _on_tick(self):
        self.game_state.add_passive_tokens(0.1)

    def _update_ui(self):
        gs = self.game_state
        self.lbl_tokens.setText(f"{format_number(gs.tokens)} Token")
        self.lbl_rates.setText(
            f"{format_number(gs.tokens_per_command)} Tk/Command\n"
            f"{format_number(gs.tokens_per_sec)} Tk/s"
        )

        s = gs.specs
        self.lbl_specs.setText(
            f"Specs :\n"
            f"CPU : {s['CPU']}\n"
            f"GPU : {s['GPU']}\n"
            f"RAM : {s['RAM']}\n"
            f"STORAGE : {s['STORAGE']}"
        )
        self.lbl_bench.setText(f"BENCH_SCORE : {format_number(s['BENCH_SCORE'])}")

        self.tree_widget.refresh_tree()

    def _on_news_added(self, title: str, news_type: str):
        # 새 뉴스가 들어오면 기존 뉴스 1을 2로 밀어내고 상단에 표시
        self.lbl_news_2.setText(self.lbl_news_1.text())
        self.lbl_news_1.setText(title)

    def _show_news_popup(self):
        QMessageBox.information(
            self,
            "전체 뉴스 / AI 활동 / 도감",
            "계획서 3.2절의 확장 뉴스 & 도감 창이 이곳에 연결될 예정입니다."
        )