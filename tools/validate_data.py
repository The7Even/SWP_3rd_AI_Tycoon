import json
import os
import sys

# 프로젝트 루트 경로 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.game_state import GameState


def load_json(rel_path: str):
    full_path = os.path.join(ROOT_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"[ERROR] 파일을 찾을 수 없습니다: {rel_path}")
        return None
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_effective_balance_chapter(node: dict) -> int:
    """
    실제 플레이 체감 비용 구간 기준으로 챕터를 재분류:
    - ch1_start -> Chap 0(튜토리얼 졸업 관문) 비용에 포함
    - ch2_start -> Chap 1(Chap 1 졸업 관문) 비용에 포함
    - ...
    - ch7_start -> Chap 6 비용에 포함
    - ch8_singularity -> Chap 7 비용에 포함
    """
    uid = node.get("id", "")
    chap = int(node.get("chapter", 1))

    if uid == "ch8_singularity":
        return 7
    for c in range(1, 8):
        if uid == f"ch{c}_start":
            return c - 1
    return chap


def validate_all():
    print("=" * 78)
    print("  AI 키우기 - 데이터 무결성 & 실질 구간별 밸런스 검증 리포트")
    print("=" * 78)

    upg_raw = load_json(os.path.join("data", "upgrades.json"))
    dlg_raw = load_json(os.path.join("data", "ai_dialogues.json"))
    news_raw = load_json(os.path.join("data", "news.json"))

    if not upg_raw:
        return

    upgrades = upg_raw.get("upgrades", upg_raw) if isinstance(upg_raw, dict) else upg_raw
    errors = []
    warnings = []

    # 1. ID 중복 및 기본 필드 검사
    id_map: dict[str, dict] = {}
    coord_map: dict[tuple[int, int], list[str]] = {}

    for idx, node in enumerate(upgrades):
        uid = node.get("id")
        if not uid:
            errors.append(f"인덱스 {idx} 노드에 'id'가 없습니다.")
            continue
        if uid in id_map:
            errors.append(f"중복된 노드 ID 발견: '{uid}'")
        id_map[uid] = node

        row = int(node.get("row", 0))
        col = int(node.get("col", 0))
        coord_map.setdefault((row, col), []).append(uid)

    for (row, col), uids in coord_map.items():
        if len(uids) > 1:
            warnings.append(f"좌표 겹침 경고 (row={row}, col={col}): {', '.join(uids)}")

    # 2. 선행 노드(req) 존재 여부 및 순환 참조 / 도달 가능성(BFS) 검사
    children_map: dict[str, list[str]] = {uid: [] for uid in id_map}
    roots = []

    for uid, node in id_map.items():
        reqs = node.get("req", [])
        if not reqs:
            roots.append(uid)
        for r in reqs:
            if r not in id_map:
                errors.append(f"노드 '{uid}'의 선행 조건 '{r}'가 upgrades.json에 존재하지 않습니다.")
            else:
                children_map[r].append(uid)

    visited = set()
    queue = list(roots)
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        for nxt in children_map.get(curr, []):
            if nxt not in visited:
                queue.append(nxt)

    unreachable = set(id_map.keys()) - visited
    for uid in sorted(unreachable):
        errors.append(f"도달 불가능(고립/순환참조 의심) 노드: '{uid}'")

    # 3. GameState 매핑(대사 트리거 & 도감 해금) 정합성 검사
    node_triggers_json = dlg_raw.get("node_triggers", {}) if isinstance(dlg_raw, dict) else {}
    for node_id, trig_key in GameState.NODE_DIALOGUE_TRIGGER_MAP.items():
        if node_id not in id_map:
            warnings.append(f"NODE_DIALOGUE_TRIGGER_MAP의 노드 '{node_id}'가 upgrades.json에 없습니다.")
        if trig_key not in node_triggers_json:
            errors.append(f"NODE_DIALOGUE_TRIGGER_MAP의 키 '{trig_key}'가 ai_dialogues.json에 없습니다.")

    for node_id, dex_id in GameState.NODE_DEX_UNLOCK_MAP.items():
        if node_id not in id_map:
            warnings.append(f"NODE_DEX_UNLOCK_MAP의 노드 '{node_id}'가 upgrades.json에 없습니다.")

    # 4. 실질 플레이 구간별 비용 vs 고유 챕터 누적 스탯 시뮬레이션
    print("\n[실질 챕터 구간별 비용 & 고유 챕터 누적 스탯 요약]")
    print(f"{'구간':<12} | {'노드수':<6} | {'구간 총 비용':<18} | {'챕터 누적 Tk/Cmd':<16} | {'챕터 누적 Tk/s':<16}")
    print("-" * 78)

    sim_state = GameState()
    for chap in range(0, 9):
        # 비용은 다음 챕터 관문 노드(ch{chap+1}_start)까지 포함한 실질 구간 기준
        cost_nodes = [u for u in upgrades if get_effective_balance_chapter(u) == chap]
        # 스탯 효과는 해당 고유 챕터(node["chapter"] == chap) 소속 노드만 누적 반영
        stat_nodes = [u for u in upgrades if int(u.get("chapter", 1)) == chap]

        if not cost_nodes and not stat_nodes:
            continue

        total_cost = sum(float(u.get("cost", 0)) for u in cost_nodes)
        for u in stat_nodes:
            u["purchased"] = True
            sim_state._apply_upgrade_effects(u)

        gate_label = f"Ch.{chap}→Ch.{chap + 1}" if chap < 8 else "Ch.8"
        print(
            f"{gate_label:<12} | {len(cost_nodes):<6} | "
            f"{total_cost:<18,.0f} | "
            f"{sim_state.tokens_per_command:<16,.1f} | "
            f"{sim_state.tokens_per_sec:<16,.1f}"
        )

    # 5. 최종 결과 출력
    print("\n" + "=" * 78)
    if errors:
        print(f"❌ 치명적 오류 {len(errors)}건 발견:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("✅ 치명적 오류 0건! 트리 연결 및 매핑이 모두 정상입니다.")

    if warnings:
        print(f"\n⚠️ 주의/경고 {len(warnings)}건:")
        for w in warnings:
            print(f"  - {w}")

    if news_raw:
        items = news_raw.get("news", news_raw) if isinstance(news_raw, dict) else news_raw
        print(f"\n📰 로드된 뉴스 데이터: 총 {len(items)}건")
    print("=" * 78)


if __name__ == "__main__":
    validate_all()