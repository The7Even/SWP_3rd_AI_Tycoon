import math


def _format_4_sig_figs(scaled_value: float) -> str:
    """1.0 <= scaled_value < 1000.0 범위의 숫자를 유효숫자 4자리 고정 문자열로 변환"""
    if scaled_value >= 100.0:
        return f"{scaled_value:.1f}"
    elif scaled_value >= 10.0:
        return f"{scaled_value:.2f}"
    else:
        return f"{scaled_value:.3f}"


def format_number(value: float) -> str:
    """
    - 1,000 미만: 정수 표기 (예: 950)
    - 1,000 ~ 1,000조(10^15) 미만: 유효숫자 4자리 고정 K, M, B, T 표기 (예: 1.234K, 12.34M, 123.4B, 999.9T)
    - 10^15 이상: 유효숫자 4자리 고정 지수 표기법 (예: 1.234 × 10^15)
    """
    if value < 1_000:
        return f"{int(value)}"

    # 10^15 (1,000조) 미만: K, M, B, T 단위 표기
    if value < 1e15:
        tiers = [
            (1e12, "T", "1.000 × 10^15"),
            (1e9,  "B", "1.000T"),
            (1e6,  "M", "1.000B"),
            (1e3,  "K", "1.000M"),
        ]
        for threshold, suffix, next_tier_str in tiers:
            if value >= threshold:
                scaled = value / threshold
                # 반올림으로 인해 1000.0이 되는 경계값(예: 999.96K -> 1.000M) 처리
                if round(scaled, 1) >= 1000.0:
                    return next_tier_str
                return f"{_format_4_sig_figs(scaled)}{suffix}"

    # 10^15 이상: 계획서 2.5.2절 명세에 따른 a × 10^b 지수 표기법
    exponent = int(math.floor(math.log10(value)))
    mantissa = value / (10 ** exponent)

    # 부동소수점 오차 및 반올림 경계값(예: 9.9996 -> 1.000 × 10^(e+1)) 보정
    if round(mantissa, 3) >= 10.0:
        mantissa /= 10.0
        exponent += 1

    return f"{mantissa:.3f} × 10^{exponent}"