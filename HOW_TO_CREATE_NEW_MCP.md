# 🚀 새 MCP 서버 만들기 - 완벽 가이드

템플릿을 활용해서 **30분 안에** 새로운 MCP 서버를 만드는 실전 절차입니다.

---

## 📋 준비물

- ✅ Python 3.12+
- ✅ Git
- ✅ `public-support-mcp` 템플릿 (이 프로젝트)

---

## 🎯 전체 절차 (한눈에)

```
1. 프로젝트 생성 (2분)
   ↓
2. 기본 구조 확인 (3분)
   ↓
3. 도구 설계 (5분)
   ↓
4. 도구 구현 (10분)
   ↓
5. 테스트 (5분)
   ↓
6. 배포 (5분)
```

**총 30분 ⏱️**

---

## 📝 상세 절차

---

## **STEP 1: 프로젝트 생성** ⏱️ 2분

### 예시: "날씨 MCP" 만들기

```bash
# 1-1. 템플릿 디렉토리로 이동
cd c:/public-support-mcp

# 1-2. 새 프로젝트 생성
python create_mcp_project.py \
  --name "weather-mcp" \
  --description "실시간 날씨 정보 제공 MCP 서버" \
  --output ../weather-mcp

# 1-3. 생성된 프로젝트로 이동
cd ../weather-mcp

# 1-4. 의존성 설치
pip install -r requirements.txt
```

**생성되는 구조:**
```
weather-mcp/
├── main.py              ✅ MCP 코어 (표준 준수)
├── state.py             ✅ 세션 관리
├── schemas.py           ✅ 데이터 모델
├── tools/
│   ├── __init__.py
│   └── example.py       🔧 여기를 수정
├── requirements.txt
└── README.md
```

---

## **STEP 2: 기본 구조 확인** ⏱️ 3분

### 2-1. 서버 실행 테스트

```bash
# 서버 시작
python -m uvicorn main:app --reload --port 3100
```

**다른 터미널에서:**
```bash
# 테스트
curl http://localhost:3100/

# 예상 응답:
{
  "mcp": true,
  "name": "weather-mcp",
  "version": "1.0.0"
}
```

✅ **성공!** 기본 서버가 작동합니다.

### 2-2. 파일 구조 이해

**수정 불필요 (공통 부분):**
```
✅ main.py의 MCP 프로토콜 핸들러
✅ 세션 관리 (SESSION_STORE)
✅ 오류 처리 (isError, 표준 오류 코드)
✅ FastAPI 설정
```

**수정 필요 (프로젝트별):**
```
🔧 main.py → TOOL_DEFINITIONS (도구 정의)
🔧 main.py → TOOL_REGISTRY (핸들러 등록)
🔧 tools/*.py (도구 구현)
🔧 state.py → SessionState (필요시)
```

---

## **STEP 3: 도구 설계** ⏱️ 5분

### 3-1. 어떤 도구가 필요한가?

**예시: 날씨 MCP**
```
✅ get_current_weather   - 현재 날씨
✅ get_forecast          - 5일 예보
✅ get_air_quality       - 공기질
```

### 3-2. 각 도구의 입출력 설계

**도구 1: `get_current_weather`**
```python
# 입력
{
  "city": "Seoul",
  "units": "celsius"  # 선택
}

# 출력
{
  "city": "Seoul",
  "temperature": 15,
  "condition": "Cloudy",
  "humidity": 65,
  "wind_speed": 5
}
```

---

## **STEP 4: 도구 구현** ⏱️ 10분

### 4-1. 도구 정의 (`main.py`)

```python
# main.py

TOOL_DEFINITIONS = [
    {
        "name": "get_current_weather",
        "description": "현재 날씨 정보를 조회합니다",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "도시명 (예: Seoul, Tokyo)"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "온도 단위 (기본: celsius)"
                }
            },
            "required": ["city"],
        },
    },
    # 더 많은 도구 추가...
]
```

### 4-2. 도구 핸들러 구현 (`tools/weather.py`)

```python
# tools/weather.py

from typing import Dict, Any
from state import SessionState
import requests


def get_current_weather(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    """현재 날씨 조회"""
    city = args.get("city")
    units = args.get("units", "celsius")
    
    # 실제 API 호출 (예시: OpenWeather API)
    api_key = "YOUR_API_KEY"
    url = f"https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric" if units == "celsius" else "imperial"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # 상태 업데이트
    state.interaction_count += 1
    
    return {
        "city": city,
        "temperature": data["main"]["temp"],
        "condition": data["weather"][0]["description"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"]
    }
```

### 4-3. 핸들러 등록 (`main.py`)

```python
# main.py

from tools.weather import get_current_weather

TOOL_REGISTRY = {
    "get_current_weather": get_current_weather,
}
```

---

## **STEP 5: 테스트** ⏱️ 5분

### 5-1. 서버 재시작

```bash
# 서버 재시작 (--reload 옵션이면 자동)
python -m uvicorn main:app --reload --port 3100
```

### 5-2. 도구 목록 확인

```bash
curl -X POST http://localhost:3100/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

**예상 응답:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_current_weather",
        "description": "현재 날씨 정보를 조회합니다",
        ...
      }
    ]
  }
}
```

### 5-3. 도구 실행 테스트

```bash
curl -X POST http://localhost:3100/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_current_weather",
      "arguments": {
        "city": "Seoul",
        "units": "celsius"
      }
    }
  }'
```

