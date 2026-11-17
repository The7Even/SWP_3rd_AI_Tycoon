from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QPushButton, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from core.game_state import GameState
from core.save_manager import SaveManager
from core.number_format import format_number
from ui.console_widget import VirtualConsoleWidget
from ui.tree_widget import UpgradeTreeWidget
from ui.news_dialog import NewsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 키우기 - Prototype")
        self.resize(1150, 720)

        self.game_state = GameState()
        self.save_manager = SaveManager()
        self.news_dialog = None

        self._init_ui()
        self._connect_signals()

        # 시작 시 기존 세이브 파일 로드 및 손상/백업 예외 처리 (계획서 2.5.3절)
        self._load_initial_save()

        # 0.1초(100ms) 주기 패시브 토큰 수급 타이머
        self.passive_timer = QTimer(self)
        self.passive_timer.timeout.connect(self._on_tick)
        self.passive_timer.start(100)

        # 25초 주기 상시 랜덤 뉴스 발생 타이머
        self.news_timer = QTimer(self)
        self.news_timer.timeout.connect(self.game_state.trigger_random_news)
        self.news_timer.start(25000)

        # 30초 주기 자동 저장 및 백업 타이머 (계획서 2.2.4절)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._on_autosave_tick)
        self.autosave_timer.start(30000)

        self._update_ui()
        self._refresh_mini_news()

    def _load_initial_save(self):
        status, data = self.save_manager.load_auto()
        if status == "SUCCESS" and data:
            self.game_state.from_dict(data)
        elif status == "RECOVERED_FROM_BACKUP" and data:
            self.game_state.from_dict(data)
            QMessageBox.information(
                self,
                "세이브 데이터 자동 복구",
                "기본 세이브 파일의 손상이 감지되어 백업 파일(.bak)로부터 진행 상황을 안전하게 복구했습니다."
            )
        elif status == "CORRUPTED_ALL":
            QMessageBox.warning(
                self,
                "세이브 데이터 손상 안내",
                "세이브 파일과 백업 파일이 모두 손상되어 데이터를 복구할 수 없습니다.\n새로운 게임 상태로 초기화하여 시작합니다."
            )
            self.save_manager.clear_all_saves()
            self.game_state.reset_state(emit_signal=False)

    def _on_autosave_tick(self):
        ok, msg = self.save_manager.save_auto(self.game_state.to_dict())
        if not ok and msg == "PERMISSION_ERROR":
            self.autosave_timer.stop()
            reply = QMessageBox.warning(
                self,
                "자동 저장 권한 오류",
                "현재 저장 경로에 쓰기 권한이 부족합니다. 새 저장 경로를 지정하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                new_dir = QFileDialog.getExistingDirectory(self, "새 세이브 저장 폴더 선택")
                if new_dir and self.save_manager.set_save_directory(new_dir):
                    self.save_manager.save_auto(self.game_state.to_dict())
                    self.autosave_timer.start(30000)

    def closeEvent(self, event):
        """프로그램 종료 시 자동 저장 수행"""
        self.save_manager.save_auto(self.game_state.to_dict())
        event.accept()

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
        btn_news_expand.setFixedSize(28, 24)
        btn_news_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_news_expand.setToolTip("전체 뉴스 / AI 활동 / 도감 / 설정 열기")
        btn_news_expand.clicked.connect(self._show_news_popup)

        news_header.addWidget(lbl_news_title)
        news_header.addStretch()
        news_header.addWidget(btn_news_expand)
        news_layout.addLayout(news_header)

        self.lbl_news_1 = QLabel()
        self.lbl_news_2 = QLabel()
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

    def _apply_mini_card_style(self, label: QLabel, news_item: dict):
        color_schemes = {
            "info": ("#fae17d", "#9a6700"),
            "danger": ("#f28b96", "#a40e26"),
            "story": ("#d99be6", "#6639ba")
        }
        bg, border = color_schemes.get(news_item.get("category", "info"), ("#fae17d", "#9a6700"))
        label.setText(news_item["title"])
        label.setStyleSheet(f"""
            background-color: {bg}; border: 1px solid {border};
            border-radius: 4px; padding: 6px; font-size: 12px; font-weight: bold;
        """)

    def _refresh_mini_news(self):
        history = self.game_state.news_history
        if len(history) >= 1:
            self._apply_mini_card_style(self.lbl_news_1, history[0])
        if len(history) >= 2:
            self._apply_mini_card_style(self.lbl_news_2, history[1])

    def _on_news_added(self, news_item: dict):
        self._refresh_mini_news()

    def _show_news_popup(self):
        if self.news_dialog is None:
            self.news_dialog = NewsDialog(self.game_state, self.save_manager, self)
        self.news_dialog.refresh_all()
        self.news_dialog.show()
        self.news_dialog.raise_()
        self.news_dialog.activateWindow()