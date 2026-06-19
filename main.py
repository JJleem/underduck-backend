from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI

from routers import attendance, featured, health, matches, mom_vote, push, vote_comment

app = FastAPI(title="Underduck API")

app.include_router(health.router)
app.include_router(matches.router)
app.include_router(mom_vote.router)
app.include_router(vote_comment.router)
app.include_router(attendance.router)
app.include_router(featured.router)
app.include_router(push.router)
