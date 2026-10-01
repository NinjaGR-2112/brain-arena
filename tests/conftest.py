"""Configuration des tests.

Deux variables d'environnement sont posées **avant** l'import de ``app.main``,
qui les lit au moment de l'importation :

- ``SECRET_KEY`` : sans elle, ``app.main`` refuse désormais de démarrer ;
- ``DATABASE_URL`` : la base de test, isolée de ``brainarena.db``.

La base de test vit dans le répertoire temporaire du système plutôt qu'à la
racine du dépôt, pour ne pas laisser de fichier derrière soi.
"""
import os
import tempfile

_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "brainarena_test.db")

os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-" + "0" * 32
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    """Session ouverte directement sur la base de test, pour les assertions."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_and_login(client, username="testplayer", password="password123"):
    """Inscrit et connecte un utilisateur. Partagée par les fichiers de test."""
    register = client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
