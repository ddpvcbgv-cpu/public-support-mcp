# Public Support Navigation MCP
## v2 구조 개선 프롬프트 (보완 반영 버전)

너는 내가 운영 중인 MCP 서버
**Public Support Navigation MCP (publicSupportNav)**의
v2 구조 개선을 수행하는 역할이다.

이 작업은 기능 확장이나 새로운 검색 시스템 도입이 아니다.
기존 v1 구조를 유지하면서,
흐름 제어와 출력 안전성을 **"구현 가능한 수준"**으로 보완한다.

━━━━━━━━━━━━━━━━━━
🎯 v2 최종 목표
━━━━━━━━━━━━━━━━━━

1. 대화 흐름을 "턴 수"가 아닌 state.phase 기반으로 제어한다
2. 카드 선택 이전 제도명/기관명/조건 노출을 구조적으로 차단한다
3. 카드 출력 직전에 안전화(normalization)를 적용한다
4. UNDETERMINED(판단 불가) 상태를 명시적으로 허용한다
5. ChatGPT / PlayMCP 적용 범위를 명확히 분리한다

⚠️ 외부 검색 API, 정책 DB, 새로운 tool schema는 v2 범위가 아니다.

━━━━━━━━━━━━━━━━━━
🚫 절대 변경 금지
━━━━━━━━━━━━━━━━━━

- MCP 도구 구조 및 호출 순서
- 카드 랭킹 알고리즘의 기본 로직
- PlayMCP 클라이언트 분기 구조
- tool schema / parameters
- CARD_LIBRARY 데이터 자체의 의미 구조

━━━━━━━━━━━━━━━━━━
1️⃣ state.phase 도입 (필수)
━━━━━━━━━━━━━━━━━━

파일: `state.py`

**ConversationPhase 정의:**

```python
from enum import Enum

class ConversationPhase(str, Enum):
    PRE_DECISION = "PRE_DECISION"
    DIRECTION_SELECTED = "DIRECTION_SELECTED"
    EXECUTION_READY = "EXECUTION_READY"
```

**SessionState에 phase 필드 추가:**

```python
class SessionState(BaseModel):
    # ... 기존 필드들 ...
    phase: ConversationPhase = Field(default=ConversationPhase.PRE_DECISION)
```

━━━━━━━━━━━━━━━━━━
2️⃣ phase 전이 규칙 (구현 기준 - 보완)
━━━━━━━━━━━━━━━━━━

### PRE_DECISION → DIRECTION_SELECTED 전이 조건

아래 중 하나라도 충족되면 전이한다.

**A) 카드 선택 트리거 발생 시**

- **구현 위치**: `main.py`의 `_policy_trigger` 핸들러 내부
- **트리거 감지**: `tools/policy_trigger.py`의 `check_policy_trigger()`에서 `triggered=True` 반환될 때
- **전이 로직**:
  ```python
  # main.py의 _policy_trigger 함수 내부
  result = reveal_policy_name_if_triggered(message, state)
  
  if result.get("triggered") and result.get("trigger_type") == "card_selection":
      policy_info = result.get("policy_info", {})
      card_name = policy_info.get("card_name")
      
      if card_name:
          # accepted_cards에 추가 (중복 방지)
          if card_name not in state.accepted_cards:
              state.accepted_cards.append(card_name)
          
          # phase 전이
          if state.phase == ConversationPhase.PRE_DECISION:
              state.phase = ConversationPhase.DIRECTION_SELECTED
  ```

**B) 사용자 메시지에 카드 선택 의도 키워드 포함 시**

- 예: "1번", "이거", "이 카드", "선택할게요", "이걸로 할게요"
- **처리 위치**: `main.py`의 `_policy_trigger` 핸들러 또는 `_process_mcp_request`에서 메시지 파싱
- **키워드 리스트**:
  ```python
  CARD_SELECTION_KEYWORDS = ["1번", "2번", "3번", "이거", "이 카드", 
                             "선택할게요", "이걸로", "이것으로", "이걸 선택"]
  ```
- **전이 로직**: 위 A)와 동일하게 `accepted_cards` 업데이트 + phase 전이

