
import pytest

from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Memastikan seluruh model terdaftar
from app.models import (
    CalonMahasiswa,
    ProgramStudi,
    JalurMasuk
)


@pytest.fixture
def test_session_factory(tmp_path):
    # Membuat database SQLite sementara
    database_url = URL.create(
        "sqlite",
        database=str(tmp_path / "test_pmb.db")
    )

    test_engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False
        }
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    # Membuat seluruh tabel untuk testing
    Base.metadata.create_all(bind=test_engine)

    yield TestingSessionLocal

    # Membersihkan database setelah testing
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def db_session(test_session_factory):
    db = test_session_factory()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(test_session_factory):

    # Menggunakan database testing
    # sebagai pengganti database utama
    def override_get_db():
        db = test_session_factory()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
