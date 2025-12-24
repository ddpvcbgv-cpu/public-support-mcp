# MCP 서버 빠른 시작 가이드

## 🚀 5단계로 새 MCP 서버 만들기

### Step 1: 프로젝트 복사 (5분)
```bash
# 템플릿에서 새 프로젝트 생성
cp -r mcp-server-template my-new-mcp-server
cd my-new-mcp-server
```

### Step 2: 기본 정보 수정 (10분)
`main.py`에서 다음 부분 수정:
- `MCP_SPEC["name"]` - 서버 이름
- `MCP_SPEC["version"]` - 버전
- `MCP_SPEC["description"]` - 설명
- FastAPI app의 title, version, description

### Step 3: 첫 번째 도구 만들기 (30분)
1. `tools/my_first_tool.py` 생성
2. 도구 함수 작성
3. `main.py`에 import
4. `TOOL_REGISTRY`에 등록
5. `MCP_SPEC["tools"]`에 추가

### Step 4: 로컬 테스트 (10분)
```bash
# 가상환경 설정
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 서버 실행
uvicorn main:app --reload

# 다른 터미널에서 테스트
curl http://localhost:8000/
curl http://localhost:8000/mcp
```

### Step 5: MCP Inspector로 검증 (5분)
```bash
npx @modelcontextprotocol/inspector
```
- 브라우저에서 `http://localhost:8000` 입력
- 연결 확인
- Tools 탭에서 도구 목록 확인

## ✅ 체크리스트

### 필수 확인사항
- [ ] `inputSchema` (camelCase!) 사용
- [ ] JSON-RPC 응답에 `id` 필드 포함
- [ ] CORS 설정 완료
- [ ] MCP Inspector 연결 성공

### 자주 하는 실수
- ❌ `input_schema` (snake_case) → ✅ `inputSchema` (camelCase)
- ❌ POST body 파싱 안 함 → ✅ `await request.body()` 사용
- ❌ JSON-RPC id 누락 → ✅ 모든 응답에 `id` 포함

## 📝 다음 단계

1. 나머지 도구들 추가
2. README 작성
3. Render 배포
4. PlayMCP 업로드

## 🆘 문제 해결

### MCP Inspector 연결 안 됨
1. 서버가 실행 중인지 확인
2. CORS 설정 확인
3. `GET /` 응답 확인 (mcp: true 있어야 함)

### Tools 목록 안 보임
1. `MCP_SPEC["tools"]`에 도구 추가했는지 확인
2. `inputSchema` (camelCase) 확인
3. Inspector 재연결

### PlayMCP 업로드 실패
1. MCP Inspector 연결 먼저 확인
2. Render 로그 확인
3. `POST /` 로그에서 JSON-RPC 요청 확인

