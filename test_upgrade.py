"""업그레이드 기능 테스트 스크립트"""
import json
import requests

BASE_URL = "http://localhost:8000"


def test_normalize_with_context_aware():
    """Context-Aware 기능 테스트"""
    print("\n=== 1. Context-Aware 테스트 ===")
    
    # 첫 번째 메시지
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "normalize_user_context",
            "arguments": {"message": "월세가 너무 부담돼요. 생활비도 부족하고요."},
            "use_rich_response": True,
        }
    )
    
    result = response.json()
    print(f"✅ 응답 받음: {result.get('ok')}")
    print(f"📝 Content: {result.get('content', '')[:100]}...")
    
    if result.get('attachments'):
        profile = result['attachments'][0]['data'].get('profile', {})
        print(f"👤 추론된 프로파일: {profile}")
    
    session_id = result.get('session_id')
    
    # 두 번째 메시지 (같은 세션)
    response2 = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "normalize_user_context",
            "arguments": {"message": "병원도 가야 하는데 돈이 없어요."},
            "session_id": session_id,
            "use_rich_response": True,
        }
    )
    
    result2 = response2.json()
    print(f"\n✅ 두 번째 응답 받음")
    
    if result2.get('attachments'):
        interaction_count = result2['attachments'][0]['data'].get('interaction_count', 0)
        print(f"🔄 상호작용 횟수: {interaction_count}")


def test_scoring_system():
    """스코어링 시스템 테스트"""
    print("\n\n=== 2. 스코어링 시스템 테스트 ===")
    
    # 사용자 컨텍스트 설정
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "normalize_user_context",
            "arguments": {"message": "월세 연체되고 있어요. 급해요."},
        }
    )
    session_id = response.json().get('session_id')
    
    # 긴급도 설정
    requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "assess_urgency_level",
            "arguments": {"context": {"message": "당장 내일까지 월세 내야해요"}},
            "session_id": session_id,
        }
    )
    
    # 혜택 추천 (스코어링 적용)
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "rank_support_cards",
            "arguments": {"domain": "주거·월세"},
            "session_id": session_id,
            "use_rich_response": True,
        }
    )
    
    result = response.json()
    print(f"✅ 혜택 추천 받음")
    print(f"📊 Content: {result.get('content', '')}")
    
    if result.get('attachments'):
        for i, card in enumerate(result['attachments'], 1):
            card_data = card['data']
            print(f"\n{i}. {card_data.get('title')}")
            print(f"   적합도: {card_data.get('eligibility_score')}%")
            print(f"   배지: {card_data.get('visual', {}).get('badge')}")
            print(f"   색상: {card_data.get('visual', {}).get('color')}")


def test_rich_action_steps():
    """Rich Action Steps 테스트"""
    print("\n\n=== 3. Rich Action Steps 테스트 ===")
    
    # 컨텍스트 설정
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "normalize_user_context",
            "arguments": {"message": "의료비 지원 받고 싶어요"},
        }
    )
    session_id = response.json().get('session_id')
    
    # 도메인 선택
    requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "rank_support_cards",
            "arguments": {"domain": "의료·돌봄"},
            "session_id": session_id,
        }
    )
    
    # 행동 단계 생성
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "generate_action_steps",
            "arguments": {},
            "session_id": session_id,
            "use_rich_response": True,
        }
    )
    
    result = response.json()
    print(f"✅ 행동 단계 받음")
    print(f"📋 Content: {result.get('content', '')}")
    
    if result.get('attachments'):
        for action in result['attachments']:
            action_data = action['data']
            print(f"\n📍 {action_data.get('title')}")
            print(f"   예상 시간: {action_data.get('estimated_time')}")
            print(f"   난이도: {action_data.get('difficulty')}")


def test_backward_compatibility():
    """하위 호환성 테스트 (기존 방식)"""
    print("\n\n=== 4. 하위 호환성 테스트 ===")
    
    # Rich Response 없이 호출
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        json={
            "tool": "normalize_user_context",
            "arguments": {"message": "도움이 필요해요"},
            # use_rich_response 없음
        }
    )
    
    result = response.json()
    print(f"✅ 기존 방식 응답 받음: {result.get('ok')}")
    print(f"📝 Content 타입: {type(result.get('content'))}")
    print(f"🔍 Attachments 있음: {'attachments' in result}")


if __name__ == "__main__":
    print("🚀 업그레이드 기능 테스트 시작\n")
    print("=" * 60)
    
    try:
        test_normalize_with_context_aware()
        test_scoring_system()
        test_rich_action_steps()
        test_backward_compatibility()
        
        print("\n" + "=" * 60)
        print("✅ 모든 테스트 완료!")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 서버가 실행 중이지 않습니다.")
        print("다음 명령으로 서버를 시작하세요:")
        print("  uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

