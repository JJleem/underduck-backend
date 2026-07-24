from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    date: str
    time: str
    location: str
    opponent: str
    type: str
    weather: str | None = None


class MatchPatch(BaseModel):
    # 부분 수정. 보낸 필드만 갱신(None=미변경). updateMatchResult/writeMatchMom/writeMatchWeather 모두 커버.
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
    weather: str | None = None
    attendance_status: str | None = None


class PhotoAdd(BaseModel):
    urls: list[str]


class PhotoRemove(BaseModel):
    url: str


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
    voter_name: str
    voted_for: str
    vote_type: str


class MomVoteDelete(BaseModel):
    match_id: int
    voter_name: str
    vote_type: str | None = None


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
    kakao_id: str
    nickname: str
    message: str


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
    kakao_id: str
    nickname: str
    response: str  # "참석" | "불참" | "미정"


class AttendanceStatus(BaseModel):
    status: str  # "진행중" | "마감"


# ── featured ──
class FeaturedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    player_name: str
    title_id1: str | None = None
    title_id2: str | None = None
    title_id3: str | None = None


class FeaturedUpsert(BaseModel):
    player_name: str
    title_ids: list[str]


# ── push_subscription ──
class PushOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint: str
    p256dh: str | None = None
    auth: str | None = None


class PushCreate(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushDelete(BaseModel):
    endpoint: str


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
    no: str
    name: str
    pos: str
    status: str


class RosterPrefPosUpdate(BaseModel):
    # 선호 포지션은 본인만 설정 → 프론트 API 라우트가 세션 실명을 name으로 강제.
    name: str
    pref_pos: str  # CSV (최대 3, 프론트 검증)


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
    date: str
    title: str
    content: str
    important: bool = False
    location: str | None = None


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


class LineupUpsert(BaseModel):
    match_id: int
    quarter: str
    formation: str
    players: list[str] = []
    subs: list[str] = []
    substitutions: list[dict] = []


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
    name: str
    message: str


# ── users ──
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kakao_id: str
    nickname: str | None = None
    profile_image: str | None = None
    joined_at: datetime | None = None
    last_login: datetime | None = None


class UserUpsert(BaseModel):
    kakao_id: str
    nickname: str
    profile_image: str


# ── media ──
class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str | None = None
    url: str | None = None
    title: str | None = None
    uploaded_at: datetime | None = None


class MediaCreate(BaseModel):
    type: str
    url: str
    title: str


# ── name_alias (카카오 닉네임 → 로스터 실명) ──
class NameAliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kakao_name: str
    real_name: str


class NameAliasUpsert(BaseModel):
    kakao_name: str
    real_name: str


# ── board_post (전술게시판) ──
class BoardPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kakao_id: str | None = None
    author: str | None = None
    title: str | None = None
    youtube_url: str | None = None
    body: str | None = None
    created_at: datetime | None = None
    comment_count: int = 0


class BoardPostCreate(BaseModel):
    kakao_id: str
    author: str
    title: str
    youtube_url: str
    body: str | None = None


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
    kakao_id: str
    author: str
    message: str
