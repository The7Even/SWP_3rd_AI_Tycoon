import os
import json
import time
import random
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor
from core.number_format import format_number
from ui.singularity_controller import SingularityDialogueController


class InlinePromptBox(QTextEdit):
    """하단 초록 테두리 박스 안에서 고스트 텍스트 위에 직접 타이핑하고 Enter로 제출하는 입력 위젯"""

    def __init__(self, console_widget):
        super().__init__()
        self.console = console_widget
        self.last_key_time = 0.0
        self.setReadOnly(True)
        self.setFixedHeight(44)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def keyPressEvent(self, event):
        if self.console.is_booting or self.console.is_dialogue_mode:
            return

        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V:
            self.console.show_feedback("붙여넣기는 허용되지 않습니다.", is_error=True)
            return
        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.key() == Qt.Key.Key_Insert:
            self.console.show_feedback("붙여넣기는 허용되지 않습니다.", is_error=True)
            return

        key = event.key()
        if key == Qt.Key.Key_Backspace:
            self.console.handle_backspace()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.console.handle_enter()
            return

        text = event.text()
        if text and text.isprintable():
            now_ms = time.time() * 1000.0
            cooldown = self.console.game_state.input_cooldown_ms
            if (now_ms - self.last_key_time) < cooldown:
                self.console.on_cooldown_blocked(cooldown)
                return
            self.last_key_time = now_ms
            self.console.handle_char_input(text)
            return

        super().keyPressEvent(event)


class ClickableLogView(QTextEdit):
    """독대/엔딩 연출 중 클릭 시 현재 줄 출력이나 대기 연출을 즉시 완료하는 로그 뷰"""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


