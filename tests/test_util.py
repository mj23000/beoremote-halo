"""Test helper functions for button values located in `beoremote_halo/util.py`."""

import string
from collections.abc import Callable

import pytest

from beoremote_halo import MAX_VALUE, MIN_VALUE
from beoremote_halo.const import BUTTON_CONTENT_TEXT_MAX_LENGTH, BUTTON_SUBTITLE_MAX_LENGTH, BUTTON_TITLE_MAX_LENGTH, PAGE_TITLE_MAX_LENGTH
from beoremote_halo.util import (
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


# Longer than any of the length limits
TEXT = string.ascii_letters


@pytest.mark.parametrize(
    argnames=("trim", "max_length"),
    ids=("button_text", "button_subtitle", "button_title", "page_title"),
    argvalues=[
        (trim_button_text, BUTTON_CONTENT_TEXT_MAX_LENGTH),
        (trim_button_subtitle, BUTTON_SUBTITLE_MAX_LENGTH),
        (trim_button_title, BUTTON_TITLE_MAX_LENGTH),
        (trim_page_title, PAGE_TITLE_MAX_LENGTH),
    ],
)
def test_trim(trim: Callable[[str], str], max_length: int) -> None:
    """Test that the trim functions shorten text above their length limit, and leave other text unchanged."""
    at_limit = TEXT[:max_length]

    assert trim(at_limit) == at_limit
    assert trim(at_limit[:-1]) == at_limit[:-1]
    assert trim(TEXT[: max_length + 1]) == at_limit
    assert not trim("")
