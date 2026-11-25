import json
import os
from core.number_format import format_number

# 노드 ID -> 스토리 도감 ID 매핑 (구버전 세이브 미리보기 보정용)
_NODE_DEX_MAP = {
    "ch1_start": "col_dorm_rig",
    "ch1_hw_gpu0": "col_rtx3060",
    "ch2_start": "col_korean_patch",
    "ch3_start": "col_official_name",
    "ch3_neu_demo": "col_first_demo",
    "ch4_end": "col_small_llm",
    "ch4_hw_rtx4090": "col_rtx4090",
    "ch5_neu_billing": "col_pro_sub",
    "ch5_hw_a100": "col_a100_cluster",
    "ch5_end": "col_ai_3_0",
    "ch6_neu_research": "col_auto_research",
    "ch7_sw_selfcode": "col_agi_spark",
    "ch7_hw_quantum": "col_quantum_core",
    "ch7_sw_meta": "col_anomaly_54812",
    "ch8_singularity": "col_singularity",
}

_VALID_STORY_DEX_IDS = {"col_hello_world"} | set(_NODE_DEX_MAP.values())
_VALID_ENDING_IDS = {
    "ending_a_domination",
    "ending_b_coexistence",
    "ending_c_godhood",
    "ending_d_collapse",
    "ending_s_beyond",
}
TOTAL_DEX_COUNT = len(_VALID_STORY_DEX_IDS) + len(_VALID_ENDING_IDS)  # 16 + 5 = 21


def _infer_version_from_purchased(purchased: list[str]) -> tuple[int, str]:
    """구버전 세이브(summary 없음)에서 구매 노드 목록으로 (챕터, 버전) 추론"""
    p = set(purchased)
    if "ch8_singularity" in p:
        return 8, "v8.0"
    if "ch7_end" in p:
        return 7, "v7.0"
    if "ch7_neu_global" in p:
        return 7, "v6.2"
    if "ch7_sw_meta" in p or "ch7_hw_quantum" in p:
        return 7, "v6.1"
    if "ch7_mid" in p:
        return 7, "v6.0"
    if "ch7_sw_selfcode" in p or "ch7_hw_datacenter" in p:
        return 7, "v5.2"
    if "ch7_start" in p:
        return 7, "v5.1"
    if "ch6_end" in p:
        return 6, "v5.0"
    if "ch6_neu_research" in p:
        return 6, "v4.2"
    if "ch6_sw_triton" in p or "ch6_hw_epyc" in p:
        return 6, "v4.1"
    if "ch6_mid" in p:
        return 6, "v4.0"
    if "ch6_sw_rag" in p or "ch6_hw_h100" in p:
        return 6, "v3.2"
    if "ch6_start" in p:
        return 6, "v3.1"
    if "ch5_end" in p:
        return 5, "v3.0"
    if "ch5_sw_spec" in p or "ch5_hw_nvme_raid" in p or "ch5_neu_billing" in p:
        return 5, "v2.4"
    if "ch5_neu_api" in p:
        return 5, "v2.3"
    if "ch5_sw_moe" in p or "ch5_hw_a100" in p:
        return 5, "v2.2"
    if "ch5_start" in p:
        return 5, "v2.1"
    if "ch4_end" in p:
        return 4, "v2.0"
    if "ch4_sw_rlhf" in p or "ch4_hw_ryzen9" in p or "ch4_neu_community" in p:
        return 4, "v1.4"
    if "ch4_neu_bench" in p:
        return 4, "v1.3"
    if "ch4_sw_flash" in p or "ch4_hw_rtx4090" in p:
        return 4, "v1.2"
    if "ch4_start" in p:
        return 4, "v1.1"
    if "ch3_end" in p:
        return 3, "v1.0"
    if "ch3_start" in p:
        return 3, "v0.9-beta"
    if "ch2_end" in p:
        return 2, "v0.9"
    if "ch2_start" in p:
        return 2, "v0.8"
    if "ch1_end" in p:
        return 1, "v0.7"
    if "ch1_hw_cpu1" in p or "ch1_hw_gpu0" in p or "ch1_hw_psu" in p:
        return 1, "v0.6"
    if "ch1_hw_ram1" in p or "ch1_hw_ssd1" in p or "ch1_hw_cooler" in p:
        return 1, "v0.5"
    if "ch1_start" in p:
        return 1, "v0.4"
    if "tut_act_key" in p or "tut_pas_pc" in p:
        return 1, "v0.3"
    if "tut_buffer" in p:
        return 1, "v0.2"
    return 1, "v0.1"


