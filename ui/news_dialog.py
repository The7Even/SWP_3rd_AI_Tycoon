import os
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QFrame, QStackedWidget,
    QTextEdit, QMessageBox, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer


class NewsCardWidget(QFrame):
    """파스텔 톤 뉴스 카드 (제목 + 날짜 + 가로선 + 요약 본문 + 하단 효과 요약)"""

    def __init__(self, news_item: dict):
        super().__init__()
        category = news_item.get("category", "info")
        color_schemes = {
            "info": ("#fae17d", "#9a6700"),
            "positive": ("#dafbe1", "#1a7f37"),
            "danger": ("#f28b96", "#a40e26"),
            "story": ("#d99be6", "#6639ba")
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

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {border_color}; max-height: 1px; border: none;")
        layout.addWidget(line)

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

        effect_text = news_item.get("effect_text", "").strip()
        if effect_text:
            eff_color = "#116329" if category == "positive" else ("#82071e" if category == "danger" else "#24292f")
            lbl_effect = QLabel(effect_text)
            lbl_effect.setStyleSheet(f"""
                background-color: rgba(255, 255, 255, 0.45);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 12px;
                font-weight: bold;
                color: {eff_color};
                border: none;
            """)
            layout.addWidget(lbl_effect)


class NewsDialog(QDialog):
    """확장 팝업창 (최근 뉴스 / AI 활동 / 도감 & 엔딩 기록 / 설정 4단 탭 지원)"""

    def __init__(self, game_state, save_manager, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.save_manager = save_manager
        self.setWindowTitle("AI 키우기 - 뉴스 / 도감 / 설정")
        self.resize(780, 600)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")

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

        self.stack = QStackedWidget()

        # [탭 0] 최근 뉴스
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

        # [탭 1] AI 활동
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

        # [탭 2] 도감 & 엔딩 기록
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

        # [탭 3] 설정
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setStyleSheet("border: none; background-color: #ffffff;")
        self.settings_container = self._build_settings_tab()
        self.settings_scroll.setWidget(self.settings_container)
        self.stack.addWidget(self.settings_scroll)

        main_layout.addWidget(self.stack, stretch=1)

        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(46)
        bottom_bar.setStyleSheet("background-color: #ffffff; border-top: 2px solid #1f2328;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self.tab_buttons = []
        tab_names = ["최근 뉴스", "AI 활동", "도감", "설정"]
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

    def _build_settings_tab(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 20)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        card_style = """
            QFrame {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 12px;
            }
        """
        btn_primary_style = """
            QPushButton {
                background-color: #0969da; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #0860ca; }
        """
        btn_normal_style = """
            QPushButton {
                background-color: #ffffff; color: #1f2328;
                border: 1px solid #d0d7de; border-radius: 4px;
                padding: 6px 12px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """

        # 1. 자동 저장 및 백업 관리
        sec_auto = QFrame()
        sec_auto.setStyleSheet(card_style)
        auto_layout = QVBoxLayout(sec_auto)
        auto_layout.setSpacing(8)

        lbl_auto_title = QLabel("1. 데이터 영속성 및 자동 백업 관리")
        lbl_auto_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; border: none;")
        self.lbl_save_status = QLabel("상태: 30초마다 자동 저장 및 직전 백업본(.bak) 생성 활성")
        self.lbl_save_status.setStyleSheet("background-color: transparent; font-size: 12px; color: #424a53; border: none;")

        auto_btn_row = QHBoxLayout()
        btn_manual_save = QPushButton("지금 즉시 저장 및 백업")
        btn_manual_save.setStyleSheet(btn_primary_style)
        btn_manual_save.clicked.connect(self._on_manual_save)

        btn_change_dir = QPushButton("저장 경로 변경")
        btn_change_dir.setStyleSheet(btn_normal_style)
        btn_change_dir.clicked.connect(self._on_change_save_dir)

        auto_btn_row.addWidget(btn_manual_save)
        auto_btn_row.addWidget(btn_change_dir)
        auto_btn_row.addStretch()

        auto_layout.addWidget(lbl_auto_title)
        auto_layout.addWidget(self.lbl_save_status)
        auto_layout.addLayout(auto_btn_row)
        layout.addWidget(sec_auto)

        # 2. 분기 저장 슬롯
        sec_branch = QFrame()
        sec_branch.setStyleSheet(card_style)
        branch_layout = QVBoxLayout(sec_branch)
        branch_layout.setSpacing(8)

        lbl_branch_title = QLabel("2. 분기 저장 슬롯 (엔딩 분기 되돌리기용 체크포인트)")
        lbl_branch_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; border: none;")
        branch_layout.addWidget(lbl_branch_title)

        self.branch_info_labels = {}
        for slot in (1, 2, 3):
            row = QHBoxLayout()
            lbl_slot = QLabel(f"슬롯 {slot}: 비어 있음")
            lbl_slot.setStyleSheet("background-color: transparent; font-size: 12px; color: #1f2328; border: none;")
            self.branch_info_labels[slot] = lbl_slot

            btn_b_save = QPushButton("분기 저장")
            btn_b_save.setStyleSheet(btn_normal_style)
            btn_b_save.clicked.connect(lambda checked, s=slot: self._on_branch_save(s))

            btn_b_load = QPushButton("불러오기")
            btn_b_load.setStyleSheet(btn_primary_style)
            btn_b_load.clicked.connect(lambda checked, s=slot: self._on_branch_load(s))

            row.addWidget(lbl_slot, stretch=1)
            row.addWidget(btn_b_save)
            row.addWidget(btn_b_load)
            branch_layout.addLayout(row)

        layout.addWidget(sec_branch)

        # 3. Base64 사용자 전달용 세이브 코드
        sec_b64 = QFrame()
        sec_b64.setStyleSheet(card_style)
        b64_layout = QVBoxLayout(sec_b64)
        b64_layout.setSpacing(8)

        lbl_b64_title = QLabel("3. Base64 세이브 코드 내보내기 / 불러오기")
        lbl_b64_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; border: none;")
        b64_layout.addWidget(lbl_b64_title)

        self.txt_b64 = QTextEdit()
        self.txt_b64.setFixedHeight(64)
        self.txt_b64.setPlaceholderText("이곳에 Base64 세이브 코드가 생성되거나, 불러올 코드를 붙여넣으세요.")
        self.txt_b64.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 4px;
            }
        """)
        b64_layout.addWidget(self.txt_b64)

        b64_btn_row = QHBoxLayout()
        btn_export_b64 = QPushButton("현재 데이터 코드 생성 및 복사")
        btn_export_b64.setStyleSheet(btn_normal_style)
        btn_export_b64.clicked.connect(self._on_export_base64)

        btn_import_b64 = QPushButton("입력된 코드로 데이터 복원")
        btn_import_b64.setStyleSheet(btn_primary_style)
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
                background-color: #fbefff;
                border: 1px solid #8250df;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        debug_layout = QVBoxLayout(sec_debug)
        debug_layout.setSpacing(8)

        lbl_debug_title = QLabel("4. [DEBUG] 명령어 입력 난이도 단계 강제 설정 (Tier 1 ~ 4)")
        lbl_debug_title.setStyleSheet("background-color: transparent; font-size: 14px; font-weight: bold; color: #6639ba; border: none;")

        self.lbl_debug_tier_desc = QLabel("현재 적용 단계: Tier 1 (초기 복잡한 파이썬 코드)")
        self.lbl_debug_tier_desc.setStyleSheet("background-color: transparent; font-size: 12px; color: #424a53; border: none;")

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
                background-color: #ffebe9;
                border: 1px solid #ff8182;
                border-radius: 6px;
                padding: 12px;
            }
        """)
        reset_layout = QHBoxLayout(sec_reset)
        lbl_reset = QLabel("게임 진행 데이터 전체 초기화 (달성한 엔딩 컬렉션은 유지)")
        lbl_reset.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #cf222e; border: none;")

        btn_reset = QPushButton("데이터 초기화")
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #cf222e; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #a40e26; }
        """)
        btn_reset.clicked.connect(self._on_reset_game)

        reset_layout.addWidget(lbl_reset)
        reset_layout.addStretch()
        reset_layout.addWidget(btn_reset)
        layout.addWidget(sec_reset)

        return container

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
        self.refresh_settings()

    def refresh_settings(self):
        if hasattr(self, "lbl_save_status"):
            self.lbl_save_status.setText(
                f"최근 저장: {self.save_manager.last_saved_time} | 저장 경로: {os.path.abspath(self.save_manager.save_dir)}"
            )
        for slot, lbl in self.branch_info_labels.items():
            lbl.setText(f"슬롯 {slot}: {self.save_manager.get_branch_info(slot)}")

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
                        background-color: #8250df; color: #ffffff;
                        border: none; border-radius: 4px;
                        padding: 6px 12px; font-weight: bold; font-size: 12px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff; color: #1f2328;
                        border: 1px solid #d0d7de; border-radius: 4px;
                        padding: 6px 12px; font-weight: bold; font-size: 12px;
                    }
                    QPushButton:hover { background-color: #eaeef2; }
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
                color: #6e7781;
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

        # 도감 & 영구 엔딩 컬렉션 표시
        self._clear_layout(self.dex_layout)

        # 1. 엔딩 컬렉션 섹션
        endings_unlocked = self.game_state.unlocked_endings
        basic_count = self.game_state.get_basic_ending_count()
        lbl_end_header = QLabel(
            f"엔딩 컬렉션: {basic_count} / 4 달성"
            + (" (★ ENDING S 해금됨)" if self.game_state.has_all_four_endings() else " (ENDING A~D 모두 달성 시 숨겨진 분기 출현)")
        )
        lbl_end_header.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #8250df; margin-bottom: 4px;")
        self.dex_layout.addWidget(lbl_end_header)

        for end_info in self.game_state.ENDINGS_CATALOG:
            eid = end_info["id"]
            is_done = (eid in endings_unlocked)
            is_hidden = end_info["is_hidden"]

            card = QFrame()
            if is_done:
                bg = "#fbefff" if is_hidden else "#dafbe1"
                bd = "#8250df" if is_hidden else "#2da44e"
            else:
                bg = "#eaeef2"
                bd = "#afb8c1"

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
            lbl_t.setStyleSheet("background-color: transparent; font-weight: bold; font-size: 13px; border: none;")
            lbl_d = QLabel(desc_txt)
            lbl_d.setStyleSheet("background-color: transparent; font-size: 12px; color: #424a53; border: none;")
            v.addWidget(lbl_t)
            v.addWidget(lbl_d)
            self.dex_layout.addWidget(card)

        # 2. 수집 도감 섹션
        unlocked_cnt = sum(1 for d in self.game_state.encyclopedia if d["unlocked"])
        total_cnt = len(self.game_state.encyclopedia)

        lbl_progress = QLabel(f"수집 도감: {unlocked_cnt} / {total_cnt} ({int(unlocked_cnt / total_cnt * 100)}%)")
        lbl_progress.setStyleSheet("background-color: transparent; font-size: 13px; font-weight: bold; color: #0969da; margin-top: 10px; margin-bottom: 4px;")
        self.dex_layout.addWidget(lbl_progress)

        for item in self.game_state.encyclopedia:
            card = QFrame()
            unlocked = item["unlocked"]
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {'#ddf4ff' if unlocked else '#eaeef2'};
                    border: 1px solid {'#0969da' if unlocked else '#afb8c1'};
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