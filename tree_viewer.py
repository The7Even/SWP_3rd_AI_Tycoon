import os
import sys
import json
import copy
import shutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QPushButton, QLabel, QFrame, QFileDialog, QMessageBox,
    QSplitter, QFormLayout, QLineEdit, QSpinBox, QComboBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QShortcut, QKeySequence
from core.number_format import format_number


class FullTreeCanvas(QWidget):
    """잠금 해제 조건 없이 data/upgrades.json 전체 노드를 보여주고 선택할 수 있는 캔버스"""

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
        self.setMinimumWidth(620)
        self.rebuild(self.upgrades)

    def rebuild(self, upgrades: list[dict], select_id: str | None = None):
        self.upgrades = upgrades
        if select_id is not None:
            self.selected_id = select_id

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
            btn.setFixedSize(152, 66)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            uid = upg["id"]
            btn.clicked.connect(lambda checked, target_id=uid: self._handle_click(target_id))
            btn.show()
            self.node_buttons[uid] = btn

        total_height = self.top_margin + (max_row * self.row_height) + 80
        self.setMinimumHeight(total_height)
        self.resize(max(self.width(), 620), total_height)
        self._apply_all_styles()
        self._reposition_nodes()

    def _handle_click(self, uid: str):
        self.selected_id = uid
        self._apply_all_styles()
        self.update()
        target = next((u for u in self.upgrades if u["id"] == uid), None)
        if target:
            self.on_node_selected(target)

    def _apply_all_styles(self):
        for upg in self.upgrades:
            uid = upg["id"]
            btn = self.node_buttons.get(uid)
            if not btn:
                continue

            ntype = upg.get("type", "common")
            is_story = (ntype == "story" or isinstance(upg.get("story_event"), dict))
            style_key = "story" if is_story else ntype
            bg_c, hover_c, border_c, txt_c, type_kr = self.TYPE_STYLES.get(
                style_key, self.TYPE_STYLES["common"]
            )

            cost_str = format_number(float(upg.get("cost", 0)))
            if is_story and not str(upg["name"]).startswith("[STORY"):
                ev_num = upg.get("story_event", {}).get("number", "") if isinstance(upg.get("story_event"), dict) else ""
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
                f"설명: {upg.get('desc', '')}"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_nodes()

    def _reposition_nodes(self):
        w = max(self.width(), 620)
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
            cx = col_x.get(int(upg.get("col", 2)), int(w * 0.50))
            cy = self.top_margin + (int(upg.get("row", 1)) - 1) * self.row_height + 46
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


