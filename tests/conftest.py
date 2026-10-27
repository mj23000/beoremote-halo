"""Test fixtures."""

import copy
from collections.abc import AsyncGenerator

import pytest
from aiohttp import web
from pytest_aiohttp import AiohttpServer

from beoremote_halo import BaseConfiguration, Halo
from tests.const import CONFIGURATION
from tests.fake_halo import FakeHalo


@pytest.fixture
def configuration() -> BaseConfiguration:
    """Example configuration for testing.

    Returns:
        Example config
    """
    return copy.deepcopy(CONFIGURATION)


@pytest.fixture(autouse=True)  # ruff: ignore[pytest-fixture-autouse] - every test should use the shortened timings
def fast_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shorten connection timeouts and the reconnect delay."""
    monkeypatch.setattr("beoremote_halo.halo.WEBSOCKET_TIMEOUT", 0.1)


@pytest.fixture
async def fake_halo(aiohttp_server: AiohttpServer) -> FakeHalo:
    """Start a fake Halo WebSocket server.

    Returns:
        Fake Halo
    """
    fake = FakeHalo()
    app = web.Application()
    app.router.add_get("/", fake.handler)
    fake.server = await aiohttp_server(app)  # ty: ignore[unresolved-attribute]
    return fake


@pytest.fixture
async def halo(fake_halo: FakeHalo, configuration: BaseConfiguration) -> AsyncGenerator[Halo]:
    """Halo client pointed at the fake Halo.

    Yields:
        Halo client
    """
    client = Halo(fake_halo.server.host, configuration, port=fake_halo.server.port)  # ty: ignore[unresolved-attribute]
    yield client
    await client.disconnect()
