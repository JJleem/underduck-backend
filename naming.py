"""카카오 닉네임 → 로스터 실명 매핑 해석 (name_alias 테이블 기반).

쓰는 곳: mom_vote / vote_comment / attendance / feedback 의 이름 저장 시점에
닉네임을 실명으로 정규화해, 로스터·스탯(실명 기준) 페이지와 연결되도록 한다.
"""
from sqlalchemy.orm import Session

from db.models import NameAlias


def resolve_name(db: Session, name: str | None) -> str | None:
    """name 이 name_alias 에 등록된 카카오 닉네임이면 실명으로, 아니면 원본 그대로 반환."""
    if not name:
        return name
    row = db.get(NameAlias, name.strip())
    return row.real_name if row else name
