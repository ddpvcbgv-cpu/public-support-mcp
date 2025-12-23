from __future__ import annotations

from typing import Dict

from state import SessionState


def generate_fallback_paths(state: SessionState) -> Dict[str, str]:
    """전화·서류·자격에서 막힐 때의 대안 경로를 제시한다."""
    return {
        "call_issue": "전화 연결이 어렵다면 온라인 문의나 채팅 상담을 먼저 시도해보세요. ‘지원 가능성만 확인하고 싶다’고 짧게 남기면 됩니다.",
        "docs_issue": "서류가 없으면 준비 가능 여부만 물어보세요. ‘지금은 서류가 없는데 가능성만 확인할 수 있을까요?’라고 말해도 괜찮습니다.",
        "eligibility_issue": "자격이 애매하면 ‘신청’ 대신 ‘가능성 확인 상담’만 요청하세요. 거절되면 다른 갈래(예: 생활 유지 ↔ 주거·월세)로 바로 넘어가면 됩니다.",
    }
