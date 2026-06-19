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
