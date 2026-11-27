from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QMessageBox, QFileDialog, QDialog, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QParallelAnimationGroup, QPoint, QEasingCurve
from PyQt6.QtGui import QFontMetrics
from core.game_state import GameState
from core.save_manager import SaveManager
from core.sound_manager import SoundManager
from core.number_format import format_number
from ui.console_widget import VirtualConsoleWidget
from ui.tree_widget import UpgradeTreeWidget
from ui.news_dialog import NewsDialog
from ui.window_style import apply_dark_titlebar


class StoryEventDialog(QDialog):
    """스토리 노드 해금 시 등장하는 챕터 스토리 연출 팝업 (1~18번 이벤트)"""

    def __init__(self, story_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"STORY EVENT #{story_data.get('number', '')} - {story_data.get('chapter', '')}")
        apply_dark_titlebar(self, "#0d1117")
        self.setFixedSize(520, 310)
        self.setStyleSheet("QDialog { background-color: #0d1117; border: 2px solid #bc8cff; }")

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
        lbl_title.setStyleSheet("color: #f0f6fc; font-size: 16px; font-weight: bold;")
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
            QPushButton:hover { background-color: #9a67ea; }
        """)
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)


class AiNamingDialog(QDialog):
    """Chap 3 공개 베타 진입 시 AI 공식 명칭을 지정하는 다크 워크스테이션 전용 팝업"""

    PRESETS = ["Aether", "Nexus", "Lumina", "Chronos", "Vortex"]

    def __init__(self, current_name: str = "Proto-AI", parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 공식 명칭 지정")
        apply_dark_titlebar(self, "#0d1117")
        self.setFixedSize(440, 245)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                border: 1.5px solid #388bfd;
                font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        lbl_badge = QLabel("◆ MODEL RELEASE · v0.9-beta")
        lbl_badge.setStyleSheet(
            "color: #58a6ff; font-family: 'Consolas', 'D2Coding', monospace; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(lbl_badge)

        lbl_desc = QLabel(
            "공개 베타 배포를 앞두고 AI의 공식 명칭을 지정하세요.\n"
            "(미입력 시 기본 명칭 'Proto-AI'가 유지됩니다.)"
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #c9d1d9; font-size: 12.5px; line-height: 1.4;")
        layout.addWidget(lbl_desc)

        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #090c10;
                border: 1.5px solid #30363d;
                border-radius: 6px;
            }
            QFrame:focus-within {
                border-color: #58a6ff;
            }
        """)
        in_row = QHBoxLayout(input_frame)
        in_row.setContentsMargins(10, 6, 10, 6)
        in_row.setSpacing(6)

        lbl_prompt = QLabel(">")
        lbl_prompt.setStyleSheet(
            "color: #3fb950; font-family: 'Consolas', 'D2Coding', monospace; font-size: 14px; font-weight: bold; border: none;"
        )

        self.input_edit = QLineEdit(current_name)
        self.input_edit.setMaxLength(20)
        self.input_edit.selectAll()
        self.input_edit.setPlaceholderText("모델명 입력 (최대 20자)")
        self.input_edit.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #f0f6fc;
                border: none;
                font-family: 'Pretendard', 'Consolas', sans-serif;
                font-size: 14px;
                font-weight: bold;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
            }
        """)
        self.input_edit.returnPressed.connect(self.accept)

        in_row.addWidget(lbl_prompt)
        in_row.addWidget(self.input_edit, stretch=1)
        layout.addWidget(input_frame)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        lbl_pre = QLabel("추천:")
        lbl_pre.setStyleSheet("color: #8b949e; font-size: 11px;")
        preset_row.addWidget(lbl_pre)

        for name in self.PRESETS:
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #161b22;
                    color: #8b949e;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #21262d;
                    color: #79c0ff;
                    border-color: #388bfd;
                }
            """)
            btn.clicked.connect(lambda checked, n=name: self.input_edit.setText(n))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_cancel = QPushButton("기본값 유지")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 5px;
                padding: 0px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("명칭 확정")
        btn_ok.setFixedHeight(32)
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                color: #ffffff;
                border: 1px solid #388bfd;
                border-radius: 5px;
                padding: 0px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388bfd; }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_name(self) -> str:
        return self.input_edit.text().strip()


