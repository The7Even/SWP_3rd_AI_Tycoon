import copy
import random
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal


class GameState(QObject):
    state_changed = pyqtSignal()
    news_added = pyqtSignal(dict)  # 뉴스 딕셔너리 전체 전달

    RANDOM_NEWS_POOL = [
        {
            "title": "InstantGram, AI 개발 우려 표명.. AI 산업 주춤",
            "content": "최근 InstantGram의 CEO가 제8차 AI 컨퍼런스에서 한 발언이 화제가 되고 있다. AI의 급격한 발전은 인류에게...",
            "category": "danger"
        },
        {
            "title": "글로벌 GPU 품귀 현상 심화, 그래픽카드 가격 20% 급등",
            "content": "전 세계적인 AI 학습 열풍으로 인해 고성능 연산 장비의 재고가 바닥나며 하드웨어 시장이 요동치고 있다.",
            "category": "danger"
        },
        {
            "title": "오픈소스 커뮤니티, 초경량 양자화 기법 논문 공개",
            "content": "기존 대비 절반 이하의 VRAM만으로도 동등한 추론 성능을 내는 새로운 알고리즘이 발표되어 개발자들의 환호를 받고 있다.",
            "category": "info"
        },
        {
            "title": "국내 대학생 개발자들 사이에서 '나만의 LLM 만들기' 열풍",
            "content": "기숙사 방 한켠에서 시작한 개인 AI 프로젝트가 잇따라 벤치마크 기록을 경신하며 업계의 주목을 받고 있다.",
            "category": "story"
        }
    ]

    INITIAL_UPGRADES = [
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

    def __init__(self):
        super().__init__()
        self.reset_state(emit_signal=False)

    def reset_state(self, emit_signal: bool = True):
        """게임 상태를 초기값으로 리셋"""
        self.tokens: float = 0.0
        self.tokens_per_command: float = 24.0
        self.tokens_per_sec: float = 6.0
        self.input_cooldown_ms: int = 200
        self.virtual_day_offset: int = 0

        self.specs = {
            "CPU": "Intel i5-12400F (로컬 테스트용)",
            "GPU": "내장 그래픽",
            "RAM": "DDR4 16GB",
            "STORAGE": "NVMe 512GB",
            "BENCH_SCORE": 120.0
        }

        self.news_history = [
            {
                "title": "1인 개발 AI, 최초 공개 후 커뮤니티 화제...",
                "date": "2026. 11. 05",
                "content": "지난밤 개인 개발자로부터 탄생한 초기 로컬 AI 모델이 공식적으로 첫 구동을 시작했다. 아직은 단순 명령어만 처리하지만...",
                "category": "story"
            },
            {
                "title": "InstantGram, AI 개발 우려 표명.. AI 산업 주춤",
                "date": "2026. 11. 04",
                "content": "최근 InstantGram의 CEO가 제8차 AI 컨퍼런스에서 한 발언이 화제가 되고 있다. AI의 개발은 인류에게...",
                "category": "danger"
            }
        ]

        self.ai_activities = [
            {"name": "로컬 백그라운드 토큰 마이닝", "rate": "6 Tk/s", "status": "가동 중"},
            {"name": "유료 API 베타 테스터 응답", "rate": "잠김 (소형 LLM 배포 후 해금)", "status": "대기"},
            {"name": "자율 데이터 크롤링 및 정제 파이프라인", "rate": "잠김 (상용 서비스 후 해금)", "status": "대기"}
        ]

        self.encyclopedia = [
            {"id": "col_hello_world", "name": "첫 번째 프롬프트", "desc": "로컬 환경에서 AI의 첫 응답을 받아냈다.", "unlocked": True},
            {"id": "col_rtx3060", "name": "가성비의 제왕 RTX 3060", "desc": "중고 그래픽카드를 영입해 본격적인 병렬 연산을 시작했다.", "unlocked": False},
            {"id": "col_small_llm", "name": "나만의 소형 LLM", "desc": "수능 1등급 수준의 추론 능력을 갖춘 모델을 배포했다.", "unlocked": False},
            {"id": "col_agi_spark", "name": "자아의 불꽃", "desc": "AI가 스스로 코드를 수정하기 시작한 흔적을 발견했다.", "unlocked": False}
        ]

        self.upgrades = copy.deepcopy(self.INITIAL_UPGRADES)

        if emit_signal:
            self.state_changed.emit()
            if self.news_history:
                self.news_added.emit(self.news_history[0])

    def to_dict(self) -> dict:
        """현재 상태를 저장 가능한 딕셔너리로 직렬화"""
        return {
            "version": 1,
            "tokens": self.tokens,
            "tokens_per_command": self.tokens_per_command,
            "tokens_per_sec": self.tokens_per_sec,
            "input_cooldown_ms": self.input_cooldown_ms,
            "virtual_day_offset": self.virtual_day_offset,
            "specs": copy.deepcopy(self.specs),
            "purchased_upgrades": [u["id"] for u in self.upgrades if u["purchased"]],
            "unlocked_encyclopedia": [d["id"] for d in self.encyclopedia if d["unlocked"]],
            "ai_activities": copy.deepcopy(self.ai_activities),
            "news_history": copy.deepcopy(self.news_history)
        }

    def from_dict(self, data: dict):
        """저장된 딕셔너리 데이터를 현재 상태에 복원"""
        self.reset_state(emit_signal=False)

        self.tokens = float(data.get("tokens", 0.0))
        self.tokens_per_command = float(data.get("tokens_per_command", 24.0))
        self.tokens_per_sec = float(data.get("tokens_per_sec", 6.0))
        self.input_cooldown_ms = int(data.get("input_cooldown_ms", 200))
        self.virtual_day_offset = int(data.get("virtual_day_offset", 0))

        if isinstance(data.get("specs"), dict):
            self.specs.update(data["specs"])

        purchased_ids = set(data.get("purchased_upgrades", []))
        for u in self.upgrades:
            u["purchased"] = (u["id"] in purchased_ids)

        unlocked_dex_ids = set(data.get("unlocked_encyclopedia", ["col_hello_world"]))
        for d in self.encyclopedia:
            d["unlocked"] = (d["id"] in unlocked_dex_ids)

        if isinstance(data.get("ai_activities"), list):
            self.ai_activities = copy.deepcopy(data["ai_activities"])

        if isinstance(data.get("news_history"), list) and len(data["news_history"]) > 0:
            self.news_history = copy.deepcopy(data["news_history"])

        self.state_changed.emit()
        if self.news_history:
            self.news_added.emit(self.news_history[0])

    def _get_current_game_date(self) -> str:
        base_date = datetime(2026, 11, 5) + timedelta(days=self.virtual_day_offset)
        self.virtual_day_offset += 1
        return base_date.strftime("%Y. %m. %d")

    def push_news(self, title: str, content: str, category: str = "info"):
        news_item = {
            "title": title,
            "date": self._get_current_game_date(),
            "content": content,
            "category": category
        }
        self.news_history.insert(0, news_item)
        if len(self.news_history) > 30:
            self.news_history.pop()
        self.news_added.emit(news_item)

    def trigger_random_news(self):
        sample = random.choice(self.RANDOM_NEWS_POOL)
        self.push_news(sample["title"], sample["content"], sample["category"])

    def unlock_encyclopedia(self, item_id: str):
        for item in self.encyclopedia:
            if item["id"] == item_id and not item["unlocked"]:
                item["unlocked"] = True
                break

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
            self.unlock_encyclopedia("col_rtx3060")
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec)} Tk/s"
        elif upgrade_id == "act_macro_v1":
            self.input_cooldown_ms = 50
            self.tokens_per_command += 50
            self.specs["BENCH_SCORE"] += 3000
        elif upgrade_id == "pas_vram_expand":
            self.tokens_per_sec += 45
            self.specs["GPU"] = "Dual RTX 3060 (NVLink)"
            self.specs["BENCH_SCORE"] += 4500
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec)} Tk/s"
        elif upgrade_id == "pre_milestone_sync":
            self.tokens_per_command *= 1.5
            self.tokens_per_sec *= 1.5
            self.specs["RAM"] = "DDR5 64GB"
            self.specs["BENCH_SCORE"] += 8000
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec)} Tk/s"
        elif upgrade_id == "milestone_1":
            self.tokens_per_sec += 150
            self.specs["CPU"] = "Ryzen 9 7950X"
            self.specs["GPU"] = "RTX 4090 24GB"
            self.specs["BENCH_SCORE"] += 25000
            self.unlock_encyclopedia("col_small_llm")
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec)} Tk/s"
            self.ai_activities[1] = {"name": "유료 API 베타 테스터 응답", "rate": "150 Tk/s", "status": "가동 중"}
            self.push_news(
                "OO, 개인 개발 AI 최초 수능 1등급 달성",
                "최근 1인 개발로 탄생한 AI 모델 OO이 모의 수능 전 과목 1등급을 달성하며 학계와 산업계의 이목을 끌었다...",
                "info"
            )