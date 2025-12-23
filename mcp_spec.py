from __future__ import annotations

from typing import Any, Dict, List


def _tool(name: str, description: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "arguments": {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        },
    }


def get_spec() -> Dict[str, Any]:
    tools: List[Dict[str, Any]] = [
        _tool(
            "normalize_user_context",
            "사용자 발화를 행정적 조건으로 정리해 상황 요약과 키워드를 제공합니다.",
            {"message": {"type": "string", "description": "사용자 입력 문장"}},
        ),
        _tool(
            "assess_urgency_level",
            "문맥을 기반으로 긴급도 레벨(1~3)을 추정합니다.",
            {
                "context": {
                    "type": "object",
                    "description": "message 필드가 포함된 임의 컨텍스트",
                    "properties": {"message": {"type": "string"}, "urgency_hint": {"type": "integer"}},
                }
            },
        ),
        _tool(
            "expose_available_domains",
            "현재 상황에서 열려 있는 지원 분야(주거·월세, 생활 유지 등)를 제안합니다.",
            {},
        ),
        _tool(
            "rank_support_cards",
            "우선 탐색할 혜택 카드 2~3개를 제안합니다.",
            {},
        ),
        _tool(
            "generate_action_steps",
            "오늘/내일/막히면의 행동 단계를 제공합니다.",
            {},
        ),
        _tool(
            "generate_fallback_paths",
            "전화/서류/자격에서 막힐 때의 대안 경로를 제시합니다.",
            {},
        ),
        _tool(
            "compose_safe_response",
            "마지막에 붙는 감정 안전 문장을 반환합니다.",
            {},
        ),
    ]

    return {
        "name": "public-support-mcp",
        "version": "0.50-demo",
        "description": (
            "공공 지원 내비게이터: 판정이 아닌 선택지·행동 설계 중심의 MCP 서버 (데모용). "
            "실제 제도 명이나 공공 API는 사용하지 않습니다."
        ),
        "endpoints": {"spec": "/mcp", "call": "/mcp/call"},
        "tools": tools,
    }
