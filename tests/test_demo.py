"""Test the CLI's home automation demo located in `beoremote_halo/cli/demo.py`."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from beoremote_halo import (
    MAX_VALUE,
    Button,
    ButtonEvent,
    ButtonEventState,
    ButtonState,
    Halo,
    StatusEvent,
    StatusEventState,
    Text,
    UpdateButton,
    WheelEvent,
    get_all_buttons,
    get_default_button,
)
from beoremote_halo.cli.demo import (
    OVEN_TIMER_START,
    OVEN_TIMER_TITLE,
    WHEEL_STEP,
    Countdown,
    Demo,
    demo_configuration,
    format_time,
    parse_time,
)
from beoremote_halo.models import WheelEventValues
from tests.fake_halo import wait_until


@pytest.fixture(autouse=True)  # ruff: ignore[pytest-fixture-autouse] - every test should use the shortened timings
def fast_countdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shorten the time between countdown updates.

    Still long enough for the tests to see each update, and pause the countdown, before the next one is sent.
    """
    monkeypatch.setattr("beoremote_halo.cli.demo.COUNTDOWN_INTERVAL", 0.05)


@pytest.fixture
def halo(monkeypatch: pytest.MonkeyPatch) -> Halo:
    """Disconnected Halo with the demo configuration, recording the updates sent to it.

    Returns:
        Halo client
    """
    halo = Halo("127.0.0.1", demo_configuration())
    monkeypatch.setattr(halo, "update", AsyncMock(wraps=halo.update))
    return halo


def get_button(halo: Halo, title: str) -> Button:
    """Get a button from the Halo's configuration by its title.

    Returns:
        Button
    """
    return next(button for button in get_all_buttons(halo.configuration) if button.title == title)


def sent_updates(halo: Halo) -> list[UpdateButton]:
    """Get the button updates sent to the Halo.

    Returns:
        Sent updates
    """
    return [call.args[0].update for call in cast("AsyncMock", halo.update).call_args_list]


async def wait_for_updates(halo: Halo, count: int) -> list[UpdateButton]:
    """Wait for a number of updates to have been sent to the Halo.

    Returns:
        Sent updates
    """
    await wait_until(lambda: len(sent_updates(halo)) >= count)
    return sent_updates(halo)


def test_demo_configuration() -> None:
    """Test that the demo configuration is valid, and has the oven timer as its default button."""
    configuration = demo_configuration()

    assert [page.title for page in configuration.configuration.pages] == ["Kitchen", "Living room"]
    assert len(get_all_buttons(configuration)) == len(set(map(str, (button.id_ for button in get_all_buttons(configuration)))))
    default_button = get_default_button(configuration)
    assert default_button is not None
    assert default_button.title == OVEN_TIMER_TITLE
    assert default_button.content == Text(OVEN_TIMER_START)

    # Every configuration gets new IDs
    assert demo_configuration().configuration.uuid_id != configuration.configuration.uuid_id


@pytest.mark.parametrize(
    argnames=("text", "seconds"),
    ids=("zero", "seconds", "minutes"),
    argvalues=[("00:00", 0), ("00:42", 42), ("01:35", 95)],
)
def test_format_and_parse_time(text: str, seconds: int) -> None:
    """Test converting between `mm:ss` and seconds."""
    assert parse_time(text) == seconds
    assert format_time(seconds) == text


async def test_wheel_event(halo: Halo) -> None:
    """Test that the wheel changes a button's value, clamped to the valid range."""
    demo = Demo(halo)
    light = get_button(halo, "Kitchen Light")
    initial_value = light.value
    assert initial_value is not None
    assert initial_value + 2 * WHEEL_STEP > MAX_VALUE

    await demo.on_wheel_event(WheelEvent(WheelEventValues.WHEEL_CLOCKWISE_FAST, id_=light.id_))
    await demo.on_wheel_event(WheelEvent(WheelEventValues.WHEEL_COUNTER_CLOCKWISE_NORMAL, id_=light.id_))

    assert [update.value for update in sent_updates(halo)] == [MAX_VALUE, MAX_VALUE - WHEEL_STEP]
    assert light.value == MAX_VALUE - WHEEL_STEP


