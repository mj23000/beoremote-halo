"""Test helper functions for button values located in `beoremote_halo/util.py`."""

import pytest

from beoremote_halo import MAX_VALUE, MIN_VALUE
from beoremote_halo.const import BUTTON_CONTENT_TEXT_MAX_LENGTH, BUTTON_SUBTITLE_MAX_LENGTH, BUTTON_TITLE_MAX_LENGTH, PAGE_TITLE_MAX_LENGTH
from beoremote_halo.util import (
    check_valid_serial_number,
    clamp_button_value,
    interpolate_button_value,
    trim_button_subtitle,
    trim_button_text,
    trim_button_title,
    trim_page_title,
)


@pytest.mark.parametrize(
    argnames=("value", "expected_value"),
    ids=(
        "no_clamp_int",
        "no_clamp_float",
        "clamp_to_minimum",
        "clamp_to_maximum",
        "zero_value",
    ),
    argvalues=[
        (5, 5),
        (5.5, 5),
        (-200.0, MIN_VALUE),
        (200.0, MAX_VALUE),
        (0, 0),
    ],
)
def test_clamp_button_value(value: float, expected_value: int) -> None:
    """Test `clamp_button_value`."""
    assert clamp_button_value(value) == expected_value


@pytest.mark.parametrize(
    argnames=("value", "min_value", "max_value", "expected_value"),
    ids=(
        "unchanged",
        "unchanged_float",
        "negative_minimum",
        "positive_minimum",
        "negative_maximum",
    ),
    argvalues=[
        (10, MIN_VALUE, MAX_VALUE, 10),
        (10.0, 0, 100.0, 10),
        (0, -100, 100, 50),
        (50, 33, 70, 45),
        (-150, -200, -100, 50),
    ],
)
def test_interpolate_button_value(value: int, min_value: int, max_value: int, expected_value: int) -> None:
    """Test `interpolate_button_value`."""
    assert interpolate_button_value(value, min_value, max_value) == expected_value


@pytest.mark.parametrize(
    argnames=("text", "expected_text"),
    ids=(
        "at_limit",
        "under_limit",
        "above_limit",
        "no_value",
    ),
    argvalues=[
        ("abcdef", "abcdef"),
        ("abcde", "abcde"),
        ("abcdefg", "abcdef"),
        ("", ""),
    ],
)
def test_trim_button_text(text: str, expected_text: str) -> None:
    """Test `trim_button_text`."""
    trimmed = trim_button_text(text)
    assert trimmed == expected_text
    assert len(trimmed) <= BUTTON_CONTENT_TEXT_MAX_LENGTH


@pytest.mark.parametrize(
    argnames=("text", "expected_text"),
    ids=(
        "at_limit",
        "under_limit",
        "above_limit",
        "no_value",
    ),
    argvalues=[
        ("abcdefhijklmnop", "abcdefhijklmnop"),
        ("abcdefhijklmno", "abcdefhijklmno"),
        ("abcdefhijklmnopq", "abcdefhijklmnop"),
        ("", ""),
    ],
)
def test_trim_button_subtitle(text: str, expected_text: str) -> None:
    """Test `trim_button_subtitle`."""
    trimmed = trim_button_subtitle(text)
    assert trimmed == expected_text
    assert len(trimmed) <= BUTTON_SUBTITLE_MAX_LENGTH


@pytest.mark.parametrize(
    argnames=("text", "expected_text"),
    ids=(
        "at_limit",
        "under_limit",
        "above_limit",
        "no_value",
    ),
    argvalues=[
        ("abcdefhijklmnop", "abcdefhijklmnop"),
        ("abcdefhijklmno", "abcdefhijklmno"),
        ("abcdefhijklmnopq", "abcdefhijklmnop"),
        ("", ""),
    ],
)
def test_trim_button_title(text: str, expected_text: str) -> None:
    """Test `trim_button_title`."""
    trimmed = trim_button_title(text)
    assert trimmed == expected_text
    assert len(trimmed) <= BUTTON_TITLE_MAX_LENGTH


@pytest.mark.parametrize(
    argnames=("text", "expected_text"),
    ids=(
        "at_limit",
        "under_limit",
        "above_limit",
        "no_value",
    ),
    argvalues=[
        ("String for unit testing Beoremote Halo-", "String for unit testing Beoremote Halo-"),
        ("String for unit testing Beoremote Halo", "String for unit testing Beoremote Halo"),
        ("This is a string for unit testing Beoremote Halo", "This is a string for unit testing Beorem"),
        ("", ""),
    ],
)
def test_trim_page_title(text: str, expected_text: str) -> None:
    """Test `trim_page_title`."""
    trimmed = trim_page_title(text)
    assert trimmed == expected_text
    assert len(trimmed) <= PAGE_TITLE_MAX_LENGTH


@pytest.mark.parametrize(
    argnames=("serial_number", "expected_result"),
    ids=(
        "valid",
        "invalid_too_short",
        "invalid_too_long",
        "invalid_str",
    ),
    argvalues=[
        ("12345678", True),
        ("1234567", False),
        ("123456789", False),
        ("Notvalid", False),
    ],
)
def test_check_valid_serial_number(serial_number: str, expected_result: str) -> None:
    """Test `check_valid_serial_number`."""
    assert check_valid_serial_number(serial_number) == expected_result
