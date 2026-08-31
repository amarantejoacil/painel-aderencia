import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.seed import seed_if_empty

TEST_URL = "postgresql+psycopg2://aderencia:aderencia@127.0.0.1:5432/aderencia_test"
engine = create_engine(TEST_URL, pool_pre_ping=True)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    try:
        seed_if_empty(db)
    finally:
        db.close()

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
