"""Test model validation from `beoremote_halo/models.py`."""

import re
from contextlib import AbstractContextManager
from contextlib import nullcontext as does_not_raise
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from beoremote_halo import (
    BaseConfiguration,
    Button,
    ButtonState,
    Configuration,
    Event,
    Icon,
    Icons,
    Page,
    Update,
    UpdateButton,
    UpdateDisplayPage,
    UpdateNotification,
)
from tests.const import CONFIGURATION

# Trust that pydantic validation works as intended. Only test Mixin methods and custom validation
# Don't include pydantic link in the "match" parameter's value, as it contains the used version of pydantic


@pytest.mark.parametrize(
    argnames=("buttons", "expected_error"),
    ids=(
        "no_default",
        "one_default",
        "two_default",
    ),
    argvalues=[
        (
            [
                Button("test", Icon(Icons.ALARM)),
                Button("test 2", Icon(Icons.ALARM)),
            ],
            does_not_raise(),
        ),
        (
            [
                Button("test", Icon(Icons.ALARM)),
                Button("test 2", Icon(Icons.ALARM), default=True),
            ],
            does_not_raise(),
        ),
        (
            [
                Button("test", Icon(Icons.ALARM), default=True, id_=UUID("09087e8d-cb69-4d96-9faf-56cbbca893a2")),
                Button("test 2", Icon(Icons.ALARM), default=True, id_=UUID("b719446d-2233-4642-92e6-2ca2be7103e1")),
            ],
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for Page\n1\n  Value error, Only a single Button can be default per configuration. Default buttons found [Button(id_=UUID('09087e8d-cb69-4d96-9faf-56cbbca893a2'), title='test', content=Icon(icon=<Icons.ALARM: 'alarm'>), subtitle=None, value=None, state=None, default=True), Button(id_=UUID('b719446d-2233-4642-92e6-2ca2be7103e1'), title='test 2', content=Icon(icon=<Icons.ALARM: 'alarm'>), subtitle=None, value=None, state=None, default=True)] [type=value_error, input_value=[Button(id_=UUID('09087e8...ate=None, default=True)], input_type=list]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
    ],
)
def test_page(buttons: list[Button], expected_error: AbstractContextManager) -> None:
    """Test `Page` model validation."""
    with expected_error:
        Page("Test", buttons)


@pytest.mark.parametrize(
    argnames=("pages", "expected_error"),
    ids=(
        "no_default",
        "one_default",
        "two_default",
    ),
    argvalues=[
        (
            [
                Page("Test", [Button("test", Icon(Icons.ALARM))]),
                Page("Test 2", [Button("test", Icon(Icons.ALARM))]),
            ],
            does_not_raise(),
        ),
        (
            [
                Page("Test", [Button("test", Icon(Icons.ALARM))]),
                Page("Test 2", [Button("test", Icon(Icons.ALARM), default=True)]),
            ],
            does_not_raise(),
        ),
        (
            [
                Page(
                    "Test",
                    [Button("test", Icon(Icons.ALARM), default=True, id_=UUID("6201484f-281a-4d0a-ace8-deb924014c41"))],
                    id_=UUID("d5c6e132-5d88-4a3a-b6f0-4838ce84dc57"),
                ),
                Page(
                    "Test 2",
                    [Button("test", Icon(Icons.ALARM), default=True, id_=UUID("f2d02002-c298-4575-9a7f-41e2595aec11"))],
                    id_=UUID("7f68f7ff-7b97-4a52-91b3-9e47f85a1189"),
                ),
            ],
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for Configuration\n0\n  Value error, Only a single Button can be default per configuration. Default buttons found [Button(id_=UUID('6201484f-281a-4d0a-ace8-deb924014c41'), title='test', content=Icon(icon=<Icons.ALARM: 'alarm'>), subtitle=None, value=None, state=None, default=True), Button(id_=UUID('f2d02002-c298-4575-9a7f-41e2595aec11'), title='test', content=Icon(icon=<Icons.ALARM: 'alarm'>), subtitle=None, value=None, state=None, default=True)] [type=value_error, input_value=[Page(id_=UUID('d5c6e132-...e=None, default=True)])], input_type=list]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
    ],
)
def test_configuration(pages: list[Page], expected_error: AbstractContextManager) -> None:
    """Test `Configuration` model validation."""
    with expected_error:
        Configuration(pages)


@pytest.mark.parametrize(
    argnames=("message", "expected_error"),
    ids=(
        "valid",
        "no_message",
        "too_long",
        "too_many_lines",
        "too_long_line",
    ),
    argvalues=[
        (
            """This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
""",
            does_not_raise(),
        ),
        (None, does_not_raise()),
        (
            "This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. This is a placeholder message for testing purposes. ",  # ruff: ignore[line-too-long]
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for UpdateNotification\n1\n  Value error, Defined message contains too many characters. Valid range: 0..350 [type=value_error, input_value='This is a placeholder me... for testing purposes. ', input_type=str]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
        (
            """This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
This is a placeholder message for testing purposes.
""",
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for UpdateNotification\n1\n  Value error, Defined message contains too many lines: 6. Valid range: 0..5 [type=value_error, input_value='This is a placeholder me...for testing purposes.\\n', input_type=str]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
        (
            "This is a placeholder message for testing purposes. This one is longer.",
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for UpdateNotification\n1\n  Value error, Defined message contains a line with too many characters: 71. Valid range: 0..60 [type=value_error, input_value='This is a placeholder me...es. This one is longer.', input_type=str]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
    ],
)
def test_update_notification(message: str | None, expected_error: AbstractContextManager) -> None:
    """Test `UpdateNotification` model validation."""
    with expected_error:
        UpdateNotification("Test", message)


@pytest.mark.parametrize(
    argnames=("id_", "expected_error"),
    ids=(
        "valid_str",
        "valid_uuid",
        "invalid",
    ),
    argvalues=[
        (
            "8e87d851-70e1-41ab-9b5e-50a0733d348a",
            does_not_raise(),
        ),
        (
            UUID("d5a0a28c-cf53-4c0e-b4f8-005fb2d3b97a"),
            does_not_raise(),
        ),
        (
            "invalid_uuid",
            pytest.raises(
                ValidationError,
                match=re.escape(
                    "1 validation error for Button\nid_\n  Value error, Malformed UUID str: invalid_uuid [type=value_error, input_value='invalid_uuid', input_type=str]\n",  # ruff: ignore[line-too-long]
                ),
            ),
        ),
    ],
)
def test_id_mixin_id(id_: UUID | str, expected_error: AbstractContextManager) -> None:
    """Test `id_` validation from `_HaloIdMixin`."""
    with expected_error:
        Button("Test", Icon(Icons.ALARM), id_=id_)


def test_id_mixin_uuid_id() -> None:
    """Test `uuid_id` from `_HaloIdMixin`."""
    # str initialized button IDs are automatically converted to UUID
    button = Button("Test", Icon(Icons.ALARM), id_="7c9a7ba2-bc01-4fc9-a410-71785dc26846")
    assert button.uuid_id == UUID("7c9a7ba2-bc01-4fc9-a410-71785dc26846")


def test_id_mixin_str_id() -> None:
    """Test `str_id` from `_HaloIdMixin`."""
    button = Button("Test", Icon(Icons.ALARM), id_=UUID("87b4b6b8-9496-410a-9102-ba86a2bf3f7c"))
    assert button.str_id == "87b4b6b8-9496-410a-9102-ba86a2bf3f7c"


def test_mixin_to_json() -> None:
    """Test `to_json` from `_HaloConfigMixin`."""
    assert (
        CONFIGURATION.to_json()
        == '{"configuration":{"id":"1b8decea-af8c-4837-9fbc-4261644492df","pages":[{"id":"8b836136-b71d-4611-b7f0-d136e68ceb0f","title":"Dining room","buttons":[{"id":"3c494ca3-5bbb-420e-babc-0752838b457d","title":"Chandelier","content":{"icon":"lights"},"subtitle":"20%","value":20,"state":"active","default":true}]},{"id":"11aa7fbf-853d-40e7-8f6c-7625bfec8736","title":"Garage","buttons":[{"id":"eb8996b6-0b00-4634-a844-35fd3b0ce3fe","title":"Door","content":{"icon":"door"},"subtitle":"Opening","value":60,"state":"active","default":false},{"id":"d60e0927-6863-4eb1-a073-f4d2d45899e8","title":"Light","content":{"text":"Off"},"subtitle":"0%","state":"inactive","default":false}]}],"version":"1.0.2"}}'  # ruff: ignore[line-too-long]
    )


def test_mixin_from_json() -> None:
    """Test `from_json` from `_HaloConfigMixin`."""
    assert BaseConfiguration.from_json(CONFIGURATION.to_json()) == CONFIGURATION


def test_mixin_to_dict() -> None:
    """Test `to_dict` from `_HaloConfigMixin`."""
    assert CONFIGURATION.to_dict() == {
        "configuration": {
            "id": "1b8decea-af8c-4837-9fbc-4261644492df",
            "pages": [
                {
                    "buttons": [
                        {
                            "content": {"icon": "lights"},
                            "default": True,
                            "id": "3c494ca3-5bbb-420e-babc-0752838b457d",
                            "state": "active",
                            "subtitle": "20%",
                            "title": "Chandelier",
                            "value": 20,
                        },
                    ],
                    "id": "8b836136-b71d-4611-b7f0-d136e68ceb0f",
                    "title": "Dining room",
                },
                {
                    "buttons": [
                        {
                            "content": {"icon": "door"},
                            "default": False,
                            "id": "eb8996b6-0b00-4634-a844-35fd3b0ce3fe",
                            "state": "active",
                            "subtitle": "Opening",
                            "title": "Door",
                            "value": 60,
                        },
                        {
                            "content": {"text": "Off"},
                            "default": False,
                            "id": "d60e0927-6863-4eb1-a073-f4d2d45899e8",
                            "state": "inactive",
                            "subtitle": "0%",
                            "title": "Light",
                        },
                    ],
                    "id": "11aa7fbf-853d-40e7-8f6c-7625bfec8736",
                    "title": "Garage",
                },
            ],
            "version": "1.0.2",
        },
    }


def test_mixin_from_dict() -> None:
    """Test `from_dict` from `_HaloConfigMixin`."""
    assert BaseConfiguration.from_dict(CONFIGURATION.to_dict()) == CONFIGURATION


def test_icons_match_documentation() -> None:
    """Test that every documented icon is available as an `Icons` value, and vice versa."""
    documented_icons = {path.name for path in (Path(__file__).parent.parent / "docs" / "icons").iterdir()}

    assert {icon.value for icon in Icons} == documented_icons


EVENT_FIELDS = {
    "button": {"id": "3c494ca3-5bbb-420e-babc-0752838b457d", "state": "pressed"},
    "power": {"capacity": 50, "state": "low"},
    "status": {"state": "ok", "message": "update"},
    "system": {"state": "active"},
    "wheel": {"id": "3c494ca3-5bbb-420e-babc-0752838b457d", "counts": 1},
}


@pytest.mark.parametrize("event_type", EVENT_FIELDS)
def test_event_type_selects_model(event_type: str) -> None:
    """Test that an event is deserialized as the model of its type, and not as another model its fields happen to match."""
    assert Event.from_dict({"event": {"type": event_type, **EVENT_FIELDS[event_type]}}).event.type_ == event_type

    for other_type, fields in EVENT_FIELDS.items():
        if other_type != event_type:
            with pytest.raises(ValidationError):
                Event.from_dict({"event": {"type": event_type, **fields}})


@pytest.mark.parametrize(
    argnames="event",
    ids=("missing_type", "unknown_type"),
    argvalues=[{"state": "active"}, {"type": "unknown", "state": "active"}],
)
def test_event_without_valid_type(event: dict[str, str]) -> None:
    """Test that an event without a known type is rejected."""
    with pytest.raises(ValidationError, match="event"):
        Event.from_dict({"event": event})


@pytest.mark.parametrize(
    argnames="update",
    ids=("button", "display_page", "notification"),
    argvalues=[
        Update(UpdateButton(state=ButtonState.ACTIVE, id_=UUID(int=1))),
        Update(UpdateDisplayPage(page_id=UUID(int=2), button_id=UUID(int=3))),
        Update(UpdateNotification("Title", "Message", id_=UUID(int=4))),
    ],
)
def test_update_round_trip(update: Update) -> None:
    """Test that each type of update is deserialized as itself, including fields serialized with another name."""
    assert Update.from_json(update.to_json()) == update
