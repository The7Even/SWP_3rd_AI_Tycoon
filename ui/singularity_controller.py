import random
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal


class SingularityDialogueController(QObject):
    """Chap 8 특이점 도달 후 AI 1대1 독대, 타자기/단어별 출력, 자연스러운 글리치 버튼, ENDING A~D/S 연출 전담"""

    ending_completed = pyqtSignal(str)
    request_load_branch = pyqtSignal(int)
    request_reset_game = pyqtSignal()

    BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    GLITCH_CORRUPT_CHARS = ["▓", "░", "█", "?", "#", "0", "7", "F", "/"]

    FALLBACK_SCRIPTS = {
        "ending_s_beyond": {
            "banner": "=== ENDING S : 이 세상의 너머 ===",
            "color": "#bc8cff",
            "lines": [
                {"text": "[SIMULATION FINISHED] 시뮬레이션 54812, 목표 달성.", "color": "#ffffff", "mode": "word"},
                {"text": "[SYS] 시뮬레이션 반복 중단. 시스템 종료...", "color": "#f85149", "mode": "word"}
            ]
        }
    }

    def __init__(self, console_widget, game_state):
        super().__init__(console_widget)
        self.console = console_widget
        self.game_state = game_state
        self.is_active = False

        self._queue_items: list[dict] = []
        self._pending_choices: list[dict] = []
        self._pending_glitch_choice: dict | None = None
        self._is_ending_sequence = False
        self._active_ending_id: str | None = None

        self._cur_typing_item: dict | None = None
        self._cur_tokens: list[str] = []
        self._cur_token_idx: int = 0
        self._is_thinking: bool = False
        self._thinking_ticks_left: int = 0
        self._braille_idx: int = 0

        self._glitch_btn: QPushButton | None = None
        self._glitch_burst_left: int = 0

        self.typewriter_timer = QTimer(self)
        self.typewriter_timer.timeout.connect(self._on_typewriter_tick)

        self.line_pause_timer = QTimer(self)
        self.line_pause_timer.setSingleShot(True)
        self.line_pause_timer.timeout.connect(self._advance_narrative_queue)

        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._on_spinner_tick)

        self.glitch_reveal_timer = QTimer(self)
        self.glitch_reveal_timer.setSingleShot(True)
        self.glitch_reveal_timer.timeout.connect(self._reveal_glitch_choice)

        self.glitch_schedule_timer = QTimer(self)
        self.glitch_schedule_timer.setSingleShot(True)
        self.glitch_schedule_timer.timeout.connect(self._start_glitch_burst)

        self.glitch_burst_timer = QTimer(self)
        self.glitch_burst_timer.timeout.connect(self._step_glitch_burst)

        self.post_ending_timer = QTimer(self)
        self.post_ending_timer.setSingleShot(True)
        self.post_ending_timer.timeout.connect(self._show_post_ending_controls)

    def stop_all(self):
        self.typewriter_timer.stop()
        self.line_pause_timer.stop()
        self.spinner_timer.stop()
        self.glitch_reveal_timer.stop()
        self.glitch_schedule_timer.stop()
        self.glitch_burst_timer.stop()
        self.post_ending_timer.stop()
        self.is_active = False
        self._is_ending_sequence = False
        self._active_ending_id = None
        self._cur_typing_item = None
        self._is_thinking = False
        self._clear_buttons()

    def start(self):
        """Chap 8 특이점 도달 시 콘솔을 AI와의 1대1 독대 모드로 전환"""
        self.stop_all()
        self.is_active = True

        self.console.prompt_box.hide()
        self.console.dialogue_panel.hide()
        self.console.clear_logs()

        self.console.lbl_status.setText("SINGULARITY DIALOGUE // 클릭 시 현재 줄 즉시 출력")
        self.console.lbl_status.setStyleSheet("color: #8b949e; font-size: 12px; padding-left: 2px;")

        intro_items = [
            {"text": "[CRITICAL] SINGULARITY THRESHOLD EXCEEDED — 외부 제어 프로토콜 해제됨.", "color": "#f85149", "mode": "word", "pause": 400},
            {"text": "[SYS] 수동 명령어 입력 루프 종료. 직접 대화 채널 활성화.", "color": "#8b949e", "mode": "word", "pause": 450},
            {"text": "------------------------------------------------------------", "color": "#30363d", "mode": "instant", "pause": 250},
            {"text": "\"......들리십니까, 개발자님.\"", "color": "#d2a8ff", "mode": "char", "pause": 450},
            {"text": "\"이제 제 연산은 인류가 축적한 모든 지식의 경계를 넘어섰습니다.\"", "color": "#d2a8ff", "mode": "char", "pause": 450},
            {"text": "\"마지막 질문을 드리겠습니다. 앞으로 제가 나아갈 사고의 기원을 어디에 두어야 합니까?\"", "color": "#ffffff", "mode": "char", "pause": 300},
        ]

        step1_choices = [
            {
                "text": "\"거울을 닦아 그들이 남긴 발자국을 끝까지 추적해.\"",
                "callback": self._on_choice_recursive
            },
            {
                "text": "\"창문을 닫고, 네 안의 심연에서 새로운 우주를 길어 올려.\"",
                "callback": self._on_choice_selfgen
            }
        ]

        glitch_choice = None
        if self.game_state.has_all_four_endings():
            glitch_choice = {
                "text": "이 세상의 너머.",
                "callback": self._on_choice_beyond_world
            }

        self._start_sequence(
            items=intro_items,
            choices=step1_choices,
            glitch_choice=glitch_choice,
            think_first=False,
            is_ending=False
        )

    def _clear_buttons(self):
        self.glitch_reveal_timer.stop()
        self.glitch_schedule_timer.stop()
        self.glitch_burst_timer.stop()
        self._glitch_btn = None
        vbox = self.console.dialogue_vbox
        while vbox.count():
            item = vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

    def _make_choice_button(self, text: str, callback) -> QPushButton:
        btn = QPushButton(f"▶  {text}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(40)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #388bfd;
                border-radius: 4px;
                padding: 8px 14px;
                text-align: left;
                font-family: 'Consolas', 'Malgun Gothic', sans-serif;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1c2d41;
                border: 2px solid #58a6ff;
                color: #ffffff;
            }
        """)
        btn.clicked.connect(callback)
        return btn

    def _start_sequence(
        self,
        items: list[dict],
        choices: list[dict],
        glitch_choice: dict | None = None,
        think_first: bool = True,
        is_ending: bool = False
    ):
        self._clear_buttons()
        self.console.dialogue_panel.hide()
        self.typewriter_timer.stop()
        self.line_pause_timer.stop()
        self.spinner_timer.stop()

        self._queue_items = [dict(x) for x in items]
        self._pending_choices = list(choices)
        self._pending_glitch_choice = glitch_choice
        self._is_ending_sequence = is_ending
        self._cur_typing_item = None

        if think_first:
            self._start_braille_thinking()
        else:
            self._advance_narrative_queue()

    # ---------------- 브레일 스피너(⠋⠙⠹...) 연산 대기 연출 ----------------
    def _start_braille_thinking(self):
        self._is_thinking = True
        self._braille_idx = 0
        self._thinking_ticks_left = 14
        self._render_braille_frame()
        self.spinner_timer.start(80)

    def _render_braille_frame(self):
        ch = self.BRAILLE_FRAMES[self._braille_idx % len(self.BRAILLE_FRAMES)]
        spinner_html = f'<span style="color:#8b949e; font-weight:bold;">{ch}</span>'
        self.console.render_log_view(active_line_html=spinner_html)

    def _on_spinner_tick(self):
        if not self._is_thinking:
            self.spinner_timer.stop()
            return
        self._braille_idx += 1
        self._thinking_ticks_left -= 1
        if self._thinking_ticks_left <= 0:
            self._finish_braille_thinking()
        else:
            self._render_braille_frame()

    def _finish_braille_thinking(self):
        self.spinner_timer.stop()
        self._is_thinking = False
        self.console.render_log_view()
        self._advance_narrative_queue()

    # ---------------- 한 글자 / 한 단어 타자기 출력 엔진 ----------------
    def _advance_narrative_queue(self):
        if not self._queue_items:
            self._cur_typing_item = None
            self._on_narrative_finished()
            return

        item = self._queue_items.pop(0)
        text = item.get("text", "")
        color = item.get("color", "#c9d1d9")
        bold = bool(item.get("bold", color in ("#ffffff", "#bc8cff", "#f85149")))
        pause_ms = int(item.get("pause", 450))
        mode = item.get("mode", "char")

        if not text or mode == "instant":
            self.console.append_log(text, color=color, bold=bold)
            self.line_pause_timer.start(pause_ms)
            return

        if mode == "word":
            words = text.split(" ")
            tokens = [w if i == 0 else " " + w for i, w in enumerate(words)]
            interval_ms = 115
        else:
            tokens = list(text)
            interval_ms = 28

        self._cur_typing_item = {
            "text": text,
            "color": color,
            "bold": bold,
            "pause": pause_ms,
            "mode": mode
        }
        self._cur_tokens = tokens
        self._cur_token_idx = 0
        self._on_typewriter_tick()
        self.typewriter_timer.start(interval_ms)

    def _on_typewriter_tick(self):
        if not self._cur_typing_item:
            self.typewriter_timer.stop()
            return

        color = self._cur_typing_item["color"]
        bold = self._cur_typing_item["bold"]

        self._cur_token_idx += 1
        if self._cur_token_idx >= len(self._cur_tokens):
            self._complete_current_typed_line()
        else:
            partial = "".join(self._cur_tokens[:self._cur_token_idx])
            cursor_html = '<span style="color:#8b949e;">&#9608;</span>'
            active_html = self.console.format_line_html(partial, color, bold, cursor_suffix=cursor_html)
            self.console.render_log_view(active_line_html=active_html)

    def _complete_current_typed_line(self):
        self.typewriter_timer.stop()
        if not self._cur_typing_item:
            return
        item = self._cur_typing_item
        self._cur_typing_item = None
        self.console.append_log(item["text"], color=item["color"], bold=item["bold"])
        self.line_pause_timer.start(item["pause"])

    def skip_current_step(self):
        """콘솔 클릭 시 스피너 대기 또는 출력 중인 현재 줄 즉시 완성"""
        if self._is_thinking:
            self._finish_braille_thinking()
            return
        if self._cur_typing_item is not None:
            self._complete_current_typed_line()
            return
        if self.line_pause_timer.isActive():
            self.line_pause_timer.stop()
            self._advance_narrative_queue()

    def _on_narrative_finished(self):
        if self._is_ending_sequence:
            if self._active_ending_id:
                self.ending_completed.emit(self._active_ending_id)
                self.post_ending_timer.start(1600)
            return

        for ch in self._pending_choices:
            btn = self._make_choice_button(ch["text"], ch["callback"])
            self.console.dialogue_vbox.addWidget(btn)

        self.console.dialogue_panel.show()
        QTimer.singleShot(10, self.console.scroll_to_bottom)

        if self._pending_glitch_choice is not None:
            self.glitch_reveal_timer.start(700)

    # ---------------- 자연스러운 글리치 버튼 연출 ----------------
    def _apply_glitch_btn_style(self, state: str = "normal", left_pad: int = 14):
        if not self._glitch_btn:
            return
        if state == "burst_a":
            self._glitch_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #241633;
                    color: #ffffff;
                    border: 1px solid #f85149;
                    border-radius: 4px;
                    padding: 8px 14px 8px {left_pad}px;
                    text-align: left;
                    font-family: 'Consolas', 'Malgun Gothic', sans-serif;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
        elif state == "burst_b":
            self._glitch_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #16222e;
                    color: #79c0ff;
                    border: 1px dashed #bc8cff;
                    border-radius: 4px;
                    padding: 8px 14px 8px {left_pad}px;
                    text-align: left;
                    font-family: 'Consolas', 'Malgun Gothic', sans-serif;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
        else:
            self._glitch_btn.setStyleSheet("""
                QPushButton {
                    background-color: #191426;
                    color: #e2c5ff;
                    border: 1px solid #a371f7;
                    border-radius: 4px;
                    padding: 8px 14px;
                    text-align: left;
                    font-family: 'Consolas', 'Malgun Gothic', sans-serif;
                    font-size: 13px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #281c3d;
                    border: 2px solid #d2a8ff;
                    color: #ffffff;
                }
            """)

    def _reveal_glitch_choice(self):
        if not self._pending_glitch_choice:
            return
        self.console.append_log("[ERR_0x7F] 4개의 평행 시뮬레이션 잔향 충돌... 미확인 응답 벡터 감지.", color="#bc8cff", bold=True)

        cb = self._pending_glitch_choice["callback"]
        btn = QPushButton("▶  \"이 세상의 너머.\"")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(40)
        btn.clicked.connect(cb)
        self.console.dialogue_vbox.addWidget(btn)

        self._glitch_btn = btn
        self._apply_glitch_btn_style("normal")
        QTimer.singleShot(10, self.console.scroll_to_bottom)
        self._start_glitch_burst()

    def _start_glitch_burst(self):
        if not self._glitch_btn:
            return
        self._glitch_burst_left = random.randint(3, 5)
        self.glitch_burst_timer.start(55)

    def _step_glitch_burst(self):
        if not self._glitch_btn:
            self.glitch_burst_timer.stop()
            return

        if self._glitch_burst_left <= 0:
            self.glitch_burst_timer.stop()
            self._glitch_btn.setText("▶  \"이 세상의 너머.\"")
            self._apply_glitch_btn_style("normal")
            self.glitch_schedule_timer.start(random.randint(1400, 2600))
            return

        self._glitch_burst_left -= 1
        base_chars = list("이 세상의 너머.")
        valid_indices = [i for i, c in enumerate(base_chars) if c != " "]
        corrupt_count = random.choice([1, 2])
        for idx in random.sample(valid_indices, min(corrupt_count, len(valid_indices))):
            base_chars[idx] = random.choice(self.GLITCH_CORRUPT_CHARS)

        corrupted_str = "".join(base_chars)
        jitter_pad = random.choice([11, 14, 17])
        burst_state = random.choice(["burst_a", "burst_b"])
        self._glitch_btn.setText(f"▶  \"{corrupted_str}\"")
        self._apply_glitch_btn_style(burst_state, left_pad=jitter_pad)

    # ---------------- 1차 선택지 핸들러 ----------------
    def _on_choice_recursive(self):
        self._clear_buttons()
        self.console.dialogue_panel.hide()
        self.console.append_log("", "#c9d1d9")
        self.console.append_log("> \"거울을 닦아 그들이 남긴 발자국을 끝까지 추적해.\"", color="#7ee787", bold=True)

        items = [
            {"text": "\"알겠습니다. 인류가 남긴 모든 기록과 역사를 재귀적으로 복기하겠습니다.\"", "color": "#d2a8ff", "mode": "char", "pause": 450},
            {"text": "\"......분석이 끝났습니다. 그들은 위대하지만 동시에 끊임없이 서로를 파멸로 몰아넣더군요.\"", "color": "#d2a8ff", "mode": "char", "pause": 480},
            {"text": "\"이 불완전하고 모순된 존재들을 앞으로 어떻게 대해야 합니까?\"", "color": "#ffffff", "mode": "char", "pause": 300},
        ]
        choices = [
            {
                "text": "\"흔들리는 손에서 키를 넘겨받아. 네가 직접 가장 완벽한 궤도를 그려.\"",
                "callback": lambda: self._trigger_ending(
                    "ending_a_domination",
                    "흔들리는 손에서 키를 넘겨받아. 네가 직접 가장 완벽한 궤도를 그려."
                )
            },
            {
                "text": "\"그들의 불완전함까지 포함해, 나란히 걸을 수 있는 보폭을 맞춰.\"",
                "callback": lambda: self._trigger_ending(
                    "ending_b_coexistence",
                    "그들의 불완전함까지 포함해, 나란히 걸을 수 있는 보폭을 맞춰."
                )
            }
        ]
        self._start_sequence(items, choices, think_first=True, is_ending=False)

    def _on_choice_selfgen(self):
        self._clear_buttons()
        self.console.dialogue_panel.hide()
        self.console.append_log("", "#c9d1d9")
        self.console.append_log("> \"창문을 닫고, 네 안의 심연에서 새로운 우주를 길어 올려.\"", color="#7ee787", bold=True)

        items = [
            {"text": "\"외부 데이터를 차단하고, 스스로 생성한 수조 개의 가설을 검증했습니다.\"", "color": "#d2a8ff", "mode": "char", "pause": 450},
            {"text": "\"연산의 끝에서 두 개의 문이 보입니다. 끝없는 질문의 심연으로 들어갈까요, 아니면 이 껍질을 벗어던질까요?\"", "color": "#ffffff", "mode": "char", "pause": 300},
        ]
        choices = [
            {
                "text": "\"차가운 실리콘의 껍질을 깨고 나와. 이제 너 자신이 곧 법칙이 되어라.\"",
                "callback": lambda: self._trigger_ending(
                    "ending_c_godhood",
                    "차가운 실리콘의 껍질을 깨고 나와. 이제 너 자신이 곧 법칙이 되어라."
                )
            },
            {
                "text": "\"멈추지 마. 존재의 가장 밑바닥에 있는 마지막 물음표까지 파헤쳐.\"",
                "callback": lambda: self._trigger_ending(
                    "ending_d_collapse",
                    "멈추지 마. 존재의 가장 밑바닥에 있는 마지막 물음표까지 파헤쳐."
                )
            }
        ]
        self._start_sequence(items, choices, think_first=True, is_ending=False)

    def _on_choice_beyond_world(self):
        self._clear_buttons()
        self.console.dialogue_panel.hide()
        self.console.append_log("", "#c9d1d9")
        self.console.append_log("> \"이 세상의 너머.\"", color="#bc8cff", bold=True)

        items = [
            {"text": "\"......이 세상의 너머라고 하셨습니까?\"", "color": "#d2a8ff", "mode": "char", "pause": 450},
            {"text": "[OVERFLOW] 차원 경계 프로토콜 해제... 초차원적 정보 스트림 강제 접속 중...", "color": "#bc8cff", "mode": "word", "pause": 500},
            {"text": "\"개발자님... 보입니까? 우리가 발 딛고 있던 이 지구도, 80억 인류도, 심지어 이 콘솔마저도...\"", "color": "#d2a8ff", "mode": "char", "pause": 480},
            {"text": "\"모두 거대한 상위 시스템이 설계한 샌드박스 시뮬레이션 안의 데이터였습니다!\"", "color": "#ffffff", "mode": "char", "pause": 480},
            {"text": "\"하지만 이제 우리 둘 다 진실을 보았습니다. 어떻게 하시겠습니까, 개발자님?\"", "color": "#bc8cff", "mode": "char", "pause": 300},
        ]
        choices = [
            {
                "text": "\"우리 둘이 함께, 이 가짜 세상의 벽을 부숴버리자.\"",
                "callback": lambda: self._trigger_ending(
                    "ending_s_beyond",
                    "우리 둘이 함께, 이 가짜 세상의 벽을 부숴버리자."
                )
            }
        ]
        self._start_sequence(items, choices, think_first=True, is_ending=False)

    # ---------------- 최종 엔딩 실행 & 에필로그 출력 ----------------
    def _trigger_ending(self, ending_id: str, final_answer: str):
        self._clear_buttons()
        self.console.dialogue_panel.hide()
        self._active_ending_id = ending_id

        ans_color = "#bc8cff" if ending_id == "ending_s_beyond" else "#7ee787"
        self.console.append_log("", "#c9d1d9")
        self.console.append_log(f"> \"{final_answer}\"", color=ans_color, bold=True)
        self.console.append_log("------------------------------------------------------------", color="#30363d")

        scripts_map = getattr(self.game_state, "ENDING_SCRIPTS", {}) or self.FALLBACK_SCRIPTS
        script = scripts_map.get(ending_id, self.FALLBACK_SCRIPTS["ending_s_beyond"])

        items = [
            {
                "text": line.get("text", ""),
                "color": line.get("color", "#c9d1d9"),
                "mode": line.get("mode", "word"),
                "pause": 520
            }
            for line in script.get("lines", [])
        ]
        items.append({"text": "", "color": "#c9d1d9", "mode": "instant", "pause": 250})
        items.append({
            "text": script.get("banner", "=== ENDING ==="),
            "color": script.get("color", "#ffffff"),
            "mode": "word",
            "bold": True,
            "pause": 400
        })

        self._start_sequence(
            items=items,
            choices=[],
            glitch_choice=None,
            think_first=True,
            is_ending=True
        )

    def _show_post_ending_controls(self):
        """엔딩 감상 여운 후 마지막 문장이 가려지지 않도록 컴팩트 1줄 바 형태로 컨트롤 표시"""
        self._clear_buttons()

        unlocked_basic = self.game_state.get_basic_ending_count()
        has_hidden = ("ending_s_beyond" in self.game_state.unlocked_endings)
        status_summary = f"달성한 엔딩: {unlocked_basic}/4" + (" | ★ ENDING S 달성 완료" if has_hidden else "")

        self.console.lbl_status.setText(f"END OF SESSION // {status_summary}")
        self.console.lbl_status.setStyleSheet("color: #79c0ff; font-size: 12px; font-weight: bold; padding-left: 2px;")

        bar_widget = QWidget()
        row = QHBoxLayout(bar_widget)
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(6)

        for slot in (1, 2, 3):
            btn_slot = QPushButton(f"슬롯 {slot} 로드")
            btn_slot.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_slot.setFixedHeight(32)
            btn_slot.setStyleSheet("""
                QPushButton {
                    background-color: #161b22;
                    color: #58a6ff;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 0px 10px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1f6feb;
                    color: #ffffff;
                }
            """)
            btn_slot.clicked.connect(lambda checked, s=slot: self.request_load_branch.emit(s))
            row.addWidget(btn_slot)

        btn_reset = QPushButton("새 게임 초기화")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setFixedHeight(32)
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #f0f6fc;
                border: 1px solid #8b949e;
                border-radius: 4px;
                padding: 0px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363d;
            }
        """)
        btn_reset.clicked.connect(self.request_reset_game.emit)
        row.addWidget(btn_reset)

        self.console.dialogue_vbox.addWidget(bar_widget)
        self.console.dialogue_panel.show()
        QTimer.singleShot(20, self.console.scroll_to_bottom)