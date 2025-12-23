from __future__ import annotations

from typing import Dict

from state import SessionState


def generate_action_steps(state: SessionState) -> Dict[str, str]:
    """지금 바로 할 수 있는 1~3단계 행동을 제안한다."""
    domain = state.chosen_domain or "생활 유지"

    today = (
        "오늘은 짧게 상황을 한 문장으로 정리해두세요. 예) “월세 연체 걱정, 이번 달 생활비 부족”. "
        "이 문장을 가지고 전화·상담을 시작하면 부담이 줄어요."
    )

    tomorrow = (
        f"내일은 {domain} 쪽으로 ‘지원 가능성만 먼저 확인하고 싶다’고 문의해보세요. "
        "지역(시/군/구)만 알려주면 더 빨라지지만, 지금은 전국 공통 경로부터 살펴보셔도 괜찮습니다."
    )

    stuck = (
        "연결이 어렵거나 답을 못 들으면, ‘신청’이 아니라 ‘자격 확인 상담’만 먼저 부탁한다고 말해보세요. "
        "서류가 없어도 현재 상황만 말하고 가볍게 시작하셔도 됩니다."
    )

    return {"today": today, "tomorrow": tomorrow, "stuck": stuck}