class UpgradeTreeEditorWindow(QMainWindow):
    # effects JSON에 바로 꽂아 넣을 수 있는 프리셋 목록
    EFFECT_PRESETS = [
        ("명령어당 토큰 추가 (+cmd_add)", {"cmd_add": 10}),
        ("명령어당 토큰 배율 (×cmd_mul)", {"cmd_mul": 1.5}),
        ("초당 토큰 추가 (+sec_add)", {"sec_add": 20}),
        ("초당 토큰 배율 (×sec_mul)", {"sec_mul": 1.5}),
        ("입력 쿨다운 단축 (cooldown_add)", {"cooldown_add": -15}),
        ("벤치마크 점수 증가 (bench_add)", {"bench_add": 500}),
        ("CPU 스펙 변경 (spec_cpu)", {"spec_cpu": "AMD Ryzen 9 7950X"}),
        ("GPU 스펙 변경 (spec_gpu)", {"spec_gpu": "NVIDIA RTX 4090 24GB"}),
        ("RAM 스펙 변경 (spec_ram)", {"spec_ram": "DDR5 128GB"}),
        ("스토리지 변경 (spec_storage)", {"spec_storage": "NVMe Gen5 4TB"}),
        ("도감 항목 해금 (unlock_dex)", {"unlock_dex": "col_small_llm"}),
        ("명령어 티어 상승 (tier_min)", {"tier_min": 2}),
        ("특이점 독대 진입 (trigger_singularity)", {"trigger_singularity": True}),
    ]

    def __init__(self, json_path: str = os.path.join("data", "upgrades.json")):
        super().__init__()
        self.json_path = json_path
        self.upgrades: list[dict] = []
        self.current_node_id: str | None = None
        self.is_dirty: bool = False

        self._load_upgrades()
        self.resize(1300, 880)
        self._init_ui()
        self._update_window_title()

        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save_json)

        if self.upgrades:
            self.canvas._handle_click(self.upgrades[0]["id"])

    def _load_upgrades(self):
        if not os.path.exists(self.json_path):
            QMessageBox.critical(None, "파일 없음", f"'{self.json_path}' 파일을 찾을 수 없습니다.")
            sys.exit(1)
        with open(self.json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("upgrades", []) if isinstance(raw, dict) else raw
        self.upgrades = copy.deepcopy(items)
        self.is_dirty = False

    def _update_window_title(self):
        mark = " *" if self.is_dirty else ""
        self.setWindowTitle(
            f"AI 키우기 - 업그레이드 트리 에디터 ({len(self.upgrades)}개 노드){mark}"
        )

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ================= [상단 툴바] =================
        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("background-color: #ffffff; border-bottom: 2px solid #d0d7de;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(6)

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

        tb_layout.addSpacing(12)

        btn_add = QPushButton("+ 노드 추가")
        btn_add.setFixedHeight(28)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #1a7f37; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 0px 10px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #116329; }
        """)
        btn_add.clicked.connect(self._add_new_node)
        tb_layout.addWidget(btn_add)

        btn_del = QPushButton("- 선택 삭제")
        btn_del.setFixedHeight(28)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #cf222e; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 0px 10px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #a40e26; }
        """)
        btn_del.clicked.connect(self._delete_selected_node)
        tb_layout.addWidget(btn_del)

        tb_layout.addStretch()

        btn_reload = QPushButton("되돌리기")
        btn_reload.setFixedHeight(28)
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa; color: #24292f;
                border: 1px solid #d0d7de; border-radius: 4px;
                padding: 0px 10px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """)
        btn_reload.clicked.connect(self._reload_from_file)
        tb_layout.addWidget(btn_reload)

        btn_export = QPushButton("PNG 저장")
        btn_export.setFixedHeight(28)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa; color: #24292f;
                border: 1px solid #d0d7de; border-radius: 4px;
                padding: 0px 10px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """)
        btn_export.clicked.connect(self._export_png)
        tb_layout.addWidget(btn_export)

        btn_save = QPushButton("JSON 저장 (Ctrl+S)")
        btn_save.setFixedHeight(28)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0969da; color: #ffffff;
                border: none; border-radius: 4px;
                padding: 0px 12px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background-color: #0860ca; }
        """)
        btn_save.clicked.connect(self._save_json)
        tb_layout.addWidget(btn_save)

        root.addWidget(toolbar)

        # ================= [좌측 트리 + 우측 에디터 스플리터] =================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측 트리 스크롤 영역
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: #f6f8fa;")
        self.canvas = FullTreeCanvas(self.upgrades, self._on_node_selected)
        self.scroll.setWidget(self.canvas)
        splitter.addWidget(self.scroll)

        # 우측 노드 편집 패널 (스크롤 지원)
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setMinimumWidth(420)
        editor_scroll.setStyleSheet("QScrollArea { border: none; border-left: 2px solid #d0d7de; background-color: #ffffff; }")

        editor_panel = QWidget()
        ed_layout = QVBoxLayout(editor_panel)
        ed_layout.setContentsMargins(16, 14, 16, 16)
        ed_layout.setSpacing(10)

        lbl_ed_title = QLabel("노드 속성 & JSON 프리셋 편집기")
        lbl_ed_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0969da;")
        ed_layout.addWidget(lbl_ed_title)

        editor_panel.setStyleSheet("""
            QWidget { background-color: #ffffff; }
            QLabel { font-size: 12px; font-weight: bold; color: #24292f; }
            QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                color: #1f2328;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
                background-color: #ffffff;
                border: 1px solid #0969da;
            }
        """)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.ed_id = QLineEdit()
        self.ed_name = QLineEdit()

        self.ed_chapter = QSpinBox()
        self.ed_chapter.setRange(0, 8)

        pos_row = QHBoxLayout()
        self.ed_row = QSpinBox()
        self.ed_row.setRange(1, 200)
        self.ed_col = QComboBox()
        self.ed_col.addItem("1 (좌)", 1)
        self.ed_col.addItem("2 (중)", 2)
        self.ed_col.addItem("3 (우)", 3)
        pos_row.addWidget(QLabel("Row:"))
        pos_row.addWidget(self.ed_row)
        pos_row.addWidget(QLabel("Col:"))
        pos_row.addWidget(self.ed_col)

        self.ed_type = QComboBox()
        self.ed_type.addItem("active (액티브 / SW)", "active")
        self.ed_type.addItem("passive (패시브 / HW)", "passive")
        self.ed_type.addItem("common (공통 / 중립)", "common")
        self.ed_type.addItem("story (스토리)", "story")

        self.ed_cost = QLineEdit()
        self.ed_cost.setPlaceholderText("숫자 입력 (예: 1500)")

        self.ed_req = QLineEdit()
        self.ed_req.setPlaceholderText("쉼표로 구분 (예: ch1_hw_ram1, ch1_hw_ssd1)")

        self.ed_desc = QPlainTextEdit()
        self.ed_desc.setFixedHeight(56)

        form.addRow("ID :", self.ed_id)
        form.addRow("이름 :", self.ed_name)
        form.addRow("챕터 :", self.ed_chapter)
        form.addRow("위치 :", pos_row)
        form.addRow("타입 :", self.ed_type)
        form.addRow("비용 :", self.ed_cost)
        form.addRow("선행(req) :", self.ed_req)
        form.addRow("설명 :", self.ed_desc)
        ed_layout.addLayout(form)

        # ---- 효과(effects) JSON + 프리셋 삽입 바 ----
        fx_header = QHBoxLayout()
        fx_header.setSpacing(6)
        lbl_fx = QLabel("효과 (effects JSON)")
        self.cmb_fx_preset = QComboBox()
        for label, payload in self.EFFECT_PRESETS:
            self.cmb_fx_preset.addItem(label, payload)

        btn_insert_fx = QPushButton("+ 추가")
        btn_insert_fx.setFixedHeight(26)
        btn_insert_fx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_insert_fx.setStyleSheet("""
            QPushButton {
                background-color: #ddf4ff; color: #0969da;
                border: 1px solid #54aeff; border-radius: 4px;
                padding: 0px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #b6e3ff; }
        """)
        btn_insert_fx.clicked.connect(self._insert_effect_preset)

        btn_fmt_fx = QPushButton("정렬")
        btn_fmt_fx.setFixedHeight(26)
        btn_fmt_fx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fmt_fx.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa; color: #24292f;
                border: 1px solid #d0d7de; border-radius: 4px;
                padding: 0px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """)
        btn_fmt_fx.clicked.connect(self._format_effects_json)

        fx_header.addWidget(lbl_fx)
        fx_header.addStretch()
        fx_header.addWidget(btn_fmt_fx)
        ed_layout.addLayout(fx_header)

        fx_preset_row = QHBoxLayout()
        fx_preset_row.setSpacing(6)
        fx_preset_row.addWidget(self.cmb_fx_preset, stretch=1)
        fx_preset_row.addWidget(btn_insert_fx)
        ed_layout.addLayout(fx_preset_row)

        self.ed_effects = QPlainTextEdit()
        self.ed_effects.setFixedHeight(130)
        self.ed_effects.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'D2Coding', monospace; font-size: 12px; }"
        )
        ed_layout.addWidget(self.ed_effects)

        # ---- 스토리(story_event) JSON + 원클릭 템플릿 버튼 ----
        st_header = QHBoxLayout()
        st_header.setSpacing(6)
        lbl_st = QLabel("스토리 이벤트 (story_event JSON, 선택)")

        btn_fill_story = QPushButton("기본 템플릿 채우기")
        btn_fill_story.setFixedHeight(26)
        btn_fill_story.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fill_story.setStyleSheet("""
            QPushButton {
                background-color: #fbefff; color: #8250df;
                border: 1px solid #d2a8ff; border-radius: 4px;
                padding: 0px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #ecd8ff; }
        """)
        btn_fill_story.clicked.connect(self._insert_story_template)

        btn_clear_story = QPushButton("비우기")
        btn_clear_story.setFixedHeight(26)
        btn_clear_story.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear_story.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa; color: #57606a;
                border: 1px solid #d0d7de; border-radius: 4px;
                padding: 0px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #eaeef2; }
        """)
        btn_clear_story.clicked.connect(self.ed_story.clear if hasattr(self, "ed_story") else lambda: self._clear_story_box())

        st_header.addWidget(lbl_st)
        st_header.addStretch()
        st_header.addWidget(btn_fill_story)
        st_header.addWidget(btn_clear_story)
        ed_layout.addLayout(st_header)

        self.ed_story = QPlainTextEdit()
        self.ed_story.setFixedHeight(125)
        self.ed_story.setPlaceholderText("비워두면 story_event 필드가 저장되지 않습니다.")
        self.ed_story.setStyleSheet(
            "QPlainTextEdit { font-family: 'Consolas', 'D2Coding', monospace; font-size: 11px; }"
        )
        ed_layout.addWidget(self.ed_story)

        # ---- 적용 버튼 & 상태 안내 ----
        self.btn_apply = QPushButton("노드 변경 적용 (트리에 즉시 반영)")
        self.btn_apply.setFixedHeight(36)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #8250df; color: #ffffff;
                border: none; border-radius: 5px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #6639ba; }
        """)
        self.btn_apply.clicked.connect(self._apply_node_changes)
        ed_layout.addWidget(self.btn_apply)

        self.lbl_status = QLabel("프리셋으로 JSON을 손쉽게 추가한 뒤 [노드 변경 적용] → [JSON 저장]을 눌러주세요.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #57606a; font-size: 11px; font-weight: normal;")
        ed_layout.addWidget(self.lbl_status)
        ed_layout.addStretch()

        editor_scroll.setWidget(editor_panel)
        splitter.addWidget(editor_scroll)
        splitter.setSizes([830, 470])
        root.addWidget(splitter, stretch=1)

    # ---------------- JSON 프리셋 & 템플릿 헬퍼 ----------------
    def _insert_effect_preset(self):
        preset_data = self.cmb_fx_preset.currentData()
        if not isinstance(preset_data, dict):
            return

        raw = self.ed_effects.toPlainText().strip() or "{}"
        try:
            current_obj = json.loads(raw)
            if not isinstance(current_obj, dict):
                raise ValueError("JSON 객체({})가 아닙니다.")
        except Exception as e:
            QMessageBox.warning(
                self,
                "현재 JSON 문법 오류",
                f"기존 effects JSON의 문법 오류를 먼저 고치거나 비운 뒤 추가해 주세요:\n{e}"
            )
            return

        current_obj.update(copy.deepcopy(preset_data))
        self.ed_effects.setPlainText(json.dumps(current_obj, ensure_ascii=False, indent=2))
        added_key = next(iter(preset_data.keys()))
        self.lbl_status.setText(f"프리셋 삽입됨: '{added_key}' 키가 effects JSON에 추가되었습니다.")

    def _format_effects_json(self):
        raw = self.ed_effects.toPlainText().strip() or "{}"
        try:
            obj = json.loads(raw)
            self.ed_effects.setPlainText(json.dumps(obj, ensure_ascii=False, indent=2))
            self.lbl_status.setText("effects JSON 자동 정렬 완료.")
        except Exception as e:
            QMessageBox.warning(self, "JSON 문법 오류", f"정렬할 수 없습니다:\n{e}")

    def _insert_story_template(self):
        # 현재 트리에 존재하는 최대 스토리 번호 + 1 자동 산출
        max_num = 0
        for u in self.upgrades:
            se = u.get("story_event")
            if isinstance(se, dict) and isinstance(se.get("number"), int):
                max_num = max(max_num, se["number"])

        chap_num = int(self.ed_chapter.value())
        node_title = self.ed_name.text().strip() or "새 스토리 이벤트"
        template = {
            "number": max_num + 1,
            "chapter": f"Chap {chap_num}. 소제목",
            "title": node_title,
            "node_role": "중간 노드",
            "content": "이곳에 스토리 팝업 본문을 작성하세요. ({ai_name}, {ai_version} 치환 가능)"
        }
        self.ed_story.setPlainText(json.dumps(template, ensure_ascii=False, indent=2))
        type_idx = self.ed_type.findData("story")
        if type_idx >= 0:
            self.ed_type.setCurrentIndex(type_idx)
        self.lbl_status.setText(f"스토리 템플릿(#{max_num + 1})이 생성되었습니다.")

    def _clear_story_box(self):
        self.ed_story.clear()

    # ---------------- 기존 트리 조작 및 저장 로직 ----------------
    def _jump_to_chapter(self, chap: int):
        y = self.canvas.get_chapter_y(chap)
        sb = self.scroll.verticalScrollBar()
        if sb:
            sb.setValue(y)

    def _on_node_selected(self, upg: dict):
        self.current_node_id = upg["id"]
        self.ed_id.setText(str(upg.get("id", "")))
        self.ed_name.setText(str(upg.get("name", "")))
        self.ed_chapter.setValue(int(upg.get("chapter", 1)))
        self.ed_row.setValue(int(upg.get("row", 1)))

        col_idx = self.ed_col.findData(int(upg.get("col", 2)))
        self.ed_col.setCurrentIndex(col_idx if col_idx >= 0 else 1)

        type_idx = self.ed_type.findData(str(upg.get("type", "common")))
        self.ed_type.setCurrentIndex(type_idx if type_idx >= 0 else 2)

        self.ed_cost.setText(str(upg.get("cost", 0)))
        self.ed_req.setText(", ".join(upg.get("req", [])))
        self.ed_desc.setPlainText(str(upg.get("desc", "")))
        self.ed_effects.setPlainText(
            json.dumps(upg.get("effects", {}), ensure_ascii=False, indent=2)
        )

        if isinstance(upg.get("story_event"), dict):
            self.ed_story.setPlainText(
                json.dumps(upg["story_event"], ensure_ascii=False, indent=2)
            )
        else:
            self.ed_story.clear()

        self.lbl_status.setText(f"편집 중: [{upg['id']}] {upg['name']}")

    def _apply_node_changes(self):
        if not self.current_node_id:
            return
        target = next((u for u in self.upgrades if u["id"] == self.current_node_id), None)
        if not target:
            return

        new_id = self.ed_id.text().strip()
        if not new_id:
            QMessageBox.warning(self, "입력 오류", "노드 ID는 비워둘 수 없습니다.")
            return
        if new_id != self.current_node_id and any(u["id"] == new_id for u in self.upgrades):
            QMessageBox.warning(self, "ID 중복", f"'{new_id}' ID가 이미 존재합니다.")
            return

        new_name = self.ed_name.text().strip() or new_id

        raw_cost = self.ed_cost.text().strip().replace(",", "")
        try:
            cost_num = float(raw_cost)
            new_cost = int(cost_num) if cost_num.is_integer() else cost_num
        except ValueError:
            QMessageBox.warning(self, "비용 오류", "비용(cost)은 숫자로 입력해야 합니다.")
            return

        raw_fx = self.ed_effects.toPlainText().strip() or "{}"
        try:
            new_effects = json.loads(raw_fx)
            if not isinstance(new_effects, dict):
                raise ValueError("JSON 객체({}) 형식이어야 합니다.")
        except Exception as e:
            QMessageBox.warning(self, "효과 JSON 오류", f"effects JSON 문법을 확인해주세요:\n{e}")
            return

        raw_story = self.ed_story.toPlainText().strip()
        new_story = None
        if raw_story:
            try:
                parsed_story = json.loads(raw_story)
                if not isinstance(parsed_story, dict):
                    raise ValueError("JSON 객체({}) 형식이어야 합니다.")
                new_story = parsed_story
            except Exception as e:
                QMessageBox.warning(self, "스토리 JSON 오류", f"story_event JSON 문법을 확인해주세요:\n{e}")
                return

        raw_reqs = [x.strip() for x in self.ed_req.text().split(",") if x.strip()]
        all_ids = {u["id"] for u in self.upgrades}
        all_ids.discard(self.current_node_id)
        all_ids.add(new_id)
        missing_reqs = [r for r in raw_reqs if r not in all_ids]
        if missing_reqs:
            reply = QMessageBox.question(
                self,
                "미존재 선행 노드 확인",
                f"다음 선행 노드 ID가 현재 트리에 없습니다:\n{', '.join(missing_reqs)}\n\n그래도 적용할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        old_id = self.current_node_id
        if new_id != old_id:
            for u in self.upgrades:
                if "req" in u and old_id in u["req"]:
                    u["req"] = [new_id if r == old_id else r for r in u["req"]]

        target["id"] = new_id
        target["name"] = new_name
        target["chapter"] = int(self.ed_chapter.value())
        target["row"] = int(self.ed_row.value())
        target["col"] = int(self.ed_col.currentData())
        target["type"] = str(self.ed_type.currentData())
        target["cost"] = new_cost
        target["req"] = raw_reqs
        target["desc"] = self.ed_desc.toPlainText().strip()
        target["effects"] = new_effects

        if new_story is not None:
            target["story_event"] = new_story
        elif "story_event" in target:
            del target["story_event"]

        self.current_node_id = new_id
        self.is_dirty = True
        self._update_window_title()
        self.canvas.rebuild(self.upgrades, select_id=new_id)
        self.lbl_status.setText(f"적용 완료: [{new_id}] {new_name} (저장은 Ctrl+S)")

    def _add_new_node(self):
        base_node = next((u for u in self.upgrades if u["id"] == self.current_node_id), None)
        if base_node:
            chap = int(base_node.get("chapter", 1))
            row = int(base_node.get("row", 1)) + 1
            col = int(base_node.get("col", 2))
            req_list = [base_node["id"]]
        else:
            chap = 1
            row = max((int(u.get("row", 1)) for u in self.upgrades), default=0) + 1
            col = 2
            req_list = []

        seq = 1
        while True:
            cand_id = f"ch{chap}_new_{seq}"
            if not any(u["id"] == cand_id for u in self.upgrades):
                break
            seq += 1

        new_node = {
            "id": cand_id,
            "chapter": chap,
            "row": row,
            "col": col,
            "name": "새 업그레이드",
            "type": "common",
            "cost": 100,
            "req": req_list,
            "desc": "새 노드 설명",
            "effects": {"cmd_add": 10}
        }
        self.upgrades.append(new_node)
        self.is_dirty = True
        self._update_window_title()
        self.canvas.rebuild(self.upgrades, select_id=cand_id)
        self._on_node_selected(new_node)
        self.lbl_status.setText(f"새 노드 추가됨: [{cand_id}] — 프리셋으로 효과를 추가해 보세요.")

    def _delete_selected_node(self):
        if not self.current_node_id:
            return
        target = next((u for u in self.upgrades if u["id"] == self.current_node_id), None)
        if not target:
            return

        reply = QMessageBox.warning(
            self,
            "노드 삭제 확인",
            f"[{target['id']}] {target['name']} 노드를 삭제할까요?\n"
            "다른 노드의 선행 조건(req)에서도 이 ID가 자동으로 제거됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        del_id = target["id"]
        self.upgrades = [u for u in self.upgrades if u["id"] != del_id]
        for u in self.upgrades:
            if "req" in u and del_id in u["req"]:
                u["req"] = [r for r in u["req"] if r != del_id]

        self.is_dirty = True
        self._update_window_title()

        next_id = self.upgrades[0]["id"] if self.upgrades else None
        self.current_node_id = next_id
        self.canvas.rebuild(self.upgrades, select_id=next_id)
        if next_id:
            self._on_node_selected(self.upgrades[0])
        self.lbl_status.setText(f"노드 삭제 완료: [{del_id}]")

    def _save_json(self):
        try:
            if os.path.exists(self.json_path):
                shutil.copy2(self.json_path, self.json_path + ".bak")

            sorted_upgrades = sorted(
                self.upgrades,
                key=lambda u: (int(u.get("chapter", 0)), int(u.get("row", 0)), int(u.get("col", 0)))
            )
            self.upgrades = sorted_upgrades

            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump({"upgrades": self.upgrades}, f, ensure_ascii=False, indent=2)

            self.is_dirty = False
            self._update_window_title()
            self.canvas.rebuild(self.upgrades, select_id=self.current_node_id)
            self.lbl_status.setText(f"저장 완료! ({self.json_path}, 백업: .bak)")
            QMessageBox.information(self, "저장 완료", f"'{self.json_path}' 파일이 안전하게 저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"JSON 저장 중 오류가 발생했습니다:\n{e}")

    def _reload_from_file(self):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "되돌리기 확인",
                "저장하지 않은 변경 사항이 모두 사라집니다. 파일에서 다시 불러올까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._load_upgrades()
        self._update_window_title()
        next_id = self.upgrades[0]["id"] if self.upgrades else None
        self.canvas.rebuild(self.upgrades, select_id=next_id)
        if next_id:
            self._on_node_selected(self.upgrades[0])
        self.lbl_status.setText("파일에서 원본 데이터를 다시 불러왔습니다.")

    def _export_png(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "업그레이드 트리 이미지 저장", "upgrade_tree_preview.png", "PNG Images (*.png)"
        )
        if save_path:
            pixmap = self.canvas.grab()
            pixmap.save(save_path, "PNG")
            QMessageBox.information(self, "저장 완료", f"전체 트리 이미지가 저장되었습니다:\n{save_path}")

    def closeEvent(self, event):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "저장하지 않은 변경 사항",
                "저장하지 않은 변경 사항이 있습니다. 저장하고 종료할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save_json()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = UpgradeTreeEditorWindow()
    win.show()
    sys.exit(app.exec())