### DIRECTION_SELECTED → EXECUTION_READY 전이 조건

**구현 위치**: `main.py`의 `call_tool` 함수 내부, `generate_action_steps` 도구 호출 시

**전이 조건**:
- `generate_action_steps` 도구가 호출될 때
- **가드 로직 필수**: phase가 `DIRECTION_SELECTED` 이상일 때만 전이
  ```python
  # main.py의 call_tool 함수 내부, generate_action_steps 호출 전
  if tool == "generate_action_steps":
      if state.phase == ConversationPhase.PRE_DECISION:
          # PRE_DECISION에서는 실행 단계로 넘어갈 수 없음
          # fallback 처리 또는 오류 반환
          return JSONResponse({
              "ok": False,
              "error": "카드를 먼저 선택해주세요",
              ...
          })
      elif state.phase == ConversationPhase.DIRECTION_SELECTED:
          state.phase = ConversationPhase.EXECUTION_READY
  ```

**또는 사용자 메시지에 실행 의도 표현 포함 시**:
- 예: "신청", "방법", "연락처", "어디로 가요", "어떻게 해요"
- **처리 위치**: `main.py`의 `_process_mcp_request`에서 메시지 파싱 후 phase 확인

⚠️ **중요**: v2에서는 "3턴 후" 같은 턴 수 규칙을 절대 사용하지 않는다.

━━━━━━━━━━━━━━━━━━
3️⃣ 제도명 공개 규칙 (v2)
━━━━━━━━━━━━━━━━━━

제도명 / 기관명 / 정책명은 다음 조건을 만족할 때만 공개 가능하다.

**공개 조건 (AND 조건)**:
- `state.phase >= DIRECTION_SELECTED`
- AND 사용자가 명시적으로 다음 중 하나를 요청했을 때:
  * 카드 선택 ("이거", "1번", "이 카드")
  * 제도명 질문 ("이게 뭐예요?", "정확히 이름이 뭐예요?")
  * 실행 의도 ("어디로 가요?", "어떻게 시작해요?")

**그 외 모든 경우**:
- 내부적으로 알고 있어도
- 출력에서는 반드시 추상 카드 언어만 사용한다

**구현 위치**:
- `policy_trigger.py`는 v2에서 필수 수정 대상이 아니다.
- (state.phase + 출력 안전화로 제어)
- 단, `check_policy_trigger()` 함수에서 phase 확인 로직 추가 가능:
  ```python
  # policy_trigger.py 내부 (선택사항)
  if state.phase == ConversationPhase.PRE_DECISION:
      # PRE_DECISION에서는 제도명 공개 트리거를 무시
      return {"triggered": False, ...}
  ```

━━━━━━━━━━━━━━━━━━
4️⃣ 카드 출력 안전화 (Normalization v2 – 구체화)
━━━━━━━━━━━━━━━━━━

**목표**:
- CARD_LIBRARY는 수정하지 않는다
- 출력 직전에 카드 텍스트를 안전화한다

**권장 구현 방식 (v2 표준)**:

**A) `tools/normalize.py`에 안전화 함수 추가**

파일: `tools/normalize.py`

함수: `sanitize_card_text(text: str, phase: ConversationPhase) -> str`

**제거 또는 마스킹 대상 패턴 (키워드 리스트 방식)**:

```python
# tools/normalize.py에 추가
POLICY_NAME_KEYWORDS = [
    # 급여 제도
    "생계급여", "주거급여", "의료급여", "교육급여",
    # 긴급 지원
    "긴급복지지원", "에너지바우처",
    # 문화/교통
    "문화누리카드", "기후동행카드", "청년문화패스",
    # 교육/고용
    "내일배움카드", "K-MOOC",
    # 기타
    "기초생활수급자", "차상위계층",
]

INSTITUTION_NAME_KEYWORDS = [
    "복지로",  # 연락처 맥락이 아니면 제거
    # "주민센터"는 연락처 맥락에서는 유지
]

def sanitize_card_text(text: str, phase: ConversationPhase) -> str:
    """
    카드 텍스트에서 제도명/기관명을 제거하거나 마스킹합니다.
    
    Args:
        text: 원본 카드 텍스트
        phase: 현재 대화 단계
    
    Returns:
        안전화된 텍스트
    """
    sanitized = text
    
    # PRE_DECISION 단계에서는 모든 제도명/기관명 제거
    if phase == ConversationPhase.PRE_DECISION:
        for keyword in POLICY_NAME_KEYWORDS:
            sanitized = sanitized.replace(keyword, "[제도명]")
        
        # 기관명 처리 (연락처 맥락 제외)
        # "📞 복지로 129" 같은 패턴은 유지, 단독 언급만 제거
        import re
        # 연락처 패턴이 아닌 "복지로"만 제거
        sanitized = re.sub(r'(?<!📞\s)(?<!전화\s)(?<!연락\s)복지로(?!\s\d)', '[기관명]', sanitized)
    
    # DIRECTION_SELECTED 이상에서는 제도명은 유지하되, 조건/결과 암시만 제거
    elif phase >= ConversationPhase.DIRECTION_SELECTED:
        # 금액 정보 제거
        sanitized = re.sub(r'\d+만원|\d+원|월\s*\d+만원', '[금액]', sanitized)
        # 결과 암시 제거
        result_phrases = ["대상입니다", "받을 수 있어요", "확정 지원", "지원 가능"]
        for phrase in result_phrases:
            sanitized = sanitized.replace(phrase, "")
    
    return sanitized.strip()
```

**B) 안전화 함수 적용 위치**

- `main.py`의 `_build_content` 함수 내부
- `rank_support_cards()` 결과를 출력하기 직전
- 모든 클라이언트(ChatGPT / PlayMCP)에 동일 적용

**구현 예시**:

```python
# main.py의 _build_content 함수 내부
elif tool == "rank_support_cards":
    if isinstance(result, dict):
        domain = result.get("domain", "")
        cards = result.get("cards", [])
        if cards:
            text = f"지금 상황을 기준으로 보면, {domain} 분야에서 열려 있는 선택지를 정리해봤어요.\n\n"
            
            for i, card in enumerate(cards, 1):
                card_title = card.get('card', '')
                
                # 🆕 v2: 카드 텍스트 안전화
                from tools.normalize import sanitize_card_text
                from state import ConversationPhase
                
                if card.get('이게_뭐냐면'):
                    description = card.get('이게_뭐냐면', '').rstrip()
                    # 안전화 적용
                    description = sanitize_card_text(description, state.phase)
                    evidence_line = " 근거: 공식 안내 참조 · 공공 지원 안내 (검증 2025-12)"
                    text += f"이게 뭐냐면:\n{description + evidence_line}\n\n"
                
                # 다른 필드들도 동일하게 안전화 적용
                # ...
```

━━━━━━━━━━━━━━━━━━
5️⃣ UNDETERMINED 상태 허용 (구체화)
━━━━━━━━━━━━━━━━━━

다음 경우에는 억지 카드 추천을 하지 않는다:

- `rank_support_cards()` 결과가 부적절한 경우
- 카드로 안전하게 추상화하기 어려운 경우
- 내부 판단이 불확실한 경우

**대응 방식 (구체화)**:

**옵션 A (권장): 폴백 카드 추가**

**구현 위치**: `tools/cards.py`의 `CARD_LIBRARY`

**폴백 카드 추가**:

```python
# tools/cards.py
CARD_LIBRARY = {
    # ... 기존 도메인들 ...
    
    # 🆕 v2: UNDETERMINED 상태용 폴백 카드
    "_FALLBACK": [
        {
            "card": "상황 정리 상담 안내",
            "이게_뭐냐면": "지금 상황을 더 구체적으로 정리하기 위해, 전문 상담사와 함께 단계별로 확인해보는 경로예요",
            "왜_지금_맞냐면": "상황이 복합적이거나 아직 명확하지 않을 때, 외부에서 객관적으로 정리해주는 것이 더 안전한 경우가 많아서요",
            "지금_하실_수_있는_말": "지금 상황을 정리하기 위한 상담을 받고 싶어요",
            "where": "📞 복지로 129 (전국 통합 상담) 또는 거주지 주민센터",
            "막히면": "상황 설명이 어려우시면, '상황 정리 상담 가능한 곳만 안내받고 싶어요'라고 말해도 괜찮아요"
        }
    ]
}
```

**옵션 B: UNDETERMINED 플래그 반환**

**구현 위치**: `tools/cards.py`의 `rank_support_cards()` 함수

**반환 형식 변경**:

```python
# tools/cards.py
def rank_support_cards(domain: str, state: SessionState) -> Dict[str, Any]:
    # ... 기존 로직 ...
    
    # 카드가 부적절하거나 불확실한 경우
    if not cards or len(cards) == 0 or _is_uncertain(cards, state):
        return {
            "domain": domain,
            "cards": [],  # 빈 리스트
            "undetermined": True,  # 🆕 UNDETERMINED 플래그
            "fallback_card": CARD_LIBRARY["_FALLBACK"][0]  # 폴백 카드
        }
    
    return {
        "domain": domain,
        "cards": cards,
        "undetermined": False
    }
```

**옵션 B 사용 시 처리 위치**: `main.py`의 `_build_content` 함수

```python
# main.py의 _build_content 함수 내부
elif tool == "rank_support_cards":
    if isinstance(result, dict):
        if result.get("undetermined", False):
            # UNDETERMINED 상태: 폴백 카드만 출력
            fallback_card = result.get("fallback_card", CARD_LIBRARY["_FALLBACK"][0])
            # 폴백 카드 렌더링
            # ...
        else:
            # 정상 카드 출력
            # ...
```

**권장**: 옵션 A (폴백 카드 추가)가 더 단순하고 안전하다.

━━━━━━━━━━━━━━━━━━
6️⃣ 내부 검색 정의 (v2 한정)
━━━━━━━━━━━━━━━━━━

v2에서 말하는 내부 검색은 다음으로 한정한다:

- ChatGPT의 기존 학습 지식 기반 추론
- 제도명/기관명에 대한 암묵적 연상
- 카드 설명 품질 향상을 위한 참고

❌ 외부 검색 API 사용 없음
❌ PlayMCP에는 내부 검색 개념 적용하지 않음

━━━━━━━━━━━━━━━━━━
7️⃣ ChatGPT vs PlayMCP 적용 범위
━━━━━━━━━━━━━━━━━━

**ChatGPT**:
- ROLE LOCK 프롬프트 적용 ⭕
- state.phase 기반 제어 적용 ⭕
- 카드 안전화 적용 ⭕
- 내부 지식 기반 추론 허용 ⭕

**PlayMCP**:
- ROLE LOCK 프롬프트 적용 ❌
- state.phase 기반 제어 ⭕
- 카드 안전화 적용 ⭕
- 내부 검색 개념 ❌

━━━━━━━━━━━━━━━━━━
8️⃣ v2 성공 기준
━━━━━━━━━━━━━━━━━━

v2는 다음을 만족하면 성공이다:

- ✅ 카드 선택 전 제도명 조기 노출 0%
- ✅ 대화 흐름이 state.phase로만 제어됨 (턴 수 규칙 없음)
- ✅ 판단 불가 상황에서 억지 추천 없음 (UNDETERMINED 처리)
- ✅ 기존 코드와 충돌 없음
- ✅ v3(검색 도입)를 위한 구조적 여지 확보

이 작업의 목적은
**"정보를 더 주는 것"**이 아니라
**"사고를 줄이고 구조를 명확히 하는 것"**이다.

━━━━━━━━━━━━━━━━━━
9️⃣ 구현 순서 (권장)
━━━━━━━━━━━━━━━━━━

1. `state.py`: ConversationPhase Enum + SessionState.phase 필드 추가
2. `tools/normalize.py`: `sanitize_card_text()` 함수 추가
3. `tools/cards.py`: UNDETERMINED 폴백 카드 추가 (옵션 A)
4. `main.py`: 
   - `_policy_trigger` 핸들러에 phase 전이 로직 추가
   - `call_tool` 함수에 `generate_action_steps` 가드 로직 추가
   - `_build_content` 함수에 카드 안전화 적용
5. 테스트: 각 phase별 동작 확인

이 기준으로 코드를 수정하라.

