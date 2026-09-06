import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.services import cache


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.reset_for_tests()
    yield
    cache.reset_for_tests()


@pytest.fixture()
def api_client(monkeypatch):
    """A FastAPI TestClient wired to its own isolated in-memory DB (via
    dependency override on get_db — StaticPool so the single in-memory
    SQLite connection is shared across every request within one test,
    since plain ":memory:" would otherwise hand each connection its own
    empty database). The real background scheduler is disabled: API
    contract tests shouldn't depend on network calls or a live poll
    cycle, and starting real threads per test would leak across tests.
    """
    monkeypatch.setattr("app.services.scheduler.start_scheduler", lambda: None)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.db.session import get_db
    from app.main import app
    from app.core.limiter import limiter

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()  # tests share the TestClient's fixed "testclient" IP — don't let one test's calls count against another's

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    limiter.reset()
    engine.dispose()
