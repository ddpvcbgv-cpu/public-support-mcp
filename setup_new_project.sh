#!/bin/bash
# 새 MCP 서버 프로젝트 생성 스크립트

set -e

PROJECT_NAME=$1

if [ -z "$PROJECT_NAME" ]; then
    echo "사용법: ./setup_new_project.sh <프로젝트명>"
    exit 1
fi

echo "🚀 새 MCP 서버 프로젝트 생성: $PROJECT_NAME"

# 디렉토리 생성
mkdir -p "$PROJECT_NAME"
cd "$PROJECT_NAME"

# 기본 파일 복사
echo "📁 기본 파일 생성 중..."
cp ../mcp_template_main.py main.py
cp ../state.py state.py
cp ../requirements.txt requirements.txt

# tools 디렉토리 생성
mkdir -p tools
touch tools/__init__.py

# .gitignore 생성
cat > .gitignore << EOF
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.venv/
venv/
env/
*.log
.DS_Store
EOF

# README 템플릿 생성
cat > README.md << EOF
# $PROJECT_NAME

MCP 서버 설명을 여기에 작성하세요.

## 설치

\`\`\`bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
\`\`\`

## 실행

\`\`\`bash
uvicorn main:app --reload
\`\`\`

## 검증

\`\`\`bash
python ../validate_mcp_server.py
\`\`\`

## MCP Inspector 연결

\`\`\`bash
npx @modelcontextprotocol/inspector
\`\`\`

서버 URL: http://localhost:8000
EOF

echo "✅ 프로젝트 생성 완료!"
echo ""
echo "다음 단계:"
echo "1. cd $PROJECT_NAME"
echo "2. main.py에서 MCP_SPEC 수정"
echo "3. 도구 구현"
echo "4. python ../validate_mcp_server.py 실행"

