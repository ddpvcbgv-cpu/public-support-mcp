# 배포 체크리스트

## ✅ 배포 전 확인 사항

### 코드 품질
- [x] Linter 오류 없음
- [x] 기본 기능 테스트 통과
- [x] 모든 버그 수정 완료
  - [x] `selected_l1` 변수 정의 추가
  - [x] L2 embedded 옵션 (B) 구현
  - [x] `state.previous_mcp_meta` 저장 추가

### 기능 구현 완료
- [x] v1.2 A~H 요구사항 모두 구현
- [x] Phase 2: 3-Level Layering 구현
- [x] Confirmation 처리 및 unlock 로직
- [x] card_overrides 지원

### 테스트
- [x] Phase 1 테스트 4개 구현
- [x] Phase 2 테스트 2개 구현
- [ ] Confirmation 후 unlock 테스트 (추가 권장)

### 문서
- [x] BUG_FIX_SUMMARY.md 작성
- [x] PHASE1_IMPLEMENTATION_SUMMARY.md 작성
- [x] PHASE2_IMPLEMENTATION_SUMMARY.md 작성
- [x] V1_2_IMPLEMENTATION_COMPLETE.md 작성

## 배포 후 확인 사항

1. **기본 기능 테스트**
   - orchestrate_full_response 정상 작동
   - mcp_meta 생성 확인
   - layering 정보 확인

2. **Confirmation 플로우 테스트**
   - INFERRED → TEMPORARY_SUGGESTION 생성
   - 사용자 응답 → unlock 확인

3. **L2 embedded 테스트**
   - L1=3 조건 충족 시 L2 embedded 확인
   - dedicated L2와 embedded L2 중복 없음 확인

4. **Crisis 플로우 테스트**
   - Step 1 확인 질문
   - UNSAFE 선택 시 Step 2 메시지
   - 카드 없음 확인

## 알려진 제한사항

1. **Rate limit 대안 경로**: 현재 체크만 구현, 대안 경로 제공 로직은 미구현 (추후 추가)
2. **Confirmation unlock 테스트**: 코드는 구현되었으나 테스트 파일에 없음 (추가 권장)

## 배포 일시
- 날짜: 2025-01-XX
- 버전: v1.2 + Phase 2
- 주요 변경사항:
  - v1.2 A~H 요구사항 구현
  - 3-Level Layering 구현
  - 버그 수정 (selected_l1, L2 embedded, previous_mcp_meta)

