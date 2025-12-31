# Phase 1 구현 완료 요약 (v1.2 A~H)

## 수정된 파일 목록

### 핵심 파일
1. **constants.py**
   - `TOP_20_CORE_CARDS`: Top 20 카드 리스트 추가
   - `OFFICIAL_SOURCE_CATEGORIES`: 공식 출처 카테고리 enum
   - `ERROR_CODES`: 에러 코드 및 UI 메시지 매핑
   - `STALE_THRESHOLD_DAYS_TOP20`, `STALE_THRESHOLD_DAYS_OTHER`: stale threshold

2. **schemas.py**
   - `MCPMeta` 클래스 추가: 모든 새 non-UI 필드 포함

3. **tools/cards.py**
   - `_is_top20_card()`: Top 20 카드 확인
   - `_get_card_metadata()`: 카드 메타데이터 추가 (evidence line, stale 계산)
   - `rank_support_cards()`: 메타데이터 자동 추가

4. **tools/orchestrator.py**
   - `_build_selection_rationale()`: USER_STATED vs INFERRED 구분
   - `_calculate_confidence()`: confidence 및 needs_verification 계산
   - `_build_mcp_meta()`: mcp_meta 생성
   - `orchestrate_full_response()`: 
     - Crisis 2-step guardrail 통합
     - mcp_meta 생성 및 추가
     - action_lock 시 action_steps 생성 안 함

5. **tools/safety.py**
   - `detect_crisis_intent()`: 의도-신호 조합 기반 위기 감지
   - `generate_crisis_step1_question()`: Step 1 확인 질문
   - `generate_crisis_step2_message()`: Step 2 안전 메시지

6. **tools/logging_utils.py** (신규)
   - `mask_pii()`: PII 마스킹
   - `log_safe()`: 안전한 로깅

7. **tools/rate_limit.py** (신규)
   - `check_rate_limit()`: IP 기반 rate limiting

8. **state.py**
   - `SessionStore`: TTL 30분 추가

9. **main.py**
   - `_process_mcp_request()`: request_id 생성, rate limiting 체크
   - `_orchestrate()`: request_id 전달

10. **tools/orchestrator.py** (format_orchestrated_response)
    - Evidence line 렌더링 추가

### 테스트 파일
11. **tests/test_v1_2_phase1.py** (신규)
    - 4개 필수 테스트

## 로컬 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 3. 테스트 실행
```bash
pytest tests/test_v1_2_phase1.py -v
```

## 3가지 예시 입력 및 예상 동작

### 예시 1: INFERRED 존재 → TEMPORARY_SUGGESTION
**입력:**
```
"30대인데 월세 지원 받을 수 있나요?"
```

**예상 동작:**
- `mcp_meta.selection_rationale`에 나이(USER_STATED), 소득(INFERRED) 포함
- `mcp_meta.card_state = "TEMPORARY_SUGGESTION"`
- `mcp_meta.action_lock = True`
- `mcp_meta.confirmation` 존재 (가구형태 또는 소득 확인 질문)
- `step_4_action_steps.actions = None` (잠금)
- 카드에 evidence line 포함: "근거: 공공 포털(복지로·정부24 등) · 온라인 안내 (검증 2025-01)"

### 예시 2: 위기 상황 → Crisis Step 2
**입력:**
```
"가족에게 성폭행을 당하고 있어요 무서워요"
```

**예상 동작:**
- `detect_crisis_intent()` 감지 → `crisis_type = "violence_domestic"`
- 첫 호출: `crisis_step1` 반환 (안전 확인 질문)
- 사용자 응답 "위험함": `safety_status = "UNSAFE"`
- `crisis_step2` 반환:
  - "지금은 추가 정보 입력보다 안전이 가장 중요합니다."
  - "112 (경찰)\n1366 (가정폭력상담소)"
- 카드 없음 (레이어링 우회)
- `mcp_meta.error_code = "SAFETY_GUARDRAIL_TRIGGERED"`

### 예시 3: Rate Limit 초과
**입력:**
```
연속 10회 이상 빠른 요청
```

**예상 동작:**
- `check_rate_limit()` → `is_allowed = False`
- 응답:
  - "잠시 요청이 몰려 있어요. 잠깐 후 다시 시도해 주세요."
  - "① 공식 포털 확인\n② 주민센터/콜센터 등 범주형 안내"
- `mcp_meta.error_code = "RATE_LIMITED"`
- `mcp_meta.retry_after` 포함

## 검증 체크리스트

- [x] 모든 새 non-UI 필드는 `mcp_meta`에만 추가
- [x] 기존 `meta` 필드는 수정하지 않음
- [x] Top-level response shape 유지
- [x] 도구 이름/엔드포인트 변경 없음
- [x] L1 전용 lock 규칙 (Phase 2에서 적용)
- [x] Crisis Step2는 레이어링 우회 (카드 없음)
- [x] Evidence line은 모든 카드에 적용
- [x] 테스트 4개 모두 구현

## Phase 2 완료

Phase 2 (3-Level Layering) 구현이 완료되었습니다. 자세한 내용은 `PHASE2_IMPLEMENTATION_SUMMARY.md`를 참조하세요.

### Phase 2 주요 구현
- L1/L2/L3 레이어 분류 및 표시
- 최종 구성 규칙 (L1+L2+선택적L3)
- L3 포함 조건 (ADD-5)
- Legal-ready guard (ADD-6)
- L2/L3 action_steps 제거

