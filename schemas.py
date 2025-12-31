"""Rich Content 스키마 정의 - 구조화된 응답 포맷"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ProgressBar(BaseModel):
    """진행 상태 표시"""
    current_step: int = Field(description="현재 단계")
    total_steps: int = Field(description="전체 단계")
    next_action: str = Field(description="다음 행동")


class Visual(BaseModel):
    """시각적 힌트"""
    icon: str = Field(default="📋", description="아이콘 이모지")
    color: str = Field(default="#2196F3", description="색상 코드")
    badge: Optional[str] = Field(default=None, description="배지 텍스트 (예: 긴급, 추천)")


class BenefitCard(BaseModel):
    """혜택 카드 상세 정보"""
    title: str = Field(description="혜택 제목")
    description: str = Field(description="혜택 설명")
    eligibility_score: Optional[int] = Field(default=None, description="적합도 점수 (0~100)")
    amount: Optional[str] = Field(default=None, description="지원 금액/규모")
    where: Optional[str] = Field(default=None, description="신청 장소/연락처")
    how: Optional[str] = Field(default=None, description="신청 방법")
    say: Optional[str] = Field(default=None, description="상담 시 할 말")
    why: Optional[str] = Field(default=None, description="추천 이유")
    progress: Optional[ProgressBar] = Field(default=None, description="진행 상태")
    visual: Optional[Visual] = Field(default=None, description="시각적 힌트")
    tags: List[str] = Field(default_factory=list, description="태그 (예: 긴급, 장기지원)")


class ActionStep(BaseModel):
    """행동 단계"""
    phase: Literal["today", "tomorrow", "stuck"] = Field(description="단계 구분")
    title: str = Field(description="단계 제목")
    description: str = Field(description="상세 설명")
    estimated_time: Optional[str] = Field(default=None, description="예상 소요 시간")
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Field(default=None, description="난이도")


class UserProfile(BaseModel):
    """사용자 프로파일 (추론된 정보)"""
    age_range: Optional[str] = Field(default=None, description="연령대 (예: 20대, 60대 이상)")
    household_size: Optional[int] = Field(default=None, description="가구원 수")
    income_level: Optional[str] = Field(default=None, description="소득 수준 (상/중/하)")
    employment_status: Optional[str] = Field(default=None, description="고용 상태")
    location: Optional[str] = Field(default=None, description="지역")
    primary_concern: Optional[str] = Field(default=None, description="주요 관심사")


class ConversationTurn(BaseModel):
    """대화 턴"""
    message: str = Field(description="사용자 메시지")
    intent: Optional[str] = Field(default=None, description="의도 분류")
    keywords: List[str] = Field(default_factory=list, description="추출된 키워드")
    urgency: Optional[int] = Field(default=None, description="긴급도")
    timestamp: Optional[str] = Field(default=None, description="시간")


class RichAttachment(BaseModel):
    """Rich Content 첨부"""
    type: Literal["card", "action", "profile", "chart", "list"] = Field(description="첨부 타입")
    data: Dict[str, Any] = Field(description="첨부 데이터")


class RichResponse(BaseModel):
    """구조화된 응답"""
    content: str = Field(description="텍스트 메시지 (AI가 읽을 수 있는)")
    attachments: List[RichAttachment] = Field(default_factory=list, description="구조화된 첨부")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")

