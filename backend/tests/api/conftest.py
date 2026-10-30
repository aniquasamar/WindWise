import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from synth_db import build_synthetic_db


@pytest.fixture(scope="session")
def client():
    """The real app, served from a synthetic database (no network and no real data needed)."""
    db = build_synthetic_db(Path(tempfile.mkdtemp()) / "wind.sqlite")
    os.environ["WIND_DB_PATH"] = str(db)
    from app.container import get_service

    get_service.cache_clear()
    from app.main import create_app

    # raise_server_exceptions=False so an internal error comes back as the 500 response a client would see
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        yield c
    os.environ.pop("WIND_DB_PATH", None)
    get_service.cache_clear()