# 🎨 MCP 서버 템플릿 가이드

현재 `public-support-mcp` 프로젝트를 템플릿화해서 **새로운 MCP 서버를 빠르게 생성**할 수 있습니다.

---

## 🏗️ 템플릿 구조

### **공통 부분** (재사용 가능)
```
✅ MCP 프로토콜 핸들러 (JSON-RPC 2.0)
✅ FastAPI 기본 구조
✅ 세션 관리 (SESSION_STORE)
✅ 오류 처리 (isError, 표준 오류 코드)
✅ SSE 스트림 엔드포인트
✅ CORS 설정
```

### **가변 부분** (프로젝트별 커스터마이징)
```
🔧 도구 정의 (tools/)
🔧 비즈니스 로직
🔧 상태 필드 (SessionState)
🔧 스키마 (schemas.py)
🔧 도메인 규칙
```

---

## 🚀 새 프로젝트 만들기

### **방법 1: 자동 생성 스크립트 (추천)**

```bash
# 1. 새 프로젝트 생성
python create_mcp_project.py \
  --name "weather-mcp" \
  --description "실시간 날씨 정보 제공 MCP 서버" \
  --output ../weather-mcp

# 2. 생성된 프로젝트로 이동
cd ../weather-mcp

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행
python -m uvicorn main:app --reload --port 3100
```

**생성되는 구조:**
```
weather-mcp/
├── main.py              # MCP 코어 (✅ 표준 준수)
├── state.py             # 세션 관리
├── schemas.py           # 데이터 모델
├── requirements.txt     # 의존성
├── tools/              # 🔧 도구 구현 (여기를 수정)
│   ├── __init__.py
│   └── example.py
├── README.md
└── .gitignore
```

---

### **방법 2: 수동 복사 + 수정**

```bash
# 1. 템플릿 복사
cp -r public-support-mcp weather-mcp
cd weather-mcp

# 2. 불필요한 파일 제거
rm -rf __pycache__
rm -rf tools/__pycache__
rm tools/{actions,cards,domains,fallback,normalize,safety,scoring,urgency}.py

# 3. main.py 수정
# - PROJECT_CONFIG 변경
# - TOOL_DEFINITIONS 수정
# - TOOL_REGISTRY 업데이트

# 4. tools/ 에 새 도구 추가
# - 예: tools/weather.py

# 5. state.py 커스터마이징
# - SessionState 필드 수정
```

---

## 🛠️ 커스터마이징 가이드

### **1️⃣ 프로젝트 설정**

```python
# main.py

PROJECT_CONFIG = {
    "name": "weather-mcp",  # 🔧 변경
    "version": "1.0.0",
    "description": "실시간 날씨 정보 MCP",  # 🔧 변경
}
```

---

### **2️⃣ 도구 정의**

```python
# main.py

TOOL_DEFINITIONS = [
    {
        "name": "get_current_weather",  # 🔧 도구명
        "description": "현재 날씨 정보를 가져옵니다",  # 🔧 설명
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {  # 🔧 파라미터
                    "type": "string",
                    "description": "도시명 (예: Seoul)"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "온도 단위"
                }
            },
            "required": ["city"],  # 🔧 필수 파라미터
        },
    },
    # 🔧 더 많은 도구 추가...
]
```

---

### **3️⃣ 도구 핸들러 구현**

```python
# tools/weather.py

from typing import Dict, Any
from state import SessionState
import requests  # 외부 API 호출 예시


def get_current_weather(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    """날씨 정보 조회"""
    city = args.get("city")
    units = args.get("units", "celsius")
    
    # 🔧 실제 비즈니스 로직 구현
    # 예: 외부 API 호출
    response = requests.get(f"https://api.weather.com/current?city={city}")
    weather_data = response.json()
    
    # 상태 업데이트
    state.interaction_count += 1
    state.custom_data["last_city"] = city
    
    return {
        "city": city,
        "temperature": weather_data["temp"],
        "condition": weather_data["condition"],
        "units": units
    }
```

```python
# main.py

from tools.weather import get_current_weather

TOOL_REGISTRY = {
    "get_current_weather": get_current_weather,  # 🔧 핸들러 등록
}
```

---

### **4️⃣ 세션 상태 커스터마이징**

```python
# state.py

class SessionState(BaseModel):
    """세션 상태"""
    interaction_count: int = 0
    
    # 🔧 프로젝트별 필드 추가
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    last_query_time: Optional[str] = None
    favorite_cities: List[str] = Field(default_factory=list)
```