async def test_wheel_event_ignored(halo: Halo) -> None:
    """Test that wheel events for buttons without a value, or unknown buttons, are ignored."""
    demo = Demo(halo)

    await demo.on_wheel_event(WheelEvent(WheelEventValues.WHEEL_CLOCKWISE_NORMAL, id_=get_button(halo, "Fire Place").id_))
    await demo.on_wheel_event(WheelEvent(WheelEventValues.WHEEL_CLOCKWISE_NORMAL, id_=uuid4()))

    assert sent_updates(halo) == []


async def test_button_event(halo: Halo) -> None:
    """Test that releasing a button toggles its state, and that other button events are ignored."""
    demo = Demo(halo)
    blinds = get_button(halo, "Blinds")

    await demo.on_button_event(ButtonEvent(ButtonEventState.PRESSED, id_=blinds.id_))
    await demo.on_button_event(ButtonEvent(ButtonEventState.RELEASED, id_=uuid4()))
    assert sent_updates(halo) == []

    await demo.on_button_event(ButtonEvent(ButtonEventState.RELEASED, id_=blinds.id_))
    assert blinds.state is ButtonState.INACTIVE

    await demo.on_button_event(ButtonEvent(ButtonEventState.RELEASED, id_=blinds.id_))
    assert blinds.state is ButtonState.ACTIVE

    assert [update.state for update in sent_updates(halo)] == [ButtonState.INACTIVE, ButtonState.ACTIVE]


async def test_oven_timer_button(halo: Halo) -> None:
    """Test that the oven timer button starts and pauses the countdown."""
    demo = Demo(halo)
    timer = get_button(halo, OVEN_TIMER_TITLE)
    released = ButtonEvent(ButtonEventState.RELEASED, id_=timer.id_)

    await demo.on_button_event(released)
    updates = await wait_for_updates(halo, 2)
    assert updates[0].state is ButtonState.ACTIVE
    assert updates[1].content == Text(OVEN_TIMER_START)

    await demo.on_button_event(released)
    assert timer.state is ButtonState.INACTIVE

    # Paused, so the countdown doesn't send any more updates than the state change
    await asyncio.sleep(0.1)
    assert len(sent_updates(halo)) == len(updates) + 1

    await demo.stop()


async def test_countdown(halo: Halo) -> None:
    """Test counting down to zero, which deactivates the button, and starting again."""
    timer = get_button(halo, OVEN_TIMER_TITLE)
    countdown = Countdown(halo, timer.uuid_id, "00:02")

    countdown.resume()
    assert countdown.running
    updates = await wait_for_updates(halo, 4)

    assert [update.content for update in updates[:3]] == [Text("00:02"), Text("00:01"), Text("00:00")]
    assert updates[3].state is ButtonState.INACTIVE
    assert timer.content == Text("00:00")
    assert not countdown.running

    # Starts over once finished
    countdown.resume()
    updates = await wait_for_updates(halo, 5)
    assert updates[4].content == Text("00:02")

    await countdown.stop()


async def test_countdown_pause_and_resume(halo: Halo) -> None:
    """Test pausing and resuming the countdown."""
    countdown = Countdown(halo, get_button(halo, OVEN_TIMER_TITLE).uuid_id, "00:03")

    countdown.resume()
    await wait_for_updates(halo, 1)
    countdown.pause()
    assert not countdown.running

    # Longer than the countdown interval
    await asyncio.sleep(0.1)
    assert len(sent_updates(halo)) == 1

    countdown.resume()
    updates = await wait_for_updates(halo, 5)
    assert [update.content for update in updates[:4]] == [Text("00:03"), Text("00:02"), Text("00:01"), Text("00:00")]

    await countdown.stop()


async def test_countdown_stop_before_start(halo: Halo) -> None:
    """Test that stopping a countdown that never started does nothing."""
    countdown = Countdown(halo, get_button(halo, OVEN_TIMER_TITLE).uuid_id, OVEN_TIMER_START)

    await countdown.stop()

    assert not countdown.running


@pytest.mark.parametrize(
    argnames=("state", "logged"),
    ids=("ok", "error"),
    argvalues=[(StatusEventState.OK, False), (StatusEventState.ERROR, True)],
)
def test_status_event(state: StatusEventState, logged: bool, caplog: pytest.LogCaptureFixture) -> None:
    """Test that errors reported by the Halo are logged."""
    Demo.on_status_event(StatusEvent(state, "Status message"))

    assert ("Status message" in caplog.text) is logged
