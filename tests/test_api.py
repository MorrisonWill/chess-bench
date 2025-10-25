from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.database import get_session
from app.models import Model


@pytest.mark.anyio("asyncio")
async def test_dashboard_renders(test_settings) -> None:
    async with get_session(test_settings) as session:
        session.add(Model(name="Dashboard Model", openrouter_model="test"))

    from app.main import app

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Chessbench" in response.text
