import csv
import json
import os
from collections import defaultdict


def format_num(val: float) -> str:
    """유효숫자 4자리 고정 포맷 (UI와 동일한 기준)"""
    if val == 0:
        return "0"
    abs_v = abs(val)
    if abs_v < 1000:
        if abs_v >= 100:
            return f"{val:.1f}".rstrip("0").rstrip(".")
        if abs_v >= 10:
            return f"{val:.2f}".rstrip("0").rstrip(".")
        return f"{val:.3f}".rstrip("0").rstrip(".")

    units = ["", "K", "M", "B", "T", "Qa", "Qi"]
    idx = 0
    num = float(val)
    while abs(num) >= 1000.0 and idx < len(units) - 1:
        num /= 1000.0
        idx += 1

    if abs(num) >= 100:
        s = f"{num:.1f}"
    elif abs(num) >= 10:
        s = f"{num:.2f}"
    else:
        s = f"{num:.3f}"
    return f"{s}{units[idx]}"


def format_duration(sec: float) -> str:
    if sec < 60:
        return f"{sec:.1f}초"
    mins = sec / 60.0
    if mins < 60:
        return f"{mins:.1f}분"
    hrs = mins / 60.0
    rem_mins = mins % 60.0
    return f"{int(hrs)}시간 {rem_mins:.1f}분"


