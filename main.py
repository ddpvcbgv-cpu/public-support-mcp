from __future__ import annotations

from typing import Any, Callable, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# CORS: PlayMCP 등 외부 클라이언트 호환을 위해 최소 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def _build_content(tool: str | None, arguments: Dict[str, Any], result: Any = None, error: str | None = None) -> List[Dict[str, str]]:
    message_text: str | None = None
    message_arg = arguments.get("message") if isinstance(arguments, dict) else None

    if tool == "normalize_user_context":
        if isinstance(result, dict) and result.get("summary"):
            message_text = str(result.get("summary"))
        elif message_arg:
            message_text = f"입력하신 내용을 기준으로 상황을 정리했습니다: {message_arg}"

    if not message_text:
        if error:
            message_text = f"tool '{tool}' 처리 중 오류가 있었으나 연결은 유지됩니다: {error}"
        else:
            message_text = f"tool '{tool}'이 정상적으로 처리되었습니다."

    return [{"type": "text", "text": message_text}]


@app.api_route("/mcp", methods=["GET", "POST"])
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
            response = {
                "ok": True,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "result": result,
                "content": _build_content(tool, arguments, result=result),
            }
            return JSONResponse(response)
        except HTTPException as exc:
            error_detail = getattr(exc, "detail", str(exc))
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "status": getattr(exc, "status_code", 400),
                "content": _build_content(tool, arguments, error=error_detail),
            }
            return JSONResponse(response)
        except Exception as exc:  # pragma: no cover - 데모용 방어
            error_detail = f"tool execution failed: {exc}"
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "content": _build_content(tool, arguments, error=error_detail),
            }
            return JSONResponse(response)

    response = {
        "ok": True,
        "tool": tool,
        "arguments": arguments,
        "session_id": session_id,
        "result": None,
        "content": _build_content(tool, arguments, result=None),
    }
    return JSONResponse(response)

