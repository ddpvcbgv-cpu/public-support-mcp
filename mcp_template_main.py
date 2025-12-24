"""
MCP 서버 템플릿 - 새 프로젝트 시작 시 이 파일을 main.py로 복사하고 수정하세요.

수정해야 할 부분:
1. MCP_SPEC의 name, version, description
2. TOOL_REGISTRY에 도구 등록
3. MCP_SPEC의 tools 배열에 도구 추가
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from state import SESSION_STORE, SessionState

# TODO: 여기에 도구 함수들 import
# from tools.your_tool import your_tool_function


class ToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    session_id: str
    result: Any


app = FastAPI(
    title="YOUR_MCP_SERVER_NAME",  # TODO: 수정
    version="0.1.0",  # TODO: 수정
    description="YOUR_SERVER_DESCRIPTION",  # TODO: 수정
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TODO: MCP_SPEC 수정 - name, version, description, tools
MCP_SPEC = {
    "name": "your-mcp-server",  # TODO: 수정
    "version": "0.1.0",  # TODO: 수정
    "description": "Your MCP server description",  # TODO: 수정
    "endpoints": {
        "spec": "/mcp",
        "call": "/mcp/call",
        "sse": "/sse",
    },
    "tools": [
        # TODO: 여기에 도구 추가
        # {
        #     "name": "your_tool_name",
        #     "description": "도구 설명",
        #     "inputSchema": {
        #         "type": "object",
        #         "properties": {
        #             "param1": {
        #                 "type": "string",
        #                 "description": "파라미터 설명"
        #             }
        #         },
        #         "required": ["param1"]
        #     }
        # }
    ],
}


# TODO: 도구 핸들러 함수 작성
def _your_tool(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    """도구 실행 로직"""
    # TODO: 구현
    return {"result": "example"}


ToolHandler = Callable[[Dict[str, Any], SessionState], Any]

# TODO: TOOL_REGISTRY에 도구 등록
TOOL_REGISTRY: Dict[str, ToolHandler] = {
    # "your_tool_name": _your_tool,
}


def _build_content(
    tool: str | None,
    arguments: Dict[str, Any],
    result: Any = None,
    error: str | None = None,
) -> List[Dict[str, str]]:
    """PlayMCP 호환 content 생성"""
    if error:
        message_text = f"tool '{tool}' 처리 중 오류: {error}"
    elif result:
        message_text = f"tool '{tool}'이 정상적으로 처리되었습니다."
    else:
        message_text = f"tool '{tool}' 실행 완료"

    return [{"type": "text", "text": message_text}]


@app.api_route("/mcp", methods=["GET", "POST"])
async def get_mcp_spec(_: Dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(MCP_SPEC)


@app.get("/")
async def root_get() -> JSONResponse:
    """GET: 기본 서버 정보 반환"""
    return JSONResponse(
        {
            "mcp": True,
            "name": MCP_SPEC["name"],
            "version": MCP_SPEC["version"],
            "endpoints": MCP_SPEC["endpoints"],
        }
    )


@app.post("/")
async def root_post(request: Request) -> JSONResponse:
    """POST: JSON-RPC 2.0 기반 MCP 프로토콜 처리"""
    try:
        body = await request.body()
        body_str = body.decode("utf-8") if body else "{}"
        payload = json.loads(body_str) if body else {}
    except Exception:
        payload = {}

    if payload and isinstance(payload, dict):
        method = payload.get("method")
        request_id = payload.get("id")

        if method == "initialize":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": MCP_SPEC["name"],
                            "version": MCP_SPEC["version"],
                        },
                        "capabilities": {"tools": {}, "resources": {}},
                    },
                }
            )
        elif method == "tools/list":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": MCP_SPEC["tools"]},
                }
            )
        elif method == "tools/call":
            params = payload.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            session_id, state = SESSION_STORE.get(None)
            handler = TOOL_REGISTRY.get(tool_name)

            if handler:
                try:
                    result = handler(arguments, state)
                    SESSION_STORE.set(session_id, state)
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": _build_content(tool_name, arguments, result=result)
                            },
                        }
                    )
                except Exception as exc:
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32603, "message": str(exc)},
                        }
                    )

    return JSONResponse(
        {
            "mcp": True,
            "name": MCP_SPEC["name"],
            "version": MCP_SPEC["version"],
            "endpoints": MCP_SPEC["endpoints"],
        }
    )


@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE 스트림 엔드포인트"""
    async def event_generator():
        yield {
            "event": "message",
            "data": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": MCP_SPEC,
                }
            ),
        }
        try:
            while True:
                if await request.is_disconnected():
                    break
                yield {
                    "event": "ping",
                    "data": json.dumps({"status": "alive"}),
                }
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())


@app.post("/mcp/call")
async def call_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    """레거시 호환용 엔드포인트"""
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
            return JSONResponse(
                {
                    "ok": True,
                    "tool": tool,
                    "session_id": session_id,
                    "result": result,
                    "content": _build_content(tool, arguments, result=result),
                }
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "ok": False,
                    "tool": tool,
                    "session_id": session_id,
                    "error": str(exc),
                    "content": _build_content(tool, arguments, error=str(exc)),
                }
            )

    return JSONResponse(
        {
            "ok": True,
            "tool": tool,
            "session_id": session_id,
            "result": None,
            "content": _build_content(tool, arguments, result=None),
        }
    )

