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
    MAX_BUTTONS,
    MAX_PAGES,
    MAX_VALUE,
    MIN_BUTTONS,
    MIN_PAGES,
    MIN_VALUE,
    NOTIFICATION_SUBTITLE_MAX_LENGTH,
    NOTIFICATION_SUBTITLE_MAX_LINE_LENGTH,
    NOTIFICATION_SUBTITLE_MAX_LINES,
    PAGE_TITLE_MAX_LENGTH,
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

    # This is kw_only to ensure that it is placed at the end of constructor's of classes
    # that inherit from this one. This ensures
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

    `text` should be limited to 6 characters.
    """

    text: str


class ButtonState(StrEnum):
    """Adjust the appearance of an `Icon` present on a `Button`. Has no effect on `Text`."""

    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class Button(_HaloMixin, _HaloIdMixin):
    """An interact-able element that represents an action or physical device.

    Contains a title, content (either an icon or text), subtitle, value, state and if it is the default.
    `Button`s marked as default will be preselected when interacting with the Halo.
    Only a single Button can be default in a configuration.
    `title` and `subtitle` should be limited to 15 characters.

    If no ID is provided, then one will be automatically generated.
    Ensures that the value is in the range 0-100.
    """

    title: str
    content: Icon | Text
    subtitle: str | None = None
    value: int | None = None
    state: ButtonState | None = None
    default: bool | None = False

    def __post_init__(self) -> None:
        """Ensure value is in a valid range.

        Raises:
            ValueError: Invalid button value
        """
        if self.value is not None and (self.value < MIN_VALUE or self.value > MAX_VALUE):
            msg = f"Invalid button value: {self.value}. Button value must be in the range: {MIN_VALUE}-{MAX_VALUE}"
            raise ValueError(msg)


@dataclass
class Page(_HaloMixin, _HaloIdMixin):
    """Group of `Button` elements grouped with a title in the `Configuration`.

    Contains a title, a list of buttons and an id.
    `title` should be limited to 40 characters.

    If no ID is provided, then one will be automatically generated.
    Ensures that at 1-8 buttons are in a page.
    """

    title: str
    buttons: list[Button]

    def __post_init__(self) -> None:
        """Ensure page is valid.

        Raises:
            ValueError: Invalid number of buttons
        """
        # Ensure that there are  0-8 buttons.
        number_of_buttons = len(self.buttons)
        if number_of_buttons > MAX_BUTTONS:
            msg = f"Invalid number of buttons: {number_of_buttons}. Only {MIN_BUTTONS}-{MAX_BUTTONS} buttons are allowed in a page."
            raise ValueError(msg)


@dataclass
class Configuration(_HaloMixin, _HaloIdMixin):
    """Main Configuration class.

    Contains a list of pages, the version of the API client and an ID.

    If no ID is provided, then one will be automatically generated.
    Ensures that at most one `Button` is marked default.
    Ensures that at 1-3 pages are in a configuration.
    """

    pages: list[Page]
    version: str = VERSION

    def __post_init__(self) -> None:
        """Ensure configuration is valid.

        Raises:
            ValueError: Multiple default buttons defined or invalid number of pages
        """
        # Ensure that at most one Button is marked as default.
        default_buttons: list[Button] = []
        for page in self.pages:
            default_buttons.extend(button for button in page.buttons if button.default is True)

        if len(default_buttons) > 1:
            msg = f"Only a single Button can be default per configuration. Default buttons found {default_buttons}"
            raise ValueError(msg)

        # Ensure that there are 0-3 pages.
        number_of_pages = len(self.pages)
        if number_of_pages < MIN_PAGES or number_of_pages > MAX_PAGES:
            msg = f"Invalid number of pages: {number_of_pages}. Only {MIN_PAGES}-{MAX_PAGES} pages are allowed per configuration."
            raise ValueError(msg)


@dataclass
class BaseConfiguration(_HaloMixin):
    """Root configuration class.

    Contains the main configuration class.
    """

    configuration: Configuration


class ButtonEventState(StrEnum):
    """Available states for `ButtonEvent`."""

    PRESSED = "pressed"
    RELEASED = "released"


@dataclass
class ButtonEvent(_HaloMixin, _HaloIdMixin):
    """Button event received from the Halo.

    Contains the ID and the (new) state of the button.
    """

    state: ButtonEventState
    type_: Literal[EventTypes.BUTTON] = field(default=EventTypes.BUTTON, metadata=field_options(alias="type"))


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
    type_: Literal[EventTypes.POWER] = field(default=EventTypes.POWER, metadata=field_options(alias="type"))


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
    type_: Literal[EventTypes.STATUS] = field(default=EventTypes.STATUS, metadata=field_options(alias="type"))


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
    type_: Literal[EventTypes.SYSTEM] = field(default=EventTypes.SYSTEM, metadata=field_options(alias="type"))


@dataclass
class WheelEvent(_HaloMixin, _HaloIdMixin):
    """Wheel event received from the Halo.

    Contains id of button and momentum-affected counts value with value range -5..5.

    A `WheelEvent` is only sent when the 'wheel' is used on a `Button`.
    The direction of the wheel can be determined by the value of 'counts': positive value -> clockwise, negative value -> counter-clockwise.
    The momentum of the wheel can also be determined by the counts value: 1 -> slow clockwise movement, 5 -> very fast clockwise movement.
    """

    counts: Literal[-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
    type_: Literal[EventTypes.WHEEL] = field(default=EventTypes.WHEEL, metadata=field_options(alias="type"))


@dataclass
class Event(_HaloMixin):
    """Base Event class."""

    event: WheelEvent | SystemEvent | StatusEvent | PowerEvent | ButtonEvent


@dataclass
class UpdateButton(_HaloMixin, _HaloIdMixin):
    """Button update to be sent to the Halo.

    Contains all defined button attributes

    Sending this will update the defined attributes of a single `Button` in a configuration.
    """

    state: ButtonState | None = None
    value: int | None = None
    title: str | None = None
    subtitle: str | None = None
    content: Text | Icon | None = None
    type_: Literal[UpdateTypes.BUTTON] = field(default=UpdateTypes.BUTTON, metadata=field_options(alias="type"))

    def __post_init__(self) -> None:
        """Ensure value is in a valid range.

        Raises:
            ValueError: Invalid button value
        """
        if self.value is not None and (self.value < MIN_VALUE or self.value > MAX_VALUE):
            msg = f"Invalid button value: {self.value}. Button value must be in the range: {MIN_VALUE}-{MAX_VALUE}"
            raise ValueError(msg)


@dataclass
class UpdateDisplayPage(_HaloMixin):
    """Display a specific `Page` and `Button`.

    Contains page and button id.

    Sending this will make the Halo focus on a specified button on a page.
    """

    page_id: str = field(metadata=field_options(alias="pageid"))
    button_id: str | None = field(default=None, metadata=field_options(alias="buttonid"))
    type_: Literal[UpdateTypes.DISPLAY_PAGE] = field(default=UpdateTypes.DISPLAY_PAGE, metadata=field_options(alias="type"))


@dataclass
class UpdateNotification(_HaloMixin, _HaloIdMixin):
    """Display a notification message.

    Sending this will make the Halo show a notification box with the defined title and message.
    """

    title: str | None = None
    message: str | None = field(default=None, metadata=field_options(alias="subtitle"))
    type_: Literal[UpdateTypes.NOTIFICATION] = field(default=UpdateTypes.NOTIFICATION, metadata=field_options(alias="type"))

    def __post_init__(self) -> None:
        """Warn if notification title and message can't be displayed properly."""
        if self.title and len(self.title) > PAGE_TITLE_MAX_LENGTH:
            _LOGGER.warning(
                "The provided title has a length of %s, which is more than the recommended length of %s.",
                len(self.title),
                PAGE_TITLE_MAX_LENGTH,
            )

        if self.message is None:
            return

        if len(self.message) > NOTIFICATION_SUBTITLE_MAX_LENGTH:
            _LOGGER.warning(
                "The provided message has %s characters, which is more that the maximum recommended number of lines of %s.",
                len(self.message),
                NOTIFICATION_SUBTITLE_MAX_LENGTH,
            )

        if len(self.message.splitlines()) > NOTIFICATION_SUBTITLE_MAX_LINES:
            _LOGGER.warning(
                "The provided message has %s lines, which is more that the maximum recommended number of lines of %s.",
                len(self.message.splitlines()),
                NOTIFICATION_SUBTITLE_MAX_LINES,
            )

        for line in self.message.splitlines():
            if len(line) > NOTIFICATION_SUBTITLE_MAX_LINE_LENGTH:
                _LOGGER.warning(
                    "A provided line (%s) in the subtitle has a length of %s, which is more than the recommended length of %s.",
                    line,
                    len(line),
                    NOTIFICATION_SUBTITLE_MAX_LINE_LENGTH,
                )


@dataclass
class Update(_HaloMixin):
    """An update to be sent to the Beoremote Halo."""

    update: UpdateButton | UpdateDisplayPage | UpdateNotification


class BaseWebSocketResponse(TypedDict):
    """Base class for serialized WebSocket events."""

    event: dict


EventType = WheelEvent | SystemEvent | StatusEvent | PowerEvent | ButtonEvent
