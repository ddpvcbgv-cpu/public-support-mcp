"""
v1.2 G 요구사항: Rate limiting (soft, explained)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple

# IP별 요청 카운트 (메모리 기반, 프로덕션에서는 Redis 등 사용 권장)
_request_counts: Dict[str, List[datetime]] = defaultdict(list)

# Rate limit 설정
RATE_LIMIT_BURST = 10  # 버스트 허용 횟수
RATE_LIMIT_WINDOW_SECONDS = 60  # 시간 윈도우 (초)


def check_rate_limit(ip: str) -> Tuple[bool, int]:
    """
    v1.2 G: Rate limit 체크
    
    Returns:
        (is_allowed, retry_after_seconds)
    """
    now = datetime.now()
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    
    # 윈도우 내 요청만 유지
    _request_counts[ip] = [
        req_time for req_time in _request_counts[ip]
        if req_time > window_start
    ]
    
    # 버스트 초과 체크
    if len(_request_counts[ip]) >= RATE_LIMIT_BURST:
        # 다음 요청 가능 시간 계산
        oldest_request = min(_request_counts[ip])
        retry_after = int((oldest_request + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS) - now).total_seconds())
        return False, max(1, retry_after)
    
    # 요청 기록
    _request_counts[ip].append(now)
    return True, 0

