"""
MCP Server Template - 재사용 가능한 MCP 서버 코어

이 템플릿은 MCP 프로토콜을 100% 준수하는 서버의 공통 부분을 제공합니다.
새로운 MCP 서버를 만들 때 이 코드를 복사하고 도메인 로직만 교체하세요.

✅ 제공하는 기능:
- JSON-RPC 2.0 프로토콜 처리
- MCP initialize/tools/list/tools/call 표준 구현
- 오류 처리 (isError 플래그, 표준 오류 코드)
- 세션 관리 기본 틀
- SSE 스트림 엔드포인트
- CORS 설정

🔧 커스터마이징 방법:
1. PROJECT_CONFIG 수정
2. TOOL_DEFINITIONS 정의
3. TOOL_REGISTRY 구현
4. SessionState 커스터마이징
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse


# ============================================================================
# 📋 프로젝트 설정 (커스터마이징 필요)
# ============================================================================

PROJECT_CONFIG = {
    "name": "your-mcp-server",  # 🔧 프로젝트명
    "version": "1.0.0",  # 🔧 버전
    "description": "Your MCP Server Description",  # 🔧 설명
}


# ============================================================================
# 🗂️ 세션 상태 (커스터마이징 필요)
# ============================================================================

class SessionState(BaseModel):
    """
    세션별 상태 저장소
    
    🔧 프로젝트에 맞게 필드를 추가/수정하세요
    """
    interaction_count: int = 0
    # 🔧 여기에 프로젝트별 상태 필드 추가
    # 예: user_profile, conversation_history, custom_data 등


class SessionStore:
    """스레드 안전한 세션 저장소 (재사용 가능)"""
    
    def __init__(self):
        self._store: Dict[str, SessionState] = {}
        self._lock = Lock()

    def get(self, session_id: Optional[str] = None) -> tuple[str, SessionState]:
        """세션 가져오기 또는 생성"""
        with self._lock:
            if session_id and session_id in self._store:
                return session_id, self._store[session_id]
            
            new_id = str(uuid4())
            new_state = SessionState()
            self._store[new_id] = new_state
            return new_id, new_state

    def set(self, session_id: str, state: SessionState):
        """세션 저장"""
        with self._lock:
            self._store[session_id] = state


SESSION_STORE = SessionStore()


# ============================================================================
# 🛠️ 도구 정의 (커스터마이징 필요)
# ============================================================================

TOOL_DEFINITIONS = [
    # 🔧 프로젝트의 도구를 여기에 정의하세요
    # 예시:
    {
        "name": "example_tool",
        "description": "예시 도구입니다",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "입력값"
                }
            },
            "required": ["input"],
        },
    },
]


# ============================================================================
# 🔧 도구 핸들러 (커스터마이징 필요)
# ============================================================================

ToolHandler = Callable[[Dict[str, Any], SessionState], Any]


def example_tool_handler(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    """
    예시 도구 핸들러
    
    🔧 실제 도구 로직을 구현하세요
    """
    input_value = args.get("input", "")
    state.interaction_count += 1
    
    return {
        "result": f"처리 완료: {input_value}",
        "count": state.interaction_count
    }


TOOL_REGISTRY: Dict[str, ToolHandler] = {
    # 🔧 도구명: 핸들러 함수 매핑
    "example_tool": example_tool_handler,
}


# ============================================================================
# 📤 응답 빌더 (재사용 가능 - 필요시 커스터마이징)
# ============================================================================

def build_content(tool: Optional[str], result: Any = None, error: Optional[str] = None) -> List[Dict[str, str]]:
    """
    도구 실행 결과를 MCP content 형식으로 변환
    
    🔧 프로젝트에 맞게 포맷팅 로직을 수정하세요
    """
    if error:
        return [{"type": "text", "text": f"오류: {error}"}]
    
    if not result:
        return [{"type": "text", "text": "결과 없음"}]
    
    # 기본 JSON 직렬화
    try:
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return [{"type": "text", "text": text}]
    except:
        return [{"type": "text", "text": str(result)}]


# ============================================================================
# 🌐 FastAPI 애플리케이션 (재사용 가능)
# ============================================================================

app = FastAPI(
    title=PROJECT_CONFIG["name"],
    version=PROJECT_CONFIG["version"],
    description=PROJECT_CONFIG["description"],
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 🔌 MCP 엔드포인트 (재사용 가능 - 수정 불필요)
# ============================================================================

@app.get("/")
async def root_get() -> JSONResponse:
    """GET: 기본 서버 정보"""
    return JSONResponse({
        "mcp": True,
        "name": PROJECT_CONFIG["name"],
        "version": PROJECT_CONFIG["version"],
        "endpoints": {
            "spec": "/mcp",
            "call": "/mcp/call",
            "sse": "/sse"
        },
    })


@app.post("/")
async def root_post(request: Request) -> JSONResponse:
    """POST: JSON-RPC 2.0 기반 MCP 프로토콜"""
    try:
        body = await request.body()
        body_str = body.decode('utf-8') if body else "{}"
        payload = json.loads(body_str) if body else {}
    except Exception as e:
        payload = {}
    
    if not isinstance(payload, dict):
        return JSONResponse({
            "mcp": True,
            "name": PROJECT_CONFIG["name"],
            "version": PROJECT_CONFIG["version"],
        })
    
    method = payload.get("method")
    request_id = payload.get("id")
    
    # ✅ MCP initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": PROJECT_CONFIG["name"],
                    "version": PROJECT_CONFIG["version"]
                },
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                }
            }
        })
    
    # ✅ MCP tools/list
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": TOOL_DEFINITIONS
            }
        })
    
    # ✅ MCP tools/call
    elif method == "tools/call":
        params = payload.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        session_id, state = SESSION_STORE.get(None)
        handler = TOOL_REGISTRY.get(tool_name)
        
        # 알 수 없는 도구
        if not handler:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            })
        
        # 도구 실행
        try:
            result = handler(arguments, state)
            SESSION_STORE.set(session_id, state)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": build_content(tool_name, result=result),
                    "isError": False,
                }
            })
        except Exception as exc:
            # 도구 실행 오류
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"도구 실행 오류: {str(exc)}"}],
                    "isError": True,
                }
            })
    
    # 알 수 없는 메서드
    return JSONResponse({
        "mcp": True,
        "name": PROJECT_CONFIG["name"],
        "version": PROJECT_CONFIG["version"],
    })


@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE 스트림 엔드포인트"""
    async def event_generator():
        yield {
            "event": "message",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "name": PROJECT_CONFIG["name"],
                    "version": PROJECT_CONFIG["version"],
                    "tools": TOOL_DEFINITIONS
                }
            })
        }
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                yield {
                    "event": "ping",
                    "data": json.dumps({"status": "alive"})
                }
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
    
    return EventSourceResponse(event_generator())


# ============================================================================
# 🚀 실행 (개발 서버)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3100, reload=True)
