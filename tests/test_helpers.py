"""Test helper functions for manipulating and getting attributes from Configuration values located in `beoremote_halo/helpers.py`."""

import copy
import re
from contextlib import AbstractContextManager
from contextlib import nullcontext as does_not_raise
from uuid import UUID

import pytest

from beoremote_halo import (
    MAX_VALUE,
    MIN_VALUE,
    BaseConfiguration,
    Button,
    ButtonState,
    Configuration,
    Icon,
    Icons,
    Page,
    Text,
    clear_default_button,
    delete_button,
    delete_page,
    get_all_buttons,
    get_button_from_id,
    get_button_indices,
    get_default_button,
    get_page_from_id,
    get_page_index,
    update_button,
    update_page,
)
from tests.const import (
    CHANDELIER_BUTTON,
    CONFIGURATION,
    DINING_ROOM_PAGE,
    DOOR_BUTTON,
    GARAGE_PAGE,
    LIGHT_BUTTON,
    UNUSED_BUTTON,
    UNUSED_PAGE,
)


@pytest.fixture
def configuration() -> BaseConfiguration:
    """Example configuration for testing.

    Returns:
        Example config
    """
    return copy.deepcopy(CONFIGURATION)


# Test configuration getters


@pytest.mark.parametrize(
    argnames=("button_id", "expected_error", "expected_result"),
    ids=(
        "valid_id",
        "invalid_id",
        "other_valid_id",
    ),
    argvalues=[
        (CHANDELIER_BUTTON.id_, does_not_raise(), (0, 0)),
        (UNUSED_PAGE.id_, pytest.raises(ValueError, match=f"Unable to get indices for Button with ID: {UNUSED_PAGE.id_}"), (-1, -1)),
        (LIGHT_BUTTON.id_, does_not_raise(), (1, 1)),
    ],
)
def test_get_button_indices(
    configuration: BaseConfiguration,
    button_id: UUID,
    expected_error: AbstractContextManager,
    expected_result: tuple[int, int],
) -> None:
    """Test `get_button_indices`."""
    with expected_error:
        assert get_button_indices(configuration, button_id) == expected_result


@pytest.mark.parametrize(
    argnames=("page_id", "expected_error", "expected_result"),
    ids=(
        "valid_id",
        "invalid_id",
        "other_valid_id",
    ),
    argvalues=[
        (DINING_ROOM_PAGE.id_, does_not_raise(), 0),
        (UNUSED_PAGE.id_, pytest.raises(ValueError, match=f"Unable to get index for Page with ID: {UNUSED_PAGE.id_}"), -1),
        (GARAGE_PAGE.id_, does_not_raise(), 1),
    ],
)
def test_get_page_index(
    configuration: BaseConfiguration,
    page_id: UUID,
    expected_error: AbstractContextManager,
    expected_result: int,
) -> None:
    """Test `get_page_index`."""
    with expected_error:
        assert get_page_index(configuration, page_id) == expected_result


@pytest.mark.parametrize(
    argnames=("page_id", "expected_error", "expected_result"),
    ids=(
        "valid_id",
        "invalid_id",
        "other_valid_id",
    ),
    argvalues=[
        (DINING_ROOM_PAGE.id_, does_not_raise(), DINING_ROOM_PAGE),
        (UNUSED_PAGE.id_, pytest.raises(ValueError, match=f"Unable to get Page with ID: {UNUSED_PAGE.id_}"), UNUSED_PAGE),
        (GARAGE_PAGE.id_, does_not_raise(), GARAGE_PAGE),
    ],
)
def test_get_page_from_id(
    configuration: BaseConfiguration,
    page_id: UUID,
    expected_error: AbstractContextManager,
    expected_result: Page,
) -> None:
    """Test `get_page_from_id`."""
    with expected_error:
        assert get_page_from_id(configuration, page_id) == expected_result


@pytest.mark.parametrize(
    argnames=("button_id", "expected_error", "expected_result"),
    ids=(
        "valid_id",
        "invalid_id",
        "other_valid_id",
    ),
    argvalues=[
        (CHANDELIER_BUTTON.id_, does_not_raise(), CHANDELIER_BUTTON),
        (UNUSED_BUTTON.id_, pytest.raises(ValueError, match=f"Unable to get Button with ID: {UNUSED_BUTTON.id_}"), UNUSED_BUTTON),
        (LIGHT_BUTTON.id_, does_not_raise(), GARAGE_PAGE.buttons[1]),
    ],
)
def test_get_button_from_id(
    configuration: BaseConfiguration,
    button_id: UUID,
    expected_error: AbstractContextManager,
    expected_result: Button,
) -> None:
    """Test `get_button_from_id`."""
    with expected_error:
        assert get_button_from_id(configuration, button_id) == expected_result


@pytest.mark.parametrize(
    argnames=("test_configuration", "expected_result"),
    ids=(
        "present",
        "not_present",
    ),
    argvalues=[
        (CONFIGURATION, CHANDELIER_BUTTON),
        (BaseConfiguration(Configuration([GARAGE_PAGE])), None),
    ],
)
def test_get_default_button(test_configuration: BaseConfiguration, expected_result: Button) -> None:
    """Test `get_default_button`."""
    assert get_default_button(test_configuration) == expected_result


@pytest.mark.parametrize(
    argnames=("test_configuration", "expected_result"),
    ids=(
        "present",
        "not_present",
    ),
    argvalues=[
        (CONFIGURATION, [CHANDELIER_BUTTON, DOOR_BUTTON, LIGHT_BUTTON]),
        (BaseConfiguration(Configuration([Page("unused", [])])), []),
    ],
)
def test_get_all_buttons(test_configuration: BaseConfiguration, expected_result: Button) -> None:
    """Test `get_all_buttons`."""
    assert get_all_buttons(test_configuration) == expected_result


