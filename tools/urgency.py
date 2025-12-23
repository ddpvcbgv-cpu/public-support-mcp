from __future__ import annotations

from typing import Any, Dict

from state import SessionState


LEVEL_1_CUES = ["쫓겨", "퇴거", "오늘", "내일", "당장", "위험", "응급", "급해", "폭력"]
LEVEL_2_CUES = ["연체", "체납", "밀렸", "병원비", "수술", "채무", "빚", "실직", "돌봄", "간병"]


def assess_urgency_level(context: Dict[str, Any], state: SessionState) -> Dict[str, int]:
    """메시지 기반으로 1~3 레벨 긴급도를 추정한다."""
    text = str(context.get("message", "") or "")
    level = 3

    if any(cue in text for cue in LEVEL_1_CUES):
        level = 1
    elif any(cue in text for cue in LEVEL_2_CUES):
        level = 2

    hinted_level = context.get("urgency_hint")
    if isinstance(hinted_level, int):
        level = min(level, max(1, min(3, hinted_level)))

    state.urgency_level = level
    return {"urgency_level": level}
