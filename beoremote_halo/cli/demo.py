"""Interactive home automation demo for the Beoremote Halo."""

import asyncio
import logging
from uuid import UUID

from beoremote_halo.halo import Halo
from beoremote_halo.helpers import get_button_from_id
from beoremote_halo.models import (
    BaseConfiguration,
    Button,
    ButtonEvent,
    ButtonEventState,
    ButtonState,
    Configuration,
    Icon,
    Icons,
    Page,
    StatusEvent,
    StatusEventState,
    Text,
    Update,
    UpdateButton,
    WheelEvent,
)
from beoremote_halo.util import clamp_button_value

OVEN_TIMER_TITLE = "Oven Timer"
OVEN_TIMER_START = "01:35"

# Seconds between each countdown update
COUNTDOWN_INTERVAL = 1.0

# Change in button value per wheel count
WHEEL_STEP = 5

_LOGGER = logging.getLogger(__name__)


def demo_configuration() -> BaseConfiguration:
    """Create the demo configuration with a kitchen and a living room page.

    Returns:
        Demo configuration
    """
    kitchen = Page(
        "Kitchen",
        [
            Button("Kitchen Light", Icon(Icons.LIGHTS), "On", 95, ButtonState.ACTIVE),
            Button(OVEN_TIMER_TITLE, Text(OVEN_TIMER_START), "Temp 200°C", 0, ButtonState.INACTIVE, default=True),
            Button("Dining Table", Icon(Icons.LIGHTS), "Off", 80, ButtonState.INACTIVE),
        ],
    )
    living_room = Page(
        "Living room",
        [
            Button("Fire Place", Icon(Icons.FIREPLACE), "Ignite", state=ButtonState.INACTIVE),
            Button("Blinds", Icon(Icons.BLINDS), "Closed", 100, ButtonState.ACTIVE),
            Button("TV Backlight", Icon(Icons.RGB_LIGHTS), "Off", 0, ButtonState.INACTIVE),
            Button("Thermostat", Text("21°C"), "Heating", 55, ButtonState.INACTIVE),
        ],
    )
    return BaseConfiguration(Configuration([kitchen, living_room]))


def format_time(seconds: int) -> str:
    """Format seconds as `mm:ss`.

    Returns:
        Formatted time
    """
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def parse_time(text: str) -> int:
    """Parse `mm:ss` as seconds.

    Returns:
        Seconds
    """
    minutes, seconds = text.split(":")
    return int(minutes) * 60 + int(seconds)


class Countdown:
    """Count down the time shown on a button once per second. Can be paused and resumed."""

    def __init__(self, halo: Halo, button_id: UUID, start: str) -> None:
        """Initialize countdown.

        Args:
            halo: Halo to send updates to
            button_id: ID of the button showing the time
            start: Time to count down from, as `mm:ss`
        """
        self._halo = halo
        self._button_id = button_id
        self._start = parse_time(start)
        self._running = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        """If the countdown is currently counting down."""
        return self._task is not None and not self._task.done() and self._running.is_set()

    def resume(self) -> None:
        """Start the countdown, or resume it if paused."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._count_down(), name="Oven timer")
        self._running.set()

    def pause(self) -> None:
        """Pause the countdown."""
        self._running.clear()

    async def stop(self) -> None:
        """Stop the countdown."""
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _count_down(self) -> None:
        """Update the button every second until the time has run out, then deactivate it."""
        for remaining in range(self._start, -1, -1):
            await self._running.wait()
            await self._halo.update(Update(UpdateButton(content=Text(format_time(remaining)), id_=self._button_id)))
            await asyncio.sleep(COUNTDOWN_INTERVAL)

        await self._halo.update(Update(UpdateButton(state=ButtonState.INACTIVE, id_=self._button_id)))


class Demo:
    """React to events from the Beoremote Halo using the demo configuration."""

    def __init__(self, halo: Halo) -> None:
        """Initialize demo and register its callbacks.

        Args:
            halo: Halo configured with `demo_configuration`
        """
        self._halo = halo
        self._countdowns: dict[UUID, Countdown] = {}

        halo.get_button_event(self.on_button_event)
        halo.get_wheel_event(self.on_wheel_event)
        halo.get_status_event(self.on_status_event)

    async def stop(self) -> None:
        """Stop running timers."""
        for countdown in self._countdowns.values():
            await countdown.stop()

    def _get_button(self, id_: UUID) -> Button | None:
        """Get a button from the configuration.

        Returns:
            The button, or None if it isn't part of the configuration
        """
        try:
            return get_button_from_id(self._halo.configuration, id_)
        except ValueError:
            _LOGGER.debug("Event for unknown button: %s", id_)
            return None

    async def on_wheel_event(self, event: WheelEvent) -> None:
        """Change the value of the button in focus."""
        button = self._get_button(event.uuid_id)
        if button is None or button.value is None:
            return

        value = clamp_button_value(button.value + event.counts.value * WHEEL_STEP)
        await self._halo.update(Update(UpdateButton(value=value, id_=button.uuid_id)))

    async def on_button_event(self, event: ButtonEvent) -> None:
        """Toggle the state of a button when released, and start or pause the oven timer."""
        if event.state is not ButtonEventState.RELEASED or (button := self._get_button(event.uuid_id)) is None:
            return

        state = ButtonState.INACTIVE if button.state is ButtonState.ACTIVE else ButtonState.ACTIVE
        await self._halo.update(Update(UpdateButton(state=state, id_=button.uuid_id)))

        if button.title == OVEN_TIMER_TITLE:
            countdown = self._countdowns.setdefault(button.uuid_id, Countdown(self._halo, button.uuid_id, OVEN_TIMER_START))
            if state is ButtonState.ACTIVE:
                countdown.resume()
            else:
                countdown.pause()

    @staticmethod
    def on_status_event(event: StatusEvent) -> None:
        """Log errors reported by the Halo."""
        if event.state is StatusEventState.ERROR:
            _LOGGER.warning(event.message)
