"""
v1.2 H 요구사항: PII 마스킹 및 로깅 유틸리티
"""
from __future__ import annotations

import re
from typing import Any, Dict


def mask_pii(text: str) -> str:
    """
    v1.2 H: PII 마스킹
    - 전화번호: 010-1234-5678 -> 010-****-5678
    - 주민번호: 123456-1234567 -> 123456-*******
    - 계좌번호: 숫자 패턴 마스킹
    - 상세 주소: 동/호수 정보 마스킹
    """
    if not text:
        return text
    
    # 전화번호 마스킹 (010-1234-5678, 02-123-4567 등)
    text = re.sub(r'(\d{2,3})-(\d{3,4})-\d{4}', r'\1-****-\3', text)
    text = re.sub(r'(\d{2,3})\s*(\d{3,4})\s*\d{4}', r'\1-****-\3', text)
    
    # 주민번호 마스킹 (123456-1234567 -> 123456-*******)
    text = re.sub(r'(\d{6})-(\d{7})', r'\1-*******', text)
    
    # 계좌번호 마스킹 (숫자 10자리 이상)
    text = re.sub(r'\d{10,}', lambda m: '*' * len(m.group()), text)
    
    # 상세 주소 마스킹 (동/호수)
    text = re.sub(r'(\d+동)\s*(\d+호)', r'\1 ***호', text)
    text = re.sub(r'(\d+호)', r'***호', text)
    
    return text


def log_safe(message: str, **kwargs: Any) -> None:
    """
    v1.2 H: 안전한 로깅 (PII 마스킹)
    """
    masked_message = mask_pii(message)
    print(f"[LOG] {masked_message}", **kwargs)