def load_upgrades() -> tuple[list[dict], str]:
    candidates = [
        os.path.join("data", "upgrades.json"),
        os.path.join("..", "data", "upgrades.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(path)))
                return json.load(f)["upgrades"], base_dir
    raise FileNotFoundError("data/upgrades.json 파일을 찾을 수 없습니다.")


def export_balance_csv(upgrades: list[dict], output_path: str):
    ordered = sorted(upgrades, key=lambda u: (u["row"], u["col"]))

    cmd_rate = 1.0
    sec_rate = 0.0
    cooldown_ms = 200
    tier = 1
    is_supervisor = False

    tier_cps_map = {
        1: 0.35,
        2: 0.42,
        3: 0.48,
        4: 0.55,
    }
    news_expected_multiplier = 1.06

    chapter_stats = defaultdict(lambda: {
        "nodes": 0,
        "total_cost": 0.0,
        "raw_sec": 0.0,
        "adj_sec": 0.0,
        "act_ratios": [],
        "pas_ratios": [],
        "end_cmd_rate": 0.0,
        "end_sec_rate": 0.0,
        "end_cd_tier": "",
    })

    detail_rows = []
    total_raw_sec = 0.0
    total_adj_sec = 0.0

    for u in ordered:
        ch = u["chapter"]
        row = u["row"]
        col = u["col"]
        name = u["name"]
        cost = float(u["cost"])

        if not is_supervisor:
            base_cps = tier_cps_map.get(tier, 0.4)
            effective_cps = min(base_cps, 1000.0 / max(cooldown_ms, 50) * 0.12)
            active_tps = cmd_rate * effective_cps
            passive_tps = sec_rate
        else:
            # Chap 4+ 관제탑 모드: Q/W/E 냉각 즉각 보상(분당 ~5회) + 버퍼 배율 증폭분(패시브의 약 22%)
            cooling_tps = (cmd_rate * 1.5) * (5.0 / 60.0)
            harvest_bonus_tps = sec_rate * 0.22
            active_tps = cooling_tps + harvest_bonus_tps
            passive_tps = sec_rate

        total_tps = active_tps + passive_tps

        if total_tps > 0:
            act_pct = (active_tps / total_tps) * 100.0
            pas_pct = (passive_tps / total_tps) * 100.0
            raw_sec = cost / total_tps
            adj_sec = cost / (total_tps * news_expected_multiplier)
        else:
            act_pct, pas_pct = 100.0, 0.0
            raw_sec, adj_sec = 0.0, 0.0

        total_raw_sec += raw_sec
        total_adj_sec += adj_sec

        eff = u.get("effects", {})
        cmd_rate += float(eff.get("cmd_add", 0.0))
        sec_rate += float(eff.get("sec_add", 0.0))
        if "unlock_activity" in eff:
            sec_rate += float(eff["unlock_activity"].get("bonus_sec", 0.0))

        cmd_rate *= float(eff.get("cmd_mul", 1.0))
        sec_rate *= float(eff.get("sec_mul", 1.0))
        cooldown_ms = max(20, cooldown_ms + int(eff.get("cooldown_add", 0)))
        if "tier_min" in eff:
            tier = max(tier, int(eff["tier_min"]))
        if u["id"] == "ch4_start":
            is_supervisor = True

        mode_tag = "SUP" if is_supervisor else f"T{tier}"
        cd_tier_str = f"{cooldown_ms}ms / {mode_tag}"
        ratio_str = f"{int(round(act_pct))}% / {int(round(pas_pct))}%"

        st = chapter_stats[ch]
        st["nodes"] += 1
        st["total_cost"] += cost
        st["raw_sec"] += raw_sec
        st["adj_sec"] += adj_sec
        st["act_ratios"].append(act_pct)
        st["pas_ratios"].append(pas_pct)
        st["end_cmd_rate"] = cmd_rate
        st["end_sec_rate"] = sec_rate
        st["end_cd_tier"] = cd_tier_str

        detail_rows.append([
            "노드상세",
            f"Chap {ch}" if ch > 0 else "튜토리얼",
            f"R{row}-C{col}",
            name,
            format_num(cost),
            format_num(cmd_rate),
            format_num(sec_rate),
            cd_tier_str,
            ratio_str,
            format_duration(raw_sec),
            format_duration(adj_sec),
            format_duration(total_adj_sec),
        ])

    summary_rows = []
    cum_adj_sec = 0.0
    all_act_ratios = []
    all_pas_ratios = []

    for ch in sorted(chapter_stats.keys()):
        st = chapter_stats[ch]
        avg_a = sum(st["act_ratios"]) / len(st["act_ratios"])
        avg_p = sum(st["pas_ratios"]) / len(st["pas_ratios"])
        all_act_ratios.extend(st["act_ratios"])
        all_pas_ratios.extend(st["pas_ratios"])
        cum_adj_sec += st["adj_sec"]
        ch_label = "튜토리얼" if ch == 0 else f"Chap {ch}"

        summary_rows.append([
            "챕터요약",
            ch_label,
            "-",
            f"{ch_label} 종합 ({st['nodes']}개)",
            format_num(st["total_cost"]),
            format_num(st["end_cmd_rate"]),
            format_num(st["end_sec_rate"]),
            st["end_cd_tier"],
            f"{int(round(avg_a))}% / {int(round(avg_p))}%",
            format_duration(st["raw_sec"]),
            format_duration(st["adj_sec"]),
            format_duration(cum_adj_sec),
        ])

    total_avg_a = sum(all_act_ratios) / len(all_act_ratios)
    total_avg_p = sum(all_pas_ratios) / len(all_pas_ratios)

    summary_rows.append([
        "전체합계",
        "ALL",
        "-",
        f"전체 종합 ({len(ordered)}개)",
        format_num(sum(st["total_cost"] for st in chapter_stats.values())),
        format_num(cmd_rate),
        format_num(sec_rate),
        f"{cooldown_ms}ms / SUP",
        f"{int(round(total_avg_a))}% / {int(round(total_avg_p))}%",
        format_duration(total_raw_sec),
        format_duration(total_adj_sec),
        format_duration(total_adj_sec),
    ])

    headers = [
        "구분",
        "챕터",
        "RowCol",
        "노드명",
        "비용",
        "구매후 Tk/Cmd",
        "구매후 Tk/s",
        "쿨다운/티어",
        "비율(A / P)",
        "기본소요",
        "뉴스보정소요",
        "누적소요",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(summary_rows)
        writer.writerow([])
        writer.writerows(detail_rows)


if __name__ == "__main__":
    upgrades_data, project_root = load_upgrades()
    out_csv = os.path.join(project_root, "balance_report.csv")
    export_balance_csv(upgrades_data, out_csv)
    print(f"CSV 생성 완료: {out_csv}")