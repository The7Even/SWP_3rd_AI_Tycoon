from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QPushButton, QMessageBox, QFileDialog, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QPoint, QEasingCurve
from PyQt6.QtGui import QFontMetrics
from core.game_state import GameState
from core.save_manager import SaveManager
from core.number_format import format_number
from ui.console_widget import VirtualConsoleWidget
from ui.tree_widget import UpgradeTreeWidget
from ui.news_dialog import NewsDialog


class StoryEventDialog(QDialog):
    """스토리 노드 해금 시 등장하는 챕터 스토리 연출 팝업 (1~15번 이벤트)"""

    def __init__(self, story_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"STORY EVENT #{story_data.get('number', '')} - {story_data.get('chapter', '')}")
        self.setFixedSize(520, 310)
        self.setStyleSheet("QDialog { background-color: #0d1117; border: 2px solid #8250df; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        top_meta = QHBoxLayout()
        lbl_chap = QLabel(f"◆ {story_data.get('chapter', 'STORY')}")
        lbl_chap.setStyleSheet("color: #d2a8ff; font-size: 13px; font-weight: bold;")

        lbl_role = QLabel(story_data.get("node_role", ""))
        lbl_role.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_role.setStyleSheet("""
            background-color: #21262d;
            color: #79c0ff;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        top_meta.addWidget(lbl_chap)
        top_meta.addStretch()
        top_meta.addWidget(lbl_role)
        layout.addLayout(top_meta)

        lbl_title = QLabel(story_data.get("title", ""))
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #30363d; max-height: 1px;")
        layout.addWidget(line)

        lbl_content = QLabel(story_data.get("content", ""))
        lbl_content.setWordWrap(True)
        lbl_content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lbl_content.setStyleSheet("color: #c9d1d9; font-size: 13px; line-height: 1.5;")
        layout.addWidget(lbl_content, stretch=1)

        btn_ok = QPushButton("계속 개발하기")
        btn_ok.setFixedHeight(34)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #8250df;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6639ba; }
        """)
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)