# Test configuration Setters
def test_clear_default_button(configuration: BaseConfiguration) -> None:
    """Test `clear_default_button`."""
    # Clear existing default button
    assert configuration.configuration.pages[0].buttons[0].default
    clear_default_button(configuration)
    assert not configuration.configuration.pages[0].buttons[0].default
    # Try clearing again
    clear_default_button(configuration)
    assert not configuration.configuration.pages[0].buttons[0].default


def test_update_button(configuration: BaseConfiguration) -> None:
    """Test `update_button`."""
    assert configuration.configuration.pages[0].buttons[0] == CHANDELIER_BUTTON
    # Update all available attributes with valid values
    new_values = Button("New title", Text("New"), "New subtitle", 33, ButtonState.INACTIVE, default=False)
    update_button(
        configuration,
        CHANDELIER_BUTTON.uuid_id,
        new_values.title,
        new_values.content,
        new_values.subtitle,
        new_values.value,
        new_values.state,
        new_values.default,
    )
    # Check new values
    assert configuration.configuration.pages[0].buttons[0] != CHANDELIER_BUTTON
    assert configuration.configuration.pages[0].buttons[0].title == new_values.title
    assert configuration.configuration.pages[0].buttons[0].content == new_values.content
    assert configuration.configuration.pages[0].buttons[0].subtitle == new_values.subtitle
    assert configuration.configuration.pages[0].buttons[0].value == new_values.value
    assert configuration.configuration.pages[0].buttons[0].state == new_values.state
    assert configuration.configuration.pages[0].buttons[0].default == new_values.default


@pytest.mark.parametrize(
    argnames=("value", "expected_error", "expected_result"),
    ids=(
        "too_low",
        "min_value",
        "max_value",
        "too_high",
    ),
    argvalues=[
        (-1, pytest.raises(ValueError, match=f"Invalid button value: -1. Button value must be in the range: {MIN_VALUE}-{MAX_VALUE}"), 0),
        (0, does_not_raise(), 0),
        (100, does_not_raise(), 100),
        (101, pytest.raises(ValueError, match=f"Invalid button value: 101. Button value must be in the range: {MIN_VALUE}-{MAX_VALUE}"), 0),
    ],
)
def test_update_button_value(
    configuration: BaseConfiguration,
    value: int,
    expected_error: AbstractContextManager,
    expected_result: int,
) -> None:
    """Test `update_button` with various values."""
    with expected_error:
        update_button(configuration, CHANDELIER_BUTTON.uuid_id, value=value)
        assert configuration.configuration.pages[0].buttons[0].value == expected_result


@pytest.mark.parametrize(
    argnames=("button_id", "default", "expected_error"),
    ids=(
        "same_button",
        "two_default_button",
        "no_default",
        "no_change",
    ),
    argvalues=[
        (CHANDELIER_BUTTON.id_, True, does_not_raise()),
        (
            DOOR_BUTTON.id_,
            True,
            pytest.raises(
                ValueError,
                match=re.escape(
                    f"Default button already defined: {CHANDELIER_BUTTON}. Clear existing default button before setting new one",
                ),
            ),
        ),
        (CHANDELIER_BUTTON.id_, False, does_not_raise()),
        (DOOR_BUTTON.id_, False, does_not_raise()),
    ],
)
def test_update_button_default(
    configuration: BaseConfiguration,
    button_id: UUID,
    default: bool,
    expected_error: AbstractContextManager,
) -> None:
    """Test `update_button` with various default button settings."""
    with expected_error:
        update_button(configuration, button_id, default=default)
        assert get_button_from_id(configuration, button_id).default == default


def test_update_page(configuration: BaseConfiguration) -> None:
    """Test `update_page`."""
    # Update all available attributes with valid values
    new_values = Page("New title", [Button("New button", Icon(Icons.BATH_TUB))])
    update_page(configuration, DINING_ROOM_PAGE.uuid_id, new_values.title, new_values.buttons)
    # Check new values
    assert configuration.configuration.pages[0] != DINING_ROOM_PAGE
    assert configuration.configuration.pages[0].title == new_values.title
    assert configuration.configuration.pages[0].buttons == new_values.buttons


@pytest.mark.parametrize(
    argnames=("button_id", "expected_error"),
    ids=(
        "valid",
        "not_valid",
    ),
    argvalues=[
        (UNUSED_BUTTON.id_, pytest.raises(ValueError, match=re.escape(f"Unable to get indices for Button with ID: {UNUSED_BUTTON.id_}"))),
        (CHANDELIER_BUTTON.id_, does_not_raise()),
    ],
)
def test_delete_button(configuration: BaseConfiguration, button_id: UUID, expected_error: AbstractContextManager) -> None:
    """Test `delete_button`."""
    with expected_error:
        delete_button(configuration, button_id)
        with pytest.raises(ValueError, match=f"Unable to get Button with ID: {button_id}"):
            assert get_button_from_id(configuration, button_id)


@pytest.mark.parametrize(
    argnames=("page_id", "expected_error"),
    ids=(
        "valid",
        "not_valid",
    ),
    argvalues=[
        (UNUSED_PAGE.id_, pytest.raises(ValueError, match=f"Unable to get index for Page with ID: {UNUSED_PAGE.id_}")),
        (DINING_ROOM_PAGE.id_, does_not_raise()),
    ],
)
def test_delete_page(configuration: BaseConfiguration, page_id: UUID, expected_error: AbstractContextManager) -> None:
    """Test `delete_page`."""
    with expected_error:
        delete_page(configuration, page_id)
        with pytest.raises(ValueError, match=f"Unable to get Page with ID: {page_id}"):
            assert get_page_from_id(configuration, page_id)
