from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI

from routers import (
    attendance,
    board,
    featured,
    feedback,
    health,
    lineup,
    matches,
    media,
    mom_vote,
    name_alias,
    notice,
    push,
    roster,
    stats,
    users,
    vote_comment,
)

from security import SecurityHeadersMiddleware

# 문서 라우트(/docs, /redoc, /openapi.json)는 라우터 의존성이 걸리지 않아 무인증 공개된다.
# 전체 엔드포인트·스키마가 그대로 노출되므로 운영에서는 끈다.
app = FastAPI(
    title="Underduck API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(matches.router)
app.include_router(mom_vote.router)
app.include_router(vote_comment.router)
app.include_router(attendance.router)
app.include_router(featured.router)
app.include_router(push.router)
app.include_router(roster.router)
app.include_router(stats.router)
app.include_router(notice.router)
app.include_router(lineup.router)
app.include_router(feedback.router)
app.include_router(users.router)
app.include_router(media.router)
app.include_router(name_alias.router)
app.include_router(board.router)
