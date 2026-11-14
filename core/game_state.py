from PyQt6.QtCore import QObject, pyqtSignal


class GameState(QObject):
    state_changed = pyqtSignal()
    news_added = pyqtSignal(str, str)  # (제목, 타입: 'story' | 'random')

    def __init__(self):
        super().__init__()
        self.tokens: float = 0.0
        self.tokens_per_command: float = 24.0
        self.tokens_per_sec: float = 6.0
        self.input_cooldown_ms: int = 200  # 초기 쿨다운 200ms

        # 초기 하드웨어 스펙
        self.specs = {
            "CPU": "Intel i5-12400F (로컬 테스트용)",
            "GPU": "내장 그래픽",
            "RAM": "DDR4 16GB",
            "STORAGE": "NVMe 512GB",
            "BENCH_SCORE": 120.0
        }

        # [row, col] 좌표를 포함한 업그레이드 노드 데이터
        # col: 1(Active/빨강), 2(Common/하늘 또는 Story/보라), 3(Passive/초록)
        self.upgrades = [
            {
                "id": "init_script",
                "row": 1, "col": 2,
                "name": "기초 스크립트",
                "type": "common",
                "cost": 50,
                "purchased": False,
                "req": [],
                "desc": "명령어당 토큰 +10"
            },
            {
                "id": "tokenizer_opt",
                "row": 2, "col": 2,
                "name": "토크나이저",
                "type": "common",
                "cost": 150,
                "purchased": False,
                "req": ["init_script"],
                "desc": "명령어당 토큰 +25, 쿨다운 감소"
            },
            {
                "id": "act_prompt_eng",
                "row": 3, "col": 1,
                "name": "프롬프트 튜닝",
                "type": "active",
                "cost": 400,
                "purchased": False,
                "req": ["tokenizer_opt"],
                "desc": "명령어당 토큰 2배 증가"
            },
            {
                "id": "pas_gpu_buy",
                "row": 3, "col": 3,
                "name": "RTX 3060 영입",
                "type": "passive",
                "cost": 400,
                "purchased": False,
                "req": ["tokenizer_opt"],
                "desc": "초당 토큰 +20, GPU 업그레이드"
            },
            {
                "id": "act_macro_v1",
                "row": 4, "col": 1,
                "name": "단축키 매크로",
                "type": "active",
                "cost": 800,
                "purchased": False,
                "req": ["act_prompt_eng"],
                "desc": "입력 쿨다운 50ms로 단축"
            },
            {
                "id": "pas_vram_expand",
                "row": 4, "col": 3,
                "name": "듀얼 GPU 구성",
                "type": "passive",
                "cost": 800,
                "purchased": False,
                "req": ["pas_gpu_buy"],
                "desc": "초당 토큰 +45"
            },
            {
                "id": "pre_milestone_sync",
                "row": 5, "col": 2,
                "name": "모델 가중치 병합",
                "type": "common",
                "cost": 1500,
                "purchased": False,
                "req": ["act_macro_v1", "pas_vram_expand"],
                "desc": "전체 토큰 생산 효율 1.5배"
            },
            {
                "id": "milestone_1",
                "row": 6, "col": 2,
                "name": "소형 LLM 배포",
                "type": "story",
                "cost": 3000,
                "purchased": False,
                "req": ["pre_milestone_sync"],
                "desc": "[마일스톤] 상용 API 서비스 개시"
            }
        ]

    def add_passive_tokens(self, dt_sec: float):
        if self.tokens_per_sec > 0:
            self.tokens += self.tokens_per_sec * dt_sec
            self.state_changed.emit()

    def complete_command(self):
        self.tokens += self.tokens_per_command
        self.state_changed.emit()

    def can_unlock(self, upgrade_id: str) -> bool:
        target = next((u for u in self.upgrades if u["id"] == upgrade_id), None)
        if not target or target["purchased"]:
            return False
        for req_id in target["req"]:
            req_node = next((u for u in self.upgrades if u["id"] == req_id), None)
            if not req_node or not req_node["purchased"]:
                return False
        return True

    def purchase_upgrade(self, upgrade_id: str) -> bool:
        target = next((u for u in self.upgrades if u["id"] == upgrade_id), None)
        if not target or not self.can_unlock(upgrade_id):
            return False
        if self.tokens < target["cost"]:
            return False

        self.tokens -= target["cost"]
        target["purchased"] = True
        self._apply_upgrade_effect(upgrade_id)
        self.state_changed.emit()
        return True

    def _apply_upgrade_effect(self, upgrade_id: str):
        if upgrade_id == "init_script":
            self.tokens_per_command += 10
            self.specs["BENCH_SCORE"] += 150
        elif upgrade_id == "tokenizer_opt":
            self.tokens_per_command += 25
            self.input_cooldown_ms = 120
            self.specs["BENCH_SCORE"] += 400
        elif upgrade_id == "act_prompt_eng":
            self.tokens_per_command *= 2
            self.specs["BENCH_SCORE"] += 1200
        elif upgrade_id == "pas_gpu_buy":
            self.tokens_per_sec += 20
            self.specs["GPU"] = "RTX 3060 12GB"
            self.specs["BENCH_SCORE"] += 2500
        elif upgrade_id == "act_macro_v1":
            self.input_cooldown_ms = 50
            self.tokens_per_command += 50
            self.specs["BENCH_SCORE"] += 3000
        elif upgrade_id == "pas_vram_expand":
            self.tokens_per_sec += 45
            self.specs["GPU"] = "Dual RTX 3060 (NVLink)"
            self.specs["BENCH_SCORE"] += 4500
        elif upgrade_id == "pre_milestone_sync":
            self.tokens_per_command *= 1.5
            self.tokens_per_sec *= 1.5
            self.specs["RAM"] = "DDR5 64GB"
            self.specs["BENCH_SCORE"] += 8000
        elif upgrade_id == "milestone_1":
            self.tokens_per_sec += 150
            self.specs["CPU"] = "Ryzen 9 7950X"
            self.specs["GPU"] = "RTX 4090 24GB"
            self.specs["BENCH_SCORE"] += 25000
            self.news_added.emit("1인 개발 AI, 최초 공개 후 커뮤니티 화제!", "story")