class VirtualConsoleWidget(QFrame):
    """가상 콘솔 위젯 (명령어 입력 + 개발자-AI 스피너 & 타자기 대화 담당, 특이점 이후는 SingularityDialogueController에 위임)"""

    ending_completed = pyqtSignal(str)
    request_load_branch = pyqtSignal(int)
    request_reset_game = pyqtSignal()

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    DEFAULT_COMMANDS = {
        "1": [
            {"cmd": "logits = linear_layer(hidden_states)", "output": "[RUNTIME] 선형 투영 행렬 연산 완료 (FP32)"},
            {"cmd": "init_local_ai_kernel()", "output": "[RUNTIME] 디바이스 체크 완료 (Local Compute Backend)"},
            {"cmd": "load_weights('base_v0.bin')", "output": "[RUNTIME] 초기 가중치 텐서 메모리 적재 완료"},
            {"cmd": "run_inference_step(batch=1)", "output": "[RUNTIME] 단일 배치 순전파 추론 사이클 통과"}
        ],
        "2": [
            {"cmd": "api.generate(prompt)", "output": "[RUNTIME] 토큰 스트림 파이프라인 응답 생성 완료"},
            {"cmd": "model.forward(x)", "output": "[RUNTIME] 어텐션 레이어 캐시 동기화 완료"},
            {"cmd": "sync_tensor_cache()", "output": "[RUNTIME] KV 캐시 블록 정렬 완료"}
        ],
        "3": [
            {"cmd": "exec_cluster()", "output": "[RUNTIME] 분산 노드 병렬 추론 커널 실행 완료"},
            {"cmd": "opt_step()", "output": "[RUNTIME] 그래디언트 파라미터 갱신 완료"}
        ],
        "4": [
            {"cmd": "core.run()", "output": "[RUNTIME] 초고속 코어 추론 루프 완료"},
            {"cmd": "pulse()", "output": "[RUNTIME] 신경망 동기화 펄스 전송 완료"}
        ]
    }

    BOOT_SEQUENCE = [
        ("[CC] Compiling local_ai_core.cpp ... OK", "#3fb950", 220),
        ("[LD] Linking tensor_runtime.so ... OK", "#3fb950", 240),
        ("[MEM] Allocating scratchpad buffer (64MB) ... OK", "#8b949e", 220),
        ("[WARN] Unoptimized input buffer detected (Latency: 200ms)", "#d29922", 280),
        ("> 시스템 초기화 완료... 로컬 LLM 환경 준비됨.", "#3fb950", 240),
    ]

    def __init__(
        self,
        game_state,
        commands_path: str = os.path.join("data", "commands.json"),
        dialogues_path: str = os.path.join("data", "ai_dialogues.json"),
    ):
        super().__init__()
        self.game_state = game_state
        self.commands_path = commands_path
        self.dialogues_path = dialogues_path

        self.command_pools = self._load_commands_from_json()
        self.dialogue_data = self._load_dialogues_from_json()
        self.chapter_dialogue_decks: dict[str, list[dict]] = {}

        self.is_booting = True
        self._boot_step = 0
        self._last_cooldown_ms = self.game_state.input_cooldown_ms

        self.current_cmd_entry: dict = {"cmd": "", "output": ""}
        self.typed_text = ""
        self._log_lines_html: list[str] = []

        # 개발자 입력 -> AI 사고 스피너 -> AI 타자기 출력 상태 관리
        self._dialogue_phase: str | None = None
        self._active_dev_full_text: str = ""
        self._active_ai_full_text: str = ""
        self._typing_char_idx: int = 0
        self._spinner_idx: int = 0
        self._spinner_ticks_left: int = 0
        self._active_typing_html: str | None = None
        self._pending_dev_line_idx: int | None = None

        self.setStyleSheet("VirtualConsoleWidget { background-color: #0d1117; border: none; }")
        self._init_ui()

        # 특이점 1대1 독대 및 엔딩 연출 전담 컨트롤러 연결
        self.singularity_ctrl = SingularityDialogueController(self, self.game_state)
        self.singularity_ctrl.ending_completed.connect(self.ending_completed)
        self.singularity_ctrl.request_load_branch.connect(self.request_load_branch)
        self.singularity_ctrl.request_reset_game.connect(self.request_reset_game)

        self.feedback_timer = QTimer(self)
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.timeout.connect(self._reset_prompt_border)

        self.boot_timer = QTimer(self)
        self.boot_timer.setSingleShot(True)
        self.boot_timer.timeout.connect(self._step_boot_sequence)

        # 가상 대화 전용 타이머들
        self.auto_dialogue_timer = QTimer(self)
        self.auto_dialogue_timer.setSingleShot(True)
        self.auto_dialogue_timer.timeout.connect(self._on_auto_dialogue_timeout)

        self.priority_dialogue_timer = QTimer(self)
        self.priority_dialogue_timer.timeout.connect(self._check_priority_dialogue_queue)
        self.priority_dialogue_timer.start(1200)

        self.dialogue_anim_timer = QTimer(self)
        self.dialogue_anim_timer.setSingleShot(True)
        self.dialogue_anim_timer.timeout.connect(self._step_dialogue_animation)

        # 블록 커서 깜빡임 타이머
        self._cursor_visible = True
        self.cursor_blink_timer = QTimer(self)
        self.cursor_blink_timer.timeout.connect(self._toggle_cursor_blink)
        self.cursor_blink_timer.start(530)

        self.game_state.command_tier_changed.connect(self._on_tier_changed)
        self.game_state.state_changed.connect(self._on_state_updated)

        self._update_session_header()
        self.start_boot_sequence()

    @property
    def is_dialogue_mode(self) -> bool:
        return self.singularity_ctrl.is_active

    def _normalize_cmd_item(self, item) -> dict | None:
        if isinstance(item, str) and item.strip():
            return {"cmd": item.strip(), "output": "[RUNTIME] 명령어 실행 사이클 완료"}
        if isinstance(item, dict):
            cmd_str = str(item.get("cmd") or item.get("command") or item.get("text") or "").strip()
            if not cmd_str:
                return None
            out_str = str(
                item.get("output")
                or item.get("out")
                or item.get("response")
                or item.get("log")
                or item.get("result")
                or "[RUNTIME] 명령어 실행 사이클 완료"
            ).strip()
            return {"cmd": cmd_str, "output": out_str}
        return None

    def _load_commands_from_json(self) -> dict[str, list[dict]]:
        if not os.path.exists(self.commands_path):
            return {k: [dict(x) for x in v] for k, v in self.DEFAULT_COMMANDS.items()}

        try:
            with open(self.commands_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            tiers = raw.get("tiers", raw) if isinstance(raw, dict) else {}
            loaded = {}
            for tier_key in ("1", "2", "3", "4"):
                raw_list = tiers.get(tier_key, []) if isinstance(tiers, dict) else []
                normalized = []
                if isinstance(raw_list, list):
                    for entry in raw_list:
                        norm = self._normalize_cmd_item(entry)
                        if norm:
                            normalized.append(norm)
                if normalized:
                    loaded[tier_key] = normalized
                else:
                    loaded[tier_key] = [dict(x) for x in self.DEFAULT_COMMANDS[tier_key]]
            return loaded
        except Exception:
            return {k: [dict(x) for x in v] for k, v in self.DEFAULT_COMMANDS.items()}

    def _load_dialogues_from_json(self) -> dict:
        if not os.path.exists(self.dialogues_path):
            return {"version_intros": {}, "node_triggers": {}, "chapters": {}}
        try:
            with open(self.dialogues_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
        return {"version_intros": {}, "node_triggers": {}, "chapters": {}}

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        # 상단 세션 서브바 (챕터 언급 없이 세션 주소와 연결 상태만 표시)
        session_bar = QFrame()
        session_bar.setStyleSheet("QFrame { background-color: transparent; border-bottom: 1px dashed #21262d; }")
        session_row = QHBoxLayout(session_bar)
        session_row.setContentsMargins(2, 0, 2, 5)

        self.lbl_session = QLabel("SESSION: local-node://proto-ai-core")
        self.lbl_session.setStyleSheet("""
            background-color: transparent;
            color: #8b949e;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px;
            border: none;
        """)

        self.lbl_conn = QLabel("● CONNECTED")
        self.lbl_conn.setStyleSheet("""
            background-color: transparent;
            color: #3fb950;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px;
            font-weight: bold;
            border: none;
        """)
        session_row.addWidget(self.lbl_session)
        session_row.addStretch()
        session_row.addWidget(self.lbl_conn)
        layout.addWidget(session_bar)

        self.log_view = ClickableLogView()
        self.log_view.setReadOnly(True)
        self.log_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #c9d1d9;
                border: none;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 14px;
                padding: 4px;
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
        """)
        self.log_view.clicked.connect(self._on_console_clicked)
        layout.addWidget(self.log_view, stretch=1)

        self.prompt_box = InlinePromptBox(self)
        self._apply_prompt_border("#2ea043")
        layout.addWidget(self.prompt_box)

        self.dialogue_panel = QWidget()
        self.dialogue_panel.setStyleSheet("background-color: #0d1117;")
        self.dialogue_vbox = QVBoxLayout(self.dialogue_panel)
        self.dialogue_vbox.setContentsMargins(0, 4, 0, 2)
        self.dialogue_vbox.setSpacing(8)
        self.dialogue_panel.hide()
        layout.addWidget(self.dialogue_panel)

        self.lbl_status = QLabel(f"Latency: {self.game_state.input_cooldown_ms}ms")
        self.lbl_status.setStyleSheet("""
            color: #8b949e;
            font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px;
            padding-left: 2px;
        """)
        layout.addWidget(self.lbl_status)

    def _update_session_header(self):
        ai_name = getattr(self.game_state, "ai_name", "Proto-AI") or "Proto-AI"
        slug = ai_name.strip().lower().replace(" ", "-")
        self.lbl_session.setText(f"SESSION: local-node://{slug}-core")

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._on_console_clicked()

    def _on_console_clicked(self):
        if self.is_dialogue_mode:
            self.singularity_ctrl.skip_current_step()
        else:
            self.prompt_box.setFocus()

    def _apply_prompt_border(self, border_color: str):
        self.prompt_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: #090c10;
                color: #c9d1d9;
                border: 1.5px solid {border_color};
                border-radius: 6px;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 15px;
                padding: 8px 12px;
            }}
        """)

    def scroll_to_bottom(self):
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        sb = self.log_view.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def clear_logs(self):
        self._log_lines_html.clear()
        self._reset_dialogue_state()
        self.log_view.clear()

    def _reset_dialogue_state(self):
        self.dialogue_anim_timer.stop()
        self._dialogue_phase = None
        self._active_dev_full_text = ""
        self._active_ai_full_text = ""
        self._typing_char_idx = 0
        self._spinner_idx = 0
        self._spinner_ticks_left = 0
        self._active_typing_html = None
        self._pending_dev_line_idx = None

    def append_log(self, text: str, color: str = "#c9d1d9", bold: bool = False):
        line_html = self.format_line_html(text, color, bold)
        if self._pending_dev_line_idx is not None:
            self._log_lines_html.insert(self._pending_dev_line_idx, line_html)
            self._pending_dev_line_idx += 1
        else:
            self._log_lines_html.append(line_html)

        if len(self._log_lines_html) > 160:
            self._log_lines_html.pop(0)
            if self._pending_dev_line_idx is not None:
                self._pending_dev_line_idx = max(0, self._pending_dev_line_idx - 1)

        self.render_log_view(active_line_html=self._active_typing_html)

    def format_line_html(self, text: str, color: str, bold: bool = False, cursor_suffix: str = "") -> str:
        if not text and not cursor_suffix:
            return "&nbsp;"
        escaped = self._escape_html(text)
        weight = "font-weight:bold;" if bold else ""
        return f'<span style="color:{color};{weight}">{escaped}</span>{cursor_suffix}'

    def render_log_view(self, active_line_html: str | None = None):
        lines = list(self._log_lines_html)
        if active_line_html is not None:
            lines.append(active_line_html)
        self.log_view.setHtml("<br>".join(lines))
        self.scroll_to_bottom()

    def _escape_html(self, s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace(" ", "&nbsp;")
        )

    # ==================== 일반 부팅 & 명령어 타이핑 ====================
    def start_boot_sequence(self):
        self.boot_timer.stop()
        self.feedback_timer.stop()
        self.auto_dialogue_timer.stop()
        self.singularity_ctrl.stop_all()

        self.dialogue_panel.hide()
        self.prompt_box.show()
        self.clear_logs()

        self.is_booting = True
        self._boot_step = 0
        self._last_cooldown_ms = self.game_state.input_cooldown_ms
        self.current_cmd_entry = {"cmd": "", "output": ""}
        self.typed_text = ""
        self._render_prompt_box()
        self._step_boot_sequence()

    def start_singularity_dialogue(self):
        self.boot_timer.stop()
        self.feedback_timer.stop()
        self.auto_dialogue_timer.stop()
        self._reset_dialogue_state()
        self.is_booting = False
        self.lbl_conn.setText("● SINGULARITY")
        self.lbl_conn.setStyleSheet("""
            background-color: transparent; color: #bc8cff;
            font-family: 'Consolas', 'D2Coding', monospace; font-size: 11px; font-weight: bold; border: none;
        """)
        self.singularity_ctrl.start()

    def _step_boot_sequence(self):
        if self._boot_step < len(self.BOOT_SEQUENCE):
            msg, color, delay_ms = self.BOOT_SEQUENCE[self._boot_step]
            self.append_log(msg, color=color)
            self._boot_step += 1
            self.boot_timer.start(delay_ms)
        else:
            self.append_log("  └ [BOOT] 콘솔을 클릭한 뒤 아래 명령어를 입력하고 Enter를 누르세요.", color="#8b949e")
            self.is_booting = False
            self._reset_prompt_border()
            self._pick_next_command()
            self.prompt_box.setFocus()
            self._schedule_next_auto_dialogue()

    # ==================== 가상 대화 스피너 & 타자기 출력 엔진 ====================
    def _schedule_next_auto_dialogue(self):
        delay_ms = int(random.uniform(35.0, 50.0) * 1000)
        self.auto_dialogue_timer.start(delay_ms)

    def _format_dialogue_text(self, raw: str) -> str:
        ai_name = getattr(self.game_state, "ai_name", "Proto-AI") or "Proto-AI"
        ai_ver = self.game_state.get_ai_version()
        return raw.replace("{ai_name}", ai_name).replace("{ai_version}", ai_ver)

    def _get_ai_dialogue_color(self) -> str:
        chap = self.game_state.get_current_chapter()
        if chap <= 2:
            return "#a5d6ff"
        elif chap <= 4:
            return "#58a6ff"
        elif chap <= 6:
            return "#d2a8ff"
        return "#ff7b72"

    def _get_ai_thinking_label(self) -> str:
        chap = self.game_state.get_current_chapter()
        if chap == 1:
            return "Generating tokens..."
        elif chap <= 3:
            return "추론 연산 중..."
        elif chap <= 5:
            return "컨텍스트 분석 중..."
        return "고차원 연산 중..."

    def _get_ai_typing_interval_ms(self) -> int:
        chap = self.game_state.get_current_chapter()
        if chap <= 2:
            return 28
        elif chap <= 4:
            return 22
        elif chap <= 6:
            return 17
        return 14

    def _is_tutorial_active(self) -> bool:
        upgrades = getattr(self.game_state, "upgrades", [])
        ch1_node = next((u for u in upgrades if u.get("id") == "ch1_start"), None)
        if ch1_node is not None:
            return not bool(ch1_node.get("purchased", False))
        return False

    def _is_auto_dialogue_blocked(self) -> bool:
        if self.is_booting or self.is_dialogue_mode:
            return True
        if self._is_tutorial_active():
            return True
        if getattr(self.game_state, "is_ending_locked", False):
            return True
        if self._dialogue_phase is not None:
            return True
        if self.game_state.get_ai_version() == "v0.9-beta" and not getattr(self.game_state, "ai_named", True):
            return True
        return False

    def _check_priority_dialogue_queue(self):
        if self._is_auto_dialogue_blocked():
            return
        queue = getattr(self.game_state, "pending_dialogue_queue", None)
        if not queue:
            return

        kind, key = queue.pop(0)
        if kind == "version" and key in ("v0.1", "v0.2", "v0.3"):
            self._check_priority_dialogue_queue()
            return

        entry = None
        if kind == "version":
            entry = self.dialogue_data.get("version_intros", {}).get(key)
        elif kind == "node":
            entry = self.dialogue_data.get("node_triggers", {}).get(key)

        if entry:
            self._start_dialogue_pair(entry["dev"], entry["ai"])
            self._schedule_next_auto_dialogue()

    def _on_auto_dialogue_timeout(self):
        if self._is_auto_dialogue_blocked() or getattr(self.game_state, "pending_dialogue_queue", None):
            self._schedule_next_auto_dialogue()
            return

        chap_key = str(self.game_state.get_current_chapter())
        if not self.chapter_dialogue_decks.get(chap_key):
            pool = list(self.dialogue_data.get("chapters", {}).get(chap_key, []))
            random.shuffle(pool)
            self.chapter_dialogue_decks[chap_key] = pool

        if self.chapter_dialogue_decks[chap_key]:
            entry = self.chapter_dialogue_decks[chap_key].pop()
            self._start_dialogue_pair(entry["dev"], entry["ai"])

        self._schedule_next_auto_dialogue()

    def _start_dialogue_pair(self, dev_raw: str, ai_raw: str):
        self._active_dev_full_text = f"> {self._format_dialogue_text(dev_raw)}"
        self._active_ai_full_text = self._format_dialogue_text(ai_raw)
        self._dialogue_phase = "typing_dev"
        self._typing_char_idx = 0
        self._pending_dev_line_idx = None
        self._step_dialogue_animation()

    def _step_dialogue_animation(self):
        if self._dialogue_phase == "typing_dev":
            self._typing_char_idx += 1
            partial = self._active_dev_full_text[:self._typing_char_idx]
            cursor = '<span style="color:#e6edf3;">▌</span>' if self._typing_char_idx < len(self._active_dev_full_text) else ""
            self._active_typing_html = self.format_line_html(partial, color="#e6edf3", bold=True, cursor_suffix=cursor)
            self.render_log_view(active_line_html=self._active_typing_html)

            if self._typing_char_idx < len(self._active_dev_full_text):
                self.dialogue_anim_timer.start(28)
            else:
                final_dev_html = self.format_line_html(self._active_dev_full_text, color="#e6edf3", bold=True)
                self._log_lines_html.append(final_dev_html)
                if len(self._log_lines_html) > 160:
                    self._log_lines_html.pop(0)

                self._pending_dev_line_idx = len(self._log_lines_html) - 1
                self._dialogue_phase = "thinking_ai"
                self._spinner_idx = 0
                chap = self.game_state.get_current_chapter()
                self._spinner_ticks_left = 14 if chap <= 3 else (11 if chap <= 5 else 9)
                self._step_dialogue_animation()

        elif self._dialogue_phase == "thinking_ai":
            if self._spinner_ticks_left > 0:
                frame = self.SPINNER_FRAMES[self._spinner_idx % len(self.SPINNER_FRAMES)]
                self._spinner_idx += 1
                self._spinner_ticks_left -= 1

                ai_color = self._get_ai_dialogue_color()
                think_label = self._get_ai_thinking_label()
                self._active_typing_html = self.format_line_html(
                    f"  {frame} {think_label}",
                    color=ai_color,
                    bold=False,
                )
                self.render_log_view(active_line_html=self._active_typing_html)
                self.dialogue_anim_timer.start(80)
            else:
                self._dialogue_phase = "typing_ai"
                self._typing_char_idx = 0
                self._step_dialogue_animation()

        elif self._dialogue_phase == "typing_ai":
            self._typing_char_idx += 1
            ai_color = self._get_ai_dialogue_color()
            partial = f"  {self._active_ai_full_text[:self._typing_char_idx]}"
            cursor = f'<span style="color:{ai_color};">▌</span>' if self._typing_char_idx < len(self._active_ai_full_text) else ""
            self._active_typing_html = self.format_line_html(partial, color=ai_color, bold=False, cursor_suffix=cursor)
            self.render_log_view(active_line_html=self._active_typing_html)

            if self._typing_char_idx < len(self._active_ai_full_text):
                self.dialogue_anim_timer.start(self._get_ai_typing_interval_ms())
            else:
                final_ai_html = self.format_line_html(f"  {self._active_ai_full_text}", color=ai_color, bold=False)
                insert_pos = (
                    self._pending_dev_line_idx + 1
                    if self._pending_dev_line_idx is not None
                    else len(self._log_lines_html)
                )
                self._log_lines_html.insert(insert_pos, final_ai_html)
                if len(self._log_lines_html) > 160:
                    self._log_lines_html.pop(0)

                self._reset_dialogue_state()
                self.render_log_view()

    # ==================== 명령어 프롬프트 렌더링 & 입력 ====================
    @property
    def current_target(self) -> str:
        return self.current_cmd_entry.get("cmd", "")

    def _toggle_cursor_blink(self):
        if self.is_booting or self.is_dialogue_mode:
            return
        self._cursor_visible = not self._cursor_visible
        self._render_prompt_box()

    def _render_prompt_box(self):
        target = self.current_target
        if self.is_booting or not target:
            self.prompt_box.setHtml('<span style="color:#6e7681;">&gt;&nbsp;Initializing...</span>')
            return

        matched_len = 0
        for i, ch in enumerate(self.typed_text):
            if i < len(target) and ch == target[i]:
                matched_len += 1
            else:
                break

        ok_part = self._escape_html(self.typed_text[:matched_len])
        err_part = self._escape_html(self.typed_text[matched_len:])
        remain_idx = len(self.typed_text)

        html = '<span style="color:#3fb950; font-weight:bold;">&gt;&nbsp;</span>'
        if ok_part:
            html += f'<span style="color:#3fb950; font-weight:bold;">{ok_part}</span>'
        if err_part:
            html += f'<span style="color:#ffffff; background-color:#da3633; font-weight:bold;">{err_part}</span>'

        if remain_idx < len(target):
            next_char = self._escape_html(target[remain_idx])
            rest_chars = self._escape_html(target[remain_idx + 1:])
            if self._cursor_visible:
                html += f'<span style="background-color:#3fb950; color:#0d1117; font-weight:bold;">{next_char}</span>'
            else:
                html += f'<span style="color:#8b949e;">{next_char}</span>'
            if rest_chars:
                html += f'<span style="color:#8b949e;">{rest_chars}</span>'
        else:
            if self._cursor_visible:
                html += '<span style="background-color:#3fb950; color:#0d1117;">&nbsp;</span>'
            else:
                html += '<span>&nbsp;</span>'

        self.prompt_box.setHtml(html)

    def _on_tier_changed(self, _new_tier: int):
        if not self.is_booting and not self.is_dialogue_mode:
            self._pick_next_command()

    def _on_state_updated(self):
        self._update_session_header()
        if self.is_dialogue_mode:
            return
        cur_cd = self.game_state.input_cooldown_ms
        if cur_cd != self._last_cooldown_ms:
            if cur_cd < self._last_cooldown_ms:
                self.append_log(
                    f"> [SYS] 입력 버퍼 지연 완화: {self._last_cooldown_ms}ms -> {cur_cd}ms",
                    color="#3fb950"
                )
            self._last_cooldown_ms = cur_cd
            if not self.feedback_timer.isActive():
                self._reset_prompt_border()

    def _pick_next_command(self):
        tier_key = str(getattr(self.game_state, "command_tier", 1))
        pool = self.command_pools.get(tier_key, self.DEFAULT_COMMANDS["1"])

        cur_cmd = self.current_target
        if len(pool) > 1 and any(item["cmd"] == cur_cmd for item in pool):
            candidates = [item for item in pool if item["cmd"] != cur_cmd]
            self.current_cmd_entry = dict(random.choice(candidates))
        else:
            self.current_cmd_entry = dict(random.choice(pool))

        self.typed_text = ""
        self._cursor_visible = True
        self.cursor_blink_timer.start(530)
        self._render_prompt_box()

    def handle_char_input(self, ch: str):
        target = self.current_target
        if not target or len(self.typed_text) >= len(target) + 6:
            return

        self.typed_text += ch
        self._cursor_visible = True
        self.cursor_blink_timer.start(530)
        self._apply_prompt_border("#2ea043" if target.startswith(self.typed_text) else "#f85149")
        self._render_prompt_box()

    def handle_backspace(self):
        if not self.typed_text:
            return
        self.typed_text = self.typed_text[:-1]
        self._cursor_visible = True
        self.cursor_blink_timer.start(530)
        self._apply_prompt_border("#2ea043" if self.current_target.startswith(self.typed_text) else "#f85149")
        self._render_prompt_box()

    def handle_enter(self):
        target = self.current_target
        if not target:
            return
        if self.typed_text == target:
            earned = getattr(
                self.game_state,
                "effective_tokens_per_command",
                self.game_state.tokens_per_command
            )
            runtime_out = self.current_cmd_entry.get("output", "[RUNTIME] 명령어 실행 사이클 완료")

            self.game_state.complete_command()
            self.append_log(f"> {target}   [+{format_number(earned)} Token]", color="#3fb950")
            self.append_log(f"  └ {runtime_out}", color="#8b949e")

            self.show_feedback(f"실행 완료! +{format_number(earned)} Token 획득", is_error=False)
            self._apply_prompt_border("#2ea043")
            self._pick_next_command()
        else:
            self._apply_prompt_border("#f85149")
            self.show_feedback("오타가 있거나 명령어가 완성되지 않았습니다.", is_error=True)

    def on_cooldown_blocked(self, cooldown_ms: int):
        self._apply_prompt_border("#d29922")
        self.lbl_status.setText(f"[BUFFER BUSY] 입력 지연 제한 중 ({cooldown_ms}ms)")
        self.lbl_status.setStyleSheet("""
            color: #d29922; font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px; font-weight: bold; padding-left: 2px;
        """)
        self.feedback_timer.start(400)

    def show_feedback(self, msg: str, is_error: bool = False):
        if self.is_dialogue_mode:
            return
        color = "#f85149" if is_error else "#3fb950"
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(f"""
            color: {color}; font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px; font-weight: bold; padding-left: 2px;
        """)
        self.feedback_timer.start(1100)

    def _reset_prompt_border(self):
        if self.is_dialogue_mode:
            return
        if self.current_target and not self.current_target.startswith(self.typed_text):
            self._apply_prompt_border("#f85149")
        else:
            self._apply_prompt_border("#2ea043")
        self.lbl_status.setText(f"Latency: {self.game_state.input_cooldown_ms}ms")
        self.lbl_status.setStyleSheet("""
            color: #8b949e; font-family: 'Consolas', 'D2Coding', monospace;
            font-size: 11px; padding-left: 2px;
        """)