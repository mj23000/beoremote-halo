"""Models used for the Beoremote Halo client."""

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypedDict
from uuid import UUID, uuid1

from mashumaro import field_options
from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin

from beoremote_halo.const import (
    BUTTON_CONTENT_TEXT_MAX_LENGTH,
    BUTTON_CONTENT_TEXT_MIN_LENGTH,
    BUTTON_SUBTITLE_MAX_LENGTH,
    BUTTON_SUBTITLE_MIN_LENGTH,
    BUTTON_TITLE_MAX_LENGTH,
    BUTTON_TITLE_MIN_LENGTH,
    MAX_BUTTONS,
    MAX_PAGES,
    MAX_VALUE,
    MIN_BUTTONS,
    MIN_PAGES,
    MIN_VALUE,
    NOTIFICATION_SUBTITLE_MAX_LENGTH,
    NOTIFICATION_SUBTITLE_MAX_LINE_LENGTH,
    NOTIFICATION_SUBTITLE_MAX_LINES,
    NOTIFICATION_SUBTITLE_MIN_LENGTH,
    NOTIFICATION_SUBTITLE_MIN_LINE_LENGTH,
    NOTIFICATION_SUBTITLE_MIN_LINES,
    NOTIFICATION_TITLE_MAX_LENGTH,
    NOTIFICATION_TITLE_MIN_LENGTH,
    PAGE_TITLE_MAX_LENGTH,
    PAGE_TITLE_MIN_LENGTH,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


class _HaloMixin(DataClassJSONMixin):
    """Configuration for Beoremote Halo dataclasses."""

    class Config(BaseConfig):
        """Mashumaro config."""

        omit_none = True
        serialize_by_alias = True


@dataclass
class _HaloIdMixin:
    """Mixin for Beoremote Halo dataclasses that contain an ID."""

    # This is kw_only to ensure that it is placed at the end of constructor's of classes that inherit from this one
    id_: UUID = field(default_factory=uuid1, metadata=field_options(alias="id"), kw_only=True)


class UpdateTypes(StrEnum):
    """Values present in the `type` members of Update classes."""

    BUTTON = "button"
    DISPLAY_PAGE = "displaypage"
    NOTIFICATION = "notification"


class EventTypes(StrEnum):
    """Values present in the `type` members of Event classes."""

    BUTTON = "button"
    POWER = "power"
    STATUS = "status"
    SYSTEM = "system"
    WHEEL = "wheel"


class Icons(StrEnum):
    """Available icons for buttons.

    Each `Icon` has an 'active' and 'inactive' version, which is determined by a `Button`'s `ButtonState`.
    """

    ALARM = "alarm"
    ALTERNATIVE = "alternative"
    ARM_AWAY = "arm_away"
    ARM_STAY = "arm_stay"
    AUTO = "auto"
    BATH_TUB = "bath_tub"
    BLINDS = "blinds"
    BLISS = "bliss"
    BUTLER = "butler"
    CINEMA = "cinema"
    CLEAN = "clean"
    CLOCK = "clock"
    COFFEE = "coffee"
    COOL = "cool"
    CREATIVE = "creative"
    CURTAINS = "curtains"
    DINNER = "dinner"
    DISARM = "disarm"
    DOOR = "door"
    DOORLOCK = "doorlock"
    ENERGIZE = "energize"
    ENJOY = "enjoy"
    ENTERTAIN = "entertain"
    FAN = "fan"
    FIREPLACE = "fireplace"
    FORCED_ARM = "forced_arm"
    GAMING = "gaming"
    GARAGE = "garage"
    GATE = "gate"
    GOOD_MORNING = "good_morning"
    GOOD_NIGHT = "good_night"
    HEAT = "heat"
    HUMIDITY = "humidity"
    INDULGE = "indulge"
    LEAVING = "leaving"
    LIGHTS = "lights"
    LOCK = "lock"
    MEETING = "meeting"
    MOVIE = "movie"
    MUSIC = "music"
    NOTIFICATION = "notification"
    OFF = "off"
    PARTY = "party"
    POOL = "pool"
    PRIVACY = "privacy"
    PRODUCTIVE = "productive"
    READING = "reading"
    RELAX = "relax"
    REQUEST_CAR = "request_car"
    RGB_LIGHTS = "rgb_lights"
    ROMANTIC = "romantic"
    ROOF_WINDOW = "roof_window"
    ROOM_SERVICE = "room_service"
    SECURITY = "security"
    SHADES = "shades"
    SHOWER = "shower"
    SLEEP = "sleep"
    SMART_GLASS = "smart_glass"
    SPA = "spa"
    SPRINKLER = "sprinkler"
    TRAVEL = "travel"
    TURNTABLE = "turntable"
    UNLOCK = "unlock"
    VACATION = "vacation"
    WARNING = "warning"
    WATERFALL = "waterfall"
    WELCOME = "welcome"
    WINDOW = "window"
    WORK_OUT = "work_out"
    YOGA = "yoga"


@dataclass
class Icon(_HaloMixin):
    """Icon to be shown inside of a `Button`."""

    icon: Icons


@dataclass
class Text(_HaloMixin):
    """Text to be shown inside of a `Button`.

    Args:
        text: Limited to 0-6
    """

    text: str

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_text(self.text, BUTTON_CONTENT_TEXT_MIN_LENGTH, BUTTON_CONTENT_TEXT_MAX_LENGTH)


class ButtonState(StrEnum):
    """Adjust the appearance of an `Icon` present on a `Button`. Has no effect on `Text`."""

    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class Button(_HaloMixin, _HaloIdMixin):
    """An interact-able element that represents an action or physical device.

    Args:
        title: Limited to a length of 0-15
        content: Shown in the center of the `Button` on the Halo
        subtitle: Limited to a length of 0-15
        value: Limited to value of 0-100
        state: Overall state of the `Button`. Affects the `Icon` if configured
        default: `Button`s marked as default will be preselected when interacting with the Halo.
            Only a single Button can be default in a configuration
        id_: Unique identifier for the button. If no ID is provided, then one will be automatically generated

    """

    title: str
    content: Icon | Text
    subtitle: str | None = None
    value: int | None = None
    state: ButtonState | None = None
    default: bool | None = False

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_text(self.title, BUTTON_TITLE_MIN_LENGTH, BUTTON_TITLE_MAX_LENGTH)
        _validate_text(self.subtitle, BUTTON_SUBTITLE_MIN_LENGTH, BUTTON_SUBTITLE_MAX_LENGTH)
        _validate_button_value(self.value)


@dataclass
class Page(_HaloMixin, _HaloIdMixin):
    """Group of `Button` elements grouped with a title in the `Configuration`.

    Args:
        title: Limited to a length of  0-40
        buttons: Group of `Button` elements. Limited to a length of 1-8
        id_: Unique identifier for the button. If no ID is provided, then one will be automatically generated
    """

    title: str
    buttons: list[Button]

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_text(self.title, PAGE_TITLE_MIN_LENGTH, PAGE_TITLE_MAX_LENGTH)
        _validate_list(self.buttons, MIN_BUTTONS, MAX_BUTTONS)


@dataclass
class Configuration(_HaloMixin, _HaloIdMixin):
    """Main Configuration class.

    Args:
        pages: Group of `Page` elements. Limited to a length of 1-3
        version: Version of the API
        id_: Unique identifier for the button. If no ID is provided, then one will be automatically generated
    """

    pages: list[Page]
    version: str = VERSION

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_default_button(self.pages)
        _validate_list(self.pages, MIN_PAGES, MAX_PAGES)


@dataclass
class BaseConfiguration(_HaloMixin):
    """Root configuration class.

    Args:
        configuration: Main configuration class
    """

    configuration: Configuration


class ButtonEventState(StrEnum):
    """Available states for `ButtonEvent`."""

    PRESSED = "pressed"
    RELEASED = "released"


@dataclass
class ButtonEvent(_HaloMixin, _HaloIdMixin):
    """Button event received from the Halo."""

    state: ButtonEventState
    type_: Literal[EventTypes.BUTTON] = field(metadata=field_options(alias="type"), init=False)


class PowerEventState(StrEnum):
    """Available states for `PowerEvent`."""

    CHARGING = "charging"
    FULL = "full"
    LOW = "low"
    CRITICAL = "critical"
    FAULT = "fault"
    DISCHARGING = "discharging"


@dataclass
class PowerEvent(_HaloMixin):
    """Power event received from the Halo.

    Contains the battery capacity and the (new) power state.
    """

    capacity: int
    state: PowerEventState
    type_: Literal[EventTypes.POWER] = field(metadata=field_options(alias="type"), init=False)


class StatusEventState(StrEnum):
    """Available states for `StatusEvent`."""

    OK = "ok"
    ERROR = "error"


@dataclass
class StatusEvent(_HaloMixin):
    """Status event received from the Halo.

    Contains a message and state.

    Various status messages can be received, but some common are:

    Valid configuration:
        `message: 'configuration', state: 'ok'`

    Valid update:
        `message: 'update', state: 'ok'`

    New client replacing WebSocket connection:
        `message: 'Client connection replaced, previous: <ip_address>, now: <ip_address>', state: 'ok'`

    Invalid button id referenced while sending `UpdateButton`:
        `message: 'The button id was not found the the configuration: <id>, state: 'error'`

    Invalid page and button ids referenced while sending `UpdateDisplayPage`:
        `message: 'homeautomationsystem::message::Update|homeautomationsystem::schema::Update::UpdateProperty [No oneof found] {'page_id':'<page_id>', 'button_id':'<page_id>', 'type':'displaypage'}', state: 'error'`
    """  # noqa: E501

    state: StatusEventState
    message: str | None = None
    type_: Literal[EventTypes.STATUS] = field(metadata=field_options(alias="type"), init=False)


class SystemEventState(StrEnum):
    """Available states for `SystemEvent`."""

    ACTIVE = "active"
    STANDBY = "standby"
    SLEEP = "sleep"


@dataclass
class SystemEvent(_HaloMixin):
    """System event received from the Halo.

    Contains state describing state of the system.
    """

    state: SystemEventState
    type_: Literal[EventTypes.SYSTEM] = field(metadata=field_options(alias="type"), init=False)


@dataclass
class WheelEvent(_HaloMixin, _HaloIdMixin):
    """Wheel event received from the Halo.

    Contains id of button and momentum-affected counts value with value range -5..5.

    A `WheelEvent` is only sent when the 'wheel' is used on a `Button`.
    The direction of the wheel can be determined by the value of 'counts': positive value -> clockwise, negative value -> counter-clockwise.
    The momentum of the wheel can also be determined by the counts value: 1 -> slow clockwise movement, 5 -> very fast clockwise movement.
    """

    counts: Literal[-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
    type_: Literal[EventTypes.WHEEL] = field(metadata=field_options(alias="type"), init=False)


@dataclass
class Event(_HaloMixin):
    """Base Event class."""

    event: WheelEvent | SystemEvent | StatusEvent | PowerEvent | ButtonEvent


@dataclass
class UpdateButton(_HaloMixin, _HaloIdMixin):
    """Button update to be sent to the Halo.

    Sending this will update the defined attributes of a single `Button` in a configuration.

    Args:
        state: State to update
        value: Value to update
        title: Title to update
        subtitle: Subtitle to update
        content: Content to update
    """

    state: ButtonState | None = None
    value: int | None = None
    title: str | None = None
    subtitle: str | None = None
    content: Text | Icon | None = None
    type_: Literal[UpdateTypes.BUTTON] = field(default=UpdateTypes.BUTTON, metadata=field_options(alias="type"), init=False)

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_button_value(self.value)
        _validate_text(self.title, BUTTON_TITLE_MIN_LENGTH, BUTTON_TITLE_MAX_LENGTH)
        _validate_text(self.subtitle, BUTTON_SUBTITLE_MIN_LENGTH, BUTTON_SUBTITLE_MAX_LENGTH)


@dataclass
class UpdateDisplayPage(_HaloMixin):
    """Display a specific `Page` and `Button`.

    Sending this will make the Halo focus on a specified button on a page.

    Args:
        page_id: UUID of page to display
        button_id: UUID of button in page to display
    """

    page_id: UUID = field(metadata=field_options(alias="pageid"))
    button_id: UUID | None = field(default=None, metadata=field_options(alias="buttonid"))
    type_: Literal[UpdateTypes.DISPLAY_PAGE] = field(default=UpdateTypes.DISPLAY_PAGE, metadata=field_options(alias="type"), init=False)


@dataclass
class UpdateNotification(_HaloMixin, _HaloIdMixin):
    """Display a notification message.

    Sending this will make the Halo show a notification box with the defined title and message.
    """

    title: str | None = None
    message: str | None = field(default=None, metadata=field_options(alias="subtitle"))
    type_: Literal[UpdateTypes.NOTIFICATION] = field(default=UpdateTypes.NOTIFICATION, metadata=field_options(alias="type"), init=False)

    def validate(self) -> None:
        """Ensure provided values are valid."""
        _validate_text(self.title, NOTIFICATION_TITLE_MIN_LENGTH, NOTIFICATION_TITLE_MAX_LENGTH)
        _validate_notification_message(self.message)


@dataclass
class Update(_HaloMixin):
    """An update to be sent to the Beoremote Halo."""

    update: UpdateButton | UpdateDisplayPage | UpdateNotification


class BaseWebSocketResponse(TypedDict):
    """Base class for serialized WebSocket events."""

    event: dict


EventType = WheelEvent | SystemEvent | StatusEvent | PowerEvent | ButtonEvent

# Mashumaro does not support validation. Validate manually through the `validate` methods that use these helper functions


def _validate_text(text: str | None, minimum: int, maximum: int) -> None:
    """Check if provided Button text length is within accepted limits.

    Raises:
        ValueError: Text length is not within provided limits
    """
    if text is not None and (length := len(text)) and (length < minimum or length > maximum):
        msg = f"Invalid Button text length: {length}. Button text length must be in the range: {minimum}-{maximum}"
        raise ValueError(msg)


def _validate_list(list_: list, minimum: int, maximum: int) -> None:
    """Check if list length is within accepted limits.

    Raises:
        ValueError: List length is not within provided limits
    """
    if (length := len(list_)) and (length < minimum or length > maximum):
        msg = f"Invalid list length: {length}. List length must be in the range: {minimum}-{maximum}"
        raise ValueError(msg)


def _validate_button_value(value: int | None) -> None:
    """Check if provided Button value is within accepted limits.

    Raises:
        ValueError: Value is not within 0-100
    """
    if value is not None and (value < MIN_VALUE or value > MAX_VALUE):
        msg = f"Invalid button value: {value}. Button value must be in the range: {MIN_VALUE}-{MAX_VALUE}"
        raise ValueError(msg)


def _validate_default_button(pages: list[Page]) -> None:
    """Check if provided pages only contain at most 1 default button.

    Raises:
        ValueError: More than 1 default button
    """
    default_buttons: list[Button] = []
    for page in pages:
        default_buttons.extend(button for button in page.buttons if button.default is True)

    if len(default_buttons) > 1:
        msg = f"Only a single Button can be default per configuration. Default buttons found {default_buttons}"
        raise ValueError(msg)


def _validate_notification_message(message: str | None) -> None:
    """Check if notification has valid formatting.

    Raises:
        ValueError: Invalid notification formatting
    """
    if message is not None:
        try:
            _validate_text(message, NOTIFICATION_SUBTITLE_MIN_LENGTH, NOTIFICATION_SUBTITLE_MAX_LENGTH)
            _validate_list(message.splitlines(), NOTIFICATION_SUBTITLE_MIN_LINES, NOTIFICATION_SUBTITLE_MAX_LINES)
            for line in message.splitlines():
                _validate_text(line, NOTIFICATION_SUBTITLE_MIN_LINE_LENGTH, NOTIFICATION_SUBTITLE_MAX_LINE_LENGTH)
        except ValueError as error:
            msg = "Invalid notification formatting"
            raise ValueError(msg) from error
