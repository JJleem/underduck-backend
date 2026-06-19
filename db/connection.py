from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

UNDERDUCK_DATABASE_URL = os.getenv("UNDERDUCK_DATABASE_URL")
if not UNDERDUCK_DATABASE_URL:
    raise RuntimeError(
        "UNDERDUCK_DATABASE_URL 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요."
    )

engine = create_engine(UNDERDUCK_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
