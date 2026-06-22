from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI

from routers import (
    attendance,
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

app = FastAPI(title="Underduck API")

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
