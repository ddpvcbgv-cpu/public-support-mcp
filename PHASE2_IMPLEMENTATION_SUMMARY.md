# Phase 2 구현 완료 요약 (3-Level Layering)

## 수정된 파일 목록

### 핵심 파일
1. **tools/cards.py**
   - `_classify_card_level()`: 카드를 L1/L2/L3로 분류
   - `_create_l3_card()`: L3 카드 생성
   - `rank_support_cards()`: 레이어별 카드 선택 및 prefix 추가

2. **tools/orchestrator.py**
   - `_check_legal_domain()`: Legal-ready guard (ADD-6)
   - `orchestrate_full_response()`:
     - 맥락 불명확 시 L1 제거 (L2+L3만)
     - L3 포함 조건 체크 (ADD-5)
     - Legal 도메인 시 L1 보수적 처리
     - mcp_meta.layering 및 card_layers 추가
     - L1 카드에만 action_steps 생성

3. **schemas.py**
   - `MCPMeta`: layering, card_layers 필드 추가 (이미 Phase 1에서 추가됨)

### 테스트 파일
4. **tests/test_v1_2_phase2.py** (신규)
   - 2개 레이어링 테스트

## 구현된 기능

### 3-Level Layering
- **L1 (조건부)**: 자격 확인이 필요한 지원
- **L2 (누구나)**: 누구나 이용 가능한 공공 정보
- **L3 (공식경로)**: 더 확인할 공식 경로

### 레이어 분류 로직
- 카드 이름, where, how 필드 기반 자동 분류
- 대부분의 카드는 L1 (기본값)
- "안내", "정보", "상담" 키워드 → L2
- "공식", "경로", "확인" 키워드 → L3

### 최종 구성 규칙
- 일반: 1 L1 + 1 L2 + (선택적) 1 L3
- 맥락 불명확: L2 + L3만 (L1 제거)
- 카드 개수: 2~3개 유지

### L3 포함 조건 (ADD-5)
- `any L1 action_lock==true` OR
- `any card stale==true` OR
- `user asks verify/apply/how/where` OR
- `mcp_meta.error_code in {RATE_LIMITED, UPSTREAM_TIMEOUT, UPSTREAM_QUOTA_EXCEEDED}`

### Legal-ready guard (ADD-6)
- 법적 이슈 유사 도메인 감지
- USER_STATED < 2 OR INFERRED 존재 시 L1 제거
- L2+L3만 제공 (공식 상담 경로 중심)

### action_steps 제거
- L2/L3 카드에는 action_steps 생성 안 함
- L1 카드가 있을 때만 action_steps 생성
- action_lock이 True면 action_steps 생성 안 함

## 로컬 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt pytest
```

### 2. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

### 3. 테스트 실행
```bash
# Phase 1 테스트
pytest tests/test_v1_2_phase1.py -v

# Phase 2 테스트
pytest tests/test_v1_2_phase2.py -v

# 전체 테스트
pytest tests/ -v
```

## 3가지 예시 입력 및 예상 동작

### 예시 1: 일반 케이스 → L1 + L2
**입력:**
```
"30대이고 서울에 살아요. 월세 지원 받을 수 있나요?"
```

**예상 동작:**
- `mcp_meta.layering.l1_count >= 1`
- `mcp_meta.layering.l2_count >= 1`
- 카드에 "[조건부]" 및 "[누구나]" prefix 포함
- `step_4_action_steps.actions` 생성 (L1이 있으므로)
- 카드 개수: 2~3개

### 예시 2: 맥락 불명확 → L2 + L3만
**입력:**
```
"도움이 필요해요"
```

**예상 동작:**
- `mcp_meta.layering.l1_count == 0` 또는 매우 낮음
- `mcp_meta.layering.l2_count >= 1`
- `mcp_meta.layering.l3_count >= 1`
- "[조건부]" 카드 없음 또는 매우 적음
- `step_4_action_steps.actions == None` (L1이 없으므로)
- 카드 개수: 2~3개

### 예시 3: Legal 도메인 → L2+L3만 (보수적)
**입력:**
```
"법률 상담이 필요해요"
```

**예상 동작:**
- Legal 도메인 감지
- USER_STATED 부족 → L1 제거
- L2+L3만 제공
- `mcp_meta.action_lock = True`
- 공식 상담 경로 중심 (결과 진술 없음)

## 검증 체크리스트

- [x] 레이어 정의 및 분류 로직 구현
- [x] 레이어 prefix 표시 (기존 필드 활용)
- [x] 최종 구성 규칙 (L1+L2+선택적L3)
- [x] 맥락 불명확 시 L2+L3만 허용
- [x] L3 포함 조건 구현 (ADD-5)
- [x] Legal-ready guard 구현 (ADD-6)
- [x] L2/L3 action_steps 제거
- [x] mcp_meta.layering 및 card_layers 추가
- [x] 테스트 2개 모두 구현

## 전체 구현 완료

### Phase 1 + Phase 2 통합
- v1.2 A~H 요구사항 완료
- 3-Level Layering 완료
- 모든 보완 규칙 (ADD-0 ~ ADD-6) 적용

### 수정된 파일 총계
- **Phase 1**: 11개 파일
- **Phase 2**: 4개 파일 (신규 1개)
- **총계**: 12개 파일 수정/생성

### 다음 단계
- 실제 카드에 `last_verified_date`, `official_source_category` 개별 설정
- Top 20 카드 리스트 정확한 정의
- 사용자 확인 후 unlock 로직 완성 (현재는 기본 구조만)

