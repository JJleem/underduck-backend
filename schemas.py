from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from security import pseudonymize, validate_url

# ── 입력 제약 ──────────────────────────────────────────────────────
# 상한은 DB 컬럼 길이에 맞춘다. 지금까지 초과 값은 DB 에러(500)로 떨어졌으므로
# 정상 입력의 동작은 그대로이고, 잘못된 입력만 500 → 422로 바뀐다.
# Text 컬럼은 원래 무제한이라 저장 폭탄이 가능했다 → 넉넉한 상한으로 막는다.
Tiny = Annotated[str, Field(max_length=10)]     # roster.no
Short = Annotated[str, Field(max_length=20)]    # date/time/result/status/quarter/formation
Code = Annotated[str, Field(max_length=50)]     # type / title_id / pref_pos
# kakao_id는 받는 즉시 가명화한다 → 원본이 DB에도 응답에도 남지 않는다.
KakaoId = Annotated[str, Field(max_length=64), AfterValidator(pseudonymize)]
Name = Annotated[str, Field(max_length=100)]
Title = Annotated[str, Field(max_length=200)]
Body = Annotated[str, Field(max_length=10_000)]      # 사용자 작성 본문/댓글
Csv = Annotated[str, Field(max_length=20_000)]       # 명단 CSV (goals/assists/attendees)
# URL: 길이 상한 + 실행 가능한 스킴(javascript:, data: …) 차단 → 저장형 XSS 방지
Url = Annotated[str, Field(max_length=1_000), AfterValidator(validate_url)]
# 라인업 자유 배치 좌표: 필드 기준 x, y 백분율 한 쌍
Coord = Annotated[float, Field(ge=0, le=100)]
Point = Annotated[list[Coord], Field(min_length=2, max_length=2)]


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: int
    date: str | None = None
    time: str | None = None
    location: str | None = None
    opponent: str | None = None
    our_score: int | None = None
    their_score: int | None = None
    result: str | None = None
    type: str | None = None
    goals: str | None = None
    assists: str | None = None
    mom: str | None = None
    attendees: str | None = None
    photos: str | None = None
    weather: str | None = None
    attendance_status: str | None = None


class MatchCreate(BaseModel):
    date: Short
    time: Short
    location: Title
    opponent: Title
    type: Code
    weather: Name | None = None


class MatchPatch(BaseModel):
    # 부분 수정. 보낸 필드만 갱신(None=미변경). updateMatchResult/writeMatchMom/writeMatchWeather 모두 커버.
    date: Short | None = None
    time: Short | None = None
    location: Title | None = None
    opponent: Title | None = None
    our_score: int | None = None
    their_score: int | None = None
    result: Short | None = None
    type: Code | None = None
    goals: Csv | None = None
    assists: Csv | None = None
    mom: Name | None = None
    attendees: Csv | None = None
    weather: Name | None = None
    attendance_status: Short | None = None


class PhotoAdd(BaseModel):
    urls: list[Url] = Field(max_length=20)


class PhotoRemove(BaseModel):
    url: Url


# ── mom_vote ──
class MomVoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int | None = None
    voter_name: str | None = None
    voted_for: str | None = None
    vote_type: str | None = None
    timestamp: datetime | None = None


class MomVoteCreate(BaseModel):
    match_id: int
    voter_name: Name
    voted_for: Name
    vote_type: Short


class MomVoteDelete(BaseModel):
    match_id: int
    voter_name: Name
    vote_type: Short | None = None


# ── vote_comment ──
class VoteCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int | None = None
    kakao_id: str | None = None
    nickname: str | None = None
    message: str | None = None
    timestamp: datetime | None = None


class VoteCommentCreate(BaseModel):
    match_id: int
    kakao_id: KakaoId
    nickname: Name
    message: Body


# ── attendance_vote ──
class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int | None = None
    kakao_id: str | None = None
    nickname: str | None = None
    response: str | None = None
    timestamp: datetime | None = None


class AttendanceUpsert(BaseModel):
    match_id: int
    kakao_id: KakaoId
    nickname: Name
    response: Short  # "참석" | "불참" | "미정"


class AttendanceStatus(BaseModel):
    status: Short  # "진행중" | "마감"


# ── featured ──
class FeaturedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    player_name: str
    title_id1: str | None = None
    title_id2: str | None = None
    title_id3: str | None = None


class FeaturedUpsert(BaseModel):
    player_name: Name
    title_ids: list[Code] = Field(max_length=10)


# ── push_subscription ──
class PushOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint: str
    p256dh: str | None = None
    auth: str | None = None


class PushCreate(BaseModel):
    endpoint: Url
    p256dh: Annotated[str, Field(max_length=200)]
    auth: Annotated[str, Field(max_length=200)]


class PushDelete(BaseModel):
    endpoint: Url


# ── roster ──
class RosterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    no: str | None = None
    name: str | None = None
    pos: str | None = None
    status: str | None = None
    memo: str | None = None
    pref_pos: str | None = None


class RosterCreate(BaseModel):
    no: Tiny
    name: Name
    pos: Short
    status: Short


