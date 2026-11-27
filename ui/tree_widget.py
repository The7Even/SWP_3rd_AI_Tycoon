from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPixmap, QBrush
from core.number_format import format_number


class TreeCanvas(QWidget):
    """다크 회로도(타일 QPixmap 도트 격자 + 직교 연결선 + 챕터 구분선) 기반 업그레이드 트리 캔버스"""

    CHAPTER_TITLES = {
        0: "TUTORIAL · 개발 환경 초기화",
        1: "CHAPTER 1 · 기초 연산 환경 구축",
        2: "CHAPTER 2 · 딥러닝 프레임워크 도입",
        3: "CHAPTER 3 · 하이브리드 파이프라인 & 첫 공개",
        4: "CHAPTER 4 · 아키텍처 도약 (AI 2.0)",
        5: "CHAPTER 5 · 상용화 & 유료 모델 (AI 3.0)",
        6: "CHAPTER 6 · 대중화 & 범용 지능 (AI 4.0~5.0)",
        7: "CHAPTER 7 · 국가 기간망 & 통제 경계 (AI 6.0~7.0)",
        8: "CHAPTER 8 · 특이점 (SINGULARITY)"
    }

    TYPE_COLORS = {
        "active":  ("#b62324", "#da3633", "#ff7b72", "#f85149"),
        "passive": ("#196c2e", "#238636", "#56d364", "#3fb950"),
        "common":  ("#1158c7", "#1f6feb", "#79c0ff", "#58a6ff"),
        "story":   ("#6e40c9", "#8957e5", "#d2a8ff", "#bc8cff"),
    }

    def __init__(self, game_state, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.sound_manager = None
        self.node_buttons: dict[str, QPushButton] = {}
        self.node_centers: dict[str, QPoint] = {}
        self.chapter_rows: dict[int, int] = {}
        self._node_visual_cache: dict[str, tuple] = {}

        # 16x16 도트 격자 타일을 단 한 번만 렌더링해 QBrush로 캐싱 (paintEvent 부하 제거)
        tile = QPixmap(16, 16)
        tile.fill(QColor("#0d1117"))
        tp = QPainter(tile)
        tp.setPen(QPen(QColor("#21262d"), 1.5))
        tp.drawPoint(0, 0)
        tp.end()
        self._grid_brush = QBrush(tile)

        self.row_height = 108
        self.top_margin = 36
        self.setMinimumWidth(330)
        self.setStyleSheet("background-color: #0d1117;")
        self._build_nodes()

    def _build_nodes(self):
        for btn in self.node_buttons.values():
            btn.deleteLater()
        self.node_buttons.clear()
        self.chapter_rows.clear()
        self._node_visual_cache.clear()

        max_row = 1
        for upg in self.game_state.upgrades:
            row = int(upg.get("row", 1))
            chap = int(upg.get("chapter", 1))
            if row > max_row:
                max_row = row
            if chap not in self.chapter_rows or row < self.chapter_rows[chap]:
                self.chapter_rows[chap] = row

            btn = QPushButton(self)
            btn.setFixedSize(102, 64)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            uid = upg["id"]
            btn.clicked.connect(lambda checked, x=uid: self._on_node_clicked(x))
            self.node_buttons[uid] = btn

        total_height = self.top_margin + (max_row * self.row_height) + 70
        self.setMinimumHeight(total_height)
        self.resize(self.width(), total_height)

    def _on_node_clicked(self, upgrade_id: str):
        if self.game_state.purchase_upgrade(upgrade_id):
            if self.sound_manager is not None:
                self.sound_manager.play("upgrade_buy")
            self.update_node_states()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_nodes()

    def _reposition_nodes(self):
        w = max(self.width(), 330)
        col_x = {
            1: int(w * 0.20),
            2: int(w * 0.50),
            3: int(w * 0.80),
        }

        self.node_centers.clear()
        for upg in self.game_state.upgrades:
            uid = upg["id"]
            btn = self.node_buttons.get(uid)
            if not btn:
                continue
            cx = col_x.get(upg["col"], int(w * 0.50))
            cy = self.top_margin + (upg["row"] - 1) * self.row_height + 44
            btn.move(cx - btn.width() // 2, cy - btn.height() // 2)
            self.node_centers[uid] = QPoint(cx, cy)

        self.update()

    def get_frontier_y(self) -> int:
        frontier_ys: list[int] = []
        purchased_ys: list[int] = []

        for upg in self.game_state.upgrades:
            uid = upg["id"]
            cy = self.top_margin + (int(upg.get("row", 1)) - 1) * self.row_height + 44
            if upg.get("purchased", False):
                purchased_ys.append(cy)
            elif self.game_state.can_unlock(uid):
                frontier_ys.append(cy)

        if frontier_ys:
            return int(sum(frontier_ys) / len(frontier_ys))
        if purchased_ys:
            return max(purchased_ys)
        return self.top_margin + 44

    def update_node_states(self):
        if len(self.node_buttons) != len(self.game_state.upgrades):
            self._build_nodes()
            self._reposition_nodes()

        any_visual_changed = False

        for upg in self.game_state.upgrades:
            uid = upg["id"]
            btn = self.node_buttons[uid]
            purchased = bool(upg["purchased"])
            unlocked = self.game_state.can_unlock(uid)
            affordable = self.game_state.tokens >= upg["cost"]
            ntype = upg.get("type", "common")
            is_story = (ntype == "story" or isinstance(upg.get("story_event"), dict))

            vis_state = (purchased, unlocked, affordable, is_story, ntype, upg["cost"])
            if self._node_visual_cache.get(uid) == vis_state:
                continue
            self._node_visual_cache[uid] = vis_state
            any_visual_changed = True

            bg_c, hover_c, border_c, wait_border = self.TYPE_COLORS.get(
                "story" if is_story else ntype,
                self.TYPE_COLORS["common"]
            )

            btn.setVisible(True)

            if purchased:
                btn.setEnabled(True)
                if is_story:
                    btn.setText(f"★ {upg['name']}\n[완료]")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #241833;
                            border: 1.5px solid #a371f7;
                            border-radius: 6px;
                            color: #e2c5ff;
                            font-size: 10px;
                            font-weight: bold;
                            padding: 2px 4px;
                        }
                    """)
                else:
                    btn.setText(f"{upg['name']}\n[완료]")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #12261e;
                            border: 1.5px solid #2ea043;
                            border-radius: 6px;
                            color: #7ee787;
                            font-size: 10px;
                            font-weight: bold;
                            padding: 2px 4px;
                        }
                    """)
                btn.setToolTip(
                    f"{upg['name']} (Chap {upg.get('chapter', 1)})\n"
                    f"비용: {format_number(upg['cost'])} Token\n"
                    f"효과: {upg['desc']}"
                )
            elif unlocked:
                btn.setEnabled(True)
                cost_str = format_number(upg["cost"])
                if is_story:
                    ev_num = upg.get("story_event", {}).get("number", "")
                    prefix = f"[STORY #{ev_num}]\n" if ev_num else "[STORY]\n"
                    btn.setText(f"{prefix}{upg['name']}\n({cost_str} Tk)")
                else:
                    btn.setText(f"{upg['name']}\n({cost_str} Tk)")

                if affordable:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {bg_c};
                            border: 2px solid {border_c};
                            border-radius: 6px;
                            color: #ffffff;
                            font-size: 10px;
                            font-weight: bold;
                            padding: 2px 4px;
                        }}
                        QPushButton:hover {{
                            background-color: {hover_c};
                            border: 2px solid #ffffff;
                        }}
                    """)
                else:
                    wait_text = "#d2a8ff" if is_story else "#e6edf3"
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #161b22;
                            border: 1.5px solid {wait_border};
                            border-radius: 6px;
                            color: {wait_text};
                            font-size: 10px;
                            font-weight: bold;
                            padding: 2px 4px;
                        }}
                        QPushButton:hover {{
                            background-color: #21262d;
                        }}
                    """)
                btn.setToolTip(
                    f"{upg['name']} (Chap {upg.get('chapter', 1)})\n"
                    f"비용: {format_number(upg['cost'])} Token\n"
                    f"효과: {upg['desc']}"
                )
            else:
                btn.setEnabled(False)
                btn.setText("???\n(잠김)")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0d1117;
                        border: 1px dashed #30363d;
                        border-radius: 6px;
                        color: #484f58;
                        font-size: 10px;
                    }
                """)
                btn.setToolTip("이전 단계 업그레이드를 완료하면 해금됩니다.")

        if any_visual_changed:
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(event.rect(), self._grid_brush)

        upg_map = {u["id"]: u for u in self.game_state.upgrades}
        reached_chapters = set()
        for upg in self.game_state.upgrades:
            uid = upg["id"]
            if upg["purchased"] or self.game_state.can_unlock(uid):
                reached_chapters.add(int(upg.get("chapter", 1)))

        header_font = QFont("Malgun Gothic", 8, QFont.Weight.Bold)
        painter.setFont(header_font)
        for chap in sorted(self.chapter_rows.keys()):
            start_row = self.chapter_rows[chap]
            y_line = self.top_margin + (start_row - 1) * self.row_height - 10

            painter.setPen(QPen(QColor("#30363d"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(10, y_line, self.width() - 10, y_line)

            if chap in reached_chapters:
                painter.setPen(QPen(QColor("#8b949e")))
                title = self.CHAPTER_TITLES.get(chap, f"CHAPTER {chap}")
                painter.drawText(14, y_line + 14, title)

        pen_done = QPen(QColor("#3fb950"), 2.5)
        pen_ready = QPen(QColor("#58a6ff"), 2.0)
        pen_locked = QPen(QColor("#21262d"), 1.5, Qt.PenStyle.DashLine)

        for upg in self.game_state.upgrades:
            uid = upg["id"]
            p_end = self.node_centers.get(uid)
            if not p_end:
                continue

            for req_id in upg["req"]:
                p_start = self.node_centers.get(req_id)
                req_node = upg_map.get(req_id)
                if not p_start or not req_node:
                    continue

                if req_node["purchased"] and upg["purchased"]:
                    painter.setPen(pen_done)
                elif req_node["purchased"]:
                    painter.setPen(pen_ready)
                else:
                    painter.setPen(pen_locked)

                mid_y = (p_start.y() + p_end.y()) // 2
                painter.drawLine(p_start.x(), p_start.y(), p_start.x(), mid_y)
                painter.drawLine(p_start.x(), mid_y, p_end.x(), mid_y)
                painter.drawLine(p_end.x(), mid_y, p_end.x(), p_end.y())


class UpgradeTreeWidget(QFrame):
    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self._last_frontier_sig: tuple[str, ...] | None = None
        self._scroll_anim: QPropertyAnimation | None = None
        self.setStyleSheet("UpgradeTreeWidget { background-color: #0d1117; border-left: 1px solid #30363d; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(58)
        header.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        header_vbox = QVBoxLayout(header)
        header_vbox.setContentsMargins(10, 6, 10, 6)
        header_vbox.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        lbl_title = QLabel("UPGRADE TREE")
        lbl_title.setStyleSheet("""
            background-color: transparent;
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 0.8px;
            color: #e6edf3;
            border: none;
        """)

        self.btn_focus_frontier = QPushButton("◎ 현재 위치")
        self.btn_focus_frontier.setFixedHeight(20)
        self.btn_focus_frontier.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_focus_frontier.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_focus_frontier.setToolTip("현재 해금 가능한 최전선 업그레이드 위치로 이동")
        self.btn_focus_frontier.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #79c0ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 0px 7px;
                font-size: 10.5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #13233a;
                border-color: #58a6ff;
                color: #ffffff;
            }
        """)
        self.btn_focus_frontier.clicked.connect(lambda: self.scroll_to_frontier(smooth=True))

        title_row.addWidget(lbl_title)
        title_row.addStretch()
        title_row.addWidget(self.btn_focus_frontier)
        header_vbox.addLayout(title_row)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(10)
        legend_row.addStretch()
        for color, label_txt in (
            ("#f85149", "액티브"),
            ("#3fb950", "패시브"),
            ("#58a6ff", "공통"),
            ("#bc8cff", "스토리"),
        ):
            dot = QLabel()
            dot.setFixedSize(7, 7)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: none;")
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("background-color: transparent; color: #8b949e; font-size: 10px; border: none;")
            legend_row.addWidget(dot)
            legend_row.addWidget(lbl)
        legend_row.addStretch()
        header_vbox.addLayout(legend_row)

        layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #0d1117;
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

        self.canvas = TreeCanvas(self.game_state)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll)

        QTimer.singleShot(60, lambda: self.scroll_to_frontier(smooth=False))

    def set_sound_manager(self, sound_manager):
        self.canvas.sound_manager = sound_manager

    def _compute_frontier_signature(self) -> tuple[str, ...]:
        unlocked = sorted(
            u["id"] for u in self.game_state.upgrades
            if not u.get("purchased", False) and self.game_state.can_unlock(u["id"])
        )
        if unlocked:
            return tuple(unlocked)
        purchased = sorted(u["id"] for u in self.game_state.upgrades if u.get("purchased", False))
        return tuple(purchased[-2:])

    def scroll_to_frontier(self, smooth: bool = True):
        sb = self.scroll.verticalScrollBar()
        if not sb:
            return

        target_y = self.canvas.get_frontier_y()
        viewport_h = max(120, self.scroll.viewport().height())
        desired = max(sb.minimum(), min(sb.maximum(), target_y - int(viewport_h * 0.42)))

        if self._scroll_anim and self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._scroll_anim.stop()

        if not smooth or abs(sb.value() - desired) < 6:
            sb.setValue(desired)
            return

        anim = QPropertyAnimation(sb, b"value", self)
        anim.setDuration(260)
        anim.setStartValue(sb.value())
        anim.setEndValue(desired)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim = anim
        anim.start()

    def refresh_tree(self):
        self.canvas.update_node_states()
        sig = self._compute_frontier_signature()
        if sig != self._last_frontier_sig:
            is_initial = (self._last_frontier_sig is None)
            self._last_frontier_sig = sig
            QTimer.singleShot(20, lambda: self.scroll_to_frontier(smooth=not is_initial))