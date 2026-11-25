from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from core.number_format import format_number


class TreeCanvas(QWidget):
    """다크 회로도(도트 격자 + 직교 연결선 + 챕터 구분선) 기반 업그레이드 트리 캔버스"""

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

    # 다크 UI 전용 노드 타입별 색상: (구매가능 배경, 호버 배경, 구매가능 테두리, 대기 테두리)
    TYPE_COLORS = {
        "active":  ("#b62324", "#da3633", "#ff7b72", "#f85149"),  # 액티브(좌): 코랄 레드
        "passive": ("#196c2e", "#238636", "#56d364", "#3fb950"),  # 패시브(우): 에메랄드 그린
        "common":  ("#1158c7", "#1f6feb", "#79c0ff", "#58a6ff"),  # 공통/중립(중): 일렉트릭 블루
        "story":   ("#6e40c9", "#8957e5", "#d2a8ff", "#bc8cff"),  # 스토리/마일스톤: 네온 라벤더
    }

    def __init__(self, game_state, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.node_buttons: dict[str, QPushButton] = {}
        self.node_centers: dict[str, QPoint] = {}
        self.chapter_rows: dict[int, int] = {}

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

    def update_node_states(self):
        if len(self.node_buttons) != len(self.game_state.upgrades):
            self._build_nodes()
            self._reposition_nodes()

        for upg in self.game_state.upgrades:
            uid = upg["id"]
            btn = self.node_buttons[uid]
            purchased = upg["purchased"]
            unlocked = self.game_state.can_unlock(uid)
            affordable = self.game_state.tokens >= upg["cost"]
            ntype = upg.get("type", "common")
            is_story = (ntype == "story" or isinstance(upg.get("story_event"), dict))
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

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 0. 다크 배경 및 미세 도트 격자 패턴 (16px 간격)
        painter.fillRect(self.rect(), QColor("#0d1117"))
        dot_pen = QPen(QColor("#21262d"), 1.5)
        painter.setPen(dot_pen)
        rect = event.rect()
        start_x = (rect.left() // 16) * 16
        start_y = (rect.top() // 16) * 16
        for x in range(start_x, rect.right() + 1, 16):
            for y in range(start_y, rect.bottom() + 1, 16):
                painter.drawPoint(x, y)

        # 도달(해금 또는 구매)한 챕터 판별
        reached_chapters = set()
        for upg in self.game_state.upgrades:
            uid = upg["id"]
            if upg["purchased"] or self.game_state.can_unlock(uid):
                reached_chapters.add(int(upg.get("chapter", 1)))

        # 1. 챕터 구분선 및 도달 챕터 제목
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

        # 2. 트리 전체 직교 연결선 렌더링
        for upg in self.game_state.upgrades:
            uid = upg["id"]
            p_end = self.node_centers.get(uid)
            if not p_end:
                continue

            for req_id in upg["req"]:
                p_start = self.node_centers.get(req_id)
                req_node = next((u for u in self.game_state.upgrades if u["id"] == req_id), None)
                if not p_start or not req_node:
                    continue

                if req_node["purchased"] and upg["purchased"]:
                    pen = QPen(QColor("#3fb950"), 2.5)
                elif req_node["purchased"]:
                    pen = QPen(QColor("#58a6ff"), 2.0)
                else:
                    pen = QPen(QColor("#21262d"), 1.5, Qt.PenStyle.DashLine)

                painter.setPen(pen)
                mid_y = (p_start.y() + p_end.y()) // 2
                painter.drawLine(p_start.x(), p_start.y(), p_start.x(), mid_y)
                painter.drawLine(p_start.x(), mid_y, p_end.x(), mid_y)
                painter.drawLine(p_end.x(), mid_y, p_end.x(), p_end.y())


class UpgradeTreeWidget(QFrame):
    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self.setStyleSheet("UpgradeTreeWidget { background-color: #0d1117; border-left: 1px solid #30363d; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 상단 헤더 (타이틀 + 4색 범례)
        header = QFrame()
        header.setFixedHeight(58)
        header.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d;")
        header_vbox = QVBoxLayout(header)
        header_vbox.setContentsMargins(8, 6, 8, 6)
        header_vbox.setSpacing(3)

        lbl_title = QLabel("UPGRADE TREE")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("""
            background-color: transparent;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 1px;
            color: #e6edf3;
            border: none;
        """)
        header_vbox.addWidget(lbl_title)

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
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
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll)

    def refresh_tree(self):
        self.canvas.update_node_states()