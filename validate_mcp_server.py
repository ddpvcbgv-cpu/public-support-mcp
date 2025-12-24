#!/usr/bin/env python3
"""
MCP 서버 검증 스크립트
로컬 서버가 올바르게 설정되었는지 자동으로 확인합니다.

사용법:
    python validate_mcp_server.py
"""

import json
import sys
from typing import Any, Dict

import requests


def check_endpoint(url: str, expected_status: int = 200) -> tuple[bool, str]:
    """엔드포인트 확인"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == expected_status:
            return True, f"✅ {url} - {response.status_code}"
        return False, f"❌ {url} - 예상 {expected_status}, 실제 {response.status_code}"
    except Exception as e:
        return False, f"❌ {url} - 연결 실패: {e}"


def check_mcp_spec(url: str) -> tuple[bool, str]:
    """MCP spec 형식 확인"""
    try:
        response = requests.get(f"{url}/mcp", timeout=5)
        if response.status_code != 200:
            return False, f"❌ /mcp 응답 실패: {response.status_code}"

        spec = response.json()

        # 필수 필드 확인
        required_fields = ["name", "version", "description", "tools"]
        missing = [f for f in required_fields if f not in spec]
        if missing:
            return False, f"❌ MCP spec 필수 필드 누락: {missing}"

        # tools 확인
        if not isinstance(spec["tools"], list):
            return False, "❌ tools는 배열이어야 합니다"

        if len(spec["tools"]) == 0:
            return False, "⚠️  tools가 비어있습니다 (최소 1개 필요)"

        # 각 tool의 inputSchema 확인
        errors = []
        for i, tool in enumerate(spec["tools"]):
            if "name" not in tool:
                errors.append(f"tool[{i}]: name 누락")
            if "description" not in tool:
                errors.append(f"tool[{i}]: description 누락")
            if "inputSchema" not in tool:
                errors.append(f"tool[{i}]: inputSchema 누락 (camelCase!)")
            elif "input_schema" in tool:
                errors.append(f"tool[{i}]: input_schema 대신 inputSchema 사용 (camelCase!)")

        if errors:
            return False, f"❌ Tool 정의 오류:\n  " + "\n  ".join(errors)

        return True, f"✅ MCP spec 검증 통과 ({len(spec['tools'])}개 도구)"
    except Exception as e:
        return False, f"❌ MCP spec 확인 실패: {e}"


def check_jsonrpc(url: str) -> tuple[bool, str]:
    """JSON-RPC 프로토콜 확인"""
    try:
        # initialize 요청
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            return False, f"❌ initialize 요청 실패: {response.status_code}"

        result = response.json()
        if "jsonrpc" not in result or result["jsonrpc"] != "2.0":
            return False, "❌ JSON-RPC 2.0 형식이 아닙니다"
        if "id" not in result:
            return False, "❌ JSON-RPC 응답에 id 필드가 없습니다"
        if "result" not in result:
            return False, "❌ JSON-RPC 응답에 result 필드가 없습니다"

        return True, "✅ JSON-RPC 프로토콜 검증 통과"
    except Exception as e:
        return False, f"❌ JSON-RPC 확인 실패: {e}"


def main():
    """메인 검증 함수"""
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    print(f"🔍 MCP 서버 검증 시작: {base_url}\n")

    results = []

    # 1. 기본 엔드포인트 확인
    print("1️⃣  기본 엔드포인트 확인")
    ok, msg = check_endpoint(f"{base_url}/")
    print(f"   {msg}")
    results.append(ok)

    ok, msg = check_endpoint(f"{base_url}/mcp")
    print(f"   {msg}")
    results.append(ok)

    print()

    # 2. MCP spec 확인
    print("2️⃣  MCP spec 형식 확인")
    ok, msg = check_mcp_spec(base_url)
    print(f"   {msg}")
    results.append(ok)

    print()

    # 3. JSON-RPC 확인
    print("3️⃣  JSON-RPC 프로토콜 확인")
    ok, msg = check_jsonrpc(base_url)
    print(f"   {msg}")
    results.append(ok)

    print()

    # 결과 요약
    passed = sum(results)
    total = len(results)
    print(f"📊 검증 결과: {passed}/{total} 통과")

    if all(results):
        print("\n🎉 모든 검증 통과! MCP Inspector로 연결해보세요.")
        print(f"   npx @modelcontextprotocol/inspector")
        return 0
    else:
        print("\n⚠️  일부 검증 실패. 위의 오류를 수정하세요.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n검증 중단됨")
        sys.exit(1)

