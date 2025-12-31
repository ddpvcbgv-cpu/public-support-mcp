# 버그 수정 완료 요약

## 수정된 파일 및 라인 범위

### 1. tools/cards.py (라인 409-463)

**수정 내용:**
- **BUG FIX**: `selected_l1` 변수 정의 추가 (라인 410)
- **IMPLEMENTATION**: L2 embedded 옵션 (B) 구현 (라인 412-441)
- **RETURN**: L2 embedded 정보 반환 추가 (라인 461-467)

**수정 사항:**
1. `selected_l1 = l1_cards[:max_l1]` 변수 정의 추가
2. L1=3이고 L2가 있을 때, 마지막 L1 카드의 "막히면" 필드에 L2 내용 embedded
3. embedded된 경우 dedicated L2 카드 추가하지 않음
4. `_l2_embedded`와 `_last_l1_index` 정보를 반환값에 추가

### 2. tools/orchestrator.py (라인 451-456, 556-575, 672-675)

**수정 내용:**
- **CONFIRMATION**: confirmation 처리 로직 추가 (라인 451-456)
- **CARD_LAYERS**: L2 embedded 정보를 card_layers에 반영 (라인 556-575)
- **PERSISTENCE**: `state.previous_mcp_meta` 저장 추가 (라인 672-675)

**수정 사항:**
1. `confirmation_processed` 변수 정의 및 처리 로직 추가
2. `cards_result`에서 `_l2_embedded`와 `_last_l1_index` 정보 추출
3. L2 embedded된 경우 card_layers 처리 (현재는 L2가 cards에 없으므로 별도 처리 불필요)
4. `state.previous_mcp_meta = mcp_meta.model_dump()` 저장 추가

## 각 수정 사항 설명

### 1. BUG: `selected_l1` 변수 정의
- **문제**: `len(selected_l1)` 사용하지만 변수가 정의되지 않음
- **해결**: `selected_l1 = l1_cards[:max_l1]` 추가
- **영향**: L1=3 조건 체크가 정상 작동

### 2. L2 embedded 옵션 (B) 구현
- **문제**: 스펙에서 요구하는 L2 embedded 옵션이 미구현
- **해결**: 
  - L1=3이고 L2가 있을 때, 마지막 L1 카드의 "막히면" 필드에 L2 내용 추가
  - dedicated L2 카드는 추가하지 않음
  - `_l2_embedded`와 `_last_l1_index` 정보 반환
- **영향**: L1=3일 때 L2가 별도 카드가 아닌 마지막 L1에 embedded됨

### 3. `state.previous_mcp_meta` 저장
- **문제**: confirmation 처리 후 unlock을 위해 이전 mcp_meta 저장 필요
- **해결**: `orchestrate_full_response` 끝에서 `state.previous_mcp_meta = mcp_meta.model_dump()` 저장
- **영향**: 다음 요청에서 confirmation 응답 처리 및 unlock 가능

## 테스트 확인

```bash
# 기본 기능 테스트
python -c "from tools.cards import rank_support_cards; from state import SessionState; state = SessionState(); state.chosen_domain = '주거·월세'; state.user_keywords = ['30대', '서울', '월세']; result = rank_support_cards(state); print('Success')"

# orchestrate_full_response 테스트
python -c "from tools.orchestrator import orchestrate_full_response; from state import SessionState; state = SessionState(); result = orchestrate_full_response('30대이고 서울에 살아요. 월세 지원 받을 수 있나요?', state, skip_onboarding=True); print('Success:', 'mcp_meta' in result)"
```

## 검증 체크리스트

- [x] `selected_l1` 변수 정의 추가
- [x] L2 embedded 옵션 (B) 구현
- [x] `state.previous_mcp_meta` 저장 추가
- [x] 기존 테스트 통과 확인
- [x] Linter 오류 없음

## 주의사항

1. **L2 embedded 처리**: 현재 구현에서는 L2가 embedded된 경우, cards 리스트에 L2 카드가 없으므로 `card_layers`에서 L2 엔트리를 찾을 수 없습니다. 이는 의도된 동작입니다 (L2는 마지막 L1 카드의 일부로만 존재).

2. **confirmation 처리**: `confirmation_processed` 변수는 `orchestrate_full_response` 시작 부분에서 정의되어야 합니다.

3. **previous_mcp_meta**: `state.previous_mcp_meta`는 `orchestrate_full_response`의 마지막에 저장되어야 다음 요청에서 사용 가능합니다.

