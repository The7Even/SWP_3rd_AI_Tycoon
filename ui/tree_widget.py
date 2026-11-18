from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from core.number_format import format_number


class TreeCanvas(QWidget):
    """노드 간 직교 연결선과 챕터 구분선(미도달 시 정보 비공개)을 그리는 트리 캔버스"""

    CHAPTER_TITLES = {
        1: "CHAPTER 1 · 기초 연산 환경 구축",
        2: "CHAPTER 2 · 딥러닝 프레임워크 도입",
        3: "CHAPTER 3 · 하이브리드 파이프라인 & 첫 공개",
        4: "CHAPTER 4 · 아키텍처 도약 (AI 2.0)",
        5: "CHAPTER 5 · 상용화 & 유료 모델 (AI 3.0)",
        6: "CHAPTER 6 · 대중화 & 범용 지능 (AI 4.0~5.0)",
        7: "CHAPTER 7 · 국가 기간망 & 통제 경계 (AI 6.0~7.0)",
        8: "CHAPTER 8 · 특이점 (SINGULARITY)"
    }

    # 노드 타입별 색상 팔레트: (구매가능 배경색, 호버색, 구매가능 테두리색, 토큰부족 대기 테두리색)
    TYPE_COLORS = {
        "active": ("#cf222e", "#a40e26", "#82071e", "#ff8182"),  # 액티브(좌): 붉은색 계열
        "passive": ("#1a7f37", "#116329", "#0a461c", "#4ac26b"),  # 패시브(우): 녹색 계열
        "common": ("#0969da", "#0860ca", "#0550ae", "#54aeff"),  # 공통/중립(중): 푸른색 계열
        "story": ("#8250df", "#6639ba", "#512a97", "#a371f7"),  # 스토리/마일스톤(중): 보라색 계열
    }

    def __init__(self, game_state, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.node_buttons: dict[str, QPushButton] = {}
        self.node_centers: dict[str, QPoint] = {}
        self.chapter_rows: dict[int, int] = {}

        self.row_height = 104
        self.top_margin = 34
        self.setMinimumWidth(300)
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
            btn.setFixedSize(92, 62)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            uid = upg["id"]
            btn.clicked.connect(lambda checked, x=uid: self._on_node_clicked(x))
            self.node_buttons[uid] = btn

        total_height = self.top_margin + (max_row * self.row_height) + 70
        self.setMinimumHeight(total_height)
        self.resize(self.width(), total_height)

    def _on_node_clicked(self, upgrade_id: str):
        if self.game_state.purchase_upgrade(upgrade_id):
            self.update_node_states(scroll_to_next=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_nodes()

    def _reposition_nodes(self):
        w = max(self.width(), 300)
        col_x = {
            1: int(w * 0.22),
            2: int(w * 0.50),
            3: int(w * 0.78),
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

    def update_node_states(self, scroll_to_next: bool = False):
        if len(self.node_buttons) != len(self.game_state.upgrades):
            self._build_nodes()
            self._reposition_nodes()

        first_unlocked_y = None

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

            # 트리 전체 구조가 항상 다 보이도록 모든 노드를 표시
            btn.setVisible(True)

            if purchased:
                btn.setEnabled(True)
                if is_story:
                    btn.setText(f"★ {upg['name']}\n[완료]")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #fbefff; border: 2px solid #8250df;
                            border-radius: 6px; color: #512a97; font-size: 10px; font-weight: bold;
                        }
                    """)
                else:
                    btn.setText(f"{upg['name']}\n[완료]")
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #dafbe1; border: 2px solid #2da44e;
                            border-radius: 6px; color: #1a7f37; font-size: 10px; font-weight: bold;
                        }
                    """)
                btn.setToolTip(
                    f"{upg['name']} (Chap {upg.get('chapter', 1)})\n"
                    f"비용: {format_number(upg['cost'])} Token\n"
                    f"효과: {upg['desc']}"
                )
            elif unlocked:
                btn.setEnabled(True)
                if first_unlocked_y is None:
                    first_unlocked_y = btn.y()

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
                            background-color: {bg_c}; border: 2px solid {border_c};
                            border-radius: 6px; color: #ffffff; font-size: 10px; font-weight: bold;
                        }}
                        QPushButton:hover {{ background-color: {hover_c}; }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #ffffff; border: 2px solid {wait_border};
                            border-radius: 6px; color: #24292f; font-size: 10px; font-weight: bold;
                        }}
                    """)
                btn.setToolTip(
                    f"{upg['name']} (Chap {upg.get('chapter', 1)})\n"
                    f"비용: {format_number(upg['cost'])} Token\n"
                    f"효과: {upg['desc']}"
                )
            else:
                # 아직 열리지 않은 노드는 ??? (잠김)으로 표시하되 전체 구조 윤곽은 모두 노출
                btn.setEnabled(False)
                btn.setText("???\n(잠김)")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #eaeef2; border: 1px dashed #afb8c1;
                        border-radius: 6px; color: #6e7781; font-size: 10px;
                    }
                """)
                btn.setToolTip("이전 단계 업그레이드를 완료하면 해금됩니다.")

        self.update()

        if scroll_to_next and first_unlocked_y is not None:
            parent_scroll = self.parentWidget()
            while parent_scroll and not isinstance(parent_scroll, QScrollArea):
                parent_scroll = parent_scroll.parentWidget()
            if isinstance(parent_scroll, QScrollArea):
                parent_scroll.ensureVisible(150, first_unlocked_y + 40, 20, 140)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 도달(해금 또는 구매)한 챕터 판별: 도달하기 전까지는 챕터 제목 숨김
        reached_chapters = set()
        for upg in self.game_state.upgrades:
            uid = upg["id"]
            if upg["purchased"] or self.game_state.can_unlock(uid):
                reached_chapters.add(int(upg.get("chapter", 1)))

        # 1. 모든 챕터 구분선은 표시하되, 챕터 정보 텍스트는 도달한 챕터만 표시
        header_font = QFont("Malgun Gothic", 8, QFont.Weight.Bold)
        painter.setFont(header_font)
        for chap in sorted(self.chapter_rows.keys()):
            start_row = self.chapter_rows[chap]
            y_line = self.top_margin + (start_row - 1) * self.row_height - 10

            painter.setPen(QPen(QColor("#d0d7de"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(10, y_line, self.width() - 10, y_line)

            if chap in reached_chapters:
                painter.setPen(QPen(QColor("#57606a")))
                title = self.CHAPTER_TITLES.get(chap, f"CHAPTER {chap}")
                painter.drawText(14, y_line + 13, title)

        # 2. 트리 전체의 직교 연결선을 모두 렌더링
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
                    pen = QPen(QColor("#2da44e"), 2.5)
                elif req_node["purchased"]:
                    pen = QPen(QColor("#0969da"), 2.0)
                else:
                    pen = QPen(QColor("#afb8c1"), 1.5, Qt.PenStyle.DashLine)

                painter.setPen(pen)
                mid_y = (p_start.y() + p_end.y()) // 2
                painter.drawLine(p_start.x(), p_start.y(), p_start.x(), mid_y)
                painter.drawLine(p_start.x(), mid_y, p_end.x(), mid_y)
                painter.drawLine(p_end.x(), mid_y, p_end.x(), p_end.y())


class UpgradeTreeWidget(QFrame):
    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self.setStyleSheet("UpgradeTreeWidget { background-color: #f6f8fa; border-left: 2px solid #d0d7de; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("UPGRADE TREE")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(50)
        header.setStyleSheet("""
            background-color: #ffffff;
            border-bottom: 2px solid #d0d7de;
            font-size: 16px;
            font-weight: bold;
            color: #1f2328;
        """)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background-color: #f6f8fa;")

        self.canvas = TreeCanvas(self.game_state)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll)

    def refresh_tree(self):
        self.canvas.update_node_states(scroll_to_next=False)