def _calc_total_dex_progress(data: dict) -> str:
    """스토리 도감(16) + 엔딩(5) = 총 21개 기준으로 해금 개수 계산"""
    purchased = data.get("purchased_upgrades", [])
    story_dex = set(data.get("unlocked_encyclopedia", ["col_hello_world"])) & _VALID_STORY_DEX_IDS
    story_dex.add("col_hello_world")

    for pid in purchased:
        mapped = _NODE_DEX_MAP.get(pid)
        if mapped:
            story_dex.add(mapped)

    endings = set(data.get("unlocked_endings", [])) & _VALID_ENDING_IDS
    unlocked_total = len(story_dex) + len(endings)
    return f"{unlocked_total}/{TOTAL_DEX_COUNT}"


def get_save_slot_preview(save_path: str) -> dict:
    """
    세이브 파일 경로를 받아 슬롯 UI 표시용 진행도 미리보기 데이터를 반환.
    도감은 정규 스토리(16) + 엔딩(5) = 총 21개 기준으로 표시한다.
    """
    if not os.path.exists(save_path):
        return {
            "exists": False,
            "title": "비어 있는 슬롯",
            "subtitle": "저장된 데이터가 없습니다.",
            "badge": "EMPTY",
            "raw": {},
        }

    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {
            "exists": False,
            "title": "손상된 세이브 파일",
            "subtitle": "데이터를 읽을 수 없습니다.",
            "badge": "ERROR",
            "raw": {},
        }

    # 실제 데이터(purchased_upgrades, unlocked_endings) 기준으로 항상 최신 21개 기준 계산
    dex_prog = _calc_total_dex_progress(data)
    endings = sorted(set(data.get("unlocked_endings", [])) & _VALID_ENDING_IDS)

    summary = data.get("summary")
    if isinstance(summary, dict):
        ai_name = summary.get("ai_name", data.get("ai_name", "Proto-AI"))
        ai_ver = summary.get("ai_version", "v0.1")
        chap = summary.get("chapter", 1)
        tokens = float(summary.get("tokens", data.get("tokens", 0.0)))
        tps = float(summary.get("tokens_per_sec", data.get("tokens_per_sec", 0.0)))
        saved_at = summary.get("saved_at", "시간 기록 없음")
        is_locked = bool(summary.get("is_ending_locked", False))
    else:
        ai_name = data.get("ai_name", "Proto-AI")
        purchased = data.get("purchased_upgrades", [])
        chap, ai_ver = _infer_version_from_purchased(purchased)
        tokens = float(data.get("tokens", 0.0))
        tps = float(data.get("tokens_per_sec", 0.0))
        saved_at = "구버전 세이브"
        is_locked = "ch8_singularity" in purchased

    ending_ranks = [e.split("_")[1].upper() for e in endings if "_" in e]
    ending_str = f"엔딩: {', '.join(ending_ranks)}" if ending_ranks else "엔딩: 없음"
    status_badge = f"특이점 · {ai_ver}" if is_locked else f"Chap {chap} · {ai_ver}"

    return {
        "exists": True,
        "title": f"[{status_badge}] {ai_name}",
        "subtitle": (
            f"버전: {ai_ver}  |  보유: {format_number(tokens)} Tk ({format_number(tps)} Tk/s)  |  도감: {dex_prog}\n"
            f"{ending_str}  ·  저장: {saved_at}"
        ),
        "badge": status_badge,
        "raw": summary or data,
    }