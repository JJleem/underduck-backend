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
