
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator

# 1. Alamat database SQLite
DATABASE_URL = "sqlite:///./pmb.db"

# 2. Membuat koneksi database
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# 3. Membuat session database
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 4. Base untuk seluruh model database
class Base(DeclarativeBase):
    pass

# 5. Fungsi untuk menyediakan koneksi database
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
