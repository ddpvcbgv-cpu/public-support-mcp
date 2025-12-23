from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mcp_spec import get_spec
from state import SESSION_STORE, SessionState
from tools.actions import generate_action_steps
from tools.cards import rank_support_cards
from tools.domains import expose_available_domains
from tools.fallback import generate_fallback_paths
from tools.normalize import normalize_user_context
from tools.safety import compose_safe_response
from tools.urgency import assess_urgency_level


class ToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    session_id: str
    result: Any


app = FastAPI(
    title="Public Support Navigator MCP",
    version="0.50-demo",
    description="판정이 아니라 선택지와 행동 설계에 집중하는 공공 지원 내비게이터 (데모)",
)

MCP_SPEC = get_spec()


def _normalize(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    message = str(args.get("message", "") or "").strip()
    return normalize_user_context(message, state)


def _urgency(args: Dict[str, Any], state: SessionState) -> Dict[str, int]:
    context = args.get("context", {}) or {}
    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context는 object 여야 합니다.")
    return assess_urgency_level(context, state)


def _domains(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return expose_available_domains(state)


def _cards(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return rank_support_cards(state)


def _actions(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_action_steps(state)


def _fallback(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_fallback_paths(state)


def _safety(_: Dict[str, Any], state: SessionState) -> str:
    return compose_safe_response()


ToolHandler = Callable[[Dict[str, Any], SessionState], Any]

TOOL_REGISTRY: Dict[str, ToolHandler] = {
    "normalize_user_context": _normalize,
    "assess_urgency_level": _urgency,
    "expose_available_domains": _domains,
    "rank_support_cards": _cards,
    "generate_action_steps": _actions,
    "generate_fallback_paths": _fallback,
    "compose_safe_response": _safety,
}


@app.get("/mcp")
def get_mcp_spec() -> Dict[str, Any]:
    return MCP_SPEC


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "MCP server is running", "spec": "/mcp", "call": "/mcp/call"}


@app.post("/mcp/call", response_model=ToolCallResponse)
def call_tool(req: ToolCallRequest) -> ToolCallResponse:
    session_id, state = SESSION_STORE.get(req.session_id)

    if req.tool not in TOOL_REGISTRY:
        raise HTTPException(status_code=400, detail=f"알 수 없는 tool: {req.tool}")

    handler = TOOL_REGISTRY[req.tool]

    try:
        result = handler(req.arguments, state)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - 데모용 방어
        raise HTTPException(status_code=500, detail=f"도구 실행 중 오류가 발생했습니다: {exc}") from exc

    SESSION_STORE.set(session_id, state)
    return ToolCallResponse(session_id=session_id, result=result)

