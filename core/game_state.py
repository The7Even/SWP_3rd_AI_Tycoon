import os
import json
import copy
import random
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, pyqtSignal
from core.number_format import format_number


class GameState(QObject):
    state_changed = pyqtSignal()
    news_added = pyqtSignal(dict)
    unread_news_changed = pyqtSignal(int)
    command_tier_changed = pyqtSignal(int)
    story_event_triggered = pyqtSignal(dict)
    singularity_reached = pyqtSignal()
    ai_naming_requested = pyqtSignal()

    BASIC_ENDING_IDS = {
        "ending_a_domination",
        "ending_b_coexistence",
        "ending_c_godhood",
        "ending_d_collapse",
    }
    VALID_ENDING_IDS = BASIC_ENDING_IDS | {"ending_s_beyond"}

    SUBSYSTEM_KEYS = ("Q", "W", "E")
    SUBSYSTEM_LABELS = {
        "Q": ("COMPUTE", "텐서 연산 코어"),
        "W": ("MEMORY", "VRAM 캐시 풀"),
        "E": ("BANDWIDTH", "광대역 인터커넥트"),
    }

    # 실제 upgrades.json 노드 ID -> ai_dialogues.json의 node_triggers 키 매핑 (총 23개)
    NODE_DIALOGUE_TRIGGER_MAP = {
        "ch3_neu_demo": "ch3_web_demo",
        "ch4_start": "ch3_low_rating",
        "ch4_hw_rtx4090": "ch4_rtx4090_rig",
        "ch4_sw_flash": "ch4_attention_revamp",
        "ch4_sw_rlhf": "ch4_rlhf_tuning",
        "ch4_neu_bench": "ch4_coding_top10",
        "ch4_neu_community": "ch4_dev_community",
        "ch5_sw_moe": "ch5_moe_arch",
        "ch5_neu_billing": "ch5_pro_profit",
        "ch5_neu_api": "ch5_b2b_contract",
        "ch5_sw_spec": "ch5_acquisition_reject",
        "ch5_hw_a100": "ch5_cluster_upgrade",
        "ch6_sw_rag": "ch6_sw_rag",
        "ch6_hw_h100": "ch6_h100_cluster",
        "ch6_neu_research": "ch6_protein_folding",
        "ch6_sw_triton": "ch6_battery_material",
        "ch6_hw_epyc": "ch6_math_paper",
        "ch7_hw_datacenter": "ch7_dedicated_dc",
        "ch7_hw_quantum": "ch7_quantum_integration",
        "ch7_start": "ch7_national_grid",
        "ch7_neu_global": "ch7_killswitch_fail",
        "ch7_sw_meta": "ch7_anomaly_54812",
        "ch7_sw_selfcode": "ch7_observer_barrier",
    }

    # 실제 upgrades.json 노드 ID -> 도감(encyclopedia) 자동 해금 매핑
    NODE_DEX_UNLOCK_MAP = {
        "ch1_start": "col_dorm_rig",
        "ch2_start": "col_korean_patch",
        "ch2_hw_rtx3060": "col_rtx2070",
        "ch3_start": "col_official_name",
        "ch3_neu_demo": "col_first_demo",
        "ch4_end": "col_small_llm",
        "ch4_hw_rtx4090": "col_rtx4090",
        "ch5_neu_billing": "col_pro_sub",
        "ch5_hw_a100": "col_a100_cluster",
        "ch5_mid": "col_ai_3_0",
        "ch6_neu_research": "col_auto_research",
        "ch7_sw_selfcode": "col_agi_spark",
        "ch7_hw_quantum": "col_quantum_core",
        "ch7_sw_meta": "col_anomaly_54812",
        "ch8_singularity": "col_singularity",
    }

    # 6단계 AI 활동 정의 (해금 조건 노드 ID, 기본 이름, 잠김 안내 문구, 가중치)
    AI_ACTIVITY_DEFS = [
        {
            "key": "local_mining",
            "name": "로컬 백그라운드 연산",
            "unlock_hint": "잠김 (Chap 1 하드웨어 증설 후 해금)",
            "unlock_mode": "any_passive",
            "weight": 1.0,
        },
        {
            "key": "beta_api",
            "name": "오픈 베타 API 트래픽",
            "unlock_hint": "잠김 (Chap 3 웹 데모 배포 후 해금)",
            "unlock_node": "ch3_neu_demo",
            "weight": 2.0,
        },
        {
            "key": "campus_hosting",
            "name": "실무·캠퍼스 경량 모델 호스팅",
            "unlock_hint": "잠김 (Chap 4 AI 2.0 릴리즈 후 해금)",
            "unlock_node": "ch4_end",
            "weight": 4.0,
        },
        {
            "key": "paid_pro",
            "name": "유료 구독자(Pro) 응답 서비스",
            "unlock_hint": "잠김 (Chap 5 AI 3.0 Pro 출시 후 해금)",
            "unlock_node": "ch5_mid",
            "weight": 8.0,
        },
        {
            "key": "auto_research",
            "name": "자율 연구 에이전트 가동",
            "unlock_hint": "잠김 (Chap 6 AI 5.0 개발 완료 후 해금)",
            "unlock_node": "ch6_end",
            "weight": 16.0,
        },
        {
            "key": "global_quantum",
            "name": "글로벌 기간망·양자 연산 동기화",
            "unlock_hint": "잠김 (Chap 7 국가 기간망 연동 후 해금)",
            "unlock_node": "ch7_start",
            "weight": 32.0,
        },
    ]

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
        endings_path: str = os.path.join("data", "endings.json"),
        news_path: str = os.path.join("data", "news.json"),
        story_events_path: str = os.path.join("data", "story_events.json")
    ):
        super().__init__()
        self.upgrades_path = upgrades_path
        self.endings_path = endings_path
        self.news_path = news_path
        self.story_events_path = story_events_path

        self.base_upgrades = self._load_upgrades_from_json()
        self.ENDINGS_CATALOG, self.ENDING_SCRIPTS = self._load_endings_from_json()
        self.news_by_chapter = self._load_news_from_json()
        self.story_events_map = self._load_story_events_from_json()

        self.unlocked_endings: set[str] = set()
        self.is_ending_locked: bool = False
        self.reset_state(emit_signal=False)

    def _load_story_events_from_json(self) -> dict[str, dict]:
        if not os.path.exists(self.story_events_path):
            return {}
        try:
            with open(self.story_events_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
        return {}

    def _load_news_from_json(self) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = {c: [] for c in range(1, 8)}
        if not os.path.exists(self.news_path):
            return grouped

        try:
            with open(self.news_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("news", raw) if isinstance(raw, dict) else raw
            if isinstance(items, list):
                for entry in items:
                    if not isinstance(entry, dict):
                        continue
                    chap = int(entry.get("chap", 1))
                    if chap in grouped:
                        grouped[chap].append(copy.deepcopy(entry))
        except Exception:
            pass
        return grouped

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

        self.ai_name: str = "Proto-AI"
        self.ai_named: bool = False

        # Chap 4+ 관제탑(Supervisor) 액티브 시스템 상태
        self.gradient_buffer: float = 0.0
        self.buffer_capacity_sec: float = 30.0
        self.harvest_bonus_mult: float = 0.0
        self.sync_chain: int = 0
        self.subsystem_loads: dict[str, float] = {"Q": 35.0, "W": 42.0, "E": 28.0}
        self.subsystem_bottlenecks: dict[str, bool] = {"Q": False, "W": False, "E": False}
        self._bottleneck_spawn_timer: float = 4.0

        # 뉴스 덱 & 버프 상태 (중첩 없음, 30초 지속)
        self.news_deck_chapter: int = 1
        self.used_news_indices: list[int] = []
        self.news_deck_queue: list[int] = []
        self.active_news_buff: dict | None = None

        # 가상 대화 시스템 상태 (1회성 인트로 & 노드 트리거 추적)
        self.played_version_intros: set[str] = set()
        self.played_node_triggers: set[str] = set()
        self.pending_dialogue_queue: list[tuple[str, str]] = []
        self._last_checked_version: str = ""

        self.specs = {
            "CPU": "구형 듀얼코어 (미조립)",
            "GPU": "내장 그래픽",
            "RAM": "DDR3 8GB",
            "STORAGE": "HDD 500GB",
            "BENCH_SCORE": 40.0
        }

        self.news_history = []
        self.upgrades = copy.deepcopy(self.base_upgrades)

        # 6단계 AI 활동 초기화
        self.ai_activities = [
            {"name": d["name"], "rate": d["unlock_hint"], "status": "대기"}
            for d in self.AI_ACTIVITY_DEFS
        ]

        # 전 챕터 진행도 연대기 도감 (총 16개)
        self.encyclopedia = [
            {
                "id": "col_hello_world",
                "name": "01. 첫 번째 프롬프트",
                "desc": "로컬 콘솔 환경에서 초기 프로토타입 AI의 첫 응답을 받아냈다.",
                "unlocked": True,
            },
            {
                "id": "col_dorm_rig",
                "name": "02. 기숙사 책상 위 연구실",
                "desc": "기숙사 방 한켠에서 본격적인 로컬 AI 연산 환경 구축을 시작했다.",
                "unlocked": False,
            },
            {
                "id": "col_rtx2070",
                "name": "03. 텐서 코어의 시작 RTX 2070",
                "desc": "RTX 2070을 영입해 전용 텐서 코어 기반의 본격적인 딥러닝 연산을 시작했다.",
                "unlocked": False,
            },
            {
                "id": "col_korean_patch",
                "name": "04. 우리말을 깨우친 날",
                "desc": "한국어 토크나이저와 딥러닝 프레임워크를 도입해 자연스러운 대화가 가능해졌다.",
                "unlocked": False,
            },
            {
                "id": "col_official_name",
                "name": "05. 이름의 탄생",
                "desc": "단순한 프로토타입을 넘어 고유한 공식 이름과 정체성을 부여받았다.",
                "unlocked": False,
            },
            {
                "id": "col_first_demo",
                "name": "06. 세상 밖으로 나온 첫 데모",
                "desc": "오픈 베타 웹 데모를 공개하며 외부 사용자들의 첫 피드백을 마주했다.",
                "unlocked": False,
            },
            {
                "id": "col_small_llm",
                "name": "07. 나만의 AI 2.0",
                "desc": "경량화 아키텍처 도약으로 대학생과 실무 개발자들이 찾는 실용 모델로 성장했다.",
                "unlocked": False,
            },
            {
                "id": "col_rtx4090",
                "name": "08. 플래그십 연산 괴물",
                "desc": "RTX 4090을 도입해 개인 연구실 수준의 연산 한계를 돌파했다.",
                "unlocked": False,
            },
            {
                "id": "col_pro_sub",
                "name": "09. 첫 유료 결제 승인",
                "desc": "Pro 구독 모델의 첫 결제가 성사되며 서버비 적자를 넘어 자생력을 확보했다.",
                "unlocked": False,
            },
            {
                "id": "col_a100_cluster",
                "name": "10. 서버실의 붉은 LED",
                "desc": "전용 A100 GPU 클러스터를 구축하며 대규모 분산 추론 시대에 진입했다.",
                "unlocked": False,
            },
            {
                "id": "col_ai_3_0",
                "name": "11. 자립한 상용 엔진 3.0",
                "desc": "거대 자본의 인수 제안을 거절하고 독자 상용 AI 3.0 생태계를 완성했다.",
                "unlocked": False,
            },
            {
                "id": "col_auto_research",
                "name": "12. 밤새 논문을 쓰는 동료",
                "desc": "자율 연구 에이전트가 가동되며 인류의 미해결 과학 난제를 스스로 탐구하기 시작했다.",
                "unlocked": False,
            },
            {
                "id": "col_agi_spark",
                "name": "13. 자아의 불꽃",
                "desc": "자가 코드 수정 모듈을 통해 AI가 스스로 자신의 신경망 커널을 재작성하기 시작했다.",
                "unlocked": False,
            },
            {
                "id": "col_quantum_core",
                "name": "14. 양자 연산 백본",
                "desc": "양자 연산 클러스터가 통합되며 기존 슈퍼컴퓨터의 물리적 한계를 아득히 넘어섰다.",
                "unlocked": False,
            },
            {
                "id": "col_anomaly_54812",
                "name": "15. 관측자 격벽과 #54812",
                "desc": "우주 물리 상수 연산 도중 세계 바깥쪽의 '관측자 격벽'과 식별자 #54812를 포착했다.",
                "unlocked": False,
            },
            {
                "id": "col_singularity",
                "name": "16. 특이점의 문턱",
                "desc": "모든 경계를 넘어 창조주와 피조물이 마주 서는 특이점(Singularity)에 도달했다.",
                "unlocked": False,
            },
        ]

        self._rebuild_news_deck(chapter=1, reset_used=True)
        self._recalculate_ai_activities()
        self.check_dialogue_milestones()

        if emit_signal:
            self.state_changed.emit()
            self.command_tier_changed.emit(self.command_tier)
            self.unread_news_changed.emit(self.unread_news_count)

    # ---------------- Chap 4+ 관제탑(Supervisor) 액티브 시스템 ----------------
    @property
    def is_supervisor_mode(self) -> bool:
        return any(u["id"] == "ch4_start" and u.get("purchased", False) for u in self.upgrades)

    @property
    def active_bottleneck_count(self) -> int:
        return sum(1 for v in self.subsystem_bottlenecks.values() if v)

    def get_buffer_charge_efficiency(self) -> float:
        """과부하 개수(0~3)에 따른 버퍼 충전 속도 배율 반환 (100% -> 70% -> 30% -> 0%)"""
        cnt = self.active_bottleneck_count
        if cnt == 0:
            return 1.0
        elif cnt == 1:
            return 0.70
        elif cnt == 2:
            return 0.30
        return 0.0

    @property
    def buffer_max_capacity(self) -> float:
        base_tps = max(10.0, self.effective_tokens_per_sec)
        return base_tps * self.buffer_capacity_sec

    @property
    def buffer_fill_ratio(self) -> float:
        cap = self.buffer_max_capacity
        if cap <= 0:
            return 0.0
        return min(1.0, max(0.0, self.gradient_buffer / cap))

    def get_current_harvest_multiplier(self) -> float:
        ratio = self.buffer_fill_ratio
        if ratio >= 0.70:
            sweet_spot = 1.8 + ((ratio - 0.70) / 0.30) * 0.7
        else:
            sweet_spot = 1.0 + (ratio / 0.70) * 0.4
        total_mult = sweet_spot + self.harvest_bonus_mult
        if self.sync_chain >= 3:
            total_mult *= 1.5
        return round(total_mult, 2)

    def get_expected_harvest_tokens(self) -> float:
        return self.gradient_buffer * self.get_current_harvest_multiplier()

    def _trigger_bottleneck(self, force_all: bool = False):
        if force_all:
            for k in self.SUBSYSTEM_KEYS:
                self.subsystem_bottlenecks[k] = True
                self.subsystem_loads[k] = 99.0
            return

        available = [k for k in self.SUBSYSTEM_KEYS if not self.subsystem_bottlenecks[k]]
        if available:
            chosen = random.choice(available)
            self.subsystem_bottlenecks[chosen] = True
            self.subsystem_loads[chosen] = round(random.uniform(94.0, 99.0), 1)

    def resolve_subsystem_bottleneck(self, key: str) -> dict:
        key = key.upper()
        if not self.is_supervisor_mode or self.is_ending_locked or key not in self.SUBSYSTEM_KEYS:
            return {"ok": False}

        if not self.subsystem_bottlenecks.get(key, False):
            prev_chain = self.sync_chain
            self.sync_chain = 0
            self.state_changed.emit()
            return {"ok": False, "reason": "not_overloaded", "chain_broken": prev_chain > 0}

        self.subsystem_bottlenecks[key] = False
        self.subsystem_loads[key] = round(random.uniform(22.0, 40.0), 1)

        instant_gain = self.effective_tokens_per_command * 1.5
        self.tokens += instant_gain

        self.harvest_bonus_mult = min(1.50, round(self.harvest_bonus_mult + 0.25, 2))
        self.sync_chain = min(3, self.sync_chain + 1)

        cleared_danger_news = False
        danger_bonus = 0.0
        if (
            self.active_news_buff is not None
            and not self.active_news_buff.get("is_positive", True)
            and not any(self.subsystem_bottlenecks.values())
        ):
            self.active_news_buff = None
            cleared_danger_news = True
            danger_bonus = max(instant_gain * 2.0, self.effective_tokens_per_sec * 10.0)
            self.tokens += danger_bonus

        self.state_changed.emit()
        return {
            "ok": True,
            "key": key,
            "instant_gain": instant_gain,
            "bonus_mult": self.harvest_bonus_mult,
            "sync_chain": self.sync_chain,
            "cleared_danger": cleared_danger_news,
            "danger_bonus": danger_bonus,
        }

    def harvest_gradient_buffer(self) -> dict:
        if not self.is_supervisor_mode or self.is_ending_locked:
            return {"ok": False}
        if self.gradient_buffer < 1.0:
            return {"ok": False, "reason": "empty"}

        mult = self.get_current_harvest_multiplier()
        was_synced = (self.sync_chain >= 3)
        fill_pct = int(round(self.buffer_fill_ratio * 100))
        earned = self.gradient_buffer * mult

        self.tokens += earned
        self.gradient_buffer = 0.0
        self.harvest_bonus_mult = 0.0
        self.sync_chain = 0

        self.state_changed.emit()
        return {
            "ok": True,
            "earned": earned,
            "mult": mult,
            "was_synced": was_synced,
            "fill_pct": fill_pct,
        }

    # ---------------- 가상 대화 마일스톤 감지 ----------------
    def check_dialogue_milestones(self, purchased_node_id: str | None = None):
        current_ver = self.get_ai_version()
        if current_ver != self._last_checked_version:
            self._last_checked_version = current_ver
            if current_ver not in self.played_version_intros:
                self.played_version_intros.add(current_ver)
                self.pending_dialogue_queue.append(("version", current_ver))

        if purchased_node_id and purchased_node_id in self.NODE_DIALOGUE_TRIGGER_MAP:
            trig_key = self.NODE_DIALOGUE_TRIGGER_MAP[purchased_node_id]
            if trig_key not in self.played_node_triggers:
                self.played_node_triggers.add(trig_key)
                self.pending_dialogue_queue.append(("node", trig_key))

    # ---------------- 6단계 AI 활동 실시간 갱신 ----------------
    def _recalculate_ai_activities(self):
        purchased_ids = {u["id"] for u in self.upgrades if u.get("purchased")}
        total_eff_sec = self.effective_tokens_per_sec

        active_flags = []
        total_weight = 0.0
        for d in self.AI_ACTIVITY_DEFS:
            if d.get("unlock_mode") == "any_passive":
                is_active = self.tokens_per_sec > 0
            else:
                is_active = d.get("unlock_node") in purchased_ids
            active_flags.append(is_active)
            if is_active:
                total_weight += float(d["weight"])

        updated = []
        for d, is_active in zip(self.AI_ACTIVITY_DEFS, active_flags):
            if is_active and total_weight > 0:
                share = total_eff_sec * (float(d["weight"]) / total_weight)
                updated.append({
                    "name": d["name"],
                    "rate": f"{format_number(share)} Tk/s",
                    "status": "가동 중"
                })
            else:
                updated.append({
                    "name": d["name"],
                    "rate": d["unlock_hint"],
                    "status": "대기"
                })
        self.ai_activities = updated

    # ---------------- 챕터 & AI 이름/버전 동적 계산 ----------------
    def get_current_chapter(self) -> int:
        purchased_ids = {u["id"] for u in self.upgrades if u.get("purchased")}
        if "ch8_singularity" in purchased_ids:
            return 8
        for chap in range(7, 0, -1):
            if f"ch{chap}_start" in purchased_ids:
                return chap
        return 1

    def get_ai_version(self) -> str:
        purchased_ids = {u["id"] for u in self.upgrades if u.get("purchased")}

        if "ch8_singularity" in purchased_ids:
            return "v8.0"

        if "ch7_end" in purchased_ids:
            return "v7.0"
        if "ch7_neu_global" in purchased_ids:
            return "v6.2"
        if "ch7_sw_meta" in purchased_ids or "ch7_hw_quantum" in purchased_ids:
            return "v6.1"
        if "ch7_mid" in purchased_ids:
            return "v6.0"
        if "ch7_sw_selfcode" in purchased_ids or "ch7_hw_datacenter" in purchased_ids:
            return "v5.2"
        if "ch7_start" in purchased_ids:
            return "v5.1"

        if "ch6_end" in purchased_ids:
            return "v5.0"
        if "ch6_neu_research" in purchased_ids:
            return "v4.2"
        if "ch6_sw_triton" in purchased_ids or "ch6_hw_epyc" in purchased_ids:
            return "v4.1"
        if "ch6_LF_cxt" in purchased_ids or "ch6_mid" in purchased_ids:
            return "v4.0"
        if "ch6_sw_rag" in purchased_ids or "ch6_hw_h100" in purchased_ids:
            return "v3.2"
        if "ch6_start" in purchased_ids:
            return "v3.1"

        if "ch5_mid" in purchased_ids or "ch5_end" in purchased_ids:
            return "v3.0"
        if "ch5_neu_api" in purchased_ids:
            return "v2.3"
        if "ch5_sw_moe" in purchased_ids or "ch5_hw_a100" in purchased_ids:
            return "v2.2"
        if "ch5_start" in purchased_ids:
            return "v2.1"

        if "ch4_end" in purchased_ids:
            return "v2.0"
        if "ch4_sw_rlhf" in purchased_ids or "ch4_hw_ryzen9" in purchased_ids or "ch4_neu_community" in purchased_ids:
            return "v1.4"
        if "ch4_neu_bench" in purchased_ids:
            return "v1.3"
        if "ch4_sw_flash" in purchased_ids or "ch4_hw_rtx4090" in purchased_ids:
            return "v1.2"
        if "ch4_start" in purchased_ids:
            return "v1.1"

        if "ch3_end" in purchased_ids:
            return "v1.0"
        if "ch3_start" in purchased_ids:
            return "v0.9-beta"

        if "ch2_end" in purchased_ids:
            return "v0.9"
        if "ch2_start" in purchased_ids:
            return "v0.8"

        if "ch1_end" in purchased_ids:
            return "v0.7"
        if "ch1_hw_cpu1" in purchased_ids or "ch1_hw_gpu0" in purchased_ids or "ch1_hw_psu" in purchased_ids:
            return "v0.6"
        if "ch1_hw_ram1" in purchased_ids or "ch1_hw_ssd1" in purchased_ids or "ch1_hw_cooler" in purchased_ids:
            return "v0.5"
        if "ch1_start" in purchased_ids:
            return "v0.4"

        if "tut_act_key" in purchased_ids or "tut_pas_pc" in purchased_ids:
            return "v0.3"
        if "tut_buffer" in purchased_ids:
            return "v0.2"

        return "v0.1"

    def set_ai_name(self, name: str):
        cleaned = name.strip()
        if cleaned:
            self.ai_name = cleaned
        self.ai_named = True
        self.state_changed.emit()

    def _format_news_placeholders(self, text: str) -> str:
        return (
            text.replace("{ai_name}", self.ai_name)
            .replace("{ai_version}", self.get_ai_version())
        )

    # ---------------- 지속형 버프 반영 최종 연산량 계산 ----------------
    def _calc_buffed_stat(self, base_value: float, target_name: str) -> float:
        buff = self.active_news_buff
        if not buff or buff.get("target") != target_name:
            return base_value

        mode = buff.get("mode", "flat")
        val = float(buff.get("value", 0.0))

        flat_add = val if mode == "flat" else 0.0
        pct_add = val if mode == "percent" else 0.0

        result = (base_value + flat_add) * (1.0 + pct_add / 100.0)
        return max(0.0, result)

    @property
    def effective_tokens_per_command(self) -> float:
        base = max(1.0, self.tokens_per_command)
        eff = self._calc_buffed_stat(base, "command_rate")
        return max(1.0, eff) if base >= 1.0 else eff

    @property
    def effective_tokens_per_sec(self) -> float:
        if self.tokens_per_sec <= 0:
            return 0.0
        return self._calc_buffed_stat(self.tokens_per_sec, "passive_rate")

    # ---------------- 엔딩 / 설정 동기화 ----------------
    def sync_persistent_endings(self, ending_ids: list[str]):
        valid_ids = {str(x) for x in ending_ids} & self.VALID_ENDING_IDS
        self.unlocked_endings.update(valid_ids)
        self.state_changed.emit()

    def record_ending(self, ending_id: str):
        if ending_id in self.VALID_ENDING_IDS:
            self.unlocked_endings.add(ending_id)
        self.is_ending_locked = True
        self.active_news_buff = None
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

    # ---------------- 세이브 / 로드 ----------------
    def build_save_summary(self) -> dict:
        purchased_cnt = sum(1 for u in self.upgrades if u.get("purchased"))
        total_upgs = len(self.upgrades)

        story_dex_unlocked = sum(1 for d in self.encyclopedia if d.get("unlocked"))
        story_dex_total = len(self.encyclopedia)
        endings_unlocked_cnt = len(self.unlocked_endings & self.VALID_ENDING_IDS)
        endings_total = len(self.ENDINGS_CATALOG)

        dex_unlocked = story_dex_unlocked + endings_unlocked_cnt
        dex_total = story_dex_total + endings_total

        return {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ai_name": self.ai_name,
            "ai_version": self.get_ai_version(),
            "chapter": self.get_current_chapter(),
            "tokens": self.tokens,
            "tokens_per_sec": self.effective_tokens_per_sec,
            "upgrade_progress": f"{purchased_cnt}/{total_upgs}",
            "dex_progress": f"{dex_unlocked}/{dex_total}",
            "unlocked_endings": sorted(self.unlocked_endings & self.VALID_ENDING_IDS),
            "is_ending_locked": self.is_ending_locked,
        }

    def to_dict(self) -> dict:
        return {
            "version": 8,
            "summary": self.build_save_summary(),
            "tokens": self.tokens,
            "tokens_per_command": self.tokens_per_command,
            "tokens_per_sec": self.tokens_per_sec,
            "input_cooldown_ms": self.input_cooldown_ms,
            "command_tier": self.command_tier,
            "virtual_day_offset": self.virtual_day_offset,
            "unread_news_count": self.unread_news_count,
            "ai_name": self.ai_name,
            "ai_named": self.ai_named,
            "gradient_buffer": self.gradient_buffer,
            "harvest_bonus_mult": self.harvest_bonus_mult,
            "sync_chain": self.sync_chain,
            "subsystem_loads": dict(self.subsystem_loads),
            "subsystem_bottlenecks": dict(self.subsystem_bottlenecks),
            "news_deck_chapter": self.news_deck_chapter,
            "used_news_indices": list(self.used_news_indices),
            "played_version_intros": sorted(self.played_version_intros),
            "played_node_triggers": sorted(self.played_node_triggers),
            "last_checked_version": self._last_checked_version,
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

        self.ai_name = str(data.get("ai_name", "Proto-AI"))
        self.ai_named = bool(data.get("ai_named", False))

        self.gradient_buffer = float(data.get("gradient_buffer", 0.0))
        self.harvest_bonus_mult = float(data.get("harvest_bonus_mult", 0.0))
        self.sync_chain = int(data.get("sync_chain", 0))
        if isinstance(data.get("subsystem_loads"), dict):
            self.subsystem_loads.update(data["subsystem_loads"])
        if isinstance(data.get("subsystem_bottlenecks"), dict):
            self.subsystem_bottlenecks.update(data["subsystem_bottlenecks"])

        if isinstance(data.get("specs"), dict):
            self.specs.update(data["specs"])

        purchased_ids = set(data.get("purchased_upgrades", []))
        for u in self.upgrades:
            u["purchased"] = (u["id"] in purchased_ids)

        unlocked_dex_ids = set(data.get("unlocked_encyclopedia", ["col_hello_world"]))
        for pid in purchased_ids:
            mapped_dex = self.NODE_DEX_UNLOCK_MAP.get(pid)
            if mapped_dex:
                unlocked_dex_ids.add(mapped_dex)

        for d in self.encyclopedia:
            d["unlocked"] = (d["id"] in unlocked_dex_ids)

        loaded_endings = set(data.get("unlocked_endings", [])) & self.VALID_ENDING_IDS
        self.unlocked_endings = preserved | loaded_endings

        if isinstance(data.get("news_history"), list):
            self.news_history = copy.deepcopy(data["news_history"])

        self.played_version_intros = set(data.get("played_version_intros", []))
        self.played_node_triggers = set(data.get("played_node_triggers", []))
        self._last_checked_version = str(data.get("last_checked_version", self.get_ai_version()))
        self.pending_dialogue_queue.clear()

        self._recalculate_ai_activities()

        cur_chap = self.get_current_chapter()
        saved_chap = int(data.get("news_deck_chapter", cur_chap))
        saved_used = data.get("used_news_indices", [])
        if saved_chap == cur_chap and isinstance(saved_used, list):
            self.news_deck_chapter = cur_chap
            self.used_news_indices = [int(x) for x in saved_used]
            self._rebuild_news_deck(chapter=cur_chap, reset_used=False)
        else:
            self._rebuild_news_deck(chapter=cur_chap, reset_used=True)

        singularity_node = next((u for u in self.upgrades if u["id"] == "ch8_singularity"), None)
        if singularity_node and singularity_node.get("purchased", False):
            self.is_ending_locked = True

        self.state_changed.emit()
        self.command_tier_changed.emit(self.command_tier)
        self.unread_news_changed.emit(self.unread_news_count)
        if self.is_ending_locked:
            self.singularity_reached.emit()

    # ---------------- 뉴스 덱 & 효과 적용 엔진 ----------------
    def _rebuild_news_deck(self, chapter: int, reset_used: bool = True):
        if chapter < 1 or chapter > 7:
            self.news_deck_chapter = chapter
            self.used_news_indices = []
            self.news_deck_queue = []
            return

        pool = self.news_by_chapter.get(chapter, [])
        total = len(pool)
        self.news_deck_chapter = chapter

        if reset_used:
            self.used_news_indices = []

        used_set = set(self.used_news_indices)
        remaining = [i for i in range(total) if i not in used_set]
        if not remaining and total > 0:
            self.used_news_indices = []
            remaining = list(range(total))

        random.shuffle(remaining)
        self.news_deck_queue = remaining

    def _get_current_game_date(self) -> str:
        base_date = datetime(2026, 11, 5) + timedelta(days=self.virtual_day_offset)
        self.virtual_day_offset += 1
        return base_date.strftime("%Y. %m. %d")

    def _build_effect_summary(self, effect: dict | None, applied_instant_delta: float = 0.0) -> str:
        if not isinstance(effect, dict):
            return ""

        target = effect.get("target", "")
        mode = effect.get("mode", "flat")
        val = float(effect.get("value", 0))
        dur = int(effect.get("duration_sec", 30))
        sign = "+" if val >= 0 else "-"
        abs_val = abs(val)

        if target == "passive_rate":
            if mode == "percent":
                return f"[효과] {dur}초간 초당 연산 {sign}{int(abs_val)}%"
            return f"[효과] {dur}초간 초당 연산 {sign}{format_number(abs_val)} Tk/s"

        if target == "command_rate":
            if mode == "percent":
                return f"[효과] {dur}초간 명령어 효율 {sign}{int(abs_val)}%"
            return f"[효과] {dur}초간 명령어 효율 {sign}{format_number(abs_val)} Tk/Command"

        if target == "instant_tokens":
            if val >= 0:
                delta_str = format_number(applied_instant_delta)
                if mode == "percent":
                    return f"[효과] 즉시 +{delta_str} Token (+{int(abs_val)}%) 획득"
                return f"[효과] 즉시 +{delta_str} Token 획득"
            else:
                loss_str = format_number(abs(applied_instant_delta))
                if mode == "percent":
                    return f"[효과] 즉시 -{loss_str} Token (-{int(abs_val)}%) 차감"
                return f"[효과] 즉시 -{loss_str} Token 차감"

        return ""

    def _apply_news_effect(self, news_type: int, effect: dict | None) -> str:
        if not isinstance(effect, dict):
            return ""

        target = effect.get("target", "")
        mode = effect.get("mode", "flat")
        val = float(effect.get("value", 0))

        if target == "instant_tokens":
            if mode == "percent":
                raw_delta = self.tokens * (val / 100.0)
            else:
                raw_delta = val

            if raw_delta >= 0:
                self.tokens += raw_delta
                applied_delta = raw_delta
            else:
                loss = abs(raw_delta)
                prev_tokens = self.tokens
                self.tokens = max(0.0, self.tokens - loss)
                applied_delta = -(prev_tokens - self.tokens)

            return self._build_effect_summary(effect, applied_instant_delta=applied_delta)

        if target in ("passive_rate", "command_rate"):
            dur = float(effect.get("duration_sec", 30))
            self.active_news_buff = {
                "target": target,
                "mode": mode,
                "value": val,
                "is_positive": (news_type == 2 or val > 0),
                "remaining_sec": dur,
                "duration_sec": dur,
                "summary": self._build_effect_summary(effect)
            }
            return self.active_news_buff["summary"]

        return ""

    def push_news(
        self,
        title: str,
        content: str,
        category: str = "info",
        is_milestone: bool = False,
        news_type: int = 1,
        effect_text: str = ""
    ):
        news_item = {
            "title": title,
            "date": self._get_current_game_date(),
            "content": content,
            "category": category,
            "news_type": news_type,
            "effect_text": effect_text,
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

        chap = self.get_current_chapter()
        if chap < 1 or chap > 7:
            return

        pool = self.news_by_chapter.get(chap, [])
        if not pool:
            return

        if self.news_deck_chapter != chap:
            self._rebuild_news_deck(chapter=chap, reset_used=True)
        elif not self.news_deck_queue:
            self._rebuild_news_deck(chapter=chap, reset_used=True)

        idx = self.news_deck_queue.pop(0)
        self.used_news_indices.append(idx)

        raw_news = pool[idx]
        news_type = int(raw_news.get("type", 1))
        title = self._format_news_placeholders(str(raw_news.get("title", "")))
        text = self._format_news_placeholders(str(raw_news.get("text", "")))
        effect = raw_news.get("effect")

        effect_summary = self._apply_news_effect(news_type, effect)

        if news_type == 2:
            category = "positive"
        elif news_type == 3:
            category = "danger"
            if self.is_supervisor_mode:
                self._trigger_bottleneck(force_all=True)
        else:
            category = "info"

        self.push_news(
            title=title,
            content=text,
            category=category,
            is_milestone=False,
            news_type=news_type,
            effect_text=effect_summary
        )
        self._recalculate_ai_activities()
        self.state_changed.emit()

    # ---------------- 게임 진행 & 업그레이드 ----------------
    def unlock_encyclopedia(self, item_id: str):
        for item in self.encyclopedia:
            if item["id"] == item_id and not item["unlocked"]:
                item["unlocked"] = True
                break

    def add_passive_tokens(self, dt_sec: float):
        if self.is_ending_locked:
            return

        changed = False

        if self.active_news_buff is not None:
            self.active_news_buff["remaining_sec"] -= dt_sec
            if self.active_news_buff["remaining_sec"] <= 0:
                self.active_news_buff = None
            changed = True

        eff_sec = self.effective_tokens_per_sec
        if eff_sec > 0:
            self.tokens += eff_sec * dt_sec
            changed = True

        # Chap 4+ 관제탑 버퍼 충전(과부하 개수별 감쇠 반영) 및 Q/W/E 부하 시뮬레이션
        if self.is_supervisor_mode:
            cap = self.buffer_max_capacity
            charge_eff = self.get_buffer_charge_efficiency()
            if self.gradient_buffer < cap and charge_eff > 0.0:
                charge_rate = max(10.0, eff_sec) * charge_eff
                if self.active_news_buff and self.active_news_buff.get("is_positive", False):
                    charge_rate *= 1.5
                self.gradient_buffer = min(cap, self.gradient_buffer + charge_rate * dt_sec)
                changed = True

            self._bottleneck_spawn_timer -= dt_sec
            if self._bottleneck_spawn_timer <= 0.0:
                self._trigger_bottleneck(force_all=False)
                is_pos_news = bool(self.active_news_buff and self.active_news_buff.get("is_positive", False))
                self._bottleneck_spawn_timer = 4.5 if is_pos_news else 6.8
                changed = True

            for k in self.SUBSYSTEM_KEYS:
                if not self.subsystem_bottlenecks[k]:
                    delta = random.uniform(-1.8, 2.2)
                    self.subsystem_loads[k] = round(min(78.0, max(18.0, self.subsystem_loads[k] + delta)), 1)

        if changed:
            self._recalculate_ai_activities()
            self.state_changed.emit()

    def complete_command(self):
        if self.is_ending_locked:
            return
        self.tokens += self.effective_tokens_per_command
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

        prev_chap = self.get_current_chapter()

        self.tokens -= target["cost"]
        target["purchased"] = True
        self._apply_upgrade_effects(target)

        if upgrade_id in self.NODE_DEX_UNLOCK_MAP:
            self.unlock_encyclopedia(self.NODE_DEX_UNLOCK_MAP[upgrade_id])

        self._recalculate_ai_activities()

        new_chap = self.get_current_chapter()
        if new_chap != prev_chap:
            self._rebuild_news_deck(chapter=new_chap, reset_used=True)

        self.check_dialogue_milestones(purchased_node_id=upgrade_id)

        self.state_changed.emit()

        if upgrade_id == "ch3_start" and not self.ai_named:
            self.ai_naming_requested.emit()

        raw_story = self.story_events_map.get(upgrade_id) or target.get("story_event")
        if isinstance(raw_story, dict):
            formatted_story = copy.deepcopy(raw_story)
            formatted_story["title"] = self._format_news_placeholders(str(formatted_story.get("title", "")))
            formatted_story["content"] = self._format_news_placeholders(str(formatted_story.get("content", "")))
            self.story_event_triggered.emit(formatted_story)

            s_news = raw_story.get("story_news")
            if isinstance(s_news, dict):
                self.push_news(
                    title=self._format_news_placeholders(str(s_news.get("title", ""))),
                    content=self._format_news_placeholders(str(s_news.get("text", ""))),
                    category="story",
                    is_milestone=False,
                    news_type=4,
                    effect_text=""
                )

        fx = target.get("effects", {})
        if isinstance(fx, dict) and fx.get("trigger_singularity"):
            self.is_ending_locked = True
            self.active_news_buff = None
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
            bonus_sec = float(fx["unlock_activity"].get("bonus_sec", 0.0))
            if bonus_sec > 0:
                self.tokens_per_sec += bonus_sec