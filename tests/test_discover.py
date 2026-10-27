"""Test Beoremote Halo discovery located in `beoremote_halo/cli/discover.py`."""

import asyncio
import socket
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from zeroconf import ServiceStateChange

from beoremote_halo.cli import discover
from beoremote_halo.cli.discover import SERVICE_TYPE, DiscoveredHalo, HaloDiscovery, resolve_serial

SERIAL = "12345678"
ADDRESS = "192.168.1.2"
SERVICE_NAME = f"BeoremoteHalo-{SERIAL}.{SERVICE_TYPE}"


class FakeServiceInfo:
    """Stands in for `AsyncServiceInfo`, returning the service details defined by the test."""

    # Details returned for each service name
    services: dict[str, tuple[bool, str | None, list[str]]]
    # Set when a lookup of a service with the server "hang" is cancelled
    cancelled: bool

    def __init__(self, service_type: str, name: str) -> None:
        """Initialize service info."""
        assert service_type == SERVICE_TYPE
        self._found, self.server, self._addresses = self.services[name]

    async def async_request(self, _zeroconf: object, _timeout: float) -> bool:
        """Request the service details.

        Returns:
            If the service details were found

        Raises:
            CancelledError: The lookup of a hanging service was cancelled
        """
        if self.server == "hang":
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                FakeServiceInfo.cancelled = True
                raise
        return self._found

    def parsed_addresses(self) -> list[str]:
        """Get the service's addresses.

        Returns:
            Addresses
        """
        return self._addresses


@pytest.fixture
def zeroconf(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace Zeroconf networking with mocks.

    Returns:
        Mocked `AsyncZeroconf` instance
    """
    async_zeroconf = MagicMock()
    async_zeroconf.async_close = AsyncMock()
    browser = MagicMock()
    browser.async_cancel = AsyncMock()

    monkeypatch.setattr(discover, "AsyncZeroconf", Mock(return_value=async_zeroconf))
    monkeypatch.setattr(discover, "AsyncServiceBrowser", Mock(return_value=browser))
    monkeypatch.setattr(discover, "AsyncServiceInfo", FakeServiceInfo)
    FakeServiceInfo.services = {}
    FakeServiceInfo.cancelled = False
    return async_zeroconf


def get_handler(zeroconf: MagicMock) -> Callable[..., None]:
    """Get the service state change handler passed to the service browser.

    Returns:
        Handler
    """
    browser_class = discover.AsyncServiceBrowser
    assert isinstance(browser_class, Mock)
    browser_class.assert_called_once_with(zeroconf.zeroconf, SERVICE_TYPE, handlers=browser_class.call_args.kwargs["handlers"])
    return browser_class.call_args.kwargs["handlers"][0]


async def add_service(handler: Callable[..., None], name: str, state_change: ServiceStateChange = ServiceStateChange.Added) -> None:
    """Report a service to the discovery, and let it be resolved."""
    handler(zeroconf=Mock(), service_type=SERVICE_TYPE, name=name, state_change=state_change)
    for _ in range(3):
        await asyncio.sleep(0)


async def test_discovery(zeroconf: MagicMock) -> None:
    """Test that found Halos are reported once, and that discovery is shut down on exit."""
    FakeServiceInfo.services = {SERVICE_NAME: (True, f"BeoremoteHalo-{SERIAL}.local.", [ADDRESS])}
    found: list[DiscoveredHalo] = []

    async with HaloDiscovery(found.append) as discovery:
        handler = get_handler(zeroconf)
        await add_service(handler, SERVICE_NAME)
        await add_service(handler, SERVICE_NAME, ServiceStateChange.Updated)
        await add_service(handler, SERVICE_NAME)

    assert found == [DiscoveredHalo(SERIAL, ADDRESS)]
    assert discovery.discovered == {SERIAL: DiscoveredHalo(SERIAL, ADDRESS)}
    zeroconf.async_close.assert_awaited_once()
    browser = discover.AsyncServiceBrowser
    assert isinstance(browser, Mock)
    browser.return_value.async_cancel.assert_awaited_once()


@pytest.mark.parametrize(
    argnames="details",
    ids=("not_found", "no_server", "no_addresses"),
    argvalues=[
        (False, None, []),
        (True, None, [ADDRESS]),
        (True, f"BeoremoteHalo-{SERIAL}.local.", []),
    ],
)
async def test_discovery_incomplete_service(zeroconf: MagicMock, details: tuple[bool, str | None, list[str]]) -> None:
    """Test that services without the required details are ignored."""
    FakeServiceInfo.services = {SERVICE_NAME: details}
    found: list[DiscoveredHalo] = []

    async with HaloDiscovery(found.append):
        await add_service(get_handler(zeroconf), SERVICE_NAME)

    assert found == []


async def test_discovery_cancels_pending_lookups(zeroconf: MagicMock) -> None:
    """Test that lookups still running on exit are cancelled."""
    FakeServiceInfo.services = {SERVICE_NAME: (True, "hang", [ADDRESS])}

    async with HaloDiscovery(Mock()):
        await add_service(get_handler(zeroconf), SERVICE_NAME)

    assert FakeServiceInfo.cancelled


async def test_resolve_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolving the address of a Halo from its serial number."""
    getaddrinfo = AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ADDRESS, 0))])
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)

    assert await resolve_serial(SERIAL) == ADDRESS
    getaddrinfo.assert_awaited_once_with(f"BeoremoteHalo-{SERIAL}.local", None, family=socket.AF_INET)


async def test_resolve_serial_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a Halo that can't be found raises an error."""
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(side_effect=socket.gaierror))

    with pytest.raises(OSError):  # ruff: ignore[pytest-raises-too-broad]
        await resolve_serial(SERIAL)
