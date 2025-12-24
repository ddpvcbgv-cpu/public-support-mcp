# 다음 프로젝트를 위한 완벽한 접근 가이드

## 🎯 목표: 시행착오를 50% 이상 줄이기

이번 경험을 바탕으로, 다음 MCP 서버 프로젝트는 **5-6시간 내에 완성**할 수 있습니다.

---

## 📋 단계별 접근법

### Phase 0: 준비 (10분) ⭐ **가장 중요!**

#### 1. 템플릿 준비
```bash
# 현재 프로젝트를 템플릿으로 저장
git checkout -b template
# 템플릿 파일들 정리 (mcp_template_main.py 등)
```

#### 2. 체크리스트 준비
- `MCP_SERVER_CHECKLIST.md` 확인
- 각 단계마다 체크박스 체크

#### 3. 검증 도구 준비
- `validate_mcp_server.py` 실행 가능한지 확인
- `npx @modelcontextprotocol/inspector` 설치 확인

---

### Phase 1: 프로젝트 생성 (30분)

#### ✅ 템플릿 복사
```bash
./setup_new_project.sh my-new-mcp-server
cd my-new-mcp-server
```

#### ✅ 기본 정보 수정
`main.py`에서:
- [ ] `MCP_SPEC["name"]` 수정
- [ ] `MCP_SPEC["version"]` 수정  
- [ ] `MCP_SPEC["description"]` 수정
- [ ] FastAPI app 메타데이터 수정

#### ✅ 첫 번째 도구 (최소 검증용)
- [ ] `tools/example.py` 생성
- [ ] 간단한 도구 함수 작성
- [ ] `TOOL_REGISTRY`에 등록
- [ ] `MCP_SPEC["tools"]`에 추가

**중요:** `inputSchema` (camelCase!) 사용

---

### Phase 2: 즉시 검증 (10분) ⭐ **이번엔 빠르게!**

#### ✅ 로컬 서버 실행
```bash
uvicorn main:app --reload
```

#### ✅ 자동 검증 스크립트 실행
```bash
python ../validate_mcp_server.py
```

**예상 결과:**
- ✅ 기본 엔드포인트 통과
- ✅ MCP spec 형식 통과
- ✅ JSON-RPC 프로토콜 통과

#### ✅ MCP Inspector 연결
```bash
npx @modelcontextprotocol/inspector
```

**예상 결과:**
- ✅ 연결 성공
- ✅ Tools 탭에서 도구 목록 확인
- ✅ 도구 실행 테스트 성공

**만약 실패하면:**
- `validate_mcp_server.py`의 오류 메시지 확인
- 가장 흔한 실수: `input_schema` → `inputSchema`

---

### Phase 3: 도구 구현 (2-3시간)

#### ✅ 나머지 도구들 추가
- [ ] 각 도구별 파일 생성
- [ ] `TOOL_REGISTRY`에 등록
- [ ] `MCP_SPEC["tools"]`에 추가

#### ✅ 중간 검증
도구 추가할 때마다:
```bash
python ../validate_mcp_server.py
```

---

### Phase 4: 배포 (30분)

#### ✅ Render 설정
- [ ] Git 저장소 연결
- [ ] Build Command: (없음)
- [ ] Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

#### ✅ 배포 후 검증
- [ ] `GET /` 접근 확인
- [ ] `GET /mcp` 접근 확인
- [ ] MCP Inspector 재연결
- [ ] PlayMCP 업로드 시도

---

## 🚨 자주 하는 실수 방지 체크리스트

### ❌ → ✅ 자동 체크

| 실수 | 올바른 방법 | 검증 방법 |
|------|------------|----------|
| `input_schema` | `inputSchema` | validate_mcp_server.py |
| POST body 안 읽음 | `await request.body()` | JSON-RPC 테스트 |
| JSON-RPC id 누락 | 모든 응답에 `id` 포함 | validate_mcp_server.py |
| CORS 안 설정 | CORSMiddleware 추가 | Inspector 연결 실패 시 |
| tools 배열 비어있음 | 최소 1개 도구 | validate_mcp_server.py |

---

## 📊 시간 비교

### 이번 프로젝트 (첫 시도)
- 기본 구조: 2시간
- MCP 프로토콜 구현: 3시간
- PlayMCP 연결 디버깅: 4시간
- 도구 구현: 2시간
- **총: 11시간**

### 다음 프로젝트 (템플릿 사용)
- 템플릿 복사: 10분
- 기본 정보 수정: 20분
- 첫 도구 + 검증: 30분
- 나머지 도구: 2-3시간
- 배포: 30분
- **총: 4-5시간** (50% 이상 단축!)

---

## 🎓 핵심 교훈

### 1. **템플릿의 힘**
- 한 번 만든 템플릿은 계속 재사용
- 검증된 코드는 그대로 복사

### 2. **자동화 검증**
- 수동 확인보다 자동 스크립트가 빠름
- `validate_mcp_server.py`로 즉시 확인

### 3. **단계별 검증**
- 모든 기능 구현 후 검증 ❌
- 각 단계마다 검증 ✅

### 4. **체크리스트 활용**
- 기억에 의존하지 말고 체크리스트 사용
- `MCP_SERVER_CHECKLIST.md` 따라하기

---

## 🚀 빠른 시작 명령어

```bash
# 1. 새 프로젝트 생성
./setup_new_project.sh my-new-server

# 2. 프로젝트로 이동
cd my-new-server

# 3. 기본 정보 수정
# main.py 편집

# 4. 첫 도구 추가
# tools/example.py 생성

# 5. 검증
python ../validate_mcp_server.py

# 6. Inspector 연결
npx @modelcontextprotocol/inspector
```

---

## 📝 체크리스트 요약

프로젝트 시작 전:
- [ ] 템플릿 파일 준비 완료
- [ ] 체크리스트 파일 준비 완료
- [ ] 검증 스크립트 테스트 완료

프로젝트 진행 중:
- [ ] 각 Phase 완료 시 체크리스트 확인
- [ ] 검증 스크립트로 자동 확인
- [ ] MCP Inspector로 수동 확인

프로젝트 완료 후:
- [ ] 모든 도구 MCP_SPEC에 추가
- [ ] README 작성
- [ ] 디버깅 코드 제거
- [ ] Render 배포 확인

---

## 💡 추가 팁

### Git 전략
```bash
# 템플릿 브랜치 유지
git checkout -b template
# 새 프로젝트는 새 저장소 또는 새 브랜치
```

### 문서화
- 각 도구마다 docstring 작성
- README에 사용 예시 포함
- API 엔드포인트 설명

### 테스트 (선택사항)
- pytest로 단위 테스트 작성
- 통합 테스트로 전체 플로우 검증

---

## 🎯 최종 목표

**다음 프로젝트에서:**
- ✅ 5시간 내 완성
- ✅ 시행착오 최소화
- ✅ MCP Inspector 즉시 연결
- ✅ PlayMCP 업로드 성공

**이 가이드를 따르면 가능합니다!** 🚀

