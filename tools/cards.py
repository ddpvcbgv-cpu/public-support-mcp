"""
공공 지원 내비게이터 v0.50 - 카드 라이브러리
철학: 판정하지 않고, 선택지를 차분하게 정리한다
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from constants import OFFICIAL_SOURCE_CATEGORIES, TOP_20_CORE_CARDS, STALE_THRESHOLD_DAYS_TOP20, STALE_THRESHOLD_DAYS_OTHER
from state import SessionState
from tools.domains import DOMAIN_HINTS, DOMAIN_PRIORITY


# 엔진 v0.50 철학 반영: "이게 뭐냐면" / "왜 지금 맞냐면" 구조
CARD_LIBRARY: Dict[str, List[Dict[str, str]]] = {
    "주거·월세": [
        {
            "card": "주거 안심 상담",
            "이게_뭐냐면": "월세·보증금 부담을 먼저 듣고, 지금 상황에서 열려 있는 지원 경로를 함께 정리하는 상담이에요",
            "왜_지금_맞냐면": "퇴거 걱정이나 연체 우려가 있을 때, 혼자 판단하기보다 외부에서 가능성부터 확인해주는 경로가 더 안전한 경우가 많아서요",
            "지금_하실_수_있는_말": "주거비 부담이 커서, 지원 가능성만 먼저 상담받고 싶어요",
            "where": "📞 복지로 129 (전국 통합 상담) 또는 거주지 시/군/구청 주거복지센터",
            "how": "1) 전화 후 현재 상황 간단히 말씀 2) 소득·자산 상황 공유 (대략만 알려주셔도 괜찮아요) 3) 가능한 제도 안내받기 4) 필요 서류 확인",
            "막히면": "전화 연결이 어려우시면, '복지로 앱'에서 채팅 상담도 가능해요. 또는 주민센터에 직접 방문하셔도 괜찮습니다"
        },
        {
            "card": "체납 완화 점검",
            "이게_뭐냐면": "지금 밀린 항목을 줄 세워서, 당장 끊기지 않게 우선순위를 함께 정리하는 경로예요",
            "왜_지금_맞냐면": "연체가 시작되면 우선순위 없이 모든 걸 막으려다 더 흔들리는 경우가 많아서, 순서를 먼저 잡는 게 도움이 돼요",
            "지금_하실_수_있는_말": "공과금이 밀려서요. 당장 끊기지 않게 점검 상담만 먼저 받고 싶어요",
            "where": "📞 복지로 129 → '에너지복지' 또는 '긴급복지' 키워드 / 한국전력 123 (전기료) / 지역 수도사업소 (수도료)",
            "how": "1) 체납 내역 확인 (대략만 말씀하셔도 괜찮아요) 2) 에너지바우처·긴급지원 대상 확인 3) 분할납부 또는 감면 신청",
            "막히면": "전화가 어려우시면, 주민센터에 '공과금 부담 상담'이라고만 말씀하셔도 연결해주세요"
        },
        {
            "card": "안전 이사 대비",
            "이게_뭐냐면": "급한 이사·퇴거 상황에서 임시 주거와 상담 창구를 함께 찾아보는 경로예요",
            "왜_지금_맞냐면": "쫓겨날 수 있다는 느낌이 있을 때는, 단기 대안부터 확보하면서 장기 경로를 같이 보는 편이 안전해요",
            "지금_하실_수_있는_말": "퇴거가 걱정돼요. 임시 거처나 상담 창구를 연결해 주실 수 있을까요?",
            "where": "📞 긴급복지지원 129 (즉시 연결) / 주거복지센터 / LH공사 1600-1004 (임시거처 문의)",
            "how": "1) 긴급지원 자격 확인 (위기상황 인정 여부) 2) 임시거처 제공 가능성 확인 3) 주거급여 신청 병행",
            "막히면": "자격이 애매하시면, '자격 확인'만 먼저 요청하셔도 괜찮아요. 바로 신청이 아니어도 됩니다"
        },
    ],
    "생활 유지": [
        {
            "card": "생활비 숨통 점검",
            "이게_뭐냐면": "당장 필요한 생활비를 줄이거나 보완할 수 있는 단기 경로를 함께 확인하는 거예요",
            "왜_지금_맞냐면": "소득 공백이나 공과금·식비 부담이 있을 때, 혼자 버티기보다 단기 경로부터 확보하면 준비 시간을 벌 수 있어서요",
            "지금_하실_수_있는_말": "이번 달 생활비가 모자라는데, 단기적으로 확인할 수 있는 지원이 있을까요?",
            "where": "📞 복지로 129 → '긴급복지' 또는 '생계급여' 키워드 / 거주지 읍면동 주민센터",
            "how": "1) 소득·재산 상황 말씀 (대략만 알려주셔도 괜찮아요) 2) 생계급여 신청 가능성 확인 3) 긴급지원 (위기상황 시) 4) 푸드뱅크·푸드마켓 연결",
            "막히면": "자격이 확실하지 않으셔도, '가능성 확인'만 먼저 하셔도 괜찮습니다"
        },
        {
            "card": "연체 리듬 조정",
            "이게_뭐냐면": "지금 밀린 항목을 줄 세워서, 미납 확산을 막는 우선순위를 같이 잡아보는 상담이에요",
            "왜_지금_맞냐면": "연체가 시작되면 우선순위 없이 모든 걸 막으려다 더 흔들리는 경우가 많아서, 순서를 먼저 정리하는 게 도움이 돼요",
            "지금_하실_수_있는_말": "밀린 공과금을 우선순위만이라도 잡아보고 싶습니다",
            "where": "📞 복지로 129 → '긴급복지' 키워드 / 신용회복위원회 1600-5500 (채무 상담)",
            "how": "1) 연체 항목 목록화 (대략만 말씀하셔도 괜찮아요) 2) 긴급복지 자격 확인 3) 분할납부 협의 4) 에너지바우처 등 감면 신청",
            "막히면": "서류가 없으셔도, '상황 설명'만으로 방향을 잡아주는 상담부터 하실 수 있어요"
        },
        {
            "card": "식비·생필품 완충",
            "이게_뭐냐면": "단기간 식비·생필품 부담을 줄일 수 있는 연결을 함께 탐색하는 경로예요",
            "왜_지금_맞냐면": "생활 유지가 흔들릴 때 가장 먼저 생활 필수 지출을 낮추면, 다른 걸 정리할 시간을 벌 수 있어서요",
            "지금_하실_수_있는_말": "당장 식비가 부담돼요. 가까운 곳에서 바로 문의해볼 곳이 있을까요?",
            "where": "📞 거주지 주민센터 (푸드뱅크·푸드마켓 연결) / 지역 자원봉사센터 / 사회복지관",
            "how": "1) 주민센터에서 푸드뱅크 연계 신청 2) 지역 무료급식소 위치 확인 3) 생필품 지원 프로그램 문의",
            "막히면": "주민센터 전화가 어려우시면, 직접 방문하셔서 '푸드뱅크 연결'이라고만 말씀하셔도 안내해주세요"
        },
    ],
    "의료·돌봄": [
        {
            "card": "진료비 부담 점검",
            "이게_뭐냐면": "검사·약값·치료비 중 급한 부분을 우선 확인하면서, 감당 가능한 경로를 함께 정리하는 상담이에요",
            "왜_지금_맞냐면": "병원비가 감당되지 않는다는 느낌이 있을 때, 혼자 판단하기보다 외부에서 경로를 같이 봐주는 게 부담을 낮춰요",
            "지금_하실_수_있는_말": "진료비가 커서요. 감당 가능한지 상담만 먼저 받고 싶어요",
            "where": "📞 복지로 129 → '의료급여' 또는 '긴급의료비' 키워드 / 병원 사회복지과 (원무과에 문의하면 연결해줘요)",
            "how": "1) 의료급여 자격 확인 2) 긴급의료비 지원 신청 가능성 3) 병원비 분할납부 협의 4) 재단 지원사업 (사랑의열매 등) 문의",
            "막히면": "자격이 애매하시면, '신청'이 아니라 '자격 가능성 확인'만 먼저 요청하셔도 괜찮아요"
        },
        {
            "card": "돌봄 공백 메우기",
            "이게_뭐냐면": "가족 돌봄·간병 공백을 임시로 채울 수 있는 지역 자원을 함께 탐색하는 경로예요",
            "왜_지금_맞냐면": "돌볼 사람이 부족할 때 단기 지원 연결로 시간을 벌면, 다른 걸 정리할 여유가 생겨요",
            "지금_하실_수_있는_말": "가족 돌봄이 급해요. 단기라도 숨통 틀 수 있는 자원을 알고 싶어요",
            "where": "📞 노인돌봄 1577-1389 / 장애인활동지원 1566-3232 / 지역 건강가정지원센터",
            "how": "1) 노인장기요양보험 등급 확인 2) 장애인활동지원 신청 가능성 3) 단기보호시설 문의 4) 자원봉사자 매칭",
            "막히면": "등급이 없으시거나 자격이 애매하시면, '단기 돌봄 가능성'만 먼저 문의하셔도 괜찮아요"
        },
        {
            "card": "의료비 지출 계획",
            "이게_뭐냐면": "예정된 검사·수술 비용을 나눠내거나 줄일 방법을 함께 점검하는 경로예요",
            "왜_지금_맞냐면": "큰 비용이 앞에 있을 때 미리 리듬을 잡아두면, 당황하지 않고 준비할 수 있어서요",
            "지금_하실_수_있는_말": "앞으로 병원비가 커질 것 같아요. 나눠낼 방법이 있는지 상담받고 싶어요",
            "where": "📞 병원 사회복지과 (수술 전 필수 상담) / 긴급의료비 지원 재단 / 건강보험공단 1577-1000 (본인부담상한제)",
            "how": "1) 병원에 미리 비용 문의 2) 의료비 지원 재단 신청 가능성 3) 본인부담상한제 확인 4) 분할납부 계획 수립",
            "막히면": "병원 사회복지과가 어디인지 모르시면, 원무과에 '사회복지 상담'이라고만 말씀하셔도 연결해줘요"
        },
    ],
    "고용·교육": [
        {
            "card": "취업 준비 동행",
            "이게_뭐냐면": "바로 취업을 압박하기보다, 지금까지의 공백과 상황을 함께 정리하면서 다시 움직일 방향을 잡아주는 지원이에요",
            "왜_지금_맞냐면": "취업이 안 된 기간이 길수록, 혼자 방향을 잡기보다 외부에서 흐름을 같이 정리해주는 방식이 더 잘 맞는 경우가 많아서요",
            "지금_하실_수_있는_말": "취업 준비를 오래 했는데 혼자서는 방향을 잡기 어려워서, 상담이나 준비 과정을 도와주는 지원이 있는지 알고 싶어요",
            "where": "📞 고용센터 1350 (국번없이) / 워크넷 www.work.go.kr / 지역 일자리센터",
            "how": "1) 구직등록 (실업급여 해당 시 신청 가능) 2) 직업훈련 상담 3) 취업성공패키지 신청 가능성 확인 4) 단기 일자리 정보 확인",
            "막히면": "공백이 길었다는 게 부담되시면, '공백 기간 고려한 상담'이라고 말씀하셔도 괜찮아요"
        },
        {
            "card": "경험 전환 지원",
            "이게_뭐냐면": "이직·전환을 준비할 때 필요한 최소 자격과 훈련 경로를 함께 확인하는 거예요",
            "왜_지금_맞냐면": "진입 장벽을 낮추는 경로를 먼저 찾으면, 혼자 막막해하지 않고 준비할 수 있어서요",
            "지금_하실_수_있는_말": "새로운 일로 바꾸고 싶은데, 어떤 준비부터 하면 좋을지 상담받고 싶어요",
            "where": "📞 고용센터 1350 → '직업훈련' 키워드 / HRD-Net www.hrd.go.kr / 지역 평생학습관",
            "how": "1) 직업훈련 상담 (내일배움카드) 2) 국비지원 교육 확인 3) 자격증 취득 경로 문의 4) 훈련수당 지원 확인",
            "막히면": "방향이 확실하지 않으시면, '일단 상담부터'라고 말씀하셔도 연결해줘요"
        },
        {
            "card": "근로 권리 점검",
            "이게_뭐냐면": "근로 조건·체불·휴게권 등 기본 권리를 함께 짚어주는 상담이에요",
            "왜_지금_맞냐면": "아르바이트·단기 근로에서도 권리 보호가 필요하다는 느낌이 있을 때, 외부 확인이 도움이 돼요",
            "지금_하실_수_있는_말": "지금 일하는 곳에서 권리 관련 상담을 받아보고 싶어요",
            "where": "📞 고용노동부 상담센터 1350 / 근로복지공단 1588-0075 / 권익위 국민신문고 110",
            "how": "1) 근로계약서 확인 2) 임금체불 신고 (필요 시) 3) 부당해고·괴롭힘 상담 4) 산재 신청 (업무 중 사고 시)",
            "막히면": "증거가 없으셔도, '상황 설명'만으로 방향을 잡아주는 상담부터 하실 수 있어요"
        },
    ],
    "심리·정서": [
        {
            "card": "마음 긴급 완충",
            "이게_뭐냐면": "불안·압박이 클 때 짧게 숨 고를 수 있는 상담 창구를 함께 찾아보는 거예요",
            "왜_지금_맞냐면": "정서적 여유가 먼저 확보되어야, 다른 선택을 살펴볼 수 있는 공간이 생겨요",
            "지금_하실_수_있는_말": "요즘 너무 불안한데, 짧게라도 상담 연결을 받고 싶어요",
            "where": "📞 정신건강위기상담 1577-0199 / 자살예방상담 1393 / 청소년상담 1388 / 보건소 정신건강복지센터",
            "how": "1) 24시간 전화상담 (익명 가능해요) 2) 지역 정신건강복지센터 방문 3) 무료 심리상담 신청 4) 필요 시 치료비 지원 연계",
            "막히면": "전화가 부담되시면, 온라인 채팅 상담도 가능해요. 보건소에 방문하셔도 괜찮습니다"
        },
        {
            "card": "지지 자원 연결",
            "이게_뭐냐면": "지역 커뮤니티·온라인 그룹 등 가벼운 지지망을 함께 탐색하는 경로예요",
            "왜_지금_맞냐면": "혼자 버티지 않도록, 가장 낮은 진입장벽의 연결부터 시작하는 게 부담이 덜해요",
            "지금_하실_수_있는_말": "부담 없이 얘기 나눌 곳이 있을까요? 가볍게 시작해보고 싶어요",
            "where": "📞 거주지 주민센터 (자조모임 안내) / 건강가정지원센터 / 사회복지관 / 온라인: 마음체크 mindcheck.kr",
            "how": "1) 지역 자조모임·동아리 정보 문의 2) 온라인 익명 커뮤니티 활용 3) 건강가정지원센터 프로그램 참여",
            "막히면": "대면이 부담되시면, 온라인 익명 커뮤니티부터 시작하셔도 괜찮아요"
        },
    ],
    # 🆕 확장 도메인: 사용자 명시적 요청 시에만 노출
    "문화·여가": [
        {
            "card": "문화누리카드 신청",
            "이게_뭐냐면": "영화·공연·도서·체육 등을 부담 없이 이용할 수 있도록 연간 13만원을 지원하는 카드예요",
            "왜_지금_맞냐면": "문화 활동은 사치가 아니라, 삶의 회복과 여유를 위한 정당한 권리이기 때문이에요",
            "지금_하실_수_있는_말": "문화 활동 할 여유가 없는데, 지원받을 수 있는 방법이 있을까요?",
            "where": "📞 주민센터 방문 또는 복지로 129 문의 / 온라인: 문화누리카드 홈페이지 mnuri.kr",
            "how": "1) 기초생활수급자·차상위계층 확인 2) 주민센터에서 신청 또는 온라인 신청 3) 카드 발급 후 전국 가맹점에서 사용",
            "막히면": "자격이 애매하시면 주민센터에 '문화누리카드 대상 확인'만 먼저 문의하셔도 괜찮아요"
        },
        {
            "card": "청년문화패스",
            "이게_뭐냐면": "만 19~34세 청년에게 공연·전시·영화·도서 등을 할인받거나 무료로 이용할 수 있는 경로예요",
            "왜_지금_맞냐면": "청년기에 문화 경험은 회복탄력성과 사회 연결망을 만드는 데 중요한 자원이 돼요",
            "지금_하실_수_있는_말": "청년인데 문화 생활 할 여유가 없어요. 무료나 할인으로 이용할 방법 있을까요?",
            "where": "📞 거주지 청년센터 문의 / 온라인: 지역별 청년정책 포털, 문화체육관광부 청년문화사업",
            "how": "1) 거주지 청년정책 확인 (지역마다 다름) 2) 청년센터 또는 주민센터에서 안내받기 3) 앱 설치 또는 온라인 등록",
            "막히면": "지역마다 제도가 다르니, '청년문화 지원'이라고 검색하거나 주민센터에 문의하세요"
        },
        {
            "card": "지역 공연·전시 할인",
            "이게_뭐냐면": "시립·구립 문화시설, 도서관, 박물관 등에서 무료 또는 저렴하게 이용할 수 있는 프로그램이에요",
            "왜_지금_맞냐면": "민간 시설은 비싸지만, 공공 시설은 무료나 저렴하게 열려 있어요. 몰라서 못 가는 경우가 많아요",
            "지금_하실_수_있는_말": "공공 문화시설에서 무료나 저렴하게 이용할 수 있는 게 뭐가 있을까요?",
            "where": "📞 거주지 문화재단, 도서관, 주민센터 문의 / 온라인: 문화포털 culture.go.kr",
            "how": "1) 거주지 또는 인근 지역 문화재단 홈페이지 확인 2) 무료 공연·전시·강좌 일정 검색 3) 예약 또는 현장 방문",
            "막히면": "어디서부터 시작할지 모르시면, 가까운 도서관이나 주민센터에 '문화 프로그램'이라고만 물어보세요"
        },
    ],
    "평생교육": [
        {
            "card": "평생학습관 무료 강좌",
            "이게_뭐냐면": "지역 평생학습관에서 무료 또는 저렴하게 배울 수 있는 다양한 강좌예요 (컴퓨터, 외국어, 자격증, 취미 등)",
            "왜_지금_맞냐면": "배움은 새로운 방향을 찾거나 자신감을 회복하는 데 중요한 자원이에요",
            "지금_하실_수_있는_말": "뭔가 배우고 싶은데, 무료로 배울 수 있는 곳이 있을까요?",
            "where": "📞 거주지 평생학습관, 구청·시청 평생학습과 / 온라인: 전국평생학습포털 lledu.go.kr",
            "how": "1) 거주지 평생학습관 홈페이지 확인 2) 원하는 강좌 검색 (무료/저렴한 것 많음) 3) 온라인 또는 전화로 신청",
            "막히면": "어떤 강좌가 있는지 모르시면, 주민센터에 '평생학습 강좌'라고만 물어보세요"
        },
        {
            "card": "직업 전환 교육 (국비지원)",
            "이게_뭐냐면": "새로운 직업을 준비할 때 필요한 직업훈련을 국비로 지원받는 거예요 (훈련비 무료, 훈련수당 지급 가능)",
            "왜_지금_맞냐면": "이직이나 전환을 준비할 때, 비용 부담 없이 새로운 기술을 배울 수 있어요",
            "지금_하실_수_있는_말": "새로운 일을 준비하고 싶은데, 국비로 교육받을 수 있나요?",
            "where": "📞 고용센터 1350, HRD-Net 또는 지역 평생학습관",
            "how": "1) 고용센터에서 구직 등록 2) 내일배움카드 발급 3) HRD-Net에서 원하는 훈련과정 검색 4) 훈련 신청 및 수강",
            "막히면": "방향이 확실하지 않으면, '일단 상담부터'라고 말씀하셔도 괜찮아요"
        },
        {
            "card": "온라인 무료 강의 (K-MOOC)",
            "이게_뭐냐면": "대학 수준의 강의를 무료로 온라인에서 들을 수 있는 거예요 (이수증 발급 가능)",
            "왜_지금_맞냐면": "배움을 시작하고 싶은데 시간·장소·비용이 부담될 때, 온라인으로 부담 없이 시작할 수 있어요",
            "지금_하실_수_있는_말": "집에서 무료로 배울 수 있는 온라인 강의가 있을까요?",
            "where": "🌐 K-MOOC (kmooc.kr), 국가평생교육진흥원 (nile.or.kr)",
            "how": "1) K-MOOC 홈페이지 접속 2) 원하는 강좌 검색 (전 과정 무료) 3) 회원가입 후 수강 신청 4) 수료 시 이수증 발급",
            "막히면": "어떤 강좌가 있는지 탐색만 하셔도 괜찮아요. 수강신청 전에 미리보기로 확인하세요"
        },
    ],
    "참여·활동": [
        {
            "card": "지역 자원봉사 연결",
            "이게_뭐냐면": "지역사회에서 가벼운 봉사 활동을 통해 사람들과 만나고 경험을 쌓는 경로예요",
            "왜_지금_맞냐면": "고립감이 클 때, 의미 있는 활동을 통해 연결감과 자존감을 회복할 수 있어요",
            "지금_하실_수_있는_말": "봉사 활동으로 사람들과 만나고 싶은데, 어떻게 시작하나요?",
            "where": "📞 거주지 자원봉사센터 / 온라인: 1365 자원봉사포털 (www.1365.go.kr)",
            "how": "1) 1365 포털에서 회원가입 2) 관심 분야 봉사활동 검색 3) 신청 후 참여 4) 봉사시간 인증",
            "막히면": "어디서부터 시작할지 모르시면, 주민센터에 '자원봉사'라고만 물어보세요"
        },
        {
            "card": "커뮤니티·동아리 참여",
            "이게_뭐냐면": "지역 주민센터나 복지관에서 운영하는 취미·관심사 기반 모임에 참여하는 거예요",
            "왜_지금_맞냐면": "혼자 있는 시간이 길 때, 가벼운 모임부터 시작하면 관계망을 넓힐 수 있어요",
            "지금_하실_수_있는_말": "취미 활동으로 사람들 만날 수 있는 모임이 있을까요?",
            "where": "📞 거주지 주민센터, 문화센터, 사회복지관",
            "how": "1) 주민센터나 복지관에 문의 2) 관심 분야 동아리·모임 안내받기 3) 참여 신청",
            "막히면": "대면이 부담되시면, 온라인 커뮤니티부터 시작하셔도 괜찮아요"
        },
    ],
}


def _deduplicate(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _guess_domain(state: SessionState) -> str:
    for domain, cues in DOMAIN_HINTS.items():
        if any(cue in state.user_keywords for cue in cues):
            return domain
    return DOMAIN_PRIORITY[0]


def _is_top20_card(domain: str, card_name: str) -> bool:
    """카드가 Top 20에 포함되는지 확인"""
    return (domain, card_name) in TOP_20_CORE_CARDS


def _get_card_metadata(domain: str, card: Dict[str, str]) -> Dict[str, str]:
    """카드에 메타데이터 추가 (v1.2 A 요구사항)"""
    card_name = card.get("card", "")
    
    # 기본값 설정 (실제로는 카드별로 설정되어야 함)
    # TODO: 각 카드에 last_verified_date와 official_source_category를 개별적으로 설정
    last_verified_date = card.get("last_verified_date", "2025-01")  # 기본값: 현재 월
    official_source_category = card.get("official_source_category", "공공 포털(복지로·정부24 등)")
    doc_type = card.get("doc_type", "온라인 안내")
    
    # stale 계산 (D 요구사항)
    is_top20 = _is_top20_card(domain, card_name)
    threshold_days = STALE_THRESHOLD_DAYS_TOP20 if is_top20 else STALE_THRESHOLD_DAYS_OTHER
    
    try:
        # YYYY-MM을 해당 월 1일로 해석
        verified_year, verified_month = map(int, last_verified_date.split("-"))
        verified_date = datetime(verified_year, verified_month, 1)
        now = datetime.now()
        days_since_verification = (now - verified_date).days
        stale = days_since_verification > threshold_days
    except (ValueError, AttributeError):
        # 파싱 실패 시 기본값
        stale = False
    
    # Evidence line 생성 (A 요구사항)
    stale_tag = " · 갱신 필요" if stale else ""
    evidence = f"근거: {official_source_category} · {doc_type} (검증 {last_verified_date}){stale_tag}"
    
    # 카드에 메타데이터 추가
    card_with_meta = card.copy()
    card_with_meta["last_verified_date"] = last_verified_date
    card_with_meta["official_source_category"] = official_source_category
    card_with_meta["doc_type"] = doc_type
    card_with_meta["evidence"] = evidence
    card_with_meta["stale"] = stale
    
    return card_with_meta


def _classify_card_level(domain: str, card: Dict[str, str], state: SessionState) -> str:
    """
    Phase 2: 카드를 L1/L2/L3로 분류
    
    L1: 자격 확인이 필요한 지원(조건부) - eligibility-dependent
    L2: 누구나 이용 가능한 공공 정보 - universally available
    L3: 더 확인할 공식 경로 - official next steps
    """
    card_name = card.get("card", "")
    where = card.get("where", "")
    how = card.get("how", "")
    
    # L3: 공식 경로/확인 경로 키워드
    l3_keywords = ["공식 포털", "주민센터", "콜센터", "문의", "확인", "상담소", "센터"]
    if any(kw in where.lower() or kw in card_name.lower() for kw in l3_keywords):
        # 단, "상담"이 포함된 카드는 L1일 수도 있음
        if "상담" in card_name and ("자격" in how or "확인" in how):
            return "L1"
        # 일반적인 공식 경로는 L3
        if "공식" in card_name or "경로" in card_name or "확인" in card_name:
            return "L3"
    
    # L2: 누구나 이용 가능한 정보 (상담, 안내, 정보 제공)
    l2_keywords = ["안내", "정보", "상담", "연결", "알아보기"]
    if any(kw in card_name.lower() for kw in l2_keywords):
        # 자격 확인이 필요 없는 경우
        if "자격" not in how and "확인" not in how and "신청" not in how:
            return "L2"
    
    # L1: 기본값 (자격 확인이 필요한 지원)
    # 대부분의 카드는 L1
    return "L1"


def _create_l3_card(domain: str, state: SessionState) -> Dict[str, str]:
    """
    Phase 2: L3 카드 생성 (공식 경로)
    """
    if state.region_hint:
        region = state.region_hint
        return {
            "card": "공식 확인 경로",
            "이게_뭐냐면": f"{region} 지역의 공식 지원 경로를 확인하실 수 있어요",
            "왜_지금_맞냐면": "공식 경로에서 최신 정보와 정확한 절차를 확인하실 수 있어서요",
            "지금_하실_수_있는_말": "공식 경로에서 확인하고 싶어요",
            "where": f"📞 {region} 주민센터 / 복지로 129 / 정부24",
            "how": "1) 주민센터 방문 또는 전화 2) 복지로 온라인 상담 3) 정부24 포털 확인",
            "막히면": "주민센터 전화가 어려우시면, 직접 방문하시거나 복지로 온라인 상담을 이용하세요",
            "last_verified_date": "2025-01",
            "official_source_category": "공공 포털(복지로·정부24 등)",
            "doc_type": "온라인 안내"
        }
    else:
        return {
            "card": "공식 확인 경로",
            "이게_뭐냐면": "공식 포털과 상담 창구에서 최신 정보를 확인하실 수 있어요",
            "왜_지금_맞냐면": "공식 경로에서 정확한 절차와 최신 정보를 확인하실 수 있어서요",
            "지금_하실_수_있는_말": "공식 경로에서 확인하고 싶어요",
            "where": "📞 복지로 129 / 정부24 / 주민센터",
            "how": "1) 복지로 온라인 상담 2) 정부24 포털 확인 3) 주민센터 문의",
            "막히면": "복지로 온라인 상담이 어려우시면, 주민센터에 직접 방문하시거나 전화로 문의하세요",
            "last_verified_date": "2025-01",
            "official_source_category": "공공 포털(복지로·정부24 등)",
            "doc_type": "온라인 안내"
        }


def rank_support_cards(state: SessionState) -> Dict[str, object]:
    """우선 탐색할 혜택 카드 2~3개를 제안한다."""
    # 스코어링 시스템 적용
    from tools.scoring import rank_benefits_by_score
    
    domain = state.chosen_domain or _guess_domain(state)
    available_cards = CARD_LIBRARY.get(domain, [])

    if not available_cards:
        available_cards = CARD_LIBRARY[DOMAIN_PRIORITY[0]]

    # 점수 기반 정렬
    scored_cards = rank_benefits_by_score(available_cards, state)
    
    # Phase 2: 3-Level Layering
    # 카드를 레이어별로 분류
    l1_cards = []
    l2_cards = []
    
    for card in scored_cards:
        level = _classify_card_level(domain, card, state)
        card_with_level = card.copy()
        card_with_level["_level"] = level  # 내부 추적용
        
        if level == "L1":
            l1_cards.append(card_with_level)
        elif level == "L2":
            l2_cards.append(card_with_level)
        # L3는 나중에 생성
    
    # Phase 2: 최종 구성 (L1 + L2 + 선택적 L3)
    max_cards = 3 if state.urgency_level <= 2 else 2
    selected = []
    
    # L1 선택 (최대 2개, USER_STATED >= 2 AND INFERRED == 0일 때만 3개)
    # USER_STATED/INFERRED 확인을 위해 임시로 rationale 계산
    from tools.orchestrator import _build_selection_rationale
    from tools.normalize import normalize_user_context
    normalize_result = normalize_user_context("", state)  # 키워드만 추출
    rationale = _build_selection_rationale("", state, normalize_result)
    
    user_stated_keys = set(item.get("key") for item in rationale if item.get("source") == "USER_STATED")
    has_inferred = any(item.get("source") == "INFERRED" for item in rationale)
    
    # L1=3 조건: USER_STATED distinct key count >= 2 AND INFERRED == 0
    max_l1 = 3 if (len(user_stated_keys) >= 2 and not has_inferred) else 2
    selected_l1 = l1_cards[:max_l1]  # BUG FIX: selected_l1 변수 정의
    selected.extend(selected_l1)
    
    # L2 선택
    # L1=3일 때는 마지막 L1에 L2를 embedded할 수 있음 (옵션 B)
    l2_to_add = None
    l2_embedded = False  # L2가 L1에 embedded되었는지 추적
    if l2_cards:
        l2_to_add = l2_cards[0]
    
    # L1=3이고 L2가 있으면, 마지막 L1에 L2 embedded 옵션 (B) 구현
    if l2_to_add and max_l1 == 3 and len(selected_l1) == 3:
        # 옵션 (B): L2를 마지막 L1 카드에 embedded
        last_l1_card = selected_l1[-1]
        l2_card_name = l2_to_add.get("card", "")
        l2_description = l2_to_add.get("이게_뭐냐면", "")
        
        # 마지막 L1 카드의 "막히면" 필드에 L2 내용 추가
        if "막히면" in last_l1_card:
            last_l1_card["막히면"] += f"\n\n[누구나] {l2_card_name}: {l2_description}"
        else:
            last_l1_card["막히면"] = f"[누구나] {l2_card_name}: {l2_description}"
        
        l2_embedded = True
        # dedicated L2 카드는 추가하지 않음 (옵션 B)
    elif l2_to_add:
        # 옵션 (A): dedicated L2 카드 추가
        selected.append(l2_to_add)
    elif not selected:
        # L1이 없으면 L2만 선택
        if l2_cards:
            selected.extend(l2_cards[:1])
    
    # L3는 orchestrate_full_response에서 조건부로 추가
    
    # v1.2: 각 카드에 메타데이터 추가
    selected_with_meta = [_get_card_metadata(domain, card) for card in selected]
    
    # Phase 2: 레이어 prefix 추가
    for card in selected_with_meta:
        level = card.get("_level", "L1")
        card_name = card.get("card", "")
        
        if level == "L1":
            card["card"] = f"[조건부] {card_name}"
        elif level == "L2":
            card["card"] = f"[누구나] {card_name}"
        elif level == "L3":
            card["card"] = f"[공식경로] {card_name}"

    state.shown_cards = _deduplicate(state.shown_cards + [card["card"] for card in selected_with_meta])
    
    # L2 embedded 정보 반환 (orchestrate_full_response에서 card_layers 업데이트용)
    return {
        "domain": domain, 
        "cards": selected_with_meta, 
        "_l1_cards": l1_cards, 
        "_l2_cards": l2_cards,
        "_l2_embedded": l2_embedded,  # L2가 embedded되었는지
        "_last_l1_index": len(selected_l1) - 1 if l2_embedded else None  # embedded된 경우 마지막 L1 인덱스
    }

