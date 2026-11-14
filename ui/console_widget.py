import time
import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal


class VirtualConsoleWidget(QFrame):
    command_completed = pyqtSignal()

    SAMPLE_COMMANDS = [
        "print([x**2 for x in range(1, 6)])",
        "import torch; torch.cuda.is_available()",
        "model.train(epochs=10, lr=0.001)",
        "def attention(q, k, v): return q @ k.T",
        "optimizer.zero_grad(); loss.backward()"
    ]

    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.target_cmd = random.choice(self.SAMPLE_COMMANDS)
        self.typed_text = ""
        self.history_logs = [
            "> 시스템 초기화 완료... 로컬 LLM 환경 준비됨.",
            "> 콘솔 영역을 클릭한 뒤 아래 명령어를 직접 타이핑하세요."
        ]
        self.last_input_time = 0.0
        self.warning_msg = ""

        self._init_ui()
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

        # 하단 현재 입력 프롬프트 박스 (계획서 3.2절의 초록색 테두리 영역)
        self.input_box = QLabel()
        self.input_box.setStyleSheet("""
            background-color: #161b22;
            border: 1px solid #3fb950;
            padding: 10px;
            font-family: Consolas, monospace;
            font-size: 16px;
        """)
        layout.addWidget(self.input_box)

        # 예외/경고 알림 라벨 (Ctrl+V 차단 등)
        self.status_label = QLabel("입력 대기 중... (클릭하여 포커스)")
        self.status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(self.status_label)

    def mousePressEvent(self, event):
        self.setFocus()
        self.status_label.setText("콘솔 활성화됨: 명령어를 입력하세요.")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 12px;")

    def keyPressEvent(self, event):
        # 1. Ctrl+V 붙여넣기 예외 처리 (계획서 2.5.1절)
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V:
            self.status_label.setText("[경고] 붙여넣기(Ctrl+V)는 허용되지 않습니다! 직접 입력하세요.")
            self.status_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 12px;")
            return

        # 2. 입력 쿨다운 체크 (계획서 2.4.3절)
        now = time.time() * 1000
        if now - self.last_input_time < self.game_state.input_cooldown_ms:
            return
        self.last_input_time = now

        key = event.key()
        text = event.text()

        # 3. 백스페이스 처리
        if key == Qt.Key.Key_Backspace:
            if len(self.typed_text) > 0:
                self.typed_text = self.typed_text[:-1]
                self._render_console()
            return

        # 4. 엔터키 처리 (완성 검사)
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.typed_text == self.target_cmd:
                self._on_command_success()
            else:
                self.status_label.setText("[오류] 오타가 있거나 명령어가 완성되지 않았습니다.")
                self.status_label.setStyleSheet("color: #f85149; font-size: 12px;")
            return

        # 5. 일반 출력 가능 문자 입력
        if text and text.isprintable():
            if len(self.typed_text) < len(self.target_cmd):
                self.typed_text += text
                self._render_console()

                # 마지막 글자까지 정확히 일치하면 엔터 없이도 즉시 완성 처리 가능하게 할지 여부
                if self.typed_text == self.target_cmd:
                    self._on_command_success()

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
        self._render_console()

    def _render_console(self):
        self.log_label.setText("\n".join(self.history_logs))

        # 목표 문자열과 현재 입력 문자열을 비교하여 HTML 색상 렌더링
        html_chars = ['<span style="color:#3fb950;">&gt; </span>']
        for i, target_ch in enumerate(self.target_cmd):
            safe_ch = target_ch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if safe_ch == " ":
                safe_ch = "&nbsp;"

            if i < len(self.typed_text):
                if self.typed_text[i] == target_ch:
                    # 정확히 입력한 글자 (초록색)
                    html_chars.append(f'<span style="color:#3fb950; font-weight:bold;">{safe_ch}</span>')
                else:
                    # 오타 발생 글자 (빨간색 배경 강조, 계획서 2.5.1절)
                    wrong_ch = self.typed_text[i].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    html_chars.append(f'<span style="color:#ffffff; background-color:#da3633; font-weight:bold;">{wrong_ch}</span>')
            else:
                # 아직 입력하지 않은 가이드 글자 (회색)
                html_chars.append(f'<span style="color:#6e7681;">{safe_ch}</span>')

        self.input_box.setText("".join(html_chars))