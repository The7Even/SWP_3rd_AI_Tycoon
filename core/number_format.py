def format_number(value: float) -> str:
    """일정 수치 이상일 경우 a * 10^b 지수 표기법으로 변환하여 반환"""
    if value < 1_000_000:
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.1f}"

    exponent = 0
    temp = float(value)
    while temp >= 10.0:
        temp /= 10.0
        exponent += 1

    return f"{temp:.2f} × 10^{exponent}"