**예상 응답:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"city\": \"Seoul\",\n  \"temperature\": 15,\n  ..."
      }
    ],
    "isError": false
  }
}
```

✅ **성공!** 도구가 작동합니다.

---

## **STEP 6: 배포** ⏱️ 5분

### 6-1. Git 초기화

```bash
cd ../weather-mcp

git init
git add .
git commit -m "Initial commit: Weather MCP Server

- 현재 날씨 조회 도구 구현
- OpenWeather API 연동
- MCP 프로토콜 100% 준수"
```

### 6-2. GitHub 푸시

```bash
# GitHub에 새 저장소 생성 후
git remote add origin https://github.com/YOUR_USERNAME/weather-mcp.git
git push -u origin main
```

### 6-3. Render 배포

**Render 대시보드에서:**
1. "New +" → "Web Service"
2. GitHub 저장소 연결: `weather-mcp`
3. 설정:
   ```
   Name: weather-mcp
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. "Create Web Service" 클릭

⏱️ **3~5분 후 배포 완료!**

---

## 📱 클라이언트 연결

### Claude Desktop

```json
// ~/.config/claude/claude_desktop_config.json

{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["-m", "uvicorn", "main:app", "--port", "3100"],
      "cwd": "/path/to/weather-mcp"
    }
  }
}
```

### PlayMCP

```
Server URL: https://your-app.onrender.com
또는
Server URL: http://localhost:3100 (로컬)
```

---

## ✅ 체크리스트

프로젝트 완성 전 확인:

### **필수**
- [ ] `TOOL_DEFINITIONS` 정의
- [ ] 도구 핸들러 구현
- [ ] `TOOL_REGISTRY` 등록
- [ ] 로컬 테스트 성공
- [ ] 오류 케이스 테스트

### **권장**
- [ ] 도구명 규칙 준수 (소문자, 밑줄)
- [ ] 입력 검증 추가
- [ ] 명확한 오류 메시지
- [ ] README.md 업데이트
- [ ] API 키 환경변수 처리

### **배포**
- [ ] Git 커밋
- [ ] GitHub 푸시
- [ ] Render/서버 배포
- [ ] 배포된 URL 테스트
- [ ] 클라이언트 연결 확인

---

## 🎯 실전 예시들

### **예시 1: 번역 MCP** (20분)

```bash
# 생성
python create_mcp_project.py \
  --name translate-mcp \
  --description "다국어 번역 MCP" \
  --output ../translate-mcp

# 도구 설계
- translate_text(text, target_lang)
- detect_language(text)
- transliterate(text, script)

# API: Google Translate API
```

---

### **예시 2: 데이터베이스 MCP** (25분)

```bash
# 생성
python create_mcp_project.py \
  --name db-query-mcp \
  --description "안전한 DB 쿼리 MCP" \
  --output ../db-query-mcp

# 도구 설계
- execute_query(sql)           # SELECT만 허용
- get_table_schema(table_name)
- export_to_csv(query)

# 연결: PostgreSQL
```

---

### **예시 3: 파일 관리 MCP** (15분)

```bash
# 생성
python create_mcp_project.py \
  --name file-manager-mcp \
  --description "파일 관리 MCP" \
  --output ../file-manager-mcp

# 도구 설계
- list_files(directory)
- read_file(path)
- search_files(pattern)
- get_file_info(path)

# 로컬 파일 시스템
```

---

## 💡 팁

### **빠르게 시작하기**
```bash
# 1. 생성
python create_mcp_project.py --name my-mcp --description "My MCP" --output ../my-mcp

# 2. 이동 + 설치
cd ../my-mcp && pip install -r requirements.txt

# 3. 실행
python -m uvicorn main:app --reload --port 3100

# 4. 다른 터미널에서 편집
code .
```

### **API 키 관리**
```python
# .env 파일
OPENWEATHER_API_KEY=your_key_here

# main.py
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("OPENWEATHER_API_KEY")
```

### **의존성 추가**
```bash
# requirements.txt에 추가
echo "requests==2.31.0" >> requirements.txt
pip install -r requirements.txt
```

---

## 🎉 완성!

**30분 안에 새로운 MCP 서버 완성!**

1. ✅ MCP 프로토콜 100% 준수
2. ✅ Claude Desktop 호환
3. ✅ PlayMCP 호환
4. ✅ 표준 오류 처리
5. ✅ 세션 관리
6. ✅ 배포 완료

**이제 무엇이든 만들 수 있습니다!** 🚀

---

## 📚 참고

- `MCP_TEMPLATE_GUIDE.md` - 상세 가이드
- `mcp_template_main.py` - 템플릿 코드
- `create_mcp_project.py` - 생성 스크립트
- [MCP 프로토콜](https://spec.modelcontextprotocol.io/)

---

## ❓ 자주 묻는 질문

**Q: 여러 도구를 한 번에 추가할 수 있나요?**
A: 네! `TOOL_DEFINITIONS`에 계속 추가하면 됩니다.

**Q: 외부 API가 필요한가요?**
A: 아니요. 로컬 파일, 계산, 데이터 처리 등도 가능합니다.

**Q: 기존 도구를 수정하려면?**
A: `tools/` 파일 수정 → 서버 재시작 (--reload면 자동)

**Q: 배포 비용은?**
A: Render 무료 플랜 사용 가능 (750시간/월)

**Q: 템플릿을 수정해도 되나요?**
A: 네! 프로젝트에 맞게 자유롭게 수정하세요.

