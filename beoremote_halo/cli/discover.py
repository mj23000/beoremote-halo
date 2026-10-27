"""Discover Beoremote Halos on the local network using Zeroconf."""

import asyncio
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

SERVICE_TYPE = "_zenith._tcp.local."
HOSTNAME_PREFIX = "BeoremoteHalo-"
HOSTNAME_SUFFIX = ".local."

# Time to wait for a discovered service's details, in milliseconds
SERVICE_INFO_TIMEOUT = 3000

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiscoveredHalo:
    """A Beoremote Halo found on the network."""

    serial: str
    address: str


class HaloDiscovery:
    """Browse the network for Beoremote Halos while used as an async context manager."""

    def __init__(self, on_discovered: Callable[[DiscoveredHalo], None]) -> None:
        """Initialize discovery.

        Args:
            on_discovered: Called once for each Beoremote Halo found
        """
        self.discovered: dict[str, DiscoveredHalo] = {}
        self._on_discovered = on_discovered
        self._zeroconf: AsyncZeroconf
        self._browser: AsyncServiceBrowser
        self._tasks: set[asyncio.Task[None]] = set()

    async def __aenter__(self) -> Self:
        """Start browsing.

        Returns:
            The running discovery
        """
        self._zeroconf = AsyncZeroconf()
        self._browser = AsyncServiceBrowser(self._zeroconf.zeroconf, SERVICE_TYPE, handlers=[self._on_service_state_change])
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop browsing."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._browser.async_cancel()
        await self._zeroconf.async_close()

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        """Look up details of services that have been added."""
        if state_change is ServiceStateChange.Added:
            task = asyncio.create_task(self._resolve(zeroconf, service_type, name))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _resolve(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        """Get the serial number and address of a discovered service."""
        info = AsyncServiceInfo(service_type, name)
        if not await info.async_request(zeroconf, SERVICE_INFO_TIMEOUT) or info.server is None:
            _LOGGER.debug("Unable to get details for %s", name)
            return

        addresses = info.parsed_addresses()
        serial = info.server.removeprefix(HOSTNAME_PREFIX).removesuffix(HOSTNAME_SUFFIX)
        if not addresses or serial in self.discovered:
            return

        halo = DiscoveredHalo(serial, addresses[0])
        self.discovered[serial] = halo
        self._on_discovered(halo)


def serial_to_hostname(serial: str) -> str:
    """Get the mDNS hostname of a Beoremote Halo from its serial number.

    Returns:
        Hostname
    """
    return f"{HOSTNAME_PREFIX}{serial}.local"


async def resolve_serial(serial: str) -> str:
    """Find the IPv4 address of a Beoremote Halo from its serial number.

    Raises `socket.gaierror` if the hostname of the Beoremote Halo couldn't be resolved.

    Returns:
        IPv4 address
    """
    # getaddrinfo raises instead of returning an empty list
    addresses = await asyncio.get_running_loop().getaddrinfo(serial_to_hostname(serial), None, family=socket.AF_INET)
    return str(addresses[0][4][0])
