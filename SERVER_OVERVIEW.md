# Public Support MCP Server – 구조·기능 개요

이 서비스는 FastAPI 기반 MCP 서버이며, 공공 지원 내비게이터 시나리오를 반영해 다음 세 영역을 명확히 분리합니다.

## 1. 핵심 구조

```
main.py           # FastAPI 앱 + MCP 프로토콜 (JSON-RPC, SSE, legacy endpoint)
state.py          # SessionState/SessionStore (thread-safe 세션 관리)
tools/            # 실서비스 도구(도메인별 로직) 모음
  ├── normalize.py
  ├── urgency.py
  ├── domains.py
  ├── cards.py
  ├── actions.py
  ├── fallback.py
  └── safety.py
requirements.txt  # fastapi, uvicorn, pydantic, sse-starlette
```

## 2. `main.py`에서 제공하는 엔드포인트

- `GET/POST /` – JSON-RPC initialize/ tools/list/ tools/call 처리 + GET 헬스 체크 (JSON)
- `GET/POST /mcp` – MCP spec JSON 반환 (name/version/description/endpoints/tools)
- `GET /sse` – PlayMCP/Inspector가 기대하는 Server-Sent Events 스트림
- `POST /mcp/call` – 기존 tool 호출 API (legacy clients 대응)

추가: CORS 설정, JSON-RPC 응답 포맷, `content` 텍스트 메시지를 모든 결과에 포함.

## 3. MCP_SPEC (main.py 내부)

```json
{
  "name": "public-support-mcp",
  "version": "0.50-demo",
  "description": "공공 지원 선택지·행동 중심 MCP",
  "endpoints": {
    "spec": "/mcp",
    "call": "/mcp/call",
    "sse": "/sse"
  },
  "tools": [
    {
      "name": "normalize_user_context",
      "description": "사용자 발화를 정리",
      "inputSchema": { ... }
    }
  ]
}
```

## 4. tools/ 디렉터리별 기능 요약

| 파일 | 역할 |
|------|------|
| normalize.py | 입력 메시지에서 키워드를 추출하고 summary/kewyords 업데이트 |
| urgency.py | LEVEL_CUES 기반 메시지 분석→긴급도 레벨 결정 (1~3) |
| domains.py | 사용자 키워드와 이미 정한 필드 매핑→지원 분야 제안 |
| cards.py | 도메인별 카드 추천 + 중복 제거 로직 |
| actions.py | 오늘/내일/막힐 때 행동 단계 생성 |
| fallback.py | 상담 중 막힐 때 전화·서류·자격 대안 안내 |
| safety.py | 감정 안전 메시지 반환 (마무리 문장) |

## 5. 검증 & 배포 도구

- `MCP_SERVER_CHECKLIST.md` – 구현 단계별 체크리스트
- `validate_mcp_server.py` – 로컬 `/`, `/mcp`, JSON-RPC 확인 스크립트
- `setup_new_project.sh` – 템플릿 복사 + 기본화
- `mcp_template_main.py` – 다음 프로젝트용 템플릿 코드
- `NEXT_PROJECT_GUIDE.md`, `QUICK_START.md` – 향후 프로젝트 가이드/요약

## 6. 검증 흐름 예시

1. `uvicorn main:app --reload`로 실행
2. Inspector(또는 PlayMCP)에서 `POST /` 호출 → `initialize` 응답 확인
3. `tools/list` 요청 → MCP_SPEC 도구 확인
4. `tools/call`→ 실제 도구 실행 (normalize 등)
5. `GET /mcp` → spec JSON 확인
6. `GET /sse` → SSE 이벤트 확인

문서/스크립트가 함께 있으므로, 이 파일 하나만 복사해도 구조와 흐름을 바로 이해할 수 있습니다.