class MiniNewsTickerWidget(QWidget):
    """튜토리얼 중에는 DEV GUIDE 카드를, 본편 진입 후에는 슬라이드 인 NEWS 카드를 표시하는 다크 미니 패널"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(86)

        self.lbl_empty = QLabel("수신된 뉴스가 없습니다.", self)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("""
            background-color: #0d1117;
            border: 1px dashed #30363d;
            border-radius: 5px;
            color: #8b949e;
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
            "info":      ("#272115", "#d29922", "#f2cc60"),
            "positive":  ("#12261e", "#2ea043", "#7ee787"),
            "danger":    ("#2c1619", "#f85149", "#ffa198"),
            "story":     ("#241833", "#a371f7", "#e2c5ff"),
            "guide":     ("#13233a", "#388bfd", "#79c0ff"),
            "guide_sub": ("#21262d", "#30363d", "#c9d1d9"),
        }
        bg, border, fg = color_schemes.get(category, ("#272115", "#d29922", "#f2cc60"))
        is_guide = category in ("guide", "guide_sub")
        font_size = "11px" if is_guide else "12px"

        label.setStyleSheet(f"""
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 5px;
            padding: 3px 10px;
            font-size: {font_size};
            font-weight: bold;
            color: {fg};
        """)

        title_text = news_item.get("title", "")
        eff_text = news_item.get("effect_text", "")
        if eff_text:
            label.setToolTip(f"{title_text}\n{eff_text}")
        else:
            label.setToolTip(title_text)

        if is_guide:
            label.setWordWrap(True)
            label.setText(title_text)
        else:
            label.setWordWrap(False)
            metrics = QFontMetrics(label.font())
            elided = metrics.elidedText(title_text, Qt.TextElideMode.ElideRight, max(60, width - 24))
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
        self.setWindowTitle("AI 키우기")
        apply_dark_titlebar(self, "#161b22")
        self.resize(1180, 740)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QToolTip {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)

        self.game_state = GameState()
        self.save_manager = SaveManager()
        self.sound_manager = SoundManager(settings_dir=self.save_manager.save_dir, parent=self)
        self.news_dialog = None
        self._was_tutorial_active = True
        self._tree_refresh_queued = False

        # UI 변경 감지용 캐시 (매 100ms CSS/텍스트 재파싱 차단)
        self._last_ai_badge = ""
        self._last_tokens_str = ""
        self._last_cmd_str = ""
        self._last_sec_str = ""
        self._last_bench_str = ""
        self._last_specs: dict[str, str] = {}
        self._last_buff_sig: tuple | None = None
        self._last_tut_step_sig: tuple | None = None

        self.news_toast_timer = QTimer(self)
        self.news_toast_timer.setSingleShot(True)

        self.passive_timer = QTimer(self)
        self.passive_timer.timeout.connect(self._on_tick)

        self.news_timer = QTimer(self)
        self.news_timer.timeout.connect(self._on_random_news_tick)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._on_autosave_tick)

        self._init_ui()
        self.console_widget.set_sound_manager(self.sound_manager)
        self.tree_widget.set_sound_manager(self.sound_manager)

        self.news_toast_timer.timeout.connect(lambda: self.lbl_news_toast.hide())
        self._connect_signals()

        persistent_endings = self.save_manager.load_unlocked_endings()
        self.game_state.sync_persistent_endings(persistent_endings)
        self._load_initial_save()

        self.passive_timer.start(100)
        if not self.game_state.is_ending_locked:
            self.news_timer.start(45000)
        self.autosave_timer.start(30000)

        self._update_ui()
        self._sync_bottom_right_panel(force=True)
        self._update_unread_badge(self.game_state.unread_news_count)

    def keyPressEvent(self, event):
        if (
            getattr(self.game_state, "is_supervisor_mode", False)
            and not self.console_widget.is_booting
            and not self.console_widget.is_dialogue_mode
        ):
            if event.key() in (
                Qt.Key.Key_Q,
                Qt.Key.Key_W,
                Qt.Key.Key_E,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            ):
                if event.isAutoRepeat():
                    event.accept()
                    return
                self.console_widget.keyPressEvent(event)
                return
        super().keyPressEvent(event)

    def _is_tutorial_active(self) -> bool:
        ch1_node = next((u for u in self.game_state.upgrades if u["id"] == "ch1_start"), None)
        if not ch1_node:
            return False
        return not ch1_node.get("purchased", False)

    def _on_random_news_tick(self):
        if (
            not self._is_tutorial_active()
            and not self.game_state.is_ending_locked
            and self.game_state.get_current_chapter() < 8
        ):
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
        self.sound_manager.shutdown()
        event.accept()

    def _init_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: #0d1117;")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ================= [좌측 메인 영역 (70%)] =================
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: #0d1117;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setFixedHeight(58)
        top_bar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 6, 16, 6)
        top_layout.setSpacing(14)

        ai_badge_frame = QFrame()
        ai_badge_frame.setStyleSheet("""
            QFrame {
                background-color: #21262d;
                border: 1px solid #388bfd;
                border-radius: 14px;
            }
        """)
        badge_layout = QHBoxLayout(ai_badge_frame)
        badge_layout.setContentsMargins(10, 4, 12, 4)
        badge_layout.setSpacing(6)

        pulse_dot = QLabel()
        pulse_dot.setFixedSize(7, 7)
        pulse_dot.setStyleSheet("background-color: #3fb950; border-radius: 3px; border: none;")

        self.lbl_ai_badge = QLabel("Proto-AI · v0.1")
        self.lbl_ai_badge.setStyleSheet("""
            background-color: transparent;
            color: #79c0ff;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 12px;
            font-weight: bold;
            border: none;
        """)
        badge_layout.addWidget(pulse_dot)
        badge_layout.addWidget(self.lbl_ai_badge)

        self.lbl_tokens = QLabel("0 Token")
        self.lbl_tokens.setStyleSheet("""
            background-color: transparent;
            color: #58a6ff;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 21px;
            font-weight: bold;
            border: none;
        """)

        rates_box = QWidget()
        rates_box.setStyleSheet("background-color: transparent; border: none;")
        rates_vbox = QVBoxLayout(rates_box)
        rates_vbox.setContentsMargins(0, 0, 0, 0)
        rates_vbox.setSpacing(2)

        cmd_row = QHBoxLayout()
        cmd_row.setContentsMargins(0, 0, 0, 0)
        cmd_row.setSpacing(6)
        cmd_row.addStretch()
        self.lbl_cmd_buff_icon = QLabel("")
        self.lbl_cmd_buff_icon.hide()
        self.lbl_cmd_rate = QLabel("1 Tk/Command")
        self.lbl_cmd_rate.setStyleSheet("""
            background-color: transparent;
            color: #58a6ff;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 13px;
            font-weight: bold;
            border: none;
        """)
        cmd_row.addWidget(self.lbl_cmd_buff_icon)
        cmd_row.addWidget(self.lbl_cmd_rate)

        sec_row = QHBoxLayout()
        sec_row.setContentsMargins(0, 0, 0, 0)
        sec_row.setSpacing(6)
        sec_row.addStretch()
        self.lbl_sec_buff_icon = QLabel("")
        self.lbl_sec_buff_icon.hide()
        self.lbl_sec_rate = QLabel("0 Tk/s")
        self.lbl_sec_rate.setStyleSheet("""
            background-color: transparent;
            color: #58a6ff;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 13px;
            font-weight: bold;
            border: none;
        """)
        sec_row.addWidget(self.lbl_sec_buff_icon)
        sec_row.addWidget(self.lbl_sec_rate)

        rates_vbox.addLayout(cmd_row)
        rates_vbox.addLayout(sec_row)

        top_layout.addWidget(ai_badge_frame)
        top_layout.addWidget(self.lbl_tokens)
        top_layout.addStretch()
        top_layout.addWidget(rates_box)
        left_layout.addWidget(top_bar)

        self.console_widget = VirtualConsoleWidget(self.game_state)
        left_layout.addWidget(self.console_widget, stretch=1)

        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(162)
        bottom_bar.setStyleSheet("background-color: #161b22; border-top: 1px solid #30363d;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        specs_box = QWidget()
        specs_box.setStyleSheet("background-color: #161b22; border: none;")
        specs_layout = QVBoxLayout(specs_box)
        specs_layout.setContentsMargins(14, 10, 14, 10)
        specs_layout.setSpacing(6)

        lbl_specs_header = QLabel("SYSTEM SPECS")
        lbl_specs_header.setStyleSheet("""
            background-color: transparent;
            color: #8b949e;
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.5px;
            border: none;
        """)
        specs_layout.addWidget(lbl_specs_header)

        specs_grid = QGridLayout()
        specs_grid.setContentsMargins(0, 0, 0, 0)
        specs_grid.setHorizontalSpacing(10)
        specs_grid.setVerticalSpacing(3)

        self.spec_value_labels: dict[str, QLabel] = {}
        key_style = (
            "background-color: transparent; color: #8b949e; "
            "font-family: 'Pretendard', 'Malgun Gothic', sans-serif; font-size: 12px; font-weight: bold; border: none;"
        )
        val_style = (
            "background-color: transparent; color: #e6edf3; "
            "font-family: 'Pretendard', 'Malgun Gothic', sans-serif; font-size: 12px; border: none;"
        )
        for row_idx, key in enumerate(("CPU", "GPU", "RAM", "STORAGE")):
            lbl_k = QLabel(key)
            lbl_k.setFixedWidth(64)
            lbl_k.setStyleSheet(key_style)
            lbl_v = QLabel("-")
            lbl_v.setStyleSheet(val_style)
            specs_grid.addWidget(lbl_k, row_idx, 0)
            specs_grid.addWidget(lbl_v, row_idx, 1)
            self.spec_value_labels[key] = lbl_v

        specs_layout.addLayout(specs_grid)
        specs_layout.addStretch()

        bench_frame = QFrame()
        bench_frame.setStyleSheet("""
            QFrame {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
            }
        """)
        bench_row = QHBoxLayout(bench_frame)
        bench_row.setContentsMargins(10, 4, 10, 4)

        lbl_bench_k = QLabel("BENCH_SCORE")
        lbl_bench_k.setStyleSheet("""
            background-color: transparent; color: #58a6ff;
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif; font-size: 12px; font-weight: bold; border: none;
        """)
        self.lbl_bench = QLabel("40")
        self.lbl_bench.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_bench.setStyleSheet("""
            background-color: transparent; color: #58a6ff;
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif; font-size: 12px; font-weight: bold; border: none;
        """)
        bench_row.addWidget(lbl_bench_k)
        bench_row.addStretch()
        bench_row.addWidget(self.lbl_bench)
        specs_layout.addWidget(bench_frame)

        bottom_layout.addWidget(specs_box, stretch=48)

        news_box = QFrame()
        news_box.setStyleSheet("QFrame { background-color: #161b22; border-left: 1px solid #30363d; }")
        news_layout = QVBoxLayout(news_box)
        news_layout.setContentsMargins(12, 10, 12, 10)
        news_layout.setSpacing(6)

        news_header = QHBoxLayout()
        news_header.setSpacing(6)

        self.lbl_news_title = QLabel("DEV GUIDE")
        self.lbl_news_title.setStyleSheet(
            "background-color: transparent; font-size: 13px; font-weight: bold; color: #58a6ff; border: none;"
        )

        self.lbl_unread_badge = QLabel("0")
        self.lbl_unread_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_unread_badge.setFixedHeight(18)
        self.lbl_unread_badge.setMinimumWidth(18)
        self.lbl_unread_badge.setStyleSheet("""
            background-color: #f85149;
            color: #ffffff;
            border-radius: 9px;
            padding: 0px 5px;
            font-size: 10px;
            font-weight: bold;
            border: none;
        """)
        self.lbl_unread_badge.hide()

        self.lbl_news_toast = QLabel("새 뉴스 도착")
        self.lbl_news_toast.setStyleSheet("""
            background-color: #13233a;
            color: #79c0ff;
            border: 1px solid #388bfd;
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.lbl_news_toast.hide()

        self.btn_news_expand = QPushButton("↗ 전체 / 도감 / 설정")
        self.btn_news_expand.setFixedHeight(24)
        self.btn_news_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_news_expand.setToolTip("전체 뉴스 / AI 활동 / 도감 / 설정 열기")
        self.btn_news_expand.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 0px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #58a6ff;
                color: #58a6ff;
            }
        """)
        self.btn_news_expand.clicked.connect(lambda: self._show_news_popup(auto_triggered=False))

        news_header.addWidget(self.lbl_news_title)
        news_header.addWidget(self.lbl_unread_badge)
        news_header.addWidget(self.lbl_news_toast)
        news_header.addStretch()
        news_header.addWidget(self.btn_news_expand)
        news_layout.addLayout(news_header)

        self.mini_news_ticker = MiniNewsTickerWidget()
        news_layout.addWidget(self.mini_news_ticker, stretch=1)
        bottom_layout.addWidget(news_box, stretch=52)

        left_layout.addWidget(bottom_bar)
        root_layout.addWidget(left_panel, stretch=70)

        # ================= [우측 업그레이드 트리 영역 (30%)] =================
        self.tree_widget = UpgradeTreeWidget(self.game_state)
        root_layout.addWidget(self.tree_widget, stretch=30)

    def _connect_signals(self):
        self.game_state.state_changed.connect(self._update_ui)
        self.game_state.news_added.connect(self._on_news_added)
        self.game_state.unread_news_changed.connect(self._update_unread_badge)
        self.game_state.story_event_triggered.connect(self._on_story_event_triggered)
        self.game_state.singularity_reached.connect(self._on_singularity_reached)
        self.game_state.ai_naming_requested.connect(self._on_ai_naming_requested)

        self.console_widget.ending_completed.connect(self._on_ending_completed)
        self.console_widget.request_load_branch.connect(self._on_console_load_branch)
        self.console_widget.request_reset_game.connect(self._on_console_reset_game)

    def _on_ai_naming_requested(self):
        dlg = AiNamingDialog(self.game_state.ai_name, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.get_name():
            self.game_state.set_ai_name(dlg.get_name())
        else:
            self.game_state.set_ai_name(self.game_state.ai_name)

    def _on_story_event_triggered(self, story_data: dict):
        self.sound_manager.play("story_unlock")
        dlg = StoryEventDialog(story_data, self)
        dlg.exec()

    def _on_singularity_reached(self):
        self.sound_manager.play("glitch")
        if hasattr(self, "news_timer"):
            self.news_timer.stop()
        self.console_widget.start_singularity_dialogue()

    def _on_ending_completed(self, ending_id: str):
        self.game_state.record_ending(ending_id)
        self.save_manager.save_unlocked_endings(list(self.game_state.unlocked_endings))
        self.save_manager.save_auto(self.game_state.to_dict())

    def _on_console_load_branch(self, slot: int):
        ok, result = self.save_manager.load_branch(slot)
        if ok and isinstance(result, dict):
            self.game_state.from_dict(result)
            if not self.game_state.is_ending_locked:
                self.console_widget.start_boot_sequence()
                if not self.news_timer.isActive():
                    self.news_timer.start(45000)
            self._sync_bottom_right_panel(force=True)
            QMessageBox.information(self, "분기 복원 완료", f"분기 슬롯 {slot} 시점으로 복원되었습니다.")
        else:
            QMessageBox.warning(self, "불러오기 실패", str(result))

    def _on_console_reset_game(self):
        self.save_manager.clear_all_saves()
        self.game_state.reset_state(emit_signal=True, preserve_endings=True)
        self.console_widget.start_boot_sequence()
        if not self.news_timer.isActive():
            self.news_timer.start(45000)
        self._sync_bottom_right_panel(force=True)

    def _on_tick(self):
        self.game_state.add_passive_tokens(0.1)

    def _flush_tree_refresh(self):
        self._tree_refresh_queued = False
        self.tree_widget.refresh_tree()

    def _sync_bottom_right_panel(self, force: bool = False):
        is_tut = self._is_tutorial_active()

        if is_tut:
            upg_map = {u["id"]: u["purchased"] for u in self.game_state.upgrades[:4]}
            tut_sig = (
                bool(upg_map.get("tut_buffer", False)),
                bool(upg_map.get("tut_act_key", False)),
                bool(upg_map.get("tut_pas_pc", False)),
                self.game_state.tokens >= 1,
            )
            if not force and self._was_tutorial_active and tut_sig == self._last_tut_step_sig:
                return
            self._last_tut_step_sig = tut_sig

            self.lbl_news_title.setText("DEV GUIDE")
            self.lbl_news_title.setStyleSheet(
                "background-color: transparent; font-size: 13px; font-weight: bold; color: #58a6ff; border: none;"
            )
            self.lbl_unread_badge.hide()
            self.lbl_news_toast.hide()

            if not tut_sig[0]:
                if not tut_sig[3]:
                    self.mini_news_ticker.set_guide_items(
                        "[1/4] 콘솔에 명령어를 입력해 첫 1 Token을 확보하세요.",
                        "초기 입력 지연(200ms)으로 빠른 타자가 제한될 수 있습니다."
                    )
                else:
                    self.mini_news_ticker.set_guide_items(
                        "[2/4] 우측 트리의 [버퍼 최적화 (1 Tk)]를 클릭하세요.",
                        "입력 지연을 완화하고 다음 개발 경로를 개방합니다."
                    )
            elif not (tut_sig[1] and tut_sig[2]):
                self.mini_news_ticker.set_guide_items(
                    "[3/4] 좌측(입력 매핑)과 우측(PC 조립) 노드를 모두 완료하세요.",
                    "붉은색(액티브): 입력 지연 단축·효율 / 녹색(패시브): 기본·자동 토큰 생산량 증가"
                )
            else:
                self.mini_news_ticker.set_guide_items(
                    "[4/4] 6 Token을 모아 [AI 개발 착수]를 클릭하세요!",
                    "튜토리얼을 마치고 본격적인 AI 개발 스토리가 시작됩니다."
                )
            self._was_tutorial_active = True
        else:
            if self._was_tutorial_active or force:
                self._last_tut_step_sig = None
                self.lbl_news_title.setText("NEWS")
                self.lbl_news_title.setStyleSheet(
                    "background-color: transparent; font-size: 13px; font-weight: bold; color: #e6edf3; border: none;"
                )
                self.mini_news_ticker.set_initial_items(self.game_state.news_history)
                self._update_unread_badge(self.game_state.unread_news_count)
                self._was_tutorial_active = False

    def _update_rate_badges(self):
        buff = self.game_state.active_news_buff
        if not buff:
            buff_sig = ("none",)
        else:
            buff_sig = (
                buff.get("target"),
                buff.get("mode", "flat"),
                float(buff.get("value", 0.0)),
                bool(buff.get("is_positive", True)),
                max(1, int(round(buff.get("remaining_sec", 0)))),
                buff.get("summary", ""),
            )

        # 버프 상태/초 단위가 그대로면 CSS 재파싱 생략
        if self._last_buff_sig == buff_sig:
            return
        self._last_buff_sig = buff_sig

        default_rate_style = """
            background-color: transparent; color: #58a6ff;
            font-family: 'Consolas', 'D2Coding', monospace; font-size: 13px; font-weight: bold; border: none;
        """

        if not buff:
            self.lbl_cmd_buff_icon.hide()
            self.lbl_sec_buff_icon.hide()
            self.lbl_cmd_rate.setStyleSheet(default_rate_style)
            self.lbl_sec_rate.setStyleSheet(default_rate_style)
            self.lbl_cmd_rate.setToolTip("")
            self.lbl_sec_rate.setToolTip("")
            return

        target, mode, val, is_pos, rem, summary = buff_sig
        icon_char = "▲" if is_pos else "▼"
        sign = "+" if val >= 0 else "-"
        abs_val = abs(val)
        val_str = f"{sign}{int(abs_val)}%" if mode == "percent" else f"{sign}{format_number(abs_val)}"

        if is_pos:
            tag_bg, tag_bd, tag_fg = "#12261e", "#2ea043", "#7ee787"
        else:
            tag_bg, tag_bd, tag_fg = "#2c1619", "#f85149", "#ffa198"

        tag_style = f"""
            background-color: {tag_bg};
            color: {tag_fg};
            border: 1px solid {tag_bd};
            border-radius: 4px;
            padding: 1px 6px;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px;
            font-weight: bold;
        """
        rate_style = f"""
            background-color: transparent; color: {tag_fg};
            font-family: 'Consolas', 'D2Coding', monospace; font-size: 13px; font-weight: bold; border: none;
        """

        badge_text = f"{icon_char} {val_str} ({rem}s)"

        if target == "command_rate":
            self.lbl_sec_buff_icon.hide()
            self.lbl_sec_rate.setStyleSheet(default_rate_style)
            self.lbl_sec_rate.setToolTip("")

            self.lbl_cmd_buff_icon.setText(badge_text)
            self.lbl_cmd_buff_icon.setStyleSheet(tag_style)
            self.lbl_cmd_buff_icon.setToolTip(summary)
            self.lbl_cmd_buff_icon.show()
            self.lbl_cmd_rate.setStyleSheet(rate_style)
            self.lbl_cmd_rate.setToolTip(summary)
        elif target == "passive_rate":
            self.lbl_cmd_buff_icon.hide()
            self.lbl_cmd_rate.setStyleSheet(default_rate_style)
            self.lbl_cmd_rate.setToolTip("")

            self.lbl_sec_buff_icon.setText(badge_text)
            self.lbl_sec_buff_icon.setStyleSheet(tag_style)
            self.lbl_sec_buff_icon.setToolTip(summary)
            self.lbl_sec_buff_icon.show()
            self.lbl_sec_rate.setStyleSheet(rate_style)
            self.lbl_sec_rate.setToolTip(summary)

    def _update_ui(self):
        gs = self.game_state

        badge_txt = f"{gs.ai_name} · {gs.get_ai_version()}"
        if badge_txt != self._last_ai_badge:
            self._last_ai_badge = badge_txt
            self.lbl_ai_badge.setText(badge_txt)

        tok_txt = f"{format_number(gs.tokens)} Token"
        if tok_txt != self._last_tokens_str:
            self._last_tokens_str = tok_txt
            self.lbl_tokens.setText(tok_txt)

        cmd_txt = f"{format_number(gs.effective_tokens_per_command)} Tk/Command"
        if cmd_txt != self._last_cmd_str:
            self._last_cmd_str = cmd_txt
            self.lbl_cmd_rate.setText(cmd_txt)

        sec_txt = f"{format_number(gs.effective_tokens_per_sec)} Tk/s"
        if sec_txt != self._last_sec_str:
            self._last_sec_str = sec_txt
            self.lbl_sec_rate.setText(sec_txt)

        self._update_rate_badges()

        s = gs.specs
        for key in ("CPU", "GPU", "RAM", "STORAGE"):
            val = str(s.get(key, "-"))
            if self._last_specs.get(key) != val:
                self._last_specs[key] = val
                self.spec_value_labels[key].setText(val)

        bench_txt = f"{format_number(s['BENCH_SCORE'])}"
        if bench_txt != self._last_bench_str:
            self._last_bench_str = bench_txt
            self.lbl_bench.setText(bench_txt)

        self._sync_bottom_right_panel(force=False)
        if not self._tree_refresh_queued:
            self._tree_refresh_queued = True
            QTimer.singleShot(100, self._flush_tree_refresh)

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
            category = news_item.get("category", "info")
            if category == "danger":
                self.sound_manager.play("news_bad")
                self.lbl_news_toast.setText("악재 속보 도착")
                self.lbl_news_toast.setStyleSheet("""
                    background-color: #2c1619;
                    color: #ffa198;
                    border: 1px solid #f85149;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-weight: bold;
                """)
            elif category == "positive":
                self.sound_manager.play("news_good")
                self.lbl_news_toast.setText("호재 뉴스 도착")
                self.lbl_news_toast.setStyleSheet("""
                    background-color: #12261e;
                    color: #7ee787;
                    border: 1px solid #2ea043;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-weight: bold;
                """)
            else:
                self.lbl_news_toast.setText("새 뉴스 도착")
                self.lbl_news_toast.setStyleSheet("""
                    background-color: #13233a;
                    color: #79c0ff;
                    border: 1px solid #388bfd;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-weight: bold;
                """)
            self.lbl_news_toast.show()
            self.news_toast_timer.start(3000)

    def _show_news_popup(self, auto_triggered: bool = False):
        if self.news_dialog is None:
            self.news_dialog = NewsDialog(self.game_state, self.save_manager, self, sound_manager=self.sound_manager)

        self.news_dialog.open_recent_news(
            auto_triggered=auto_triggered,
            animate_top_card=auto_triggered
        )
        self.news_dialog.show()
        self.news_dialog.raise_()
        self.news_dialog.activateWindow()