---

### **5️⃣ 응답 포맷팅 (선택)**

```python
# main.py

def build_content(tool: Optional[str], result: Any = None, error: Optional[str] = None):
    """🔧 도구별 응답 포맷 커스터마이징"""
    
    if tool == "get_current_weather":
        # 날씨 정보 특별 포맷팅
        city = result.get("city")
        temp = result.get("temperature")
        condition = result.get("condition")
        
        text = f"🌤️ {city} 현재 날씨\n\n"
        text += f"온도: {temp}°C\n"
        text += f"상태: {condition}"
        
        return [{"type": "text", "text": text}]
    
    # 기본 포맷
    return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
```

---

## 📦 프로젝트 예시

### **예시 1: 날씨 MCP**
```bash
python create_mcp_project.py \
  --name weather-mcp \
  --description "OpenWeather API 기반 날씨 정보" \
  --output ../weather-mcp
```

**도구:**
- `get_current_weather` - 현재 날씨
- `get_forecast` - 5일 예보
- `get_air_quality` - 공기질 정보

---

### **예시 2: 번역 MCP**
```bash
python create_mcp_project.py \
  --name translate-mcp \
  --description "다국어 번역 서비스" \
  --output ../translate-mcp
```

**도구:**
- `translate_text` - 텍스트 번역
- `detect_language` - 언어 감지
- `transliterate` - 음역

---

### **예시 3: 데이터베이스 MCP**
```bash
python create_mcp_project.py \
  --name db-query-mcp \
  --description "안전한 DB 쿼리 실행" \
  --output ../db-query-mcp
```

**도구:**
- `execute_query` - SELECT 쿼리 실행
- `get_schema` - 테이블 스키마 조회
- `export_to_csv` - 결과 CSV 출력

---

## ✅ 체크리스트

새 MCP 서버를 만들 때 확인할 사항:

### **필수 (표준 준수)**
- [ ] `capabilities.tools.listChanged` 명시
- [ ] `inputSchema`에 `additionalProperties: false` (매개변수 없는 도구)
- [ ] 모든 응답에 `isError` 플래그
- [ ] 알 수 없는 도구에 대한 표준 오류 코드 (-32602)
- [ ] JSON-RPC 2.0 준수

### **권장**
- [ ] 도구명 규칙 준수 (소문자, 밑줄, 1-128자)
- [ ] 입력 검증
- [ ] 명확한 오류 메시지
- [ ] 세션 관리
- [ ] 로깅

### **테스트**
- [ ] `initialize` 응답 확인
- [ ] `tools/list` 응답 확인
- [ ] 정상 도구 호출
- [ ] 오류 케이스 (알 수 없는 도구, 잘못된 입력)
- [ ] Claude Desktop 연결
- [ ] PlayMCP 연결

---

## 🎯 템플릿 파일들

| 파일 | 역할 | 수정 필요 |
|------|------|-----------|
| `mcp_template_main.py` | 템플릿 기본 구조 | 참고용 |
| `create_mcp_project.py` | 자동 생성 스크립트 | 실행만 |
| `MCP_TEMPLATE_GUIDE.md` | 이 가이드 | 읽기 |

---

## 🚀 배포

### **로컬 테스트**
```bash
python -m uvicorn main:app --reload --port 3100
```

### **Render 배포**
```bash
git init
git add .
git commit -m "Initial commit"
git push origin main
# Render 대시보드에서 연결
```

### **Docker**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3100"]
```

---

## 📚 참고 자료

- [MCP 프로토콜 명세](https://spec.modelcontextprotocol.io/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [Pydantic 문서](https://docs.pydantic.dev/)

---

## 🎉 완성된 템플릿 활용

**현재 `public-support-mcp`는 템플릿 역할을 합니다:**
1. ✅ MCP 프로토콜 100% 준수
2. ✅ 표준 오류 처리
3. ✅ 세션 관리
4. ✅ 실전 검증됨

**이제 이 구조로 무엇이든 만들 수 있습니다!** 🚀

- 날씨 API → `weather-mcp`
- 데이터베이스 → `db-query-mcp`
- 번역 → `translate-mcp`
- 파일 관리 → `file-manager-mcp`
- 계산기 → `calculator-mcp`

**각 프로젝트는 `tools/` 만 다르고, 나머지는 동일!** ✨

