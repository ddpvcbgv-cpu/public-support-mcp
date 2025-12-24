# 🚀 서버 업그레이드 가이드

## 업그레이드 내용 요약

### ✨ 주요 기능

1. **Rich Content 스키마** (`schemas.py`)
   - 구조화된 응답 포맷 (BenefitCard, ActionStep, UserProfile 등)
   - 시각적 힌트 (아이콘, 색상, 배지)
   - 진행 상태 표시

2. **Context-Aware 대화** (`state.py` 확장)
   - 대화 히스토리 자동 누적
   - 사용자 프로파일 추론
   - 상호작용 횟수 추적

3. **의도 분류 엔진** (`tools/intent.py`)
   - 메시지에서 의도 자동 분류
   - 긴급 의도 우선 감지
   - 대화 히스토리 기반 추론

4. **스코어링 시스템** (`tools/scoring.py`)
   - 사용자 상태 기반 혜택 매칭
   - 적합도 점수 계산 (0~100)
   - 점수 기반 자동 정렬

5. **Rich Response** (`main.py`)
   - 구조화된 데이터 첨부
   - 하위 호환성 유지
   - 선택적 활성화

---

## 📦 새로운 파일

```
schemas.py              # Rich Content 스키마 정의
tools/intent.py         # 의도 분류 엔진
tools/scoring.py        # 스코어링 시스템
test_upgrade.py         # 업그레이드 기능 테스트
UPGRADE_GUIDE.md        # 이 문서
```

---

## 🔧 수정된 파일

### `state.py`
```python
# 추가된 필드
conversation_history: List[ConversationTurn]  # 대화 히스토리
user_profile: UserProfile                      # 추론된 프로파일
interaction_count: int                         # 상호작용 횟수
```

### `tools/normalize.py`
- 대화 히스토리 자동 업데이트
- 사용자 프로파일 자동 추론

### `tools/cards.py`
- 스코어링 시스템 적용
- 적합도 점수 기반 정렬

### `main.py`
- `_build_rich_response()` 함수 추가
- Rich Response 지원 (선택적)
- 하위 호환성 유지

---

## 🎯 사용 방법

### 1. 기존 방식 (하위 호환)

```python
# 변경 없음 - 기존 코드 그대로 작동
response = requests.post(
    "http://localhost:8000/mcp/call",
    json={
        "tool": "normalize_user_context",
        "arguments": {"message": "도움이 필요해요"}
    }
)
```

### 2. Rich Response 사용

```python
# use_rich_response: true 추가
response = requests.post(
    "http://localhost:8000/mcp/call",
    json={
        "tool": "rank_support_cards",
        "arguments": {"domain": "주거·월세"},
        "use_rich_response": True  # 🆕
    }
)

result = response.json()
# result 구조:
# {
#   "ok": true,
#   "content": "텍스트 설명",
#   "attachments": [        # 🆕 구조화된 데이터
#     {
#       "type": "card",
#       "data": {
#         "title": "주거 안심 상담",
#         "eligibility_score": 85,
#         "visual": {
#           "icon": "💡",
#           "color": "#4CAF50",
#           "badge": "강력 추천"
#         }
#       }
#     }
#   ],
#   "metadata": {...}
# }
```

---

## 🧪 테스트

### 서버 시작
```bash
uvicorn main:app --reload
```

### 테스트 실행
```bash
python test_upgrade.py
```

### 예상 출력
```
🚀 업그레이드 기능 테스트 시작
============================================================

=== 1. Context-Aware 테스트 ===
✅ 응답 받음: True
📝 Content: 지금 말씀하신 내용을 정리하면, 월세, 생활비 같은 부분을 걱정하고 계신 걸로...
👤 추론된 프로파일: {'primary_concern': '주거', ...}

✅ 두 번째 응답 받음
🔄 상호작용 횟수: 2

=== 2. 스코어링 시스템 테스트 ===
✅ 혜택 추천 받음
📊 Content: 【주거·월세】 분야에서 3개 혜택을 찾았습니다.

1. 안전 이사 대비
   적합도: 90%
   배지: 강력 추천
   색상: #4CAF50

=== 3. Rich Action Steps 테스트 ===
✅ 행동 단계 받음
📋 Content: 행동 단계를 3단계로 나눴습니다.

📍 오늘 할 일
   예상 시간: 30분 이내
   난이도: easy

=== 4. 하위 호환성 테스트 ===
✅ 기존 방식 응답 받음: True
📝 Content 타입: <class 'list'>
🔍 Attachments 있음: False

============================================================
✅ 모든 테스트 완료!
```

---

## 📊 성능 비교

### Before (기존)
```
- 단순 키워드 매칭
- 순서대로 혜택 반환
- 대화 컨텍스트 없음
```

### After (업그레이드)
```
✅ 적합도 점수 기반 정렬
✅ 대화 히스토리 누적
✅ 사용자 프로파일 추론
✅ 구조화된 응답 (Rich Content)
✅ 시각적 힌트 (색상, 배지, 아이콘)
```

---

## 🎨 Rich Content 예시

### 혜택 카드
```json
{
  "type": "card",
  "data": {
    "title": "주거 안심 상담",
    "description": "월세·보증금 부담을 먼저 듣고...",
    "eligibility_score": 85,
    "where": "📞 복지로 129",
    "how": "1) 전화 후 현재 상황 간단히 설명...",
    "visual": {
      "icon": "💡",
      "color": "#4CAF50",
      "badge": "강력 추천"
    }
  }
}
```

### 행동 단계
```json
{
  "type": "action",
  "data": {
    "phase": "today",
    "title": "오늘 할 일",
    "description": "복지로 129에 전화...",
    "estimated_time": "30분 이내",
    "difficulty": "easy"
  }
}
```

---

## 🔍 디버깅

### 대화 히스토리 확인
```python
# 세션 상태에서 확인
state.conversation_history
# [
#   ConversationTurn(
#     message="월세가 부담돼요",
#     intent="housing_concern",
#     keywords=["월세"],
#     urgency=3
#   ),
#   ...
# ]
```

### 사용자 프로파일 확인
```python
state.user_profile
# UserProfile(
#   primary_concern="주거",
#   age_range=None,
#   employment_status=None
# )
```

### 적합도 점수 계산 로직
```python
from tools.scoring import calculate_eligibility_score

score = calculate_eligibility_score("주거 안심 상담", state)
# score = 긴급도(30) + 키워드(40) + 우선순위(20) + 히스토리(10)
```

---

## 🚨 주의사항

1. **하위 호환성**: 기존 클라이언트는 영향 없음
2. **선택적 활성화**: `use_rich_response: true` 필요
3. **메모리 관리**: 대화 히스토리는 최근 10개만 유지
4. **Mock 데이터**: 스코어링 메타데이터는 하드코딩 (실제 DB 연동 필요)

---

## 📈 다음 단계

### 즉시 가능
- [ ] 더 많은 도구에 Rich Response 적용
- [ ] 스코어링 메타데이터 확장
- [ ] 의도 분류 정확도 개선

### 중장기
- [ ] 실제 API 연동 (복지로 등)
- [ ] 데이터베이스 연결 (세션 영속화)
- [ ] 분석 대시보드 추가

---

## 💬 피드백

업그레이드 후 개선 사항:
1. **추천 품질**: 적합도 점수로 정확도 향상
2. **대화 품질**: 컨텍스트 기반 응답
3. **시각화**: Rich Content로 가독성 향상
4. **확장성**: 모듈화된 구조

---

**작성일**: 2024-12-24  
**버전**: 0.50-demo → 0.60-rich

