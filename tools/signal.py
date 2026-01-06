"""
Signal Detection Layer - 위험/취약 시그널 감지
사용자 메시지에서 위험 시그널을 코드 레벨에서 먼저 감지하여
잘못된 도메인/카드 노출을 원천 차단하는 구조
"""
from __future__ import annotations

import re
from typing import Dict, Optional


# 도메인 키 매핑 (CARD_LIBRARY 키와 일치하도록)
DOMAIN_MAPPING = {
    "법률·권리": "법률·권리 상담",
    "위기": "심리·정서",
}


def detect_signal(message: str) -> Dict[str, Optional[str]]:
    """
    사용자 메시지에서 위험/취약 시그널을 감지하여 Signal Level을 반환한다.
    
    Args:
        message: 사용자 입력 메시지
    
    Returns:
        {
            "signal_level": "LEVEL_1" | "LEVEL_2" | "LEVEL_3",
            "forced_domain": Optional[str],  # LEVEL_3 only
            "primary_domain": Optional[str], # LEVEL_2 only
        }
    """
    if not message:
        return {
            "signal_level": "LEVEL_1",
            "forced_domain": None,
            "primary_domain": None,
        }
    
    try:
        msg = message.lower()
        
        # LEVEL_3: 강한 위험 시그널 (맥락 무관, 발견 즉시 고정)
        LEVEL_3_PATTERNS = {
            "의료·돌봄": [
                r"치매", r"장기요양", r"중증", r"말기", r"입원",
                r"간병", r"요양", r"뇌졸중", r"파킨슨", r"암(\s|$)"
            ],
            "법률·권리": [
                r"고소", r"소송", r"폭행", r"협박", r"사기",
                r"학대", r"성폭력", r"가정폭력", r"스토킹"
            ],
            "위기": [
                r"자살", r"자해", r"죽고\s?싶", r"살기\s?힘들", r"극단적\s?선택"
            ],
            "주거": [
                r"퇴거", r"강제집행", r"명도", r"철거", r"노숙"
            ],
        }
        
        # LEVEL_3: 발견 즉시 강제 고정 (우선순위 최상위)
        for domain, patterns in LEVEL_3_PATTERNS.items():
            for p in patterns:
                if re.search(p, msg):
                    # 도메인 매핑 적용 (CARD_LIBRARY 키와 일치하도록)
                    mapped_domain = DOMAIN_MAPPING.get(domain, domain)
                    # "주거"는 "주거·월세"로 매핑 필요
                    if mapped_domain == "주거":
                        mapped_domain = "주거·월세"
                    return {
                        "signal_level": "LEVEL_3",
                        "forced_domain": mapped_domain,
                        "primary_domain": None,
                    }
        
        # LEVEL_2: 맥락 의존적 패턴 (정규식으로 맥락 확인)
        LEVEL_2_PATTERNS = {
            "의료·돌봄": [
                r"(싱글맘|한부모).*(돌봄|간병|육아|아이)",
                r"(장애|발달).*(돌봄|의료|치료)",
                r"중증아동"
            ],
            "생활 유지": [
                r"(생활비|식비|공과금).*(부족|모자라|막막|연체)",
                r"수입\s?없"
            ],
            "주거·월세": [
                r"(월세|전세|보증금).*(부담|연체|밀렸|막막)",
                r"집.*(불안|없|구해야)"
            ],
        }
        
        for domain, patterns in LEVEL_2_PATTERNS.items():
            for p in patterns:
                if re.search(p, msg):
                    return {
                        "signal_level": "LEVEL_2",
                        "forced_domain": None,
                        "primary_domain": domain,
                    }
        
        # LEVEL_1: 기본 탐색 (기존 로직 유지)
        return {
            "signal_level": "LEVEL_1",
            "forced_domain": None,
            "primary_domain": None,
        }
    
    except Exception:
        # 에러 발생 시 안전 기본값 (LEVEL_1)
        return {
            "signal_level": "LEVEL_1",
            "forced_domain": None,
            "primary_domain": None,
        }