class RosterPrefPosUpdate(BaseModel):
    # 선호 포지션은 본인만 설정.
    # 신원 헤더(X-Underduck-User)가 오면 백엔드가 세션 사용자로 대상을 강제한다.
    name: Name
    pref_pos: Code  # CSV (최대 3)


# ── stats (읽기전용) ──
class StatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    no: str | None = None
    name: str | None = None
    pos: str | None = None
    apps: int | None = None
    goals: int | None = None
    assists: int | None = None
    mom: int | None = None


# ── notice ──
class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: str | None = None
    title: str | None = None
    content: str | None = None
    important: bool = False
    location: str | None = None


class NoticeUpdate(BaseModel):
    date: Short
    title: Title
    content: Body
    important: bool = False
    location: Title | None = None


# ── lineup ──
class LineupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int | None = None
    quarter: str | None = None
    formation: str | None = None
    players: list[str] | None = None
    subs: list[str] | None = None
    substitutions: list[dict] | None = None
    positions: list[list[float]] | None = None
    tactic: str | None = None
    instructions: list[str] | None = None


class LineupUpsert(BaseModel):
    match_id: int
    quarter: Short
    formation: Short
    players: list[Name] = Field(default=[], max_length=30)
    subs: list[Name] = Field(default=[], max_length=30)
    substitutions: list[dict] = Field(default=[], max_length=100)
    # 좌표는 선발 11명과 1:1. 없으면 포메이션 프리셋을 쓴다.
    positions: list[Point] | None = Field(default=None, max_length=11)
    tactic: Short | None = None
    # 선발 11명의 개인 전술. 한 칸에 여러 개면 "id,id" (빈 문자열 = 지시 없음)
    instructions: list[Code] | None = Field(default=None, max_length=11)


# ── feedback ──
class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int | None = None
    timestamp: datetime | None = None
    name: str | None = None
    message: str | None = None


class FeedbackCreate(BaseModel):
    match_id: int
    name: Name
    message: Body


# ── users ──
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kakao_id: str
    nickname: str | None = None
    profile_image: str | None = None
    joined_at: datetime | None = None
    last_login: datetime | None = None


class PseudonymResolve(BaseModel):
    # 원본 카카오 ID. 쿼리/경로가 아니라 본문으로 받는다 — 서버 로그에 남지 않게.
    kakao_id: Annotated[str, Field(max_length=64)]


class PseudonymOut(BaseModel):
    kakao_id: str  # 가명 ID(pid)


class UserUpsert(BaseModel):
    kakao_id: KakaoId
    nickname: Name
    profile_image: Url


# ── media ──
class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str | None = None
    url: str | None = None
    title: str | None = None
    uploaded_at: datetime | None = None


class MediaCreate(BaseModel):
    type: Short
    url: Url
    title: Title


# ── name_alias (카카오 닉네임 → 로스터 실명) ──
class NameAliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kakao_name: str
    real_name: str


class NameAliasUpsert(BaseModel):
    kakao_name: Name
    real_name: Name


# ── board_post (전술게시판) ──
class BoardLineupQuarter(BaseModel):
    """게시판 전술 글의 쿼터 하나 — 선발 11명 배치."""
    quarter: Short = "1Q"
    formation: Short = ""
    positions: list[Point] | None = Field(default=None, max_length=11)
    players: list[Name] = Field(default=[], max_length=11)
    instructions: list[Code] = Field(default=[], max_length=11)
    tactic: Short | None = None


class BoardLineup(BaseModel):
    """전술 글 본체. 한 사람이 쿼터별로 여러 안을 낼 수 있다.

    min_length=1: 구조가 안 맞는 payload(예: 배포 과도기의 옛 프론트)가 들어와도
    quarters가 비어버린 채로 저장되지 않도록 422로 막는다.
    """
    quarters: list[BoardLineupQuarter] = Field(min_length=1, max_length=4)


class BoardPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kakao_id: str | None = None
    author: str | None = None
    title: str | None = None
    youtube_url: str | None = None
    body: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lineup: dict | None = None
    comment_count: int = 0
    like_count: int = 0
    view_count: int = 0


class BoardPostCreate(BaseModel):
    kakao_id: KakaoId
    author: Name
    title: Title
    # 유튜브 글이면 링크가, 전술 글이면 lineup이 온다.
    youtube_url: Url | None = None
    body: Body | None = None
    lineup: BoardLineup | None = None


class BoardViewOut(BaseModel):
    """조회수 증가 후의 최신 누적값."""
    view_count: int


class BoardLikeToggle(BaseModel):
    kakao_id: KakaoId


class BoardLikeOut(BaseModel):
    liked: bool
    like_count: int


class BoardLikeGiverOut(BaseModel):
    name: str   # 실명(정규화)
    count: int  # 누른 좋아요 수


# ── board_comment ──
class BoardCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int | None = None
    kakao_id: str | None = None
    author: str | None = None
    message: str | None = None
    created_at: datetime | None = None


class BoardCommentCreate(BaseModel):
    kakao_id: KakaoId
    author: Name
    message: Body