class MiniNewsTickerWidget(QWidget):
    """튜토리얼 중에는 DEV GUIDE 카드를, 본편 진입 후에는 슬라이드 인 NEWS 카드를 표시하는 미니 패널"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(86)

        self.lbl_empty = QLabel("수신된 뉴스가 없습니다.", self)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("""
            background-color: #f6f8fa;
            border: 1px dashed #d0d7de;
            border-radius: 4px;
            color: #6e7781;
            font-size: 12px;
        """)

        self.card_1 = QLabel(self)
        self.card_2 = QLabel(self)
        self._item_1: dict | None = None
        self._item_2: dict | None = None
        self._anim_group: QParallelAnimationGroup | None = None
        self._is_guide_mode: bool = True

        for card in (self.card_1, self.card_2):
            card.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            card.hide()

    def _card_geometry(self) -> tuple[int, int, int, int]:
        w = max(120, self.width())
        h = max(72, self.height())
        gap = 6
        card_h = max(30, (h - gap) // 2)
        y1 = 0
        y2 = card_h + gap
        return w, card_h, y1, y2

    def _style_card(self, label: QLabel, news_item: dict, width: int):
        category = news_item.get("category", "info")
        color_schemes = {
            "info": ("#fae17d", "#9a6700"),
            "danger": ("#f28b96", "#a40e26"),
            "story": ("#d99be6", "#6639ba"),
            "guide": ("#ddf4ff", "#0969da"),
            "guide_sub": ("#f6f8fa", "#8c959f"),
        }
        bg, border = color_schemes.get(category, ("#fae17d", "#9a6700"))
        is_guide = category in ("guide", "guide_sub")
        font_size = "11px" if is_guide else "12px"

        label.setStyleSheet(f"""
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 3px 8px;
            font-size: {font_size};
            font-weight: bold;
            color: #1f2328;
        """)

        title_text = news_item.get("title", "")
        if is_guide:
            label.setWordWrap(True)
            label.setText(title_text)
        else:
            label.setWordWrap(False)
            metrics = QFontMetrics(label.font())
            elided = metrics.elidedText(title_text, Qt.TextElideMode.ElideRight, max(60, width - 20))
            label.setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._anim_group and self._anim_group.state() == QPropertyAnimation.State.Running:
            self._anim_group.stop()
        self._snap_positions()

    def _snap_positions(self):
        w, card_h, y1, y2 = self._card_geometry()
        self.lbl_empty.setGeometry(0, 0, w, max(72, self.height()))

        if not self._item_1 and not self._item_2:
            self.lbl_empty.show()
            self.card_1.hide()
            self.card_2.hide()
            return

        self.lbl_empty.hide()
        if self._item_1:
            self._style_card(self.card_1, self._item_1, w)
            self.card_1.setGeometry(0, y1, w, card_h)
            self.card_1.show()
        else:
            self.card_1.hide()

        if self._item_2:
            self._style_card(self.card_2, self._item_2, w)
            self.card_2.setGeometry(0, y2, w, card_h)
            self.card_2.show()
        else:
            self.card_2.hide()

    def set_guide_items(self, line1: str, line2: str):
        self._is_guide_mode = True
        if self._anim_group and self._anim_group.state() == QPropertyAnimation.State.Running:
            self._anim_group.stop()
        self._item_1 = {"title": line1, "category": "guide"}
        self._item_2 = {"title": line2, "category": "guide_sub"} if line2 else None
        self._snap_positions()

    def set_initial_items(self, history: list[dict]):
        self._is_guide_mode = False
        if self._anim_group and self._anim_group.state() == QPropertyAnimation.State.Running:
            self._anim_group.stop()
        self._item_1 = history[0] if len(history) >= 1 else None
        self._item_2 = history[1] if len(history) >= 2 else None
        self._snap_positions()

    def push_animated_item(self, new_item: dict, prev_top_item: dict | None):
        if self._is_guide_mode:
            return

        if self._anim_group and self._anim_group.state() == QPropertyAnimation.State.Running:
            self._anim_group.stop()

        self.lbl_empty.hide()
        w, card_h, y1, y2 = self._card_geometry()

        self._item_2 = prev_top_item
        self._item_1 = new_item

        group = QParallelAnimationGroup(self)

        if self._item_2:
            self._style_card(self.card_2, self._item_2, w)
            self.card_2.setGeometry(0, y1, w, card_h)
            self.card_2.show()

            anim_down = QPropertyAnimation(self.card_2, b"pos", self)
            anim_down.setDuration(260)
            anim_down.setStartValue(QPoint(0, y1))
            anim_down.setEndValue(QPoint(0, y2))
            anim_down.setEasingCurve(QEasingCurve.Type.OutCubic)
            group.addAnimation(anim_down)
        else:
            self.card_2.hide()

        self._style_card(self.card_1, self._item_1, w)
        self.card_1.setGeometry(w, y1, w, card_h)
        self.card_1.show()
        self.card_1.raise_()

        anim_slide = QPropertyAnimation(self.card_1, b"pos", self)
        anim_slide.setDuration(280)
        anim_slide.setStartValue(QPoint(w, y1))
        anim_slide.setEndValue(QPoint(0, y1))
        anim_slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(anim_slide)

        self._anim_group = group
        group.start()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 키우기 - Prototype")
        self.resize(1150, 720)

        self.game_state = GameState()
        self.save_manager = SaveManager()
        self.news_dialog = None
        self._was_tutorial_active = True

        self.news_toast_timer = QTimer(self)
        self.news_toast_timer.setSingleShot(True)

        self._init_ui()
        self.news_toast_timer.timeout.connect(lambda: self.lbl_news_toast.hide())
        self._connect_signals()

        # 영구 엔딩 기록 로드 후 세이브 복원
        persistent_endings = self.save_manager.load_unlocked_endings()
        self.game_state.sync_persistent_endings(persistent_endings)
        self._load_initial_save()

        self.passive_timer = QTimer(self)
        self.passive_timer.timeout.connect(self._on_tick)
        self.passive_timer.start(100)

        self.news_timer = QTimer(self)
        self.news_timer.timeout.connect(self._on_random_news_tick)
        self.news_timer.start(25000)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._on_autosave_tick)
        self.autosave_timer.start(30000)

        self._update_ui()
        self._sync_bottom_right_panel(force=True)
        self._update_unread_badge(self.game_state.unread_news_count)

    def _is_tutorial_active(self) -> bool:
        ch1_node = next((u for u in self.game_state.upgrades if u["id"] == "ch1_start"), None)
        if not ch1_node:
            return False
        return not ch1_node.get("purchased", False)

    def _on_random_news_tick(self):
        if not self._is_tutorial_active() and not self.game_state.is_ending_locked:
            self.game_state.trigger_random_news()

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
            self.game_state.reset_state(emit_signal=False, preserve_endings=True)

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

        top_bar = QFrame()
        top_bar.setFixedHeight(50)
        top_bar.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #d0d7de;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(15, 5, 15, 5)

        self.lbl_tokens = QLabel("0 Token")
        self.lbl_tokens.setStyleSheet("color: #0969da; font-size: 20px; font-weight: bold;")

        self.lbl_rates = QLabel("1 Tk/Command\n0 Tk/s")
        self.lbl_rates.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_rates.setStyleSheet("color: #0969da; font-size: 13px; font-weight: bold;")

        top_layout.addWidget(self.lbl_tokens)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_rates)
        left_layout.addWidget(top_bar)

        self.console_widget = VirtualConsoleWidget(self.game_state)
        left_layout.addWidget(self.console_widget, stretch=1)

        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(155)
        bottom_bar.setStyleSheet("background-color: #ffffff; border-top: 2px solid #d0d7de;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

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

        news_box = QFrame()
        news_box.setStyleSheet("border-left: 2px solid #d0d7de;")
        news_layout = QVBoxLayout(news_box)
        news_layout.setContentsMargins(10, 6, 10, 8)
        news_layout.setSpacing(6)

        news_header = QHBoxLayout()
        news_header.setSpacing(6)

        self.lbl_news_title = QLabel("DEV GUIDE")
        self.lbl_news_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0969da; border: none;")

        self.lbl_unread_badge = QLabel("0")
        self.lbl_unread_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_unread_badge.setFixedHeight(20)
        self.lbl_unread_badge.setMinimumWidth(20)
        self.lbl_unread_badge.setStyleSheet("""
            background-color: #cf222e;
            color: #ffffff;
            border-radius: 10px;
            padding: 0px 6px;
            font-size: 11px;
            font-weight: bold;
            border: none;
        """)
        self.lbl_unread_badge.hide()

        self.lbl_news_toast = QLabel("새 뉴스 도착")
        self.lbl_news_toast.setStyleSheet("""
            background-color: #ddf4ff;
            color: #0969da;
            border: 1px solid #54aeff;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.lbl_news_toast.hide()

        self.btn_news_expand = QPushButton("↗")
        self.btn_news_expand.setFixedSize(28, 24)
        self.btn_news_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_news_expand.setToolTip("전체 뉴스 / AI 활동 / 도감 / 설정 열기")
        self.btn_news_expand.clicked.connect(lambda: self._show_news_popup(auto_triggered=False))

        news_header.addWidget(self.lbl_news_title)
        news_header.addWidget(self.lbl_unread_badge)
        news_header.addWidget(self.lbl_news_toast)
        news_header.addStretch()
        news_header.addWidget(self.btn_news_expand)
        news_layout.addLayout(news_header)

        self.mini_news_ticker = MiniNewsTickerWidget()
        news_layout.addWidget(self.mini_news_ticker, stretch=1)
        bottom_layout.addWidget(news_box, stretch=1)

        left_layout.addWidget(bottom_bar)
        root_layout.addWidget(left_panel, stretch=72)

        # ================= [우측 업그레이드 트리 영역 (28%)] =================
        self.tree_widget = UpgradeTreeWidget(self.game_state)
        root_layout.addWidget(self.tree_widget, stretch=28)

    def _connect_signals(self):
        self.game_state.state_changed.connect(self._update_ui)
        self.game_state.news_added.connect(self._on_news_added)
        self.game_state.unread_news_changed.connect(self._update_unread_badge)
        self.game_state.story_event_triggered.connect(self._on_story_event_triggered)
        self.game_state.singularity_reached.connect(self._on_singularity_reached)

        self.console_widget.ending_completed.connect(self._on_ending_completed)
        self.console_widget.request_load_branch.connect(self._on_console_load_branch)
        self.console_widget.request_reset_game.connect(self._on_console_reset_game)

    def _on_story_event_triggered(self, story_data: dict):
        dlg = StoryEventDialog(story_data, self)
        dlg.exec()

    def _on_singularity_reached(self):
        """Chap 8 특이점 도달 시 콘솔을 AI 1대1 독대 모드로 전환"""
        self.console_widget.start_singularity_dialogue()

    def _on_ending_completed(self, ending_id: str):
        """엔딩 도달 시 영구 엔딩 기록 저장"""
        self.game_state.record_ending(ending_id)
        self.save_manager.save_unlocked_endings(list(self.game_state.unlocked_endings))
        self.save_manager.save_auto(self.game_state.to_dict())

    def _on_console_load_branch(self, slot: int):
        ok, result = self.save_manager.load_branch(slot)
        if ok and isinstance(result, dict):
            self.game_state.from_dict(result)
            if not self.game_state.is_ending_locked:
                self.console_widget.start_boot_sequence()
            self._sync_bottom_right_panel(force=True)
            QMessageBox.information(self, "분기 복원 완료", f"분기 슬롯 {slot} 시점으로 복원되었습니다.")
        else:
            QMessageBox.warning(self, "불러오기 실패", str(result))

    def _on_console_reset_game(self):
        self.save_manager.clear_all_saves()
        self.game_state.reset_state(emit_signal=True, preserve_endings=True)
        self.console_widget.start_boot_sequence()
        self._sync_bottom_right_panel(force=True)

    def _on_tick(self):
        self.game_state.add_passive_tokens(0.1)

    def _sync_bottom_right_panel(self, force: bool = False):
        is_tut = self._is_tutorial_active()
        upg_map = {u["id"]: u["purchased"] for u in self.game_state.upgrades}

        if is_tut:
            self.lbl_news_title.setText("DEV GUIDE")
            self.lbl_news_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0969da; border: none;")
            self.lbl_unread_badge.hide()
            self.lbl_news_toast.hide()

            if not upg_map.get("tut_buffer", False):
                if self.game_state.tokens < 1:
                    self.mini_news_ticker.set_guide_items(
                        "[1/4] 콘솔에 명령어를 입력해 첫 1 Token을 확보하세요.",
                        "초기 입력 지연(200ms)으로 빠른 타자가 제한될 수 있습니다."
                    )
                else:
                    self.mini_news_ticker.set_guide_items(
                        "[2/4] 우측 트리의 [버퍼 최적화 (1 Tk)]를 클릭하세요.",
                        "입력 지연을 완화하고 다음 개발 경로를 개방합니다."
                    )
            elif not (upg_map.get("tut_act_key", False) and upg_map.get("tut_pas_pc", False)):
                self.mini_news_ticker.set_guide_items(
                    "[3/4] 좌측(입력 매핑)과 우측(PC 조립) 노드를 모두 완료하세요.",
                    "붉은색(액티브): 입력 지연 단축·효율 / 녹색(패시브): 기본·자동 토큰 생산량 증가"
                )
            else:
                self.mini_news_ticker.set_guide_items(
                    "[4/4] 10 Token을 모아 [AI 개발 착수]를 클릭하세요!",
                    "튜토리얼을 마치고 본격적인 AI 개발 스토리가 시작됩니다."
                )
            self._was_tutorial_active = True
        else:
            if self._was_tutorial_active or force:
                self.lbl_news_title.setText("NEWS")
                self.lbl_news_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1f2328; border: none;")
                self.mini_news_ticker.set_initial_items(self.game_state.news_history)
                self._update_unread_badge(self.game_state.unread_news_count)
                self._was_tutorial_active = False

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

        if (
            gs.tokens == 0
            and not gs.news_history
            and not any(u["purchased"] for u in gs.upgrades)
            and not gs.is_ending_locked
            and self.console_widget._boot_step >= len(self.console_widget.BOOT_SEQUENCE)
        ):
            self.console_widget.start_boot_sequence()

        self._sync_bottom_right_panel(force=False)
        self.tree_widget.refresh_tree()

    def _update_unread_badge(self, count: int):
        if self._is_tutorial_active() or count <= 0:
            self.lbl_unread_badge.hide()
        else:
            text = "99+" if count > 99 else str(count)
            self.lbl_unread_badge.setText(text)
            self.lbl_unread_badge.show()

    def _on_news_added(self, news_item: dict):
        if self._is_tutorial_active():
            return

        history = self.game_state.news_history
        prev_top = history[1] if len(history) >= 2 else None
        self.mini_news_ticker.push_animated_item(news_item, prev_top)

        if news_item.get("is_milestone", False):
            self._show_news_popup(auto_triggered=True)
        else:
            is_danger = (news_item.get("category") == "danger")
            if is_danger:
                self.lbl_news_toast.setText("긴급 속보 도착")
                self.lbl_news_toast.setStyleSheet("""
                    background-color: #ffebe9;
                    color: #cf222e;
                    border: 1px solid #ff8182;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-weight: bold;
                """)
            else:
                self.lbl_news_toast.setText("새 뉴스 도착")
                self.lbl_news_toast.setStyleSheet("""
                    background-color: #ddf4ff;
                    color: #0969da;
                    border: 1px solid #54aeff;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-weight: bold;
                """)
            self.lbl_news_toast.show()
            self.news_toast_timer.start(3000)

    def _show_news_popup(self, auto_triggered: bool = False):
        if self.news_dialog is None:
            self.news_dialog = NewsDialog(self.game_state, self.save_manager, self)

        self.news_dialog.open_recent_news(
            auto_triggered=auto_triggered,
            animate_top_card=auto_triggered
        )
        self.news_dialog.show()
        self.news_dialog.raise_()
        self.news_dialog.activateWindow()