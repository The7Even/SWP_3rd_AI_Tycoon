import os
import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QPushButton, QLabel, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from core.number_format import format_number


class FullTreeCanvas(QWidget):
    """잠금 해제 조건 없이 data/upgrades.json 전체 노드를 한눈에 보여주는 시각화 캔버스"""

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

    # (배경색, 호버색, 테두리색, 텍스트색, 한글 라벨)
    TYPE_STYLES = {
        "active":  ("#cf222e", "#a40e26", "#82071e", "#ffffff", "액티브(SW)"),
        "passive": ("#1a7f37", "#116329", "#0a461c", "#ffffff", "패시브(HW)"),
        "common":  ("#0969da", "#0860ca", "#0550ae", "#ffffff", "공통(중립)"),
        "story":   ("#8250df", "#6639ba", "#512a97", "#ffffff", "스토리"),
    }

    def __init__(self, upgrades: list[dict], on_node_selected, parent=None):
        super().__init__(parent)
        self.upgrades = upgrades
        self.on_node_selected = on_node_selected
        self.selected_id: str | None = None

        self.node_buttons: dict[str, QPushButton] = {}
        self.node_centers: dict[str, QPoint] = {}
        self.chapter_rows: dict[int, int] = {}

        self.row_height = 108
        self.top_margin = 36
        self.setMinimumWidth(680)
        self._build_nodes()

    def _build_nodes(self):
        for btn in self.node_buttons.values():
            btn.deleteLater()
        self.node_buttons.clear()
        self.chapter_rows.clear()

        max_row = 1
        for upg in self.upgrades:
            row = int(upg.get("row", 1))
            chap = int(upg.get("chapter", 1))
            if row > max_row:
                max_row = row
            if chap not in self.chapter_rows or row < self.chapter_rows[chap]:
                self.chapter_rows[chap] = row

            btn = QPushButton(self)
            btn.setFixedSize(156, 66)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            uid = upg["id"]
            btn.clicked.connect(lambda checked, u=upg: self._handle_click(u))
            self.node_buttons[uid] = btn

        total_height = self.top_margin + (max_row * self.row_height) + 60
        self.setMinimumHeight(total_height)
        self.resize(max(self.width(), 680), total_height)
        self._apply_all_styles()

    def _handle_click(self, upg: dict):
        self.selected_id = upg["id"]
        self._apply_all_styles()
        self.on_node_selected(upg)

    def _apply_all_styles(self):
        for upg in self.upgrades:
            uid = upg["id"]
            btn = self.node_buttons[uid]
            ntype = upg.get("type", "common")
            is_story = (ntype == "story" or isinstance(upg.get("story_event"), dict))
            style_key = "story" if is_story else ntype
            bg_c, hover_c, border_c, txt_c, type_kr = self.TYPE_STYLES.get(
                style_key, self.TYPE_STYLES["common"]
            )

            cost_str = format_number(upg.get("cost", 0))
            if is_story:
                ev_num = upg.get("story_event", {}).get("number", "")
                prefix = f"[STORY #{ev_num}] " if ev_num else "[STORY] "
                btn.setText(f"{prefix}{upg['name']}\n({cost_str} Tk)")
            else:
                btn.setText(f"{upg['name']}\n({cost_str} Tk)")

            is_selected = (uid == self.selected_id)
            sel_border = "3px solid #ffd33d" if is_selected else f"2px solid {border_c}"

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_c};
                    border: {sel_border};
                    border-radius: 6px;
                    color: {txt_c};
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px;
                }}
                QPushButton:hover {{
                    background-color: {hover_c};
                }}
            """)

            req_str = ", ".join(upg.get("req", [])) or "없음"
            btn.setToolTip(
                f"[{type_kr}] {upg['name']} (ID: {uid})\n"
                f"챕터: Chap {upg.get('chapter', 0)} | 위치: Row {upg.get('row')}, Col {upg.get('col')}\n"
                f"비용: {cost_str} Token | 선행 노드: {req_str}\n"
                f"설명: {upg.get('desc', '')}\n"
                f"효과: {json.dumps(upg.get('effects', {}), ensure_ascii=False)}"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_nodes()

    def _reposition_nodes(self):
        w = max(self.width(), 680)
        col_x = {
            1: int(w * 0.20),
            2: int(w * 0.50),
            3: int(w * 0.80),
        }

        self.node_centers.clear()
        for upg in self.upgrades:
            uid = upg["id"]
            btn = self.node_buttons.get(uid)
            if not btn:
                continue
            cx = col_x.get(upg.get("col", 2), int(w * 0.50))
            cy = self.top_margin + (upg.get("row", 1) - 1) * self.row_height + 46
            btn.move(cx - btn.width() // 2, cy - btn.height() // 2)
            self.node_centers[uid] = QPoint(cx, cy)

        self.update()

    def get_chapter_y(self, chap: int) -> int:
        row = self.chapter_rows.get(chap, 1)
        return max(0, self.top_margin + (row - 1) * self.row_height - 16)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. 모든 챕터 구분선 및 제목 표시
        header_font = QFont("Malgun Gothic", 9, QFont.Weight.Bold)
        painter.setFont(header_font)
        for chap in sorted(self.chapter_rows.keys()):
            start_row = self.chapter_rows[chap]
            y_line = self.top_margin + (start_row - 1) * self.row_height - 12

            painter.setPen(QPen(QColor("#8c959f"), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(16, y_line, self.width() - 16, y_line)

            painter.setPen(QPen(QColor("#1f2328")))
            title = self.CHAPTER_TITLES.get(chap, f"CHAPTER {chap}")
            painter.drawText(20, y_line + 14, title)

        # 2. 직교 연결선 렌더링
        for upg in self.upgrades:
            uid = upg["id"]
            p_end = self.node_centers.get(uid)
            if not p_end:
                continue

            for req_id in upg.get("req", []):
                p_start = self.node_centers.get(req_id)
                if not p_start:
                    continue

                is_highlight = (uid == self.selected_id or req_id == self.selected_id)
                pen = QPen(
                    QColor("#d29922" if is_highlight else "#57606a"),
                    2.6 if is_highlight else 1.8
                )
                painter.setPen(pen)

                mid_y = (p_start.y() + p_end.y()) // 2
                painter.drawLine(p_start.x(), p_start.y(), p_start.x(), mid_y)
                painter.drawLine(p_start.x(), mid_y, p_end.x(), mid_y)
                painter.drawLine(p_end.x(), mid_y, p_end.x(), p_end.y())


class UpgradeTreeVisualizerWindow(QMainWindow):
    def __init__(self, json_path: str = os.path.join("data", "upgrades.json")):
        super().__init__()
        self.json_path = json_path
        self.upgrades = self._load_upgrades()

        self.setWindowTitle(f"AI 키우기 - 전체 업그레이드 트리 시각화 ({len(self.upgrades)}개 노드)")
        self.resize(960, 820)

        self._init_ui()

    def _load_upgrades(self) -> list[dict]:
        if not os.path.exists(self.json_path):
            QMessageBox.critical(None, "파일 없음", f"'{self.json_path}' 파일을 찾을 수 없습니다.")
            sys.exit(1)
        with open(self.json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("upgrades", []) if isinstance(raw, dict) else raw

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 상단 툴바: 범례 + 챕터 점프 버튼 + PNG 내보내기
        toolbar = QFrame()
        toolbar.setFixedHeight(48)
        toolbar.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #d0d7de;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(6)

        legend = QLabel("● 액티브(SW)  ● 패시브(HW)  ● 공통  ● 스토리")
        legend.setStyleSheet("font-size: 12px; font-weight: bold; color: #24292f;")
        tb_layout.addWidget(legend)
        tb_layout.addSpacing(12)

        for chap in range(0, 9):
            btn_c = QPushButton(f"Ch.{chap}")
            btn_c.setFixedSize(44, 28)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.setStyleSheet("""
                QPushButton {
                    background-color: #f6f8fa; border: 1px solid #d0d7de;
                    border-radius: 4px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background-color: #eaeef2; }
            """)
            btn_c.clicked.connect(lambda checked, c=chap: self._jump_to_chapter(c))
            tb_layout.addWidget(btn_c)

        tb_layout.addStretch()

        btn_export = QPushButton("전체 트리 PNG 저장")
        btn_export.setFixedHeight(28)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #0969da; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 0px 12px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0860ca; }
        """)
        btn_export.clicked.connect(self._export_png)
        tb_layout.addWidget(btn_export)
        root.addWidget(toolbar)

        # 중앙 스크롤 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: #f6f8fa;")
        self.canvas = FullTreeCanvas(self.upgrades, self._on_node_selected)
        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll, stretch=1)

        # 하단 노드 상세 인스펙터 바
        inspector = QFrame()
        inspector.setFixedHeight(86)
        inspector.setStyleSheet("background-color: #ffffff; border-top: 2px solid #d0d7de;")
        insp_layout = QVBoxLayout(inspector)
        insp_layout.setContentsMargins(14, 8, 14, 8)
        insp_layout.setSpacing(4)

        self.lbl_insp_title = QLabel("노드를 클릭하면 상세 스펙과 선행 조건, 효과 JSON이 여기에 표시됩니다.")
        self.lbl_insp_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #0969da;")

        self.lbl_insp_detail = QLabel("총 노드 수: " + str(len(self.upgrades)) + "개 (Chap 0 ~ Chap 8)")
        self.lbl_insp_detail.setWordWrap(True)
        self.lbl_insp_detail.setStyleSheet("font-size: 12px; color: #24292f;")

        insp_layout.addWidget(self.lbl_insp_title)
        insp_layout.addWidget(self.lbl_insp_detail)
        root.addWidget(inspector)

    def _jump_to_chapter(self, chap: int):
        y = self.canvas.get_chapter_y(chap)
        sb = self.scroll.verticalScrollBar()
        if sb:
            sb.setValue(y)

    def _on_node_selected(self, upg: dict):
        req_str = ", ".join(upg.get("req", [])) or "없음"
        cost_str = format_number(upg.get("cost", 0))
        self.lbl_insp_title.setText(
            f"[{upg.get('id')}] {upg.get('name')}  |  Chap {upg.get('chapter')} (Row {upg.get('row')}, Col {upg.get('col')})  |  비용: {cost_str} Token"
        )
        self.lbl_insp_detail.setText(
            f"설명: {upg.get('desc')}   ||   선행 노드: [{req_str}]   ||   효과: {json.dumps(upg.get('effects', {}), ensure_ascii=False)}"
        )

    def _export_png(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "업그레이드 트리 이미지 저장", "upgrade_tree_preview.png", "PNG Images (*.png)"
        )
        if save_path:
            pixmap = self.canvas.grab()
            pixmap.save(save_path, "PNG")
            QMessageBox.information(self, "저장 완료", f"전체 트리 이미지가 저장되었습니다:\n{save_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = UpgradeTreeVisualizerWindow()
    win.show()
    sys.exit(app.exec())