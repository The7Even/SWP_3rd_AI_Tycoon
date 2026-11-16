import time
import random
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class VirtualConsoleWidget(QFrame):
    command_completed = pyqtSignal()

    SAMPLE_COMMANDS = [
        "print([x**2 for x in range(1, 6)])",
        "import torch; torch.cuda.is_available()",
        "model.train(epochs=10, lr=0.001)",
        "def attention(q, k, v): return q @ k.T",
        "optimizer.zero_grad(); loss.backward()"
    ]

    # 단독 입력 시 쿨다운을 유발하지 않아야 하는 수식/보조 키 목록
    MODIFIER_KEYS = {
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        Qt.Key.Key_CapsLock,
        Qt.Key.Key_NumLock,
        Qt.Key.Key_ScrollLock,
    }

    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.target_cmd = random.choice(self.SAMPLE_COMMANDS)
        self.typed_text = ""
        self.history_logs = [
            "> 시스템 초기화 완료... 로컬 LLM 환경 준비됨.",
            "> 콘솔 영역을 클릭한 뒤 아래 명령어를 입력하고 Enter를 누르세요."
        ]
        self.last_input_time = 0.0
        self.cursor_visible = True

        self._init_ui()

        # 커서 깜빡임 타이머 (500ms 간격)
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self._toggle_cursor)
        self.cursor_timer.start(500)

        self._render_console()

    def _init_ui(self):
        self.setStyleSheet("""
            VirtualConsoleWidget {
                background-color: #0d1117;
                border: 2px solid #30363d;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 상단 과거 출력 로그 영역
        self.log_label = QLabel()
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.log_label.setWordWrap(True)
        self.log_label.setStyleSheet("color: #3fb950; font-family: Consolas, monospace; font-size: 13px;")
        layout.addWidget(self.log_label, stretch=1)

        # 하단 현재 입력 프롬프트 박스
        self.input_box = QLabel()
        self.input_box.setStyleSheet("""
            background-color: #161b22;
            border: 1px solid #3fb950;
            padding: 10px;
            font-family: Consolas, monospace;
            font-size: 16px;
        """)
        layout.addWidget(self.input_box)

        # 상태 및 예외 알림 라벨
        self.status_label = QLabel("입력 대기 중... (클릭하여 포커스)")
        self.status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(self.status_label)

    def _toggle_cursor(self):
        self.cursor_visible = not self.cursor_visible
        self._render_console()

    def _reset_cursor_blink(self):
        """키 입력 직후에는 커서가 즉시 선명하게 보이도록 초기화"""
        self.cursor_visible = True
        self.cursor_timer.start(500)

    def mousePressEvent(self, event):
        self.setFocus()
        self._reset_cursor_blink()
        self._render_console()
        self.status_label.setText("콘솔 활성화됨: 명령어 입력 후 Enter를 누르세요.")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 12px;")

    def keyPressEvent(self, event):
        key = event.key()

        # 1. 수식 키(Shift, Ctrl, Alt 등)는 쿨다운 대상에서 제외
        if key in self.MODIFIER_KEYS:
            return

        # 2. Ctrl+V 붙여넣기 예외 처리 (계획서 2.5.1절)
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and key == Qt.Key.Key_V:
            self.status_label.setText("[경고] 붙여넣기(Ctrl+V)는 허용되지 않습니다! 직접 입력하세요.")
            self.status_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 12px;")
            return

        # 3. 엔터키 처리 (명령어 완성 확정 및 검증)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.typed_text == self.target_cmd:
                self._on_command_success()
            else:
                self.status_label.setText("[오류] 오타가 있거나 명령어가 완성되지 않았습니다. 수정 후 다시 Enter를 누르세요.")
                self.status_label.setStyleSheet("color: #f85149; font-size: 12px;")
            return

        # 4. 입력 쿨다운 체크
        now = time.time() * 1000
        if now - self.last_input_time < self.game_state.input_cooldown_ms:
            return

        # 5. 백스페이스 처리
        if key == Qt.Key.Key_Backspace:
            if len(self.typed_text) > 0:
                self.typed_text = self.typed_text[:-1]
                self.last_input_time = now
                self._reset_cursor_blink()
                self._render_console()
            return

        # 6. 일반 출력 가능 문자 입력
        text = event.text()
        if text and text.isprintable():
            if len(self.typed_text) < len(self.target_cmd):
                self.typed_text += text
                self.last_input_time = now
                self._reset_cursor_blink()
                self._render_console()

                if self.typed_text == self.target_cmd:
                    self.status_label.setText("입력 완료! Enter 키를 눌러 명령어를 실행하세요.")
                    self.status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

    def _on_command_success(self):
        self.history_logs.append(f"> {self.target_cmd}  [+{int(self.game_state.tokens_per_command)} Tk]")
        if len(self.history_logs) > 12:
            self.history_logs.pop(0)

        self.typed_text = ""
        self.target_cmd = random.choice(self.SAMPLE_COMMANDS)
        self.status_label.setText("명령어 실행 완료! 토큰이 지급되었습니다.")
        self.status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

        self.game_state.complete_command()
        self.command_completed.emit()
        self._reset_cursor_blink()
        self._render_console()

    def _render_console(self):
        self.log_label.setText("\n".join(self.history_logs))

        html_chars = ['<span style="color:#3fb950;">&gt; </span>']
        cursor_idx = len(self.typed_text)
        has_focus = self.hasFocus()

        for i, target_ch in enumerate(self.target_cmd):
            safe_ch = target_ch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if safe_ch == " ":
                safe_ch = "&nbsp;"

            if i < cursor_idx:
                if self.typed_text[i] == target_ch:
                    html_chars.append(f'<span style="color:#3fb950; font-weight:bold;">{safe_ch}</span>')
                else:
                    wrong_ch = self.typed_text[i].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    if wrong_ch == " ":
                        wrong_ch = "&nbsp;"
                    html_chars.append(f'<span style="color:#ffffff; background-color:#da3633; font-weight:bold;">{wrong_ch}</span>')
            elif i == cursor_idx:
                # 현재 입력할 위치의 커서 표시 (포커스 상태에 따라 깜빡임)
                if has_focus and self.cursor_visible:
                    html_chars.append(
                        f'<span style="color:#ffffff; background-color:#2ea043; text-decoration:underline;">{safe_ch}</span>'
                    )
                else:
                    html_chars.append(
                        f'<span style="color:#8b949e; text-decoration:underline;">{safe_ch}</span>'
                    )
            else:
                html_chars.append(f'<span style="color:#6e7681;">{safe_ch}</span>')

        # 모든 글자를 다 입력해서 커서가 줄 끝에 도달한 경우 엔터 대기용 끝 커서 표시
        if cursor_idx == len(self.target_cmd):
            if has_focus and self.cursor_visible:
                html_chars.append('<span style="color:#3fb950; font-weight:bold;">█</span>')
            else:
                html_chars.append('<span style="color:#161b22;">█</span>')

        self.input_box.setText("".join(html_chars))