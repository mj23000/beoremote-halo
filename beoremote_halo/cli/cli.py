"""Command line interface for discovering and interacting with Beoremote Halos."""

import argparse
import asyncio
import contextlib
import ipaddress
import json
import logging
import os
import sys
import threading
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from beoremote_halo import __version__
from beoremote_halo.cli.demo import Demo, demo_configuration
from beoremote_halo.cli.discover import DiscoveredHalo, HaloDiscovery, resolve_serial, serial_to_hostname
from beoremote_halo.const import API_VERSION, WEBSOCKET_PORT
from beoremote_halo.halo import Halo

PROG = "beoremote-halo"

DESCRIPTION = """\
CLI provided by Bang & Olufsen a/s to discover and interact with Beoremote Halos on the local network.

Project source files are located at GitHub:
https://github.com/bang-olufsen/beoremote-halo
API documentation is available at:
https://bang-olufsen.github.io/beoremote-halo/

Please report bugs or issues at:
https://github.com/bang-olufsen/beoremote-halo/issues
"""

SCAN_PROMPT = """\
Discovering Beoremote Halo on network...
If Beoremote Halo does not appear on the list, try waking it up while discovery is running.
Press enter to exit...
"""


class CliError(Exception):
    """Error that is shown to the user without a traceback."""


def ipv4_address(value: str) -> str:
    """Validate an IPv4 address argument.

    Returns:
        The IPv4 address

    Raises:
        ArgumentTypeError: Not a valid IPv4 address
    """
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError as e:
        msg = f"Incorrect IPv4 format: {value}"
        raise argparse.ArgumentTypeError(msg) from e


def serial_number(value: str) -> str:
    """Validate a serial number argument.

    Returns:
        The serial number

    Raises:
        ArgumentTypeError: Not a valid serial number
    """
    if len(value) != 8 or not value.isdigit():  # ruff: ignore[magic-value-comparison]
        msg = f"{value} is not a valid serial number"
        raise argparse.ArgumentTypeError(msg)
    return value


async def get_host(args: argparse.Namespace) -> str:
    """Get the address of the Beoremote Halo from the `--ip` or `--serial` argument.

    Returns:
        IPv4 address

    Raises:
        CliError: The serial number couldn't be found on the network
    """
    if args.ip is not None:
        return args.ip

    print(f"Searching for Beoremote Halo with serial {args.serial} on the network")
    try:
        return await resolve_serial(args.serial)
    except OSError as e:
        msg = f"Unable to locate {serial_to_hostname(args.serial)} on the network, try specifying the IP address"
        raise CliError(msg) from e


# Name of the thread waiting for enter to be pressed
INPUT_THREAD_NAME = "beoremote-halo input"
STDIN_FILENO = 0
READ_SIZE = 1024


def read_line(fd: int) -> None:
    """Read from a file descriptor until a line has been read, the end of input, or an error."""
    with contextlib.suppress(OSError):
        while (data := os.read(fd, READ_SIZE)) and b"\n" not in data:
            pass


async def wait_for_enter(prompt: str) -> None:
    """Wait for enter to be pressed, or the end of input, without blocking the event loop.

    The input is read in a daemon thread rather than the event loop's executor, as `asyncio.run` waits for executor
    threads to finish before returning, so stopping with Ctrl+C would wait for enter to be pressed. The thread reads
    the file descriptor directly, as a daemon thread blocked in `input` holds the lock of `sys.stdin`, which can abort
    the interpreter at shutdown.
    """
    loop = asyncio.get_running_loop()
    pressed: asyncio.Future[None] = loop.create_future()

    def set_pressed() -> None:
        # Not set if waiting was cancelled
        if not pressed.done():
            pressed.set_result(None)

    def read() -> None:
        read_line(STDIN_FILENO)
        # The event loop is closed if enter is pressed after waiting was cancelled
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(set_pressed)

    print(prompt, end="", flush=True)
    threading.Thread(target=read, name=INPUT_THREAD_NAME, daemon=True).start()
    await pressed


async def scan(args: argparse.Namespace) -> None:
    """Print Beoremote Halos found on the network until enter is pressed, or the timeout runs out."""

    def on_discovered(halo: DiscoveredHalo) -> None:
        print(f"Serial: {halo.serial}, {halo.address}")

    async with HaloDiscovery(on_discovered):
        if args.timeout is None:
            await wait_for_enter(SCAN_PROMPT)
        else:
            await asyncio.sleep(args.timeout)


async def run_until_stopped(halo: Halo, host: str, send_configuration: bool) -> None:
    """Connect to the Halo and keep the connection open until cancelled."""
    halo.get_on_connection_lost(lambda: print(f"Lost connection to {host}, reconnecting"))
    try:
        await halo.connect(reconnect=True, send_configuration=send_configuration)
        if not halo.websocket_connected:
            print(f"Unable to connect to {host}, retrying")
        await asyncio.Event().wait()
    finally:
        await halo.disconnect()


async def listen(args: argparse.Namespace, port: int = WEBSOCKET_PORT) -> None:
    """Print events received from a Beoremote Halo."""
    host = await get_host(args)

    def on_event(event: dict[str, Any]) -> None:
        print(json.dumps(event))

    halo = Halo(host, port=port)
    halo.get_on_connection(lambda: print(f"Listening on events from: {host}"))
    halo.get_all_events_raw(on_event)

    # Sending the default empty configuration would replace the Halo's current configuration
    await run_until_stopped(halo, host, send_configuration=False)


async def demo(args: argparse.Namespace, port: int = WEBSOCKET_PORT) -> None:
    """Configure a Beoremote Halo with the demo configuration and react to its events."""
    host = await get_host(args)

    halo = Halo(host, demo_configuration(), port=port)
    halo.get_on_connection(lambda: print(f"Demo connected to: {host}"))
    demo = Demo(halo)

    try:
        await run_until_stopped(halo, host, send_configuration=True)
    finally:
        await demo.stop()


def add_host_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the mutually exclusive `--ip` and `--serial` arguments, one of which is required."""
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ip", type=ipv4_address, help="IP address of Beoremote Halo")
    group.add_argument("--serial", type=serial_number, help="Serial number of Beoremote Halo")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser.

    Returns:
        Argument parser
    """
    parser = argparse.ArgumentParser(prog=PROG, description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--log",
        type=str.upper,
        choices=["DEBUG", "INFO"],
        default="INFO",
        help="Set logging level. Defaults to INFO",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} package version: {__version__}\nAPI version: {API_VERSION}",
    )
    subparsers = parser.add_subparsers(title="commands", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan the network for active Beoremote Halos")
    scan_parser.add_argument("--timeout", type=float, help="Scan for this many seconds instead of until enter is pressed")
    scan_parser.set_defaults(command=scan)

    listen_parser = subparsers.add_parser("listen", help="Connect to a Beoremote Halo and listen for events")
    add_host_arguments(listen_parser)
    listen_parser.set_defaults(command=listen)

    demo_parser = subparsers.add_parser("demo", help="Interactive home automation demo")
    add_host_arguments(demo_parser)
    demo_parser.set_defaults(command=demo)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        Exit code
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(format="%(levelname)-5s | %(message)s", level=args.log)

    command: Callable[[argparse.Namespace], Coroutine[Any, Any, None]] = args.command
    try:
        asyncio.run(command(args))
    except CliError as e:
        print(e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0
