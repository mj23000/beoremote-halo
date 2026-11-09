"""Test the Halo client's WebSocket handling located in `beoremote_halo/halo.py` against a local WebSocket server."""

import asyncio
import contextlib
import functools
from collections.abc import Callable
from typing import Any

import pytest
from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, TraceConfig, TraceRequestStartParams

from beoremote_halo import (
    BaseConfiguration,
    ButtonEvent,
    ButtonEventState,
    Configuration,
    ConnectionState,
    EventType,
    EventTypes,
    Halo,
    PowerEvent,
    PowerEventState,
    StatusEvent,
    StatusEventState,
    SystemEvent,
    SystemEventState,
    Update,
    UpdateButton,
    UpdateDisplayPage,
    WheelEvent,
)
from beoremote_halo.models import WheelEventValues
from tests.const import CHANDELIER_BUTTON, DINING_ROOM_PAGE, GARAGE_PAGE
from tests.fake_halo import CONFIGURATION_OK_EVENT, SYSTEM_EVENT, TIMEOUT, FakeHalo, wait_for_event, wait_for_state

BUTTON_VALUE = 50

BUTTON_EVENT = {"event": {"type": "button", "id": CHANDELIER_BUTTON.str_id, "state": "pressed"}}


async def test_configuration_is_sent_on_connect(halo: Halo, fake_halo: FakeHalo, configuration: BaseConfiguration) -> None:
    """Test that the configuration is sent on connect, followed by updates in order, without the Halo reporting being active."""
    # Like a sleeping Halo, which doesn't report its state on connect
    fake_halo.greeting = None
    connected = asyncio.Event()
    halo.get_on_connection(connected.set)
    # `update` modifies the configuration, so compare against the configuration as it was on connect
    expected_configuration = configuration.to_dict()

    await halo.connect()

    assert halo.websocket_connected
    assert halo.connection_state is ConnectionState.CONNECTED
    assert connected.is_set()

    assert await halo.update(Update(UpdateButton(value=BUTTON_VALUE, id_=CHANDELIER_BUTTON.id_)))
    assert await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))

    assert await fake_halo.next_message() == expected_configuration
    assert (await fake_halo.next_message())["update"]["value"] == BUTTON_VALUE
    assert (await fake_halo.next_message())["update"]["type"] == "displaypage"


async def test_configuration_is_not_resent_when_active(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that the Halo becoming active, e.g. after sleeping, doesn't resend the configuration."""
    fake_halo.accept_configuration = False
    system_events: asyncio.Queue[SystemEvent] = asyncio.Queue()
    halo.get_system_event(system_events.put_nowait)

    await halo.connect()
    assert "configuration" in await fake_halo.next_message()
    assert not halo.configuration_accepted

    await fake_halo.send({"event": {"type": "system", "state": "sleep"}})
    await fake_halo.send(SYSTEM_EVENT)
    # The active event sent on connect, followed by the two above
    for _ in range(3):
        await asyncio.wait_for(system_events.get(), TIMEOUT)

    assert await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))
    assert "update" in await fake_halo.next_message()

    statuses: asyncio.Queue[StatusEvent] = asyncio.Queue()
    halo.get_status_event(statuses.put_nowait)
    await fake_halo.send(CONFIGURATION_OK_EVENT)
    await asyncio.wait_for(statuses.get(), TIMEOUT)
    assert halo.configuration_accepted


async def test_events_are_dispatched(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that sync, async and partial callbacks receive events."""
    # Only the events sent by the test are counted
    fake_halo.greeting = None
    fake_halo.accept_configuration = False
    system_events: list[SystemEvent] = []
    button_events: list[ButtonEvent] = []
    all_events: list[EventTypes] = []
    raw_events: list[dict[str, Any]] = []
    received = asyncio.Event()

    # Async on purpose, to test that awaitables returned by partials are awaited
    async def on_button_event(events: list[ButtonEvent], event: ButtonEvent) -> None:  # ruff: ignore[unused-async]
        events.append(event)
        received.set()

    halo.get_system_event(system_events.append)
    halo.get_button_event(functools.partial(on_button_event, button_events))
    halo.get_all_events(lambda _, type_: all_events.append(type_))
    halo.get_all_events_raw(raw_events.append)

    await halo.connect()
    await fake_halo.send(SYSTEM_EVENT)
    await fake_halo.send(BUTTON_EVENT)
    await wait_for_event(received)

    assert system_events == [SystemEvent(SystemEventState.ACTIVE)]
    assert button_events == [ButtonEvent(ButtonEventState.PRESSED, id_=CHANDELIER_BUTTON.id_)]
    assert all_events == [EventTypes.SYSTEM, EventTypes.BUTTON]
    assert raw_events == [SYSTEM_EVENT, BUTTON_EVENT]


async def test_callback_error_does_not_break_connection(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that an exception raised in a callback is contained."""
    calls = 0
    second_call = asyncio.Event()

    def on_system_event(_: SystemEvent) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "Callback failure"
            raise TypeError(msg)
        second_call.set()

    halo.get_system_event(on_system_event)

    # The first call, for the active event sent on connect, raises
    await halo.connect()
    await fake_halo.next_message()
    await fake_halo.send(SYSTEM_EVENT)
    await wait_for_event(second_call)

    assert halo.websocket_connected
    assert await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))
    assert (await fake_halo.next_message())["update"]["type"] == "displaypage"


async def test_reconnect_drops_stale_updates(halo: Halo, fake_halo: FakeHalo, configuration: BaseConfiguration) -> None:
    """Test that updates are rejected while disconnected and the configuration is resent on reconnect."""
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    await halo.connect(reconnect=True)
    await fake_halo.connections.get()
    await fake_halo.next_message()

    await fake_halo.websocket.close()
    await wait_for_event(lost)

    assert not halo.websocket_connected
    assert not await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))

    await asyncio.wait_for(fake_halo.connections.get(), TIMEOUT)
    assert await fake_halo.next_message() == configuration.to_dict()
    assert fake_halo.received.empty()


async def test_connect_failure_raises(unused_tcp_port: int) -> None:
    """Test that a failed connection is reported when not reconnecting."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    with pytest.raises(ClientError):
        await halo.connect()

    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_connect_failure_with_reconnect_keeps_retrying(unused_tcp_port: int) -> None:
    """Test that a failed connection is retried in the background when reconnecting."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    await halo.connect(reconnect=True)
    assert not halo.websocket_connected

    await halo.disconnect()
    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_disconnect(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test disconnecting and connecting again."""
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    # Disconnecting before connecting does nothing
    await halo.disconnect()

    await halo.connect()
    first_websocket = await fake_halo.connections.get()
    await halo.disconnect()

    assert halo.connection_state is ConnectionState.DISCONNECTED
    assert not lost.is_set()
    assert not await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))

    await halo.connect()
    assert halo.websocket_connected
    assert await fake_halo.connections.get() is not first_websocket


async def test_disconnect_from_callback(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that disconnecting from within a callback doesn't deadlock."""

    async def on_system_event(_: SystemEvent) -> None:
        await halo.disconnect()

    halo.get_system_event(on_system_event)

    await halo.connect()
    await fake_halo.send(SYSTEM_EVENT)

    await wait_for_state(halo, ConnectionState.DISCONNECTED)


async def test_check_device_connection_reuses_connection(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that checking the connection while connected doesn't replace the connection."""
    await halo.connect()
    await fake_halo.connections.get()

    assert await halo.check_device_connection()
    assert fake_halo.connections.empty()


async def test_check_device_connection_failure(unused_tcp_port: int) -> None:
    """Test checking the connection to an unavailable Halo."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    assert not await halo.check_device_connection()
    with pytest.raises(ClientError):
        await halo.check_device_connection(raise_error=True)


@pytest.mark.parametrize(
    argnames=("register_callback", "data", "expected_event"),
    ids=("wheel", "status", "power"),
    argvalues=[
        (
            Halo.get_wheel_event,
            {"event": {"type": "wheel", "id": CHANDELIER_BUTTON.str_id, "counts": -2}},
            WheelEvent(WheelEventValues.WHEEL_COUNTER_CLOCKWISE_FAST, id_=CHANDELIER_BUTTON.id_),
        ),
        (
            Halo.get_status_event,
            CONFIGURATION_OK_EVENT,
            StatusEvent(StatusEventState.OK, "configuration"),
        ),
        (
            Halo.get_power_event,
            {"event": {"type": "power", "capacity": 15, "state": "low"}},
            PowerEvent(15, PowerEventState.LOW),
        ),
    ],
)
async def test_event_callbacks(
    halo: Halo,
    fake_halo: FakeHalo,
    register_callback: Callable[[Halo, Callable[[Any], None]], None],
    data: dict[str, Any],
    expected_event: EventType,
) -> None:
    """Test that each type of event is passed to its callback."""
    events: asyncio.Queue[EventType] = asyncio.Queue()
    register_callback(halo, events.put_nowait)

    await halo.connect()
    await fake_halo.send(data)

    assert await asyncio.wait_for(events.get(), TIMEOUT) == expected_event


async def test_invalid_event_is_ignored(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that an event that can't be deserialized is logged and skipped."""
    fake_halo.greeting = None
    events: asyncio.Queue[SystemEvent] = asyncio.Queue()
    halo.get_system_event(events.put_nowait)

    await halo.connect()
    await fake_halo.send({"event": {"type": "unknown"}})
    await fake_halo.send(SYSTEM_EVENT)

    assert await asyncio.wait_for(events.get(), TIMEOUT) == SystemEvent(SystemEventState.ACTIVE)
    assert "unable to deserialize WebSocket event" in caplog.text
    assert halo.websocket_connected


async def test_mislabeled_event_is_ignored(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that an event is not passed to the callback of another type its fields happen to match."""
    fake_halo.greeting = None
    fake_halo.accept_configuration = False
    status_events: list[StatusEvent] = []
    raw_events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    halo.get_status_event(status_events.append)
    halo.get_all_events_raw(raw_events.put_nowait)
    # Fields of a status event, but with the type of a system event
    mislabeled = {"event": {"type": "system", "state": "ok"}}

    await halo.connect()
    await fake_halo.send(mislabeled)
    await fake_halo.send(SYSTEM_EVENT)

    # The raw callback still receives it
    assert await asyncio.wait_for(raw_events.get(), TIMEOUT) == mislabeled
    assert await asyncio.wait_for(raw_events.get(), TIMEOUT) == SYSTEM_EVENT
    assert status_events == []
    assert "unable to deserialize WebSocket event" in caplog.text


async def test_unhandled_messages_are_ignored(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test binary messages, events without a specific callback, and losing the connection without a callback."""
    events: asyncio.Queue[EventTypes] = asyncio.Queue()
    halo.get_all_events(lambda _, type_: events.put_nowait(type_))

    await halo.connect()
    await fake_halo.connections.get()
    await fake_halo.websocket.send_bytes(b"binary")
    await fake_halo.send(SYSTEM_EVENT)

    assert await asyncio.wait_for(events.get(), TIMEOUT) == EventTypes.SYSTEM

    await fake_halo.websocket.close()
    await wait_for_state(halo, ConnectionState.DISCONNECTED)


async def test_set_configuration(halo: Halo, fake_halo: FakeHalo, configuration: BaseConfiguration) -> None:
    """Test storing and sending configurations."""
    empty_configuration = BaseConfiguration(Configuration(pages=[]))

    # Stored, but not sent while disconnected
    assert not await halo.set_configuration(empty_configuration)
    assert halo.configuration is empty_configuration

    await halo.set_configuration(configuration, send_configuration=False)
    await halo.connect()
    assert await fake_halo.next_message() == configuration.to_dict()

    assert not await halo.set_configuration(configuration, send_configuration=False)

    # `None` is replaced by an empty configuration
    assert await halo.set_configuration(None)
    assert (await fake_halo.next_message())["configuration"]["pages"] == []
    assert halo.configuration.configuration.pages == []
    assert fake_halo.received.empty()


async def test_connect_without_sending_configuration(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that the configuration isn't sent on connect when disabled."""
    await halo.connect(send_configuration=False)
    assert await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))

    assert (await fake_halo.next_message())["update"]["type"] == "displaypage"


async def test_connect_twice(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that connecting while connected doesn't start another connection."""
    await halo.connect()
    await halo.connect()

    assert "WebSocket task already active" in caplog.text
    await fake_halo.connections.get()
    assert fake_halo.connections.empty()


async def test_connection_lost_without_reconnect(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test losing the connection when not reconnecting, and connecting again afterwards."""
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    await halo.connect()
    await fake_halo.connections.get()

    await fake_halo.websocket.close()
    await wait_for_event(lost)

    assert halo.connection_state is ConnectionState.DISCONNECTED
    assert "Lost connection" in caplog.text
    assert fake_halo.connections.empty()

    await halo.connect()
    assert halo.websocket_connected


async def test_heartbeat_timeout(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a Halo that stops answering pings is treated as a lost connection."""
    fake_halo.autoping = False
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    await halo.connect()
    await wait_for_event(lost)

    assert halo.connection_state is ConnectionState.DISCONNECTED
    # The reason is only reported by newer versions of aiohttp
    assert "Lost connection" in caplog.text


async def test_websocket_protocol_error(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a WebSocket protocol error is treated as a lost connection."""
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    await halo.connect()
    await fake_halo.connections.get()

    # Larger than the client's default maximum message size of 4 MiB. The client can close the connection
    # as soon as it reads the message's length, before the fake Halo has finished sending it
    with contextlib.suppress(ConnectionError):
        await fake_halo.websocket.send_str("x" * (4 * 1024 * 1024 + 1))
    await wait_for_event(lost)

    assert "WebSocket error" in caplog.text


async def test_pending_updates_are_dropped_on_disconnect(halo: Halo, fake_halo: FakeHalo, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that data still queued when disconnecting isn't sent on the next connection."""
    send_started = asyncio.Event()

    async def blocking_send_str(*_: object, **__: object) -> None:
        send_started.set()
        await asyncio.Event().wait()

    with monkeypatch.context() as patch:
        # Simulate a slow network, the configuration is being sent while the update waits in the queue
        patch.setattr(ClientWebSocketResponse, "send_str", blocking_send_str)
        await halo.connect()
        await wait_for_event(send_started)
        assert await halo.update(Update(UpdateButton(value=BUTTON_VALUE, id_=CHANDELIER_BUTTON.id_)))

        await halo.disconnect()

    await halo.connect()
    assert "configuration" in await fake_halo.next_message()
    assert await halo.update(Update(UpdateDisplayPage(page_id=GARAGE_PAGE.uuid_id)))
    assert (await fake_halo.next_message())["update"]["type"] == "displaypage"


async def test_disconnect_while_connecting(unused_tcp_port: int) -> None:
    """Test that `connect` returns when `disconnect` is called before the first attempt has finished."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    connect = asyncio.create_task(halo.connect(reconnect=True))
    # Let `connect` create the connection task, but not run it
    await asyncio.sleep(0)
    await halo.disconnect()

    await asyncio.wait_for(connect, TIMEOUT)
    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_connect_while_disconnecting(unused_tcp_port: int) -> None:
    """Test that `connect` returns when it is replaced by a new `connect` while `disconnect` is waiting."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    first_connect = asyncio.create_task(halo.connect(reconnect=True))
    # Let `connect` create the connection task, but not run it
    await asyncio.sleep(0)
    # Started before the cancelled connection task has finished
    disconnect = asyncio.create_task(halo.disconnect())
    second_connect = asyncio.create_task(halo.connect(reconnect=True))

    await asyncio.wait_for(first_connect, TIMEOUT)
    await asyncio.wait_for(disconnect, TIMEOUT)
    await asyncio.wait_for(second_connect, TIMEOUT)

    await halo.disconnect()
    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_connect_cancelled(unused_tcp_port: int) -> None:
    """Test that cancelling `connect` is propagated to the caller."""
    halo = Halo("127.0.0.1", port=unused_tcp_port)

    connect = asyncio.create_task(halo.connect(reconnect=True))
    await asyncio.sleep(0)
    connect.cancel()

    with pytest.raises(asyncio.CancelledError):
        await connect

    await halo.disconnect()
    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_disconnect_cancelled(halo: Halo) -> None:
    """Test that cancelling `disconnect` is propagated to the caller."""
    await halo.connect()

    disconnect = asyncio.create_task(halo.disconnect())
    # Let `disconnect` start waiting for the connection task
    await asyncio.sleep(0)
    disconnect.cancel()

    with pytest.raises(asyncio.CancelledError):
        await disconnect

    assert halo.connection_state is ConnectionState.DISCONNECTED


async def test_check_device_connection(halo: Halo) -> None:
    """Test checking the connection to a Halo that sends a message on connect."""
    assert await halo.check_device_connection()
    assert not halo.websocket_connected


async def test_check_device_connection_closed(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test checking the connection to a Halo that closes the connection immediately."""
    fake_halo.greeting = None
    fake_halo.close_on_connect = True

    assert not await halo.check_device_connection()


# Sent by a Beoremote Halo for a configuration with an unknown icon
INVALID_CONFIGURATION_MESSAGE = (
    'homeautomationsystem::message::Configuration|homeautomationsystem::schema::Button::Content [No oneof found] {"icon":"rocket"}'
)
INVALID_CONFIGURATION_EVENT = {"event": {"type": "status", "state": "error", "message": INVALID_CONFIGURATION_MESSAGE}}


async def test_rejected_configuration_stops_reconnecting(halo: Halo, fake_halo: FakeHalo, caplog: pytest.LogCaptureFixture) -> None:
    """Test that the client doesn't reconnect, or resend a configuration the Halo has rejected."""
    fake_halo.accept_configuration = False
    statuses: asyncio.Queue[StatusEvent] = asyncio.Queue()
    halo.get_status_event(statuses.put_nowait)
    lost = asyncio.Event()
    halo.get_on_connection_lost(lost.set)

    await halo.connect(reconnect=True)
    await fake_halo.connections.get()
    await fake_halo.next_message()
    await fake_halo.send(INVALID_CONFIGURATION_EVENT)

    # Still passed on to the status callback
    assert (await asyncio.wait_for(statuses.get(), TIMEOUT)).state is StatusEventState.ERROR
    assert halo.configuration_rejected
    assert f"rejected the configuration: {INVALID_CONFIGURATION_MESSAGE}" in caplog.text

    await fake_halo.websocket.close()
    await wait_for_event(lost)
    # Longer than the reconnect delay
    await asyncio.sleep(0.3)
    assert fake_halo.connections.empty()
    assert fake_halo.received.empty()
    assert "not reconnecting as the configuration was rejected" in caplog.text

    # Connecting explicitly tries again
    await halo.connect(reconnect=True)
    assert halo.websocket_connected
    assert not halo.configuration_rejected


async def test_new_configuration_resumes_reconnecting(halo: Halo, fake_halo: FakeHalo, configuration: BaseConfiguration) -> None:
    """Test that setting a new configuration after a rejected one re-enables reconnecting."""
    fake_halo.accept_configuration = False
    statuses: asyncio.Queue[StatusEvent] = asyncio.Queue()
    halo.get_status_event(statuses.put_nowait)

    await halo.connect(reconnect=True)
    await fake_halo.connections.get()
    await fake_halo.next_message()
    await fake_halo.send(INVALID_CONFIGURATION_EVENT)
    await asyncio.wait_for(statuses.get(), TIMEOUT)

    configuration.configuration.pages = [DINING_ROOM_PAGE]
    assert await halo.set_configuration(configuration)
    assert not halo.configuration_rejected
    assert len((await fake_halo.next_message())["configuration"]["pages"]) == 1

    await fake_halo.websocket.close()
    await asyncio.wait_for(fake_halo.connections.get(), TIMEOUT)


@pytest.mark.parametrize(
    argnames="status",
    ids=("configuration_ok", "update_error", "invalid_update", "error_without_message"),
    argvalues=[
        CONFIGURATION_OK_EVENT["event"],
        {"state": "error", "message": "The button id was not found the the configuration"},
        {"state": "error", "message": "homeautomationsystem::message::Update|homeautomationsystem::schema::Update [No oneof found]"},
        {"state": "error"},
    ],
)
async def test_other_status_events_dont_reject_configuration(halo: Halo, fake_halo: FakeHalo, status: dict[str, str]) -> None:
    """Test that only an invalid configuration error marks the configuration as rejected."""
    statuses: asyncio.Queue[StatusEvent] = asyncio.Queue()
    halo.get_status_event(statuses.put_nowait)

    await halo.connect()
    await fake_halo.send({"event": {"type": "status", **status}})
    await asyncio.wait_for(statuses.get(), TIMEOUT)

    assert not halo.configuration_rejected


async def test_legacy_invalid_configuration_message(halo: Halo, fake_halo: FakeHalo) -> None:
    """Test that the invalid configuration message handled by the original client is still recognized."""
    statuses: asyncio.Queue[StatusEvent] = asyncio.Queue()
    halo.get_status_event(statuses.put_nowait)
    fake_halo.accept_configuration = False

    await halo.connect()
    await fake_halo.send({"event": {"type": "status", "state": "error", "message": "Invalid Configuration: too many pages"}})
    await asyncio.wait_for(statuses.get(), TIMEOUT)

    assert halo.configuration_rejected


async def test_session(fake_halo: FakeHalo, configuration: BaseConfiguration) -> None:
    """Test that a provided session is used for all connections, and is never closed by the client."""
    requests: list[str] = []

    # aiohttp requires trace callbacks to be coroutines
    async def on_request_start(_: ClientSession, __: object, params: TraceRequestStartParams) -> None:  # ruff: ignore[unused-async]
        requests.append(str(params.url))

    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)

    async with ClientSession(trace_configs=[trace_config]) as session:
        halo = Halo(fake_halo.server.host, configuration, port=fake_halo.server.port, session=session)  # ty: ignore[unresolved-attribute]

        await halo.connect()
        await halo.disconnect()
        assert await halo.check_device_connection()

        assert not session.closed
        url = f"ws://{fake_halo.server.host}:{fake_halo.server.port}/"  # ty: ignore[unresolved-attribute]
        assert requests == [url, url]

        # The session can still be used to connect again
        await halo.connect()
        assert halo.websocket_connected
        await halo.disconnect()


async def test_session_connect_timeout() -> None:
    """Test that connecting times out with a provided session, which has no connect timeout of its own."""
    writers: list[asyncio.StreamWriter] = []
    # Accepts connections, but never answers the WebSocket handshake
    server = await asyncio.start_server(lambda _, writer: writers.append(writer), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async with server, ClientSession() as session:
        halo = Halo("127.0.0.1", port=port, session=session)

        with pytest.raises(TimeoutError):
            await halo.connect()

        for writer in writers:
            writer.close()
