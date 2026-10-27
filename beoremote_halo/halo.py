"""Halo client."""

import asyncio
import contextlib
import functools
import inspect
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from enum import StrEnum
from typing import Any, Final

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

from beoremote_halo.const import WEBSOCKET_PORT, WEBSOCKET_TIMEOUT
from beoremote_halo.helpers import update_button
from beoremote_halo.models import (
    BaseConfiguration,
    ButtonEvent,
    Configuration,
    Event,
    EventType,
    EventTypes,
    PowerEvent,
    StatusEvent,
    StatusEventState,
    SystemEvent,
    Update,
    UpdateButton,
    WheelEvent,
)

# Message of the `StatusEvent` sent by the Halo when it accepts a configuration
_CONFIGURATION_ACCEPTED_MESSAGE: Final = "configuration"
# Starts of the message in the `StatusEvent` sent by the Halo when it rejects a configuration. The first is sent by
# current firmware, e.g. "homeautomationsystem::message::Configuration|... [No oneof found] {"icon":"rocket"}"
_INVALID_CONFIGURATION_MESSAGES: Final = (
    "homeautomationsystem::message::configuration",
    "invalid configuration",
)


def _empty_configuration() -> BaseConfiguration:
    """Configuration used when none is provided.

    Returns:
        Configuration without pages
    """
    return BaseConfiguration(Configuration(pages=[]))


