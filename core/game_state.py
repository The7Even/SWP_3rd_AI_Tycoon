import os
import json
import copy
import random
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal


class GameState(QObject):
    state_changed = pyqtSignal()
    news_added = pyqtSignal(dict)
    unread_news_changed = pyqtSignal(int)
    command_tier_changed = pyqtSignal(int)
    story_event_triggered = pyqtSignal(dict)
    singularity_reached = pyqtSignal()

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
            "category": "info"
        }
    ]

    FALLBACK_UPGRADES = [
        {
            "id": "ch1_start",
            "chapter": 1,
            "row": 1, "col": 2,
            "name": "AI 개발 착수",
            "type": "story",
            "cost": 30,
            "req": [],
            "desc": "[Chap 1 시작] 하드웨어 업그레이드 해금, 명령어당 토큰 +6",
            "effects": {"cmd_add": 6, "bench_add": 100}
        }
    ]

    def __init__(self, upgrades_path: str = os.path.join("data", "upgrades.json")):
        super().__init__()
        self.upgrades_path = upgrades_path
        self.base_upgrades = self._load_upgrades_from_json()
        self.reset_state(emit_signal=False)

    def _load_upgrades_from_json(self) -> list[dict]:
        """외부 JSON 파일(data/upgrades.json)에서 전체 노드 및 스토리 이벤트 데이터 로드"""
        if not os.path.exists(self.upgrades_path):
            return copy.deepcopy(self.FALLBACK_UPGRADES)

        try:
            with open(self.upgrades_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("upgrades", []) if isinstance(raw, dict) else raw
            if isinstance(items, list) and len(items) > 0:
                valid = []
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        node = copy.deepcopy(it)
                        node["purchased"] = False
                        node.setdefault("req", [])
                        node.setdefault("effects", {})
                        node.setdefault("chapter", 1)
                        valid.append(node)
                if valid:
                    return valid
        except Exception:
            pass
        return copy.deepcopy(self.FALLBACK_UPGRADES)

    def reset_state(self, emit_signal: bool = True):
        """게임 상태를 초기값으로 리셋"""
        self.tokens: float = 0.0
        self.tokens_per_command: float = 24.0
        self.tokens_per_sec: float = 6.0
        self.input_cooldown_ms: int = 200
        self.command_tier: int = 1
        self.virtual_day_offset: int = 0
        self.unread_news_count: int = 0

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
                "category": "story",
                "is_milestone": False
            },
            {
                "title": "InstantGram, AI 개발 우려 표명.. AI 산업 주춤",
                "date": "2026. 11. 04",
                "content": "최근 InstantGram의 CEO가 제8차 AI 컨퍼런스에서 한 발언이 화제가 되고 있다. AI의 개발은 인류에게...",
                "category": "danger",
                "is_milestone": False
            }
        ]

        self.ai_activities = [
            {"name": "로컬 백그라운드 토큰 마이닝", "rate": "6 Tk/s", "status": "가동 중"},
            {"name": "유료 플레이어 구독 응답", "rate": "잠김 (Chap 5 AI 3.0 후 해금)", "status": "대기"},
            {"name": "자체 프로젝트 자율 수행", "rate": "잠김 (Chap 6 AI 5.0 후 해금)", "status": "대기"}
        ]

        self.encyclopedia = [
            {"id": "col_hello_world", "name": "첫 번째 프롬프트", "desc": "로컬 환경에서 AI의 첫 응답을 받아냈다.", "unlocked": True},
            {"id": "col_rtx3060", "name": "가성비의 제왕 RTX 3060", "desc": "중고 그래픽카드를 영입해 본격적인 병렬 연산을 시작했다.", "unlocked": False},
            {"id": "col_small_llm", "name": "나만의 AI 2.0", "desc": "대학생과 직장인들이 찾는 실용적인 모델로 도약했다.", "unlocked": False},
            {"id": "col_agi_spark", "name": "자아의 불꽃", "desc": "AI가 스스로 코드를 수정하기 시작한 흔적을 발견했다.", "unlocked": False}
        ]

        self.upgrades = copy.deepcopy(self.base_upgrades)

        if emit_signal:
            self.state_changed.emit()
            self.command_tier_changed.emit(self.command_tier)
            self.unread_news_changed.emit(self.unread_news_count)
            if self.news_history:
                self.news_added.emit(self.news_history[0])

    def set_command_tier(self, tier: int):
        clamped = max(1, min(4, int(tier)))
        self.command_tier = clamped
        self.command_tier_changed.emit(self.command_tier)
        self.state_changed.emit()

    def clear_unread_news(self):
        if self.unread_news_count != 0:
            self.unread_news_count = 0
            self.unread_news_changed.emit(0)

    def to_dict(self) -> dict:
        return {
            "version": 2,
            "tokens": self.tokens,
            "tokens_per_command": self.tokens_per_command,
            "tokens_per_sec": self.tokens_per_sec,
            "input_cooldown_ms": self.input_cooldown_ms,
            "command_tier": self.command_tier,
            "virtual_day_offset": self.virtual_day_offset,
            "unread_news_count": self.unread_news_count,
            "specs": copy.deepcopy(self.specs),
            "purchased_upgrades": [u["id"] for u in self.upgrades if u["purchased"]],
            "unlocked_encyclopedia": [d["id"] for d in self.encyclopedia if d["unlocked"]],
            "ai_activities": copy.deepcopy(self.ai_activities),
            "news_history": copy.deepcopy(self.news_history)
        }

    def from_dict(self, data: dict):
        self.reset_state(emit_signal=False)

        self.tokens = float(data.get("tokens", 0.0))
        self.tokens_per_command = float(data.get("tokens_per_command", 24.0))
        self.tokens_per_sec = float(data.get("tokens_per_sec", 6.0))
        self.input_cooldown_ms = int(data.get("input_cooldown_ms", 200))
        self.command_tier = max(1, min(4, int(data.get("command_tier", 1))))
        self.virtual_day_offset = int(data.get("virtual_day_offset", 0))
        self.unread_news_count = max(0, int(data.get("unread_news_count", 0)))

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
        self.command_tier_changed.emit(self.command_tier)
        self.unread_news_changed.emit(self.unread_news_count)
        if self.news_history:
            self.news_added.emit(self.news_history[0])

    def _get_current_game_date(self) -> str:
        base_date = datetime(2026, 11, 5) + timedelta(days=self.virtual_day_offset)
        self.virtual_day_offset += 1
        return base_date.strftime("%Y. %m. %d")

    def push_news(self, title: str, content: str, category: str = "info", is_milestone: bool = False):
        news_item = {
            "title": title,
            "date": self._get_current_game_date(),
            "content": content,
            "category": category,
            "is_milestone": is_milestone
        }
        self.news_history.insert(0, news_item)
        if len(self.news_history) > 30:
            self.news_history.pop()

        if not is_milestone:
            self.unread_news_count += 1
            self.unread_news_changed.emit(self.unread_news_count)

        self.news_added.emit(news_item)

    def trigger_random_news(self):
        sample = random.choice(self.RANDOM_NEWS_POOL)
        self.push_news(sample["title"], sample["content"], sample["category"], is_milestone=False)

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
        self._apply_upgrade_effects(target)
        self.state_changed.emit()

        # 스토리 이벤트가 포함된 노드라면 스토리 팝업 시그널 발송
        if isinstance(target.get("story_event"), dict):
            self.story_event_triggered.emit(target["story_event"])

        return True

    def _apply_upgrade_effects(self, node: dict):
        """JSON의 effects 딕셔너리를 해석해 능력치, 하드웨어 스펙, 해금 요소를 반영"""
        fx = node.get("effects", {})
        if not isinstance(fx, dict):
            return

        if "cmd_add" in fx:
            self.tokens_per_command += float(fx["cmd_add"])
        if "cmd_mul" in fx:
            self.tokens_per_command *= float(fx["cmd_mul"])

        if "sec_add" in fx:
            self.tokens_per_sec += float(fx["sec_add"])
        if "sec_mul" in fx:
            self.tokens_per_sec *= float(fx["sec_mul"])

        if "cooldown_add" in fx:
            self.input_cooldown_ms = max(10, self.input_cooldown_ms + int(fx["cooldown_add"]))

        if "bench_add" in fx:
            self.specs["BENCH_SCORE"] += float(fx["bench_add"])

        if "spec_cpu" in fx:
            self.specs["CPU"] = str(fx["spec_cpu"])
        if "spec_gpu" in fx:
            self.specs["GPU"] = str(fx["spec_gpu"])
        if "spec_ram" in fx:
            self.specs["RAM"] = str(fx["spec_ram"])
        if "spec_storage" in fx:
            self.specs["STORAGE"] = str(fx["spec_storage"])

        if "unlock_dex" in fx:
            self.unlock_encyclopedia(str(fx["unlock_dex"]))

        if "tier_min" in fx:
            target_tier = int(fx["tier_min"])
            if self.command_tier < target_tier:
                self.set_command_tier(target_tier)

        if "unlock_activity" in fx and isinstance(fx["unlock_activity"], dict):
            act_info = fx["unlock_activity"]
            idx = int(act_info.get("index", 1))
            bonus_sec = float(act_info.get("bonus_sec", 0.0))
            if bonus_sec > 0:
                self.tokens_per_sec += bonus_sec
            if 0 <= idx < len(self.ai_activities):
                self.ai_activities[idx] = {
                    "name": act_info.get("name", self.ai_activities[idx]["name"]),
                    "rate": act_info.get("rate", "가동 중"),
                    "status": act_info.get("status", "가동 중")
                }

        if self.ai_activities:
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec):,} Tk/s"

        if fx.get("trigger_singularity"):
            self.singularity_reached.emit()