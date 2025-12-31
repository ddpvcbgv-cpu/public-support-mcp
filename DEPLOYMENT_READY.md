# 배포 준비 완료

## 배포 상태: ✅ READY

### 최종 확인 완료
- [x] 모든 버그 수정 완료
- [x] Linter 오류 없음
- [x] 기본 기능 테스트 통과
- [x] 모든 모듈 import 성공
- [x] FastAPI 앱 로드 성공

### 수정된 파일 목록
1. `tools/cards.py` - selected_l1 버그 수정, L2 embedded 구현
2. `tools/orchestrator.py` - confirmation 처리, previous_mcp_meta 저장
3. `tools/confirmation.py` - 신규 파일 (confirmation 처리 로직)
4. `state.py` - previous_mcp_meta 필드 추가
5. `main.py` - previous_mcp_meta 전달 추가

### 배포 후 테스트 항목
1. **기본 기능**
   - orchestrate_full_response 정상 작동
   - mcp_meta 생성 확인
   - layering 정보 확인

2. **Confirmation 플로우**
   - INFERRED → TEMPORARY_SUGGESTION 생성
   - 사용자 응답 → unlock 확인

3. **L2 embedded**
   - L1=3 조건 충족 시 L2 embedded 확인
   - dedicated L2와 embedded L2 중복 없음

4. **Crisis 플로우**
   - Step 1 확인 질문
   - UNSAFE 선택 시 Step 2 메시지
   - 카드 없음 확인

### 배포 명령어
```bash
# 로컬 테스트
uvicorn main:app --reload --port 8000

# 프로덕션 배포 (환경에 맞게 수정)
# 예: gunicorn, docker 등
```

### 주의사항
- `state.previous_mcp_meta`는 세션별로 저장되므로 세션 관리 확인 필요
- L2 embedded는 L1=3 조건에서만 작동
- Confirmation unlock은 다음 요청에서 처리됨