class ConnectionState(StrEnum):
    """State of the WebSocket connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"


class Halo:
    """Beoremote Halo client."""

    def __init__(
        self,
        host: str,
        configuration: BaseConfiguration | None = None,
        port: int = WEBSOCKET_PORT,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize Halo client.

        Args:
            host: IPv4 address
            configuration: Halo configuration. Defaults to `BaseConfiguration(Configuration([]))` if set to None
            port: WebSocket port. Defaults to 8080
            session: Session used for WebSocket connections, e.g. an application's shared session. It is never closed by the client.
                Defaults to a new session for each connection
        """
        self.host = host
        self.websocket_reconnect = False

        self._configuration = _empty_configuration() if configuration is None else configuration
        # Set when the Halo rejects the configuration, which stops reconnecting until a new configuration is set
        self._configuration_rejected = False
        # If the configuration is sent on each (re)connect, set by `connect`
        self._send_configuration = True
        # If the Halo has accepted the configuration on the current connection
        self._configuration_accepted = False
        self._url = f"ws://{host}:{port}/"
        self._session = session

        self._state = ConnectionState.DISCONNECTED
        self._websocket_task: asyncio.Task[None] | None = None
        # Reader and writer tasks of the current connection
        self._io_tasks: set[asyncio.Task[None]] = set()
        self._queue: asyncio.Queue[str] = asyncio.Queue()

        self._on_connection_lost: Callable[[], Awaitable[None] | None] | None = None
        self._on_connection: Callable[[], Awaitable[None] | None] | None = None

        self._on_all_events: Callable[[EventType, EventTypes], Awaitable[None] | None] | None = None
        self._on_all_events_raw: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None

        self._event_callbacks: dict[EventTypes, Callable[[Any], Awaitable[None] | None]] = {}

        self._logger = logging.getLogger(__name__)

    @property
    def connection_state(self) -> ConnectionState:
        """State of the WebSocket connection."""
        return self._state

    @property
    def websocket_connected(self) -> bool:
        """If the WebSocket connection is currently established."""
        return self._state is ConnectionState.CONNECTED

    def _send_data(self, data: BaseConfiguration | Update) -> bool:
        """Send data to the Beoremote Halo.

        Data is only queued while connected, so nothing stale is sent after a reconnect.

        Args:
            data: `Configuration` or `Update` to send

        Returns:
            If the data was successfully put into WebSocket queue
        """
        if not self.websocket_connected:
            self._logger.debug("Not connected, unable to send data: %s", data)
            return False

        self._queue.put_nowait(data.to_json())
        return True

    @property
    def configuration(self) -> BaseConfiguration:
        """Current configuration."""
        return self._configuration

    @property
    def configuration_accepted(self) -> bool:
        """If the Halo has accepted the current configuration on the current connection."""
        return self._configuration_accepted

    @property
    def configuration_rejected(self) -> bool:
        """If the Halo rejected the current configuration as invalid.

        While set, the client doesn't reconnect, as the same configuration would be rejected again.
        Cleared when a new configuration is set, or `connect` is called.
        """
        return self._configuration_rejected

    async def set_configuration(self, configuration: BaseConfiguration | None, send_configuration: bool = True) -> bool:
        """Set configuration.

        Setting configuration to be `None` will set the configuration to be `BaseConfiguration(Configuration([]))`.

        The configuration is always stored, and is sent on the next (re)connect if `connect` was called with `send_configuration`.

        Args:
            configuration: Configuration to set/send
            send_configuration: Send configuration to Halo. Requires WebSocket connection to be active. Defaults to True

        Returns:
            If the configuration was successfully put into WebSocket queue
        """
        self._configuration = _empty_configuration() if configuration is None else configuration
        self._configuration_rejected = False

        if send_configuration and self._send_data(self._configuration):
            self._configuration_accepted = False
            return True
        return False

    async def update(self, update: Update, update_configuration: bool = True) -> bool:
        """Send update to Halo. Requires WebSocket connection to be active.

        Args:
            update: Update event to be sent
            update_configuration: If the configuration should be modified with passed `UpdateButton` values. Defaults to True

        Returns:
            If the update was successfully put into WebSocket queue
        """
        if update_configuration and isinstance(update.update, UpdateButton):
            # Update button in configuration
            update_button(
                self._configuration,
                update.update.uuid_id,
                state=update.update.state,
                value=update.update.value,
                title=update.update.title,
                subtitle=update.update.subtitle,
                content=update.update.content,
            )

        return self._send_data(update)

    async def check_device_connection(self, raise_error: bool = False) -> bool:
        """Check WebSocket connection.

        The Halo only accepts a single client, so a new connection replaces any existing one.
        If this client is already connected, no new connection is made.

        Args:
            raise_error: Raise any errors. Defaults to False

        Returns:
            Connection successful

        Raises:
            ClientError: Error connecting and receiving from WebSocket
            TimeoutError: No message received from WebSocket in time
        """
        if self.websocket_connected:
            return True

        try:
            async with self._connect_websocket() as websocket:
                message = await websocket.receive(timeout=WEBSOCKET_TIMEOUT)
        except (ClientError, TimeoutError):
            if raise_error:
                raise
            self._logger.exception("Unable to connect to %s", self.host)
            return False

        return message.type not in {
            WSMsgType.CLOSE,
            WSMsgType.CLOSING,
            WSMsgType.CLOSED,
            WSMsgType.ERROR,
        }

    async def connect(self, reconnect: bool = False, send_configuration: bool = True) -> None:
        """Start WebSocket connection.

        Will start listening for events and allow updates to be sent.
        Waits for the first connection attempt to finish. If `reconnect` is set, a failed attempt is retried in the background.

        Args:
            reconnect: Whether or not to reconnect. Defaults to False
            send_configuration: Whether to automatically send the configuration as soon as each connect/reconnect is made.
                The Halo accepts it in any state, including asleep, and keeps it while the client stays connected. Defaults to True

        Raises:
            ClientError: First connection attempt failed and `reconnect` is not set
            TimeoutError: First connection attempt timed out and `reconnect` is not set
            CancelledError: The caller was cancelled while waiting for the first connection attempt
        """  # ruff: ignore[docstring-extraneous-exception] - raised by the connection task through `first_attempt`
        if self._websocket_task is not None and not self._websocket_task.done():
            self._logger.error("WebSocket task already active")
            return

        self.websocket_reconnect = reconnect
        self._send_configuration = send_configuration
        self._configuration_rejected = False

        first_attempt: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(
            coro=self._websocket_connection(first_attempt),
            name=f"{self.host} - task",
        )
        task.add_done_callback(functools.partial(self._on_websocket_task_done, first_attempt))
        self._websocket_task = task

        try:
            await first_attempt
        except asyncio.CancelledError:
            # `disconnect` was called before the first attempt finished, only the caller's own cancellation is raised
            if (current := asyncio.current_task()) is not None and current.cancelling():
                raise

    def _on_websocket_task_done(self, first_attempt: asyncio.Future[None], task: asyncio.Task[None]) -> None:
        """Clean up after the connection task, also when it was cancelled before it started running.

        Args:
            first_attempt: Future awaited by `connect`
            task: The finished connection task
        """
        first_attempt.cancel()

        # Don't touch the state of a connection that has been started since
        if self._websocket_task in {None, task}:
            self._state = ConnectionState.DISCONNECTED

    async def disconnect(self) -> None:
        """Stop WebSocket connection.

        Safe to call when not connected, and from within callbacks.

        Raises:
            CancelledError: The caller was cancelled while waiting for the connection to close
        """
        task, self._websocket_task = self._websocket_task, None
        if task is None or task.done():
            return

        self._state = ConnectionState.CLOSING
        task.cancel()

        # Awaiting from inside the connection's own tasks would deadlock, cancelling is enough there
        if (current := asyncio.current_task()) is task or current in self._io_tasks:
            return

        try:
            await task
        except asyncio.CancelledError:
            # Only swallow the cancellation of the connection task, not of the caller
            if current is not None and current.cancelling():
                raise

    async def _websocket_connection(self, first_attempt: asyncio.Future[None]) -> None:
        """WebSocket connection handler.

        Args:
            first_attempt: Resolved when the first connection attempt has succeeded or failed
        """
        while True:
            error = await self._connect_once(first_attempt)
            await self._on_connection_ended(error)

            reconnect = self._should_reconnect()
            if not first_attempt.done():
                # Only report the failure to `connect` when no further attempts are made
                if not reconnect and error is not None:
                    first_attempt.set_exception(error)
                else:
                    first_attempt.set_result(None)

            if not reconnect:
                return

            await asyncio.sleep(WEBSOCKET_TIMEOUT)

    def _should_reconnect(self) -> bool:
        """If the connection should be re-established after it has been lost.

        Returns:
            Reconnect
        """
        return self.websocket_reconnect and not self._configuration_rejected

    @contextlib.asynccontextmanager
    async def _connect_websocket(self, heartbeat: float | None = None) -> AsyncGenerator[ClientWebSocketResponse]:
        """Open a WebSocket connection to the Halo, using the provided session if any.

        Args:
            heartbeat: Interval between pings sent to the Halo. Defaults to no pings

        Yields:
            Established WebSocket connection
        """
        async with contextlib.AsyncExitStack() as stack:
            session = self._session or await stack.enter_async_context(ClientSession())
            # Applied here, so the timeout also works for sessions without a connect timeout
            async with asyncio.timeout(WEBSOCKET_TIMEOUT):
                websocket = await session.ws_connect(self._url, heartbeat=heartbeat)
            yield await stack.enter_async_context(websocket)

    async def _connect_once(self, first_attempt: asyncio.Future[None]) -> ClientError | TimeoutError | None:
        """Connect and handle the WebSocket connection until it is closed.

        Args:
            first_attempt: Resolved when the connection has been established

        Returns:
            The error that ended the connection, if any
        """
        self._state = ConnectionState.CONNECTING
        try:
            # Increase heartbeat time to handle slow pongs better
            async with self._connect_websocket(heartbeat=WEBSOCKET_TIMEOUT * 2) as websocket:
                await self._on_connected(websocket, first_attempt)
        except (ClientError, TimeoutError) as error:
            return error
        return None

    async def _on_connected(self, websocket: ClientWebSocketResponse, first_attempt: asyncio.Future[None]) -> None:
        """Set up a new connection, and handle it until it is closed.

        Args:
            websocket: Established WebSocket connection
            first_attempt: Resolved when the connection has been established
        """
        # A new queue drops data left from a previous connection. The configuration is queued first, so it precedes any updates
        self._queue = asyncio.Queue()
        self._configuration_accepted = False
        if self._send_configuration:
            self._queue.put_nowait(self._configuration.to_json())
        self._state = ConnectionState.CONNECTED

        if not first_attempt.done():
            first_attempt.set_result(None)

        if self._on_connection:
            await self._trigger_callback(self._on_connection)

        await self._run_connection(websocket)

    async def _on_connection_ended(self, error: ClientError | TimeoutError | None) -> None:
        """Reset connection state and notify about a lost connection.

        Args:
            error: The error that ended the connection, if any
        """
        was_connected = self.websocket_connected
        self._state = ConnectionState.DISCONNECTED

        if not was_connected:
            self._logger.debug("Unable to connect to %s: %s", self._url, error)
            return

        if self._should_reconnect():
            self._logger.debug("Lost connection to %s: %s", self._url, error)
        elif self._configuration_rejected:
            self._logger.error(
                "Lost connection to %s, not reconnecting as the configuration was rejected: %s",
                self._url,
                error,
            )
        else:
            self._logger.error("Lost connection to %s: %s", self._url, error)

        if self._on_connection_lost:
            await self._trigger_callback(self._on_connection_lost)

    async def _run_connection(self, websocket: ClientWebSocketResponse) -> None:
        """Receive events and send queued data until the connection closes or fails.

        Args:
            websocket: Established WebSocket connection
        """
        self._io_tasks = {
            asyncio.create_task(self._receive_loop(websocket), name=f"{self.host} - receive"),
            asyncio.create_task(self._send_loop(websocket), name=f"{self.host} - send"),
        }
        try:
            done, _ = await asyncio.wait(self._io_tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in self._io_tasks:
                task.cancel()
            await asyncio.gather(*self._io_tasks, return_exceptions=True)
            self._io_tasks = set()

        # Propagate errors from the task that stopped first
        for task in done:
            task.result()

    async def _receive_loop(self, websocket: ClientWebSocketResponse) -> None:
        """Handle incoming messages until the connection closes.

        Raises:
            ClientError: The connection failed
        """
        async for message in websocket:
            if message.type is WSMsgType.TEXT:
                await self._on_message(message.data)
            elif message.type is WSMsgType.ERROR:
                error = websocket.exception()
                if isinstance(error, (ClientError, TimeoutError)):
                    raise error
                msg = f"WebSocket error: {error}"
                raise ClientError(msg) from error

    async def _send_loop(self, websocket: ClientWebSocketResponse) -> None:
        """Send queued data as soon as it is available."""
        while True:
            data = await self._queue.get()
            await websocket.send_str(data)

    async def _on_message(self, event: str) -> None:
        """Handle WebSocket events."""
        # Parsed once, as the raw callback also gets the event as a dict
        try:
            raw_event = json.loads(event)
            # Trigger callbacks for raw events immediately in case there are deserialization problems
            if self._on_all_events_raw:
                await self._trigger_callback(self._on_all_events_raw, raw_event)

            deserialized_data = Event.from_dict(raw_event).event
        except (ValueError, AttributeError):
            self._logger.exception("%s unable to deserialize WebSocket event: %s", self.host, event)
            return

        if isinstance(deserialized_data, StatusEvent):
            self._on_status_event(deserialized_data)

        # Handle all events if defined
        if self._on_all_events:
            await self._trigger_callback(self._on_all_events, deserialized_data, deserialized_data.type_)

        # Handle specific events if defined
        if triggered_event := self._event_callbacks.get(deserialized_data.type_):
            await self._trigger_callback(triggered_event, deserialized_data)

    def _on_status_event(self, event: StatusEvent) -> None:
        """Detect an accepted or rejected configuration."""
        if event.state is StatusEventState.OK and event.message is not None and event.message.lower() == _CONFIGURATION_ACCEPTED_MESSAGE:
            self._configuration_accepted = True
        elif (
            event.state is StatusEventState.ERROR
            and event.message is not None
            and event.message.lower().startswith(_INVALID_CONFIGURATION_MESSAGES)
        ):
            self._configuration_rejected = True
            self._logger.error("%s rejected the configuration: %s", self.host, event.message)

    async def _trigger_callback(self, callback: Callable[..., Awaitable[None] | None], *args: object) -> None:
        """Trigger async or sync callback correctly.

        Errors raised by the callback are logged, so they can't break the connection.
        """
        try:
            result = callback(*args)
            if inspect.isawaitable(result):
                await result
        except Exception:
            self._logger.exception("%s error in callback %s", self.host, callback)

    def get_on_connection_lost(self, on_connection_lost: Callable[[], Awaitable[None] | None]) -> None:
        """Set callback for WebSocket connection lost."""
        self._on_connection_lost = on_connection_lost

    def get_on_connection(self, on_connection: Callable[[], Awaitable[None] | None]) -> None:
        """Set callback for WebSocket connection."""
        self._on_connection = on_connection

    def get_all_events(
        self,
        on_all_events: Callable[[EventType, EventTypes], Awaitable[None] | None],
    ) -> None:
        """Set callback for all events."""
        self._on_all_events = on_all_events

    def get_all_events_raw(
        self,
        on_all_events_raw: Callable[[dict[str, Any]], Awaitable[None] | None],
    ) -> None:
        """Set callback for all events as dict."""
        self._on_all_events_raw = on_all_events_raw

    def get_wheel_event(self, on_wheel_event: Callable[[WheelEvent], Awaitable[None] | None]) -> None:
        """Set callback for WheelEvent."""
        self._event_callbacks[EventTypes.WHEEL] = on_wheel_event

    def get_system_event(self, on_system_event: Callable[[SystemEvent], Awaitable[None] | None]) -> None:
        """Set callback for SystemEvent."""
        self._event_callbacks[EventTypes.SYSTEM] = on_system_event

    def get_status_event(self, on_status_event: Callable[[StatusEvent], Awaitable[None] | None]) -> None:
        """Set callback for StatusEvent."""
        self._event_callbacks[EventTypes.STATUS] = on_status_event

    def get_power_event(self, on_power_event: Callable[[PowerEvent], Awaitable[None] | None]) -> None:
        """Set callback for PowerEvent."""
        self._event_callbacks[EventTypes.POWER] = on_power_event

    def get_button_event(self, on_button_event: Callable[[ButtonEvent], Awaitable[None] | None]) -> None:
        """Set callback for ButtonEvent."""
        self._event_callbacks[EventTypes.BUTTON] = on_button_event
