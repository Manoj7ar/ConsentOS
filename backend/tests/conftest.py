from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings = Settings(
        database_url=database_url,
        cors_origins=["http://localhost:3000"],
        internal_api_shared_secret="test-secret",
        allow_mock_connected_accounts=True,
        allow_mock_token_vault=True,
        auto_approve_delay_seconds=0,
        auto_approve_when_ciba_unavailable=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {
        "x-consentos-internal-secret": "test-secret",
        "x-consentos-user-sub": "auth0|test-user",
        "x-consentos-user-email": "demo@example.com",
    }
