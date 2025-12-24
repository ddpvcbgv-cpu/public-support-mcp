# MCP 서버 개발 체크리스트

## Phase 1: 기본 구조 (30분)

### ✅ 프로젝트 설정
- [ ] FastAPI 프로젝트 생성
- [ ] requirements.txt 작성 (fastapi, uvicorn, pydantic, sse-starlette)
- [ ] 기본 디렉토리 구조 생성 (tools/, state.py)

### ✅ 핵심 파일 생성
- [ ] main.py - FastAPI 앱 기본 구조
- [ ] state.py - SessionState, SessionStore
- [ ] tools/__init__.py - 패키지 초기화

## Phase 2: MCP 프로토콜 구현 (1시간)

### ✅ 기본 엔드포인트
- [ ] GET / - 서버 정보 반환
- [ ] POST / - JSON-RPC 2.0 처리
  - [ ] initialize 메서드 구현
  - [ ] tools/list 메서드 구현
  - [ ] tools/call 메서드 구현
- [ ] GET/POST /mcp - MCP spec 반환
- [ ] GET /sse - SSE 스트림 엔드포인트

### ✅ CORS 설정
- [ ] CORSMiddleware 추가
- [ ] allow_origins=["*"] 설정

### ✅ MCP_SPEC 정의
- [ ] name, version, description
- [ ] endpoints (spec, call, sse)
- [ ] tools 배열 (최소 1개로 시작)

## Phase 3: 도구 구현 (2-3시간)

### ✅ 첫 번째 도구 (검증용)
- [ ] tools/example.py 생성
- [ ] TOOL_REGISTRY에 등록
- [ ] MCP_SPEC에 추가
- [ ] inputSchema 정의 (camelCase 주의!)

### ✅ 나머지 도구들
- [ ] 각 도구별 파일 생성
- [ ] TOOL_REGISTRY 등록
- [ ] MCP_SPEC에 모두 추가

## Phase 4: 검증 (30분)

### ✅ 로컬 테스트
- [ ] uvicorn 실행
- [ ] GET / 접근 → JSON 확인
- [ ] GET /mcp 접근 → spec 확인
- [ ] POST / 테스트 (JSON-RPC)

### ✅ MCP Inspector 연결
- [ ] npx @modelcontextprotocol/inspector 실행
- [ ] 서버 URL 등록
- [ ] 연결 성공 확인
- [ ] Tools 탭에서 도구 목록 확인
- [ ] 도구 실행 테스트

### ✅ 에러 체크
- [ ] inputSchema (camelCase) 확인
- [ ] JSON-RPC 응답 형식 확인
- [ ] 에러 핸들링 확인

## Phase 5: 배포 (30분)

### ✅ Render 설정
- [ ] Git 저장소 연결
- [ ] Build Command: (없음 또는 pip install)
- [ ] Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
- [ ] Environment: Python 3.11+

### ✅ 배포 후 검증
- [ ] GET / 접근 확인
- [ ] GET /mcp 접근 확인
- [ ] MCP Inspector 재연결
- [ ] PlayMCP 업로드 시도

## Phase 6: 문서화 (1시간)

### ✅ README 작성
- [ ] 프로젝트 설명
- [ ] 설치 방법
- [ ] 사용 방법
- [ ] API 엔드포인트 설명
- [ ] 도구 목록 및 설명

### ✅ 코드 정리
- [ ] 디버깅 print 제거
- [ ] 주석 정리
- [ ] 타입 힌팅 확인

## 🚨 자주 하는 실수 체크

- [ ] input_schema → inputSchema (camelCase!)
- [ ] POST body 파싱 (await request.body())
- [ ] JSON-RPC id 필드 포함
- [ ] 에러 응답도 JSON-RPC 형식
- [ ] CORS 설정 확인
- [ ] Render 포트 설정 ($PORT)

## 📊 예상 소요 시간

- Phase 1-2: 1.5시간 (기본 구조)
- Phase 3: 2-3시간 (도구 구현)
- Phase 4: 30분 (검증)
- Phase 5: 30분 (배포)
- Phase 6: 1시간 (문서화)

**총: 5-6시간** (이번에는 10시간+ 걸렸지만, 템플릿 있으면 절반으로!)

