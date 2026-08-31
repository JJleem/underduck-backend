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
    # 이모티콘 id. 사랑방(lounge_comment.emoticon)과 같은 체계를 쓴다 — 그림을
    # 두 벌 관리하지 않기 위해서다. 프론트가 id로 찾아 그리고 모르는 id는 무시한다.
    emoticon: Mapped[str | None] = mapped_column(String(50))
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
    positions: Mapped[list | None] = mapped_column(JSON)      # 자유 배치 좌표 [[x,y]×11], NULL이면 포메이션 프리셋
    tactic: Mapped[str | None] = mapped_column(String(20))    # 팀 전술 id (attack/balance/…)
    instructions: Mapped[list | None] = mapped_column(JSON)   # 선발 11명 개인 전술 id (빈 문자열 = 없음)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)
    # 이모티콘 id — vote_comment 와 같은 설명. 사랑방과 한 벌을 같이 쓴다.
    emoticon: Mapped[str | None] = mapped_column(String(50))


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
    updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))  # 수정 시각(수정됨 표시·정렬)
    # 조회수. 동시 조회에서 유실되지 않도록 DB에서 원자적으로 증가시킨다.
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    # 전술 글: {formation, positions, players, instructions, tactic}. 유튜브 글은 NULL.
    lineup: Mapped[dict | None] = mapped_column(JSON)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)


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


class MatchLike(Base):
    """경기 피드 좋아요. 인당 1번(match_id+kakao_id 유니크).

    board_like 와 같은 모양이지만 참조 대상이 다르므로 테이블을 나눈다.
    (한 테이블에 target_type 을 두면 두 기능의 삭제·집계가 서로 얽힌다)
    """
    __tablename__ = "match_like"
    __table_args__ = (UniqueConstraint("match_id", "kakao_id", name="uq_match_like_match_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class GalleryLike(Base):
    __tablename__ = "gallery_like"
    __table_args__ = (UniqueConstraint("artwork_id", "kakao_id", name="uq_gallery_like_art_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artwork_id: Mapped[str] = mapped_column(String(100), index=True)
    kakao_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class GalleryComment(Base):
    __tablename__ = "gallery_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artwork_id: Mapped[str] = mapped_column(String(100), index=True)
    kakao_id: Mapped[str] = mapped_column(String(64))
    author: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class LoungePost(Base):
    """사랑방 글 — 애로사항·건의(suggestion)와 잡담(chat).

    **화면엔 익명, DB엔 실명.** author 는 저장은 하되 운영진 요청에만 응답에 실린다
    (마스킹은 routers/lounge.py 가 한다). 프론트에서 가리면 개발자 도구로 다 보인다.
    """
    __tablename__ = "lounge_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kakao_id: Mapped[str] = mapped_column(String(64), index=True)  # 작성자 신원(소유권·라벨용)
    author: Mapped[str] = mapped_column(String(100))               # 실명 — 운영진에게만 노출
    category: Mapped[str] = mapped_column(String(20))              # suggestion | chat
    # 제목 앞에 붙는 아이콘(노션의 페이지 아이콘). 댓글 이모티콘과 같은 id 체계를 쓴다.
    icon: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    # 처리 상태. chat 글에는 의미가 없다(화면도 건의에만 뱃지를 그린다).
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="received", default="received")
    admin_reply: Mapped[str | None] = mapped_column(Text)
    admin_reply_author: Mapped[str | None] = mapped_column(String(100))  # 답변자는 공개해도 된다
    admin_reply_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class LoungeLike(Base):
    """사랑방 글 좋아요. 인당 1번(post_id+kakao_id 유니크).

    kakao_id 를 두는 건 **중복을 막기 위해서지 누가 눌렀는지 보여주려는 게 아니다.**
    board_like 와 달리 "누가 눌렀나"를 돌려주는 엔드포인트를 만들지 않는다 —
    익명 게시판에서 공감한 사람 명단은 그 자체로 익명성을 깎는다.
    """
    __tablename__ = "lounge_like"
    __table_args__ = (UniqueConstraint("post_id", "kakao_id", name="uq_lounge_like_post_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class LoungeComment(Base):
    """사랑방 댓글. 글·이모티콘 중 하나 이상이 있어야 한다(라우터가 검사)."""
    __tablename__ = "lounge_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    # 대댓글이면 부모 댓글 id. 깊이는 1단까지만 — 대댓글의 대댓글은 부모로 접어 올린다.
    parent_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str] = mapped_column(String(64))
    author: Mapped[str] = mapped_column(String(100))  # 실명 — 운영진에게만 노출
    message: Mapped[str | None] = mapped_column(Text)
    # 이모티콘 **id** 만 저장한다(URL 아님). 그림은 프론트가 id로 찾아 그리고,
    # 모르는 id는 무시한다 → 백엔드를 건드리지 않고 이모티콘을 늘릴 수 있다.
    emoticon: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
