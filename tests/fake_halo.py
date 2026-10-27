"""Fake Beoremote Halo WebSocket server and helpers for testing the Halo client."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from aiohttp import WSMsgType, web

from beoremote_halo import ConnectionState, Halo

TIMEOUT = 2

SYSTEM_EVENT = {"event": {"type": "system", "state": "active"}}
CONFIGURATION_OK_EVENT = {"event": {"type": "status", "state": "ok", "message": "configuration"}}


class FakeHalo:
    """WebSocket server acting as a Beoremote Halo."""

    def __init__(self) -> None:
        """Initialize fake Halo."""
        self.received: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.connections: asyncio.Queue[web.WebSocketResponse] = asyncio.Queue()
        self.disconnections: asyncio.Queue[web.WebSocketResponse] = asyncio.Queue()
        self.websocket: web.WebSocketResponse

        # Behaviour of new connections
        # Like a Beoremote Halo, report being active when a client connects
        self.greeting: dict[str, Any] | None = SYSTEM_EVENT
        self.close_on_connect = False
        # Like a Beoremote Halo, acknowledge each configuration received
        self.accept_configuration = True
        self.autoping = True

    async def handler(self, request: web.Request) -> web.WebSocketResponse:
        """Accept a client and record the messages it sends.

        Returns:
            The closed WebSocket
        """
        websocket = web.WebSocketResponse(autoping=self.autoping)
        await websocket.prepare(request)
        self.websocket = websocket
        self.connections.put_nowait(websocket)

        if self.greeting is not None:
            await websocket.send_str(json.dumps(self.greeting))

        if self.close_on_connect:
            await websocket.close()

        async for message in websocket:
            if message.type is WSMsgType.TEXT:
                data = json.loads(message.data)
                self.received.put_nowait(data)
                if self.accept_configuration and "configuration" in data:
                    await websocket.send_str(json.dumps(CONFIGURATION_OK_EVENT))

        self.disconnections.put_nowait(websocket)
        return websocket

    async def send(self, data: dict[str, Any]) -> None:
        """Send an event to the connected client."""
        await self.websocket.send_str(json.dumps(data))

    async def next_message(self) -> dict[str, Any]:
        """Get the next message sent by the client.

        Returns:
            Deserialized message
        """
        return await asyncio.wait_for(self.received.get(), TIMEOUT)


async def wait_for_event(event: asyncio.Event) -> None:
    """Wait for an `asyncio.Event` to be set."""
    await asyncio.wait_for(event.wait(), TIMEOUT)


async def wait_until(condition: Callable[[], bool]) -> None:
    """Wait for a condition to become true, for changes that don't trigger a callback."""

    async def reached() -> None:
        while not condition():  # ruff: ignore[async-busy-wait]
            await asyncio.sleep(0.001)

    await asyncio.wait_for(reached(), TIMEOUT)


async def wait_for_state(halo: Halo, state: ConnectionState) -> None:
    """Wait for the Halo client to reach a connection state."""
    await wait_until(lambda: halo.connection_state is state)
