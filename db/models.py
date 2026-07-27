from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.connection import Base


class MomVote(Base):
    """MOM 투표. (경기, 투표자, 부문) 당 1표 — 라우터가 upsert로, DB가 UNIQUE로 이중 보장."""
    __tablename__ = "mom_vote"
    __table_args__ = (
        UniqueConstraint("match_id", "voter_name", "vote_type", name="uq_mom_vote_match_voter_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    voter_name: Mapped[str | None] = mapped_column(String(100))
    voted_for: Mapped[str | None] = mapped_column(String(100))
    vote_type: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class VoteComment(Base):
    __tablename__ = "vote_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class AttendanceVote(Base):
    __tablename__ = "attendance_vote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(100))
    response: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class Featured(Base):
    __tablename__ = "featured"

    player_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    title_id1: Mapped[str | None] = mapped_column(String(50))
    title_id2: Mapped[str | None] = mapped_column(String(50))
    title_id3: Mapped[str | None] = mapped_column(String(50))


class PushSubscription(Base):
    __tablename__ = "push_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str | None] = mapped_column(Text)
    auth: Mapped[str | None] = mapped_column(Text)


class Match(Base):
    __tablename__ = "matches"

    # match_id = 시트 데이터행 0-based 인덱스. mom_vote 등이 참조하므로 보존. 신규는 max+1.
    match_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    location: Mapped[str | None] = mapped_column(String(200))
    opponent: Mapped[str | None] = mapped_column(String(200))
    our_score: Mapped[int | None] = mapped_column(Integer)
    their_score: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str | None] = mapped_column(String(20))
    type: Mapped[str | None] = mapped_column(String(50))
    goals: Mapped[str | None] = mapped_column(Text)        # CSV (득점자, 빈 슬롯 포함 가능)
    assists: Mapped[str | None] = mapped_column(Text)      # CSV (위치 대응, 빈 슬롯 포함 가능)
    mom: Mapped[str | None] = mapped_column(String(100))
    attendees: Mapped[str | None] = mapped_column(Text)    # CSV
    photos: Mapped[str | None] = mapped_column(Text)       # CSV (Cloudinary URL, 최대 5)
    weather: Mapped[str | None] = mapped_column(String(100))  # "28°C,맑음,01d,10"
    attendance_status: Mapped[str | None] = mapped_column(String(20))


class Roster(Base):
    __tablename__ = "roster"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    no: Mapped[str | None] = mapped_column(String(10))       # 등번호
    name: Mapped[str | None] = mapped_column(String(100))
    pos: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20))   # 활동/비활동
    memo: Mapped[str | None] = mapped_column(Text)
    pref_pos: Mapped[str | None] = mapped_column(String(50))  # 선호 포지션 CSV (본인 설정, 최대 3)


# stats 테이블/모델은 폐기됨: stats는 routers/stats.py에서 matches·mom_vote로 실시간 집계.
# (drop 마이그레이션: a3f1c2d4e5b6_drop_stats_table)


class Notice(Base):
    """대시보드에 노출되는 단일 활성 공지(시트 row2). id=1 고정 단일행."""
    __tablename__ = "notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text)
    important: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str | None] = mapped_column(String(200))


class Lineup(Base):
    __tablename__ = "lineup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    quarter: Mapped[str | None] = mapped_column(String(20))
    formation: Mapped[str | None] = mapped_column(String(20))
    players: Mapped[list | None] = mapped_column(JSON)        # 선발 11 (배열)
    subs: Mapped[list | None] = mapped_column(JSON)           # 대기 5 (배열)
    substitutions: Mapped[list | None] = mapped_column(JSON)  # [{out,in,time}]


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"

    kakao_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nickname: Mapped[str | None] = mapped_column(String(100))
    profile_image: Mapped[str | None] = mapped_column(Text)
    joined_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    last_login: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str | None] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str | None] = mapped_column(String(200))
    uploaded_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class NameAlias(Base):
    """카카오 닉네임 → 로스터 실명 매핑 (예: 성원→백성원, 창의→홍창의)."""
    __tablename__ = "name_alias"

    kakao_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)


class BoardPost(Base):
    """전술게시판 글 (유튜브 링크 공유). 로그인 회원 누구나 작성."""
    __tablename__ = "board_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))   # 작성자 신원(삭제 권한 판별용)
    author: Mapped[str | None] = mapped_column(String(100))    # 표시용 이름(실명 정규화)
    title: Mapped[str | None] = mapped_column(String(200))
    youtube_url: Mapped[str | None] = mapped_column(Text)      # 유튜브 링크 원본
    body: Mapped[str | None] = mapped_column(Text)             # 본문(선택)
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class BoardComment(Base):
    """전술게시판 댓글."""
    __tablename__ = "board_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class BoardLike(Base):
    """전술게시판 좋아요. 인당 1번(post_id+kakao_id 유니크)."""
    __tablename__ = "board_like"
    __table_args__ = (UniqueConstraint("post_id", "kakao_id", name="uq_board_like_post_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
