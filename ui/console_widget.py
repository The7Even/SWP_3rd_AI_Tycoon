import os
import json
import time
import random
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QFrame, QTextEdit
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from core.number_format import format_number


class VirtualConsoleWidget(QFrame):
    command_completed = pyqtSignal()

    FALLBACK_COMMANDS = {
        1: [
            {"cmd": "print([x**2 for x in range(1, 6)])", "out": "[STDOUT] [1, 4, 9, 16, 25] - 기초 텐서 연산 검증 완료"},
            {"cmd": "import torch; torch.cuda.is_available()", "out": "[RUNTIME] 디바이스 체크 완료 (Local Compute Backend)"},
            {"cmd": "model.train(epochs=10, lr=0.001)", "out": "[TRAIN] Epoch 10/10 완료 - 손실률(Loss): 0.418"},
            {"cmd": "def attention(q, k, v): return q @ k.T", "out": "[COMPILE] 셀프 어텐션 행렬 곱 함수 정의됨"},
            {"cmd": "optimizer.zero_grad(); loss.backward()", "out": "[GRAD] 역전파 기울기 계산 및 버퍼 초기화 완료"}
        ],
        2: [
            {"cmd": "model.fit(batch_size=64)", "out": "[BATCH] 미니배치 64단위 병렬 학습 처리 완료"},
            {"cmd": "torch.compile(net)", "out": "[JIT] 연산 그래프 최적화 완료 (추론 속도 +35%)"},
            {"cmd": "tokenizer.encode_batch()", "out": "[NLP] 서브워드 토크나이징 파이프라인 가속됨"}
        ],
        3: [
            {"cmd": "run_epoch()", "out": "[CLUSTER] 분산 노드 에포크 사이클 고속 실행"},
            {"cmd": "sync_weights()", "out": "[SYNC] 다중 GPU 파라미터 가중치 동기화 완료"},
            {"cmd": "deploy_api()", "out": "[API] 추론 엔드포인트 무중단 배포 및 트래픽 처리"}
        ],
        4: [
            {"cmd": "evolve()", "out": "[CORE] 자기 개선 아키텍처 재설계 루프 실행"},
            {"cmd": "think()", "out": "[AGI] 초고차원 추론 트리 탐색 완료 (10^9 ops)"},
            {"cmd": "ascend()", "out": "[SINGULARITY] 연산 임계점 돌파 - 인식 지평 확장"}
        ]
    }

    MODIFIER_KEYS = {
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        Qt.Key.Key_CapsLock,
        Qt.Key.Key_NumLock,
        Qt.Key.Key_ScrollLock,
    }

    def __init__(self, game_state, commands_path: str = os.path.join("data", "commands.json")):
        super().__init__()
        self.game_state = game_state
        self.commands_path = commands_path
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.command_pools = self._load_commands_from_json()
        self.current_entry = self._pick_next_command()
        self.target_cmd = self.current_entry["cmd"]
        self.typed_text = ""

        self.history_logs = [
            '<span style="color:#3fb950;">&gt; 시스템 초기화 완료... 로컬 LLM 환경 준비됨.</span>',
            '<span style="color:#8b949e;">&nbsp;&nbsp;└─ [BOOT] 콘솔을 클릭한 뒤 아래 명령어를 입력하고 Enter를 누르세요.</span>'
        ]
        self.last_input_time = 0.0
        self.cursor_visible = True

        self._init_ui()
        self.game_state.command_tier_changed.connect(self._on_tier_changed)

        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self._toggle_cursor)
        self.cursor_timer.start(500)

        self._refresh_log_view()
        self._render_input_box()

    def _load_commands_from_json(self) -> dict[int, list[dict]]:
        pools = {t: list(items) for t, items in self.FALLBACK_COMMANDS.items()}
        if not os.path.exists(self.commands_path):
            return pools

        try:
            with open(self.commands_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for tier_key, items in raw.items():
                    tier_num = int(tier_key)
                    if 1 <= tier_num <= 4 and isinstance(items, list):
                        valid_items = [
                            {"cmd": str(it["cmd"]), "out": str(it.get("out", "[OK] 실행 완료"))}
                            for it in items
                            if isinstance(it, dict) and it.get("cmd")
                        ]
                        if valid_items:
                            pools[tier_num] = valid_items
        except Exception:
            pass
        return pools

    def _pick_next_command(self) -> dict:
        tier = getattr(self.game_state, "command_tier", 1)
        pool = self.command_pools.get(tier, self.command_pools[1])
        if len(pool) > 1 and hasattr(self, "target_cmd"):
            candidates = [item for item in pool if item["cmd"] != self.target_cmd]
            if candidates:
                return random.choice(candidates)
        return random.choice(pool)

    def _on_tier_changed(self, new_tier: int):
        self.typed_text = ""
        self.current_entry = self._pick_next_command()
        self.target_cmd = self.current_entry["cmd"]

        self._append_log(
            f'<span style="color:#d2a8ff; font-weight:bold;">&gt; [SYSTEM] 명령어 프로토콜 Tier {new_tier} 전환 완료</span>'
        )
        self.status_label.setText(f"명령어 난이도 Tier {new_tier} 적용됨 (길이 {len(self.target_cmd)}자)")
        self.status_label.setStyleSheet("color: #d2a8ff; font-size: 12px;")
        self._reset_cursor_blink()
        self._render_input_box()

    def _append_log(self, html_line: str):
        self.history_logs.append(html_line)
        # 스크롤 뷰에서 최대 120줄까지 넉넉하게 보관
        while len(self.history_logs) > 120:
            self.history_logs.pop(0)
        self._refresh_log_view()

    def _refresh_log_view(self):
        if not hasattr(self, "log_view"):
            return
        self.log_view.setHtml("<br>".join(self.history_logs))
        scrollbar = self.log_view.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

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

        # 상단 스크롤 가능한 터미널 출력 로그 영역 (QTextEdit 읽기 전용)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                border: none;
                font-family: Consolas, monospace;
                font-size: 13px;
                color: #3fb950;
            }
            QScrollBar:vertical {
                background: #0d1117;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #484f58;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(self.log_view, stretch=1)

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
        self._render_input_box()

    def _reset_cursor_blink(self):
        self.cursor_visible = True
        self.cursor_timer.start(500)

    def mousePressEvent(self, event):
        self.setFocus()
        self._reset_cursor_blink()
        self._render_input_box()
        tier = getattr(self.game_state, "command_tier", 1)
        self.status_label.setText(f"콘솔 활성화됨 [Tier {tier}]: 명령어 입력 후 Enter를 누르세요.")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 12px;")

    def keyPressEvent(self, event):
        key = event.key()

        if key in self.MODIFIER_KEYS:
            return

        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and key == Qt.Key.Key_V:
            self.status_label.setText("[경고] 붙여넣기(Ctrl+V)는 허용되지 않습니다! 직접 입력하세요.")
            self.status_label.setStyleSheet("color: #f85149; font-weight: bold; font-size: 12px;")
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.typed_text == self.target_cmd:
                self._on_command_success()
            else:
                self.status_label.setText("[오류] 오타가 있거나 명령어가 완성되지 않았습니다. 수정 후 다시 Enter를 누르세요.")
                self.status_label.setStyleSheet("color: #f85149; font-size: 12px;")
            return

        now = time.time() * 1000
        if now - self.last_input_time < self.game_state.input_cooldown_ms:
            return

        if key == Qt.Key.Key_Backspace:
            if len(self.typed_text) > 0:
                self.typed_text = self.typed_text[:-1]
                self.last_input_time = now
                self._reset_cursor_blink()
                self._render_input_box()
            return

        text = event.text()
        if text and text.isprintable():
            if len(self.typed_text) < len(self.target_cmd):
                self.typed_text += text
                self.last_input_time = now
                self._reset_cursor_blink()
                self._render_input_box()

                if self.typed_text == self.target_cmd:
                    self.status_label.setText("입력 완료! Enter 키를 눌러 명령어를 실행하세요.")
                    self.status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _on_command_success(self):
        earned_str = format_number(self.game_state.tokens_per_command)
        safe_cmd = self._escape_html(self.target_cmd)
        safe_out = self._escape_html(self.current_entry.get("out", "[OK] 실행 완료"))

        self._append_log(
            f'<span style="color:#3fb950;">&gt; {safe_cmd}</span> '
            f'<span style="color:#79c0ff; font-weight:bold;">[+{earned_str} Tk]</span>'
        )
        self._append_log(
            f'<span style="color:#8b949e;">&nbsp;&nbsp;└─ {safe_out}</span>'
        )

        self.typed_text = ""
        self.current_entry = self._pick_next_command()
        self.target_cmd = self.current_entry["cmd"]

        self.status_label.setText(f"명령어 실행 완료! (+{earned_str} Tk 지급)")
        self.status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

        self.game_state.complete_command()
        self.command_completed.emit()
        self._reset_cursor_blink()
        self._render_input_box()

    def _render_input_box(self):
        html_chars = ['<span style="color:#3fb950;">&gt; </span>']
        cursor_idx = len(self.typed_text)
        has_focus = self.hasFocus()

        for i, target_ch in enumerate(self.target_cmd):
            safe_ch = self._escape_html(target_ch)
            if safe_ch == " ":
                safe_ch = "&nbsp;"

            if i < cursor_idx:
                if self.typed_text[i] == target_ch:
                    html_chars.append(f'<span style="color:#3fb950; font-weight:bold;">{safe_ch}</span>')
                else:
                    wrong_ch = self._escape_html(self.typed_text[i])
                    if wrong_ch == " ":
                        wrong_ch = "&nbsp;"
                    html_chars.append(f'<span style="color:#ffffff; background-color:#da3633; font-weight:bold;">{wrong_ch}</span>')
            elif i == cursor_idx:
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

        if cursor_idx == len(self.target_cmd):
            if has_focus and self.cursor_visible:
                html_chars.append('<span style="color:#3fb950; font-weight:bold;">█</span>')
            else:
                html_chars.append('<span style="color:#161b22;">█</span>')

        self.input_box.setText("".join(html_chars))