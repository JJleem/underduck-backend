"""카카오 닉네임 → 로스터 실명 매핑 해석 (name_alias 테이블 기반).

쓰는 곳: mom_vote / vote_comment / attendance / feedback 의 이름 저장 시점에
닉네임을 실명으로 정규화해, 로스터·스탯(실명 기준) 페이지와 연결되도록 한다.
"""
from sqlalchemy.orm import Session

from db.models import NameAlias, User
from deps import Caller


def resolve_name(db: Session, name: str | None) -> str | None:
    """name 이 name_alias 에 등록된 카카오 닉네임이면 실명으로, 아니면 원본 그대로 반환."""
    if not name:
        return name
    row = db.get(NameAlias, name.strip())
    return row.real_name if row else name


def caller_real_name(db: Session, kakao_id: str | None) -> str | None:
    """kakao_id → users.nickname → 실명 정규화. 매칭 실패 시 None."""
    if not kakao_id:
        return None
    u = db.get(User, kakao_id)
    if u is None or not u.nickname:
        return None
    return resolve_name(db, u.nickname.strip())


def effective_name(c: Caller, db: Session, claimed: str) -> str:
    """이름 기반 소유권이 걸린 곳에서 쓸 이름.

    mom_vote / feedback / roster.pref_pos 는 kakao_id 컬럼이 없어 '이름'이 곧 신원이다.
    신원 헤더가 오면 세션 사용자의 실명으로 강제해 남의 이름 사칭을 막는다.
    헤더가 없거나(레거시) users에서 실명을 못 찾으면 요청 값을 그대로 쓴다 → 기존 동작 유지.
    """
    if not c.is_identified or c.is_admin:
        return claimed
    return caller_real_name(db, c.kakao_id) or claimed
