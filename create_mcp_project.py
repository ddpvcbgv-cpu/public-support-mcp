#!/usr/bin/env python3
"""
MCP 프로젝트 생성기

현재 public-support-mcp를 템플릿으로 새로운 MCP 서버를 생성합니다.

사용법:
    python create_mcp_project.py \
        --name "weather-mcp" \
        --description "날씨 정보 MCP 서버" \
        --output ../weather-mcp

생성되는 구조:
    weather-mcp/
    ├── main.py              (MCP 프로토콜 핸들러)
    ├── state.py             (세션 관리)
    ├── schemas.py           (데이터 모델)
    ├── requirements.txt     (의존성)
    ├── tools/              (도구 구현)
    │   ├── __init__.py
    │   └── example.py      (예시 도구)
    ├── README.md
    └── .gitignore
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import Dict


TEMPLATE_FILES = {
    # 공통 파일 (그대로 복사)
    "requirements.txt": """fastapi==0.115.2
uvicorn[standard]==0.30.6
pydantic==2.9.2
sse-starlette==2.1.3
""",
    
    ".gitignore": """__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.venv/
venv/
.env
.DS_Store
""",
    
    "README.md": """# {project_name}

{description}

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 서버 실행
```bash
python -m uvicorn main:app --reload --port 3100
```

### 3. MCP 클라이언트 연결

**Claude Desktop:**
```json
{{
  "mcpServers": {{
    "{project_name}": {{
      "command": "python",
      "args": ["-m", "uvicorn", "main:app", "--port", "3100"],
      "cwd": "/path/to/{project_name}"
    }}
  }}
}}
```

**PlayMCP:**
```
Server URL: http://localhost:3100
```

## 🛠️ 도구 추가하기

1. `tools/` 폴더에 새 파일 생성 (예: `my_tool.py`)
2. 도구 함수 구현
3. `main.py`의 `TOOL_DEFINITIONS`에 추가
4. `TOOL_REGISTRY`에 핸들러 등록

## 📚 문서

