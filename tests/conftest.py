"""Test fixtures."""

import copy
from typing import Generator
from unittest.mock import AsyncMock, Mock

import pytest

from beoremote_halo import BaseConfiguration
from tests.const import CONFIGURATION


@pytest.fixture
def configuration() -> BaseConfiguration:
    """Example configuration for testing.

    Returns:
        Example config
    """
    return copy.deepcopy(CONFIGURATION)


@pytest.fixture
def mock_halo() -> Generator[AsyncMock]:
    """Mock Halo."""

    client = Mock()

    yield client
