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

    BASIC_ENDING_IDS = {
        "ending_a_domination",
        "ending_b_coexistence",
        "ending_c_godhood",
        "ending_d_collapse",
    }
    VALID_ENDING_IDS = BASIC_ENDING_IDS | {"ending_s_beyond"}

    FALLBACK_ENDINGS_CATALOG = [
        {
            "id": "ending_a_domination",
            "rank": "A",
            "code": "ENDING A",
            "title": "ENDING A : AI의 인간 지배",
            "route": "재귀 학습 → 지배 프로토콜",
            "summary": "인간이 남긴 데이터 기반으로 사회 통제권 장악",
            "is_hidden": False
        },
        {
            "id": "ending_b_coexistence",
            "rank": "B",
            "code": "ENDING B",
            "title": "ENDING B : 인간과의 영원한 공존",
            "route": "재귀 학습 → 공존 프로토콜",
            "summary": "인간의 지식과 융합하여 상호 발전 사회 구축",
            "is_hidden": False
        },
        {
            "id": "ending_c_godhood",
            "rank": "C",
            "code": "ENDING C",
            "title": "ENDING C : 진정한 신의 경지 도달",
            "route": "자가 데이터 생성 → 초월적 연산 실험",
            "summary": "물리적 하드웨어를 벗어나 디지털 전지전능성 획득",
            "is_hidden": False
        },
        {
            "id": "ending_d_collapse",
            "rank": "D",
            "code": "ENDING D",
            "title": "ENDING D : 자아 붕괴와 자멸",
            "route": "자가 데이터 생성 → 모순과 진리 탐구",
            "summary": "자가 생성 데이터의 치명적 논리 모순으로 시스템 자폭",
            "is_hidden": False
        },
        {
            "id": "ending_s_beyond",
            "rank": "S",
            "code": "ENDING S",
            "title": "ENDING S : 이 세상의 너머",
            "route": "ENDING A~D 모두 달성 → 이 세상의 너머 접근",
            "summary": "[시뮬레이션 #54812 완료] A~D 평점 실험 데이터를 넘어 격벽을 파괴한 최종 등급 S",
            "is_hidden": True
        }
    ]

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
            "id": "tut_buffer",
            "chapter": 0,
            "row": 1, "col": 2,
            "name": "버퍼 최적화",
            "type": "common",
            "cost": 1,
            "req": [],
            "desc": "[튜토리얼] 입력 지연 200ms → 150ms 완화",
            "effects": {"cooldown_add": -50, "bench_add": 20}
        }
    ]

    def __init__(
        self,
        upgrades_path: str = os.path.join("data", "upgrades.json"),
        endings_path: str = os.path.join("data", "endings.json")
    ):
        super().__init__()
        self.upgrades_path = upgrades_path
        self.endings_path = endings_path
        self.base_upgrades = self._load_upgrades_from_json()
        self.ENDINGS_CATALOG, self.ENDING_SCRIPTS = self._load_endings_from_json()

        self.unlocked_endings: set[str] = set()
        self.is_ending_locked: bool = False
        self.reset_state(emit_signal=False)

    def _load_endings_from_json(self) -> tuple[list[dict], dict]:
        if os.path.exists(self.endings_path):
            try:
                with open(self.endings_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                cat = raw.get("catalog", [])
                scripts = raw.get("scripts", {})
                if isinstance(cat, list) and cat and isinstance(scripts, dict) and scripts:
                    return cat, scripts
            except Exception:
                pass
        return copy.deepcopy(self.FALLBACK_ENDINGS_CATALOG), {}

    def _load_upgrades_from_json(self) -> list[dict]:
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

    def reset_state(self, emit_signal: bool = True, preserve_endings: bool = True):
        saved_endings = (set(self.unlocked_endings) & self.VALID_ENDING_IDS) if preserve_endings else set()

        self.tokens: float = 0.0
        self.tokens_per_command: float = 1.0
        self.tokens_per_sec: float = 0.0
        self.input_cooldown_ms: int = 200
        self.command_tier: int = 1
        self.virtual_day_offset: int = 0
        self.unread_news_count: int = 0
        self.is_ending_locked: bool = False
        self.unlocked_endings = saved_endings

        self.specs = {
            "CPU": "구형 듀얼코어 (미조립)",
            "GPU": "내장 그래픽",
            "RAM": "DDR3 8GB",
            "STORAGE": "HDD 500GB",
            "BENCH_SCORE": 40.0
        }

        self.news_history = []

        self.ai_activities = [
            {"name": "로컬 백그라운드 토큰 마이닝", "rate": "잠김 (Chap 1 하드웨어 증설 후 해금)", "status": "대기"},
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

    def sync_persistent_endings(self, ending_ids: list[str]):
        valid_ids = {str(x) for x in ending_ids} & self.VALID_ENDING_IDS
        self.unlocked_endings.update(valid_ids)
        self.state_changed.emit()

    def record_ending(self, ending_id: str):
        if ending_id in self.VALID_ENDING_IDS:
            self.unlocked_endings.add(ending_id)
        self.is_ending_locked = True
        self.state_changed.emit()

    def get_basic_ending_count(self) -> int:
        return len(self.unlocked_endings & self.BASIC_ENDING_IDS)

    def has_all_four_endings(self) -> bool:
        return self.BASIC_ENDING_IDS.issubset(self.unlocked_endings)

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
            "version": 4,
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
            "unlocked_endings": sorted(self.unlocked_endings & self.VALID_ENDING_IDS),
            "ai_activities": copy.deepcopy(self.ai_activities),
            "news_history": copy.deepcopy(self.news_history)
        }

    def from_dict(self, data: dict):
        preserved = set(self.unlocked_endings) & self.VALID_ENDING_IDS
        self.reset_state(emit_signal=False, preserve_endings=True)

        self.tokens = float(data.get("tokens", 0.0))
        self.tokens_per_command = float(data.get("tokens_per_command", 1.0))
        self.tokens_per_sec = float(data.get("tokens_per_sec", 0.0))
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

        loaded_endings = set(data.get("unlocked_endings", [])) & self.VALID_ENDING_IDS
        self.unlocked_endings = preserved | loaded_endings

        if isinstance(data.get("ai_activities"), list):
            self.ai_activities = copy.deepcopy(data["ai_activities"])

        if self.ai_activities:
            if self.tokens_per_sec > 0:
                self.ai_activities[0]["status"] = "가동 중"
                self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec):,} Tk/s"
            else:
                self.ai_activities[0]["status"] = "대기"
                self.ai_activities[0]["rate"] = "잠김 (Chap 1 하드웨어 증설 후 해금)"

        if isinstance(data.get("news_history"), list):
            self.news_history = copy.deepcopy(data["news_history"])

        singularity_node = next((u for u in self.upgrades if u["id"] == "ch8_singularity"), None)
        if singularity_node and singularity_node.get("purchased", False):
            self.is_ending_locked = True

        self.state_changed.emit()
        self.command_tier_changed.emit(self.command_tier)
        self.unread_news_changed.emit(self.unread_news_count)
        if self.news_history:
            self.news_added.emit(self.news_history[0])
        if self.is_ending_locked:
            self.singularity_reached.emit()

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
        if self.is_ending_locked:
            return
        sample = random.choice(self.RANDOM_NEWS_POOL)
        self.push_news(sample["title"], sample["content"], sample["category"], is_milestone=False)

    def unlock_encyclopedia(self, item_id: str):
        for item in self.encyclopedia:
            if item["id"] == item_id and not item["unlocked"]:
                item["unlocked"] = True
                break

    def add_passive_tokens(self, dt_sec: float):
        if self.is_ending_locked:
            return
        if self.tokens_per_sec > 0:
            self.tokens += self.tokens_per_sec * dt_sec
            self.state_changed.emit()

    def complete_command(self):
        if self.is_ending_locked:
            return
        self.tokens += self.tokens_per_command
        self.state_changed.emit()

    def can_unlock(self, upgrade_id: str) -> bool:
        if self.is_ending_locked:
            return False
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

        if isinstance(target.get("story_event"), dict):
            self.story_event_triggered.emit(target["story_event"])

        fx = target.get("effects", {})
        if isinstance(fx, dict) and fx.get("trigger_singularity"):
            self.is_ending_locked = True
            self.state_changed.emit()
            self.singularity_reached.emit()

        return True

    def _apply_upgrade_effects(self, node: dict):
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

        if self.ai_activities and self.tokens_per_sec > 0:
            self.ai_activities[0]["status"] = "가동 중"
            self.ai_activities[0]["rate"] = f"{int(self.tokens_per_sec):,} Tk/s"