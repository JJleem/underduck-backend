from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI

from routers import health

app = FastAPI(title="Underduck API")

app.include_router(health.router)