- [MCP 프로토콜 명세](https://spec.modelcontextprotocol.io/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)

## 📄 라이선스

MIT License
""",

    "main.py": """# main.py - MCP 서버 코어 (자동 생성됨)
# 이 파일은 템플릿에서 생성되었습니다. 필요에 따라 수정하세요.

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from state import SESSION_STORE, SessionState
# 🔧 여기에 도구 import 추가
# from tools.example import example_tool_handler

# ============================================================================
# 📋 프로젝트 설정
# ============================================================================

PROJECT_CONFIG = {{
    "name": "{project_name}",
    "version": "1.0.0",
    "description": "{description}",
}}


# ============================================================================
# 🛠️ 도구 정의
# ============================================================================

TOOL_DEFINITIONS = [
    # 🔧 여기에 도구 정의 추가
    {{
        "name": "example_tool",
        "description": "예시 도구 - 실제 도구로 교체하세요",
        "inputSchema": {{
            "type": "object",
            "properties": {{
                "message": {{
                    "type": "string",
                    "description": "입력 메시지"
                }}
            }},
            "required": ["message"],
        }},
    }},
]


# ============================================================================
# 🔧 도구 핸들러
# ============================================================================

ToolHandler = Callable[[Dict[str, Any], SessionState], Any]


def example_tool_handler(args: Dict[str, Any], state: SessionState) -> Dict[str, str]:
    \"\"\"예시 도구 핸들러\"\"\"
    message = args.get("message", "")
    state.interaction_count += 1
    
    return {{
        "result": f"처리 완료: {{message}}",
        "interaction_count": state.interaction_count
    }}


TOOL_REGISTRY: Dict[str, ToolHandler] = {{
    "example_tool": example_tool_handler,
}}


# ============================================================================
# 📤 응답 빌더
# ============================================================================

def build_content(tool: Optional[str], result: Any = None, error: Optional[str] = None) -> List[Dict[str, str]]:
    \"\"\"도구 결과를 MCP content 형식으로 변환\"\"\"
    if error:
        return [{{"type": "text", "text": f"오류: {{error}}"}}]
    
    if not result:
        return [{{"type": "text", "text": "결과 없음"}}]
    
    try:
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return [{{"type": "text", "text": text}}]
    except:
        return [{{"type": "text", "text": str(result)}}]


# ============================================================================
# 🌐 FastAPI 애플리케이션
# ============================================================================

app = FastAPI(
    title=PROJECT_CONFIG["name"],
    version=PROJECT_CONFIG["version"],
    description=PROJECT_CONFIG["description"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 🔌 MCP 엔드포인트
# ============================================================================

@app.get("/")
async def root_get() -> JSONResponse:
    return JSONResponse({{
        "mcp": True,
        "name": PROJECT_CONFIG["name"],
        "version": PROJECT_CONFIG["version"],
        "endpoints": {{"spec": "/mcp", "call": "/mcp/call", "sse": "/sse"}},
    }})


@app.post("/")
async def root_post(request: Request) -> JSONResponse:
    try:
        body = await request.body()
        payload = json.loads(body.decode('utf-8')) if body else {{}}
    except:
        payload = {{}}
    
    method = payload.get("method")
    request_id = payload.get("id")
    
    if method == "initialize":
        return JSONResponse({{
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {{
                "protocolVersion": "2024-11-05",
                "serverInfo": {{
                    "name": PROJECT_CONFIG["name"],
                    "version": PROJECT_CONFIG["version"]
                }},
                "capabilities": {{
                    "tools": {{"listChanged": False}}
                }}
            }}
        }})
    
    elif method == "tools/list":
        return JSONResponse({{
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {{"tools": TOOL_DEFINITIONS}}
        }})
    
    elif method == "tools/call":
        params = payload.get("params", {{}})
        tool_name = params.get("name")
        arguments = params.get("arguments", {{}})
        
        session_id, state = SESSION_STORE.get(None)
        handler = TOOL_REGISTRY.get(tool_name)
        
        if not handler:
            return JSONResponse({{
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {{"code": -32602, "message": f"Unknown tool: {{tool_name}}"}}
            }})
        
        try:
            result = handler(arguments, state)
            SESSION_STORE.set(session_id, state)
            
            return JSONResponse({{
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {{
                    "content": build_content(tool_name, result=result),
                    "isError": False,
                }}
            }})
        except Exception as exc:
            return JSONResponse({{
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {{
                    "content": [{{"type": "text", "text": f"도구 실행 오류: {{str(exc)}}"}}],
                    "isError": True,
                }}
            }})
    
    return JSONResponse({{"mcp": True, "name": PROJECT_CONFIG["name"]}})


@app.get("/sse")
async def sse_endpoint(request: Request):
    async def event_generator():
        yield {{
            "event": "message",
            "data": json.dumps({{
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {{"name": PROJECT_CONFIG["name"], "tools": TOOL_DEFINITIONS}}
            }})
        }}
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                yield {{"event": "ping", "data": json.dumps({{"status": "alive"}})}}
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
    
    return EventSourceResponse(event_generator())
""",

    "state.py": """# state.py - 세션 관리 (자동 생성됨)

from __future__ import annotations

from threading import Lock
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    \"\"\"
    세션 상태
    
    🔧 프로젝트에 맞게 필드를 추가/수정하세요
    \"\"\"
    interaction_count: int = 0
    # 여기에 프로젝트별 상태 필드 추가
    custom_data: Dict[str, Any] = Field(default_factory=dict)


class SessionStore:
    \"\"\"스레드 안전한 세션 저장소\"\"\"
    
    def __init__(self):
        self._store: Dict[str, SessionState] = {{}}
        self._lock = Lock()

    def get(self, session_id: Optional[str] = None) -> tuple[str, SessionState]:
        with self._lock:
            if session_id and session_id in self._store:
                return session_id, self._store[session_id]
            
            new_id = str(uuid4())
            new_state = SessionState()
            self._store[new_id] = new_state
            return new_id, new_state

    def set(self, session_id: str, state: SessionState):
        with self._lock:
            self._store[session_id] = state


SESSION_STORE = SessionStore()
""",

    "schemas.py": """# schemas.py - 데이터 모델 (자동 생성됨)

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ToolResult(BaseModel):
    \"\"\"도구 실행 결과\"\"\"
    success: bool
    data: Any
    error: Optional[str] = None


# 🔧 여기에 프로젝트별 스키마 추가
""",

    "tools/__init__.py": """# tools package
""",

    "tools/example.py": """# tools/example.py - 예시 도구 (자동 생성됨)

from typing import Dict, Any
from state import SessionState


def example_tool_handler(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    \"\"\"
    예시 도구 핸들러
    
    🔧 실제 비즈니스 로직으로 교체하세요
    \"\"\"
    message = args.get("message", "")
    state.interaction_count += 1
    
    return {{
        "result": f"처리 완료: {{message}}",
        "count": state.interaction_count
    }}
""",
}


def create_project(name: str, description: str, output_dir: str):
    """새 MCP 프로젝트 생성"""
    
    output_path = Path(output_dir)
    
    # 디렉토리 생성
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "tools").mkdir(exist_ok=True)
    
    print(f"✅ 디렉토리 생성: {output_path}")
    
    # 파일 생성
    for file_path, content in TEMPLATE_FILES.items():
        full_path = output_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 템플릿 변수 치환
        content = content.format(
            project_name=name,
            description=description
        )
        
        full_path.write_text(content, encoding='utf-8')
        print(f"✅ 파일 생성: {file_path}")
    
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   🎉 MCP 프로젝트 생성 완료!                                      ║
║                                                                   ║
║   프로젝트: {name:<50} ║
║   위치: {output_dir:<56} ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝

📋 다음 단계:

1️⃣  프로젝트 디렉토리로 이동:
   cd {output_dir}

2️⃣  의존성 설치:
   pip install -r requirements.txt

3️⃣  서버 실행:
   python -m uvicorn main:app --reload --port 3100

4️⃣  도구 구현:
   - tools/ 폴더에 도구 추가
   - main.py의 TOOL_DEFINITIONS 수정
   - TOOL_REGISTRY에 핸들러 등록

5️⃣  테스트:
   curl http://localhost:3100/

🚀 Happy coding!
""")


def main():
    parser = argparse.ArgumentParser(
        description="MCP 프로젝트 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python create_mcp_project.py --name weather-mcp --description "날씨 MCP" --output ../weather-mcp
  python create_mcp_project.py --name translate-mcp --description "번역 MCP" --output ~/translate-mcp
"""
    )
    
    parser.add_argument(
        "--name",
        required=True,
        help="프로젝트 이름 (예: weather-mcp)"
    )
    
    parser.add_argument(
        "--description",
        required=True,
        help="프로젝트 설명"
    )
    
    parser.add_argument(
        "--output",
        required=True,
        help="출력 디렉토리 경로"
    )
    
    args = parser.parse_args()
    
    create_project(args.name, args.description, args.output)


if __name__ == "__main__":
    main()

