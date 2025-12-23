from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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

MCP_SPEC = {
    "name": "public-support-mcp",
    "version": "0.50-demo",
    "description": "공공 지원 내비게이터: 판정이 아닌 선택지·행동 설계 중심의 MCP 서버 (데모용)",
    "endpoints": {
        "spec": "/mcp",
        "call": "/mcp/call",
    },
    "tools": [
        {
            "name": "normalize_user_context",
            "description": "사용자 발화를 상황 정보로 정리합니다",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "사용자 입력 문장",
                    }
                },
                "required": ["message"],
            },
        }
    ],
}


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


@app.post("/mcp/call")
async def call_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool = payload.get("tool")
    arguments = payload.get("arguments") or {}
    session_id = payload.get("session_id")

    if not isinstance(arguments, dict):
        arguments = {}

    session_id, state = SESSION_STORE.get(session_id)
    handler = TOOL_REGISTRY.get(tool)

    if handler:
        try:
            result = handler(arguments, state)
            SESSION_STORE.set(session_id, state)
            return {
                "ok": True,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "result": result,
            }
        except HTTPException as exc:
            return {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": getattr(exc, "detail", str(exc)),
                "status": getattr(exc, "status_code", 400),
            }
        except Exception as exc:  # pragma: no cover - 데모용 방어
            return {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": f"tool execution failed: {exc}",
            }

    return {
        "ok": True,
        "tool": tool,
        "arguments": arguments,
        "session_id": session_id,
        "result": None,
    }

