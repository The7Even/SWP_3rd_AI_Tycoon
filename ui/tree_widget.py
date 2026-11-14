from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QToolTip
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QRectF
from core.number_format import format_number


class SkillTreeCanvas(QWidget):
    """QPainter를 이용해 직각 연결선과 [row, col] 노드를 직접 렌더링하고 클릭/호버를 처리하는 캔버스"""

    def __init__(self, game_state, parent=None):
        super().__init__(parent)
        self.game_state = game_state
        self.node_width = 88
        self.node_height = 48
        self.row_gap = 82
        self.top_margin = 55

        self.setMouseTracking(True)
        self.hovered_node_id = None
        self._update_canvas_height()

    def _update_canvas_height(self):
        if not self.game_state.upgrades:
            self.setMinimumHeight(600)
            return
        max_row = max(u["row"] for u in self.game_state.upgrades)
        total_height = self.top_margin + max_row * self.row_gap + 40
        self.setMinimumHeight(max(600, total_height))

    def get_node_center(self, row: int, col: int):
        w = self.width()
        # 가로축 1(Active: 25%), 2(Common/Story: 50%), 3(Passive: 75%)
        x_map = {1: w * 0.25, 2: w * 0.50, 3: w * 0.75}
        center_x = x_map.get(col, w * 0.50)
        center_y = self.top_margin + (row - 1) * self.row_gap
        return center_x, center_y

    def get_node_rect(self, row: int, col: int) -> QRectF:
        cx, cy = self.get_node_center(row, col)
        return QRectF(
            cx - self.node_width / 2,
            cy - self.node_height / 2,
            self.node_width,
            self.node_height
        )

    def get_node_color(self, node: dict) -> QColor:
        """노드 타입 및 잠금/구매 상태에 따른 색상 반환"""
        base_colors = {
            "common": QColor("#7CC3F2"),   # 하늘색
            "active": QColor("#FF7676"),   # 빨간색
            "passive": QColor("#A5D6A7"),  # 초록색
            "story": QColor("#D197E6")     # 보라색
        }
        base = base_colors.get(node["type"], QColor("#7CC3F2"))

        if node["purchased"]:
            return base
        elif self.game_state.can_unlock(node["id"]):
            # 해금되었으나 아직 미구매 상태 (살짝 연하게 표시)
            if self.game_state.tokens >= node["cost"]:
                return base.lighter(108)
            else:
                return base.lighter(122)
        else:
            # 선행 조건 미달성 (잠김)
            return QColor("#D8DEE4")

    def _find_node_at(self, pos) -> dict | None:
        for node in self.game_state.upgrades:
            rect = self.get_node_rect(node["row"], node["col"])
            if rect.contains(pos):
                return node
        return None

    def mouseMoveEvent(self, event):
        node = self._find_node_at(event.position())
        new_hover_id = node["id"] if node else None

        if new_hover_id != self.hovered_node_id:
            self.hovered_node_id = new_hover_id
            if node:
                if node["purchased"] or self.game_state.can_unlock(node["id"]):
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    cost_str = format_number(node["cost"])
                    status = "완료됨" if node["purchased"] else f"비용: {cost_str} Tk"
                    tip = f"[{node['name']}]\n{node['desc']}\n({status})"
                else:
                    self.setCursor(Qt.CursorShape.ForbiddenCursor)
                    tip = "선행 업그레이드를 먼저 완료해야 합니다."
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
                QToolTip.hideText()
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            node = self._find_node_at(event.position())
            if node and self.game_state.can_unlock(node["id"]):
                if self.game_state.purchase_upgrade(node["id"]):
                    self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. 배경 클리어
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        # 행(row)별로 노드 정리
        rows = {}
        for node in self.game_state.upgrades:
            rows.setdefault(node["row"], []).append(node)
        sorted_row_keys = sorted(rows.keys())

        # 2. 연결선(Edges) 및 마일스톤 구분 점선 그리기
        pen_line = QPen(QColor("#1E1E1E"), 2)
        painter.setPen(pen_line)

        for i in range(len(sorted_row_keys) - 1):
            r1 = sorted_row_keys[i]
            r2 = sorted_row_keys[i + 1]
            nodes1 = rows[r1]
            nodes2 = rows[r2]

            # 다음 행에 story(마일스톤) 노드가 있으면 계획서 3.2절처럼 가로 점선 경계선 표시
            if any(n["type"] == "story" for n in nodes2):
                _, y1 = self.get_node_center(r1, 2)
                _, y2 = self.get_node_center(r2, 2)
                dash_y = int((y1 + y2) / 2)
                pen_dash = QPen(QColor("#57606A"), 1.5, Qt.PenStyle.DashLine)
                painter.setPen(pen_dash)
                painter.drawLine(15, dash_y, self.width() - 15, dash_y)
                painter.setPen(pen_line)

            for n1 in nodes1:
                c1 = n1["col"]
                x1, y1 = self.get_node_center(r1, c1)
                bottom_y = y1 + self.node_height / 2

                for n2 in nodes2:
                    c2 = n2["col"]
                    # 연결 조건: 같은 열이거나, 중앙(2)과 양옆(1,3)이 이어질 때
                    if c1 == c2 or {c1, c2} in [{1, 2}, {2, 3}]:
                        x2, y2 = self.get_node_center(r2, c2)
                        top_y = y2 - self.node_height / 2
                        mid_y = (bottom_y + top_y) / 2

                        if abs(x1 - x2) < 1:
                            painter.drawLine(int(x1), int(bottom_y), int(x2), int(top_y))
                        else:
                            painter.drawLine(int(x1), int(bottom_y), int(x1), int(mid_y))
                            painter.drawLine(int(x1), int(mid_y), int(x2), int(mid_y))
                            painter.drawLine(int(x2), int(mid_y), int(x2), int(top_y))

        # 3. 노드 박스 및 텍스트 그리기
        font_title = QFont("Malgun Gothic", 8, QFont.Weight.Bold)
        font_sub = QFont("Malgun Gothic", 7)

        for node in self.game_state.upgrades:
            rect = self.get_node_rect(node["row"], node["col"])
            is_unlocked = self.game_state.can_unlock(node["id"])
            can_afford = is_unlocked and (self.game_state.tokens >= node["cost"])
            is_hovered = (node["id"] == self.hovered_node_id)

            # 테두리 스타일 결정
            if node["purchased"]:
                pen_border = QPen(QColor("#111111"), 2.5)
            elif can_afford:
                pen_border = QPen(QColor("#0969DA"), 2.5 if is_hovered else 2.0)
            elif is_unlocked:
                pen_border = QPen(QColor("#57606A"), 1.5, Qt.PenStyle.DashLine)
            else:
                pen_border = QPen(QColor("#8C959F"), 1.2)

            painter.setPen(pen_border)
            painter.setBrush(QBrush(self.get_node_color(node)))
            painter.drawRoundedRect(rect, 4, 4)

            # 노드 내부 텍스트 렌더링
            if node["purchased"]:
                painter.setPen(QColor("#111111"))
                painter.setFont(font_title)
                painter.drawText(rect.adjusted(2, 4, -2, -16), Qt.AlignmentFlag.AlignCenter, node["name"])
                painter.setFont(font_sub)
                painter.drawText(rect.adjusted(2, 22, -2, -2), Qt.AlignmentFlag.AlignCenter, "[완료]")
            elif is_unlocked:
                painter.setPen(QColor("#111111") if can_afford else QColor("#424A53"))
                painter.setFont(font_title)
                painter.drawText(rect.adjusted(2, 4, -2, -16), Qt.AlignmentFlag.AlignCenter, node["name"])
                painter.setFont(font_sub)
                cost_text = f"{format_number(node['cost'])} Tk"
                painter.drawText(rect.adjusted(2, 22, -2, -2), Qt.AlignmentFlag.AlignCenter, cost_text)
            else:
                painter.setPen(QColor("#6E7781"))
                painter.setFont(font_title)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "???")


class UpgradeTreeWidget(QFrame):
    """상단 Active | Passive 헤더와 스크롤 영역을 포함하는 우측 패널 컨테이너"""

    def __init__(self, game_state):
        super().__init__()
        self.game_state = game_state
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            UpgradeTreeWidget {
                background-color: #ffffff;
                border-left: 2px solid #d0d7de;
            }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 상단 Active | Passive 헤더
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #d0d7de;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        lbl_active = QLabel("Active")
        lbl_active.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_active.setStyleSheet("font-weight: bold; font-size: 15px; border-right: 1px solid #d0d7de;")

        lbl_passive = QLabel("Passive")
        lbl_passive.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_passive.setStyleSheet("font-weight: bold; font-size: 15px;")

        header_layout.addWidget(lbl_active)
        header_layout.addWidget(lbl_passive)
        main_layout.addWidget(header)

        # 스크롤 가능한 QPainter 트리 캔버스
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: #ffffff;")

        self.canvas = SkillTreeCanvas(self.game_state)
        scroll.setWidget(self.canvas)
        main_layout.addWidget(scroll)

    def refresh_tree(self):
        self.canvas.update()