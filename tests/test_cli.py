"""Test the command line interface located in `beoremote_halo/cli/cli.py`."""

import argparse
import asyncio
import contextlib
import json
import os
import runpy
import socket
import threading
from collections.abc import Callable, Generator
from types import TracebackType
from typing import Self
from unittest.mock import AsyncMock

import pytest

from beoremote_halo import API_VERSION, __version__
from beoremote_halo.cli import cli, main
from beoremote_halo.cli.discover import DiscoveredHalo
from tests.fake_halo import SYSTEM_EVENT, TIMEOUT, FakeHalo, wait_until

SERIAL = "12345678"
# Exit code of argparse usage errors
USAGE_ERROR = 2


class FakeDiscovery:
    """Stands in for `HaloDiscovery`, finding a single Halo."""

    def __init__(self, on_discovered: Callable[[DiscoveredHalo], None]) -> None:
        """Initialize discovery."""
        self._on_discovered = on_discovered

    async def __aenter__(self) -> Self:
        """Find a Halo.

        Returns:
            The discovery
        """
        self._on_discovered(DiscoveredHalo(SERIAL, "192.168.1.2"))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop discovery."""


class Output:
    """Collect output printed while a command is running."""

    def __init__(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Initialize output."""
        self._capsys = capsys
        self.text = ""

    async def wait_for(self, text: str) -> None:
        """Wait for text to be printed."""

        def printed() -> bool:
            self.text += self._capsys.readouterr().out
            return text in self.text

        await wait_until(printed)


@pytest.fixture
def output(capsys: pytest.CaptureFixture[str]) -> Output:
    """Output printed by the CLI.

    Returns:
        Output
    """
    return Output(capsys)


@pytest.fixture
def discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace network discovery with a fake that finds a single Halo."""
    monkeypatch.setattr(cli, "HaloDiscovery", FakeDiscovery)


async def stop(task: asyncio.Task[None]) -> None:
    """Stop a running command, like pressing Ctrl+C."""
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test printing the package and API version."""
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"beoremote-halo package version: {__version__}\nAPI version: {API_VERSION}\n"


@pytest.mark.parametrize(
    argnames=("argv", "error"),
    ids=("no_command", "invalid_log_level", "no_host", "invalid_ip", "invalid_serial", "short_serial", "ip_and_serial"),
    argvalues=[
        ([], "the following arguments are required"),
        (["--log=None", "scan"], "invalid choice: 'NONE'"),
        (["listen"], "one of the arguments --ip --serial is required"),
        (["demo", "--ip=12345678"], "Incorrect IPv4 format: 12345678"),
        (["demo", "--serial=a2345678"], "a2345678 is not a valid serial number"),
        (["listen", "--serial=1234567"], "1234567 is not a valid serial number"),
        (["demo", "--ip=127.0.0.1", "--serial=12345678"], "argument --serial: not allowed with argument --ip"),
    ],
)
def test_invalid_arguments(argv: list[str], error: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that invalid arguments are rejected with a usage error."""
    with pytest.raises(SystemExit) as exit_info:
        main(argv)

    assert exit_info.value.code == USAGE_ERROR
    assert error in capsys.readouterr().err


@pytest.mark.usefixtures("discovery")
def test_scan_with_timeout(capsys: pytest.CaptureFixture[str]) -> None:
    """Test scanning for a fixed time, with the log level given in lowercase."""
    assert main(["--log=debug", "scan", "--timeout=0"]) == 0

    assert capsys.readouterr().out == f"Serial: {SERIAL}, 192.168.1.2\n"


@pytest.fixture
def stdin(monkeypatch: pytest.MonkeyPatch) -> Generator[int]:
    """Replace standard input with a pipe.

    Yields:
        File descriptor to write input to
    """
    read_fd, write_fd = os.pipe()
    monkeypatch.setattr(cli, "STDIN_FILENO", read_fd)
    yield write_fd
    for fd in (read_fd, write_fd):
        with contextlib.suppress(OSError):
            os.close(fd)


def join_input_thread() -> None:
    """Wait for the thread waiting for enter to finish."""
    for thread in threading.enumerate():
        if thread.name == cli.INPUT_THREAD_NAME:
            thread.join(TIMEOUT)


@pytest.mark.usefixtures("discovery")
def test_scan_until_enter(stdin: int, capsys: pytest.CaptureFixture[str]) -> None:
    """Test scanning until enter is pressed."""
    os.write(stdin, b"\n")

    assert main(["scan"]) == 0

    output = capsys.readouterr().out
    assert f"Serial: {SERIAL}" in output
    assert cli.SCAN_PROMPT in output


@pytest.mark.usefixtures("discovery")
def test_scan_until_end_of_input(stdin: int) -> None:
    """Test that scanning stops at the end of input, e.g. when it isn't a terminal."""
    os.close(stdin)

    assert main(["scan"]) == 0


@pytest.mark.usefixtures("discovery")
def test_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Ctrl+C exits without a traceback."""
    monkeypatch.setattr(cli, "wait_for_enter", AsyncMock(side_effect=KeyboardInterrupt))

    assert main(["scan"]) == 0


def test_read_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a line is read across several reads, and that the rest of the input isn't."""
    monkeypatch.setattr(cli, "READ_SIZE", 1)
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"ab\ncd")

    cli.read_line(read_fd)

    assert os.read(read_fd, 10) == b"cd"
    os.close(read_fd)
    os.close(write_fd)


def test_read_line_error() -> None:
    """Test that an error reading the input ends reading, like the end of input."""
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    os.close(write_fd)

    cli.read_line(read_fd)


async def test_wait_for_enter_cancelled(stdin: int) -> None:
    """Test that waiting for enter can be cancelled while still reading the input, like when Ctrl+C is pressed."""
    waiting = asyncio.create_task(cli.wait_for_enter(""))
    await asyncio.sleep(0)

    await stop(waiting)

    # Pressing enter afterwards is ignored
    os.write(stdin, b"\n")
    join_input_thread()
    await asyncio.sleep(0)


def test_enter_after_event_loop_closed(stdin: int) -> None:
    """Test that pressing enter after the event loop has closed doesn't raise in the thread waiting for it."""

    async def wait_then_stop() -> None:
        waiting = asyncio.create_task(cli.wait_for_enter(""))
        await asyncio.sleep(0)
        await stop(waiting)

    asyncio.run(wait_then_stop())

    # An exception raised in the thread would fail the test, as pytest reports it as a warning
    os.write(stdin, b"\n")
    join_input_thread()


def test_serial_not_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that a serial number that can't be found on the network is reported."""
    monkeypatch.setattr(cli, "resolve_serial", AsyncMock(side_effect=socket.gaierror))

    assert main(["listen", f"--serial={SERIAL}"]) == 1

    captured = capsys.readouterr()
    assert f"Searching for Beoremote Halo with serial {SERIAL}" in captured.out
    assert f"Unable to locate BeoremoteHalo-{SERIAL}.local on the network" in captured.err


async def test_get_host_from_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test finding the address of a Halo from its serial number."""
    resolve_serial = AsyncMock(return_value="192.168.1.2")
    monkeypatch.setattr(cli, "resolve_serial", resolve_serial)

    assert await cli.get_host(argparse.Namespace(ip=None, serial=SERIAL)) == "192.168.1.2"
    resolve_serial.assert_awaited_once_with(SERIAL)


async def test_listen(fake_halo: FakeHalo, output: Output) -> None:
    """Test printing events, without replacing the Halo's configuration, and reconnecting."""
    host = fake_halo.server.host  # ty: ignore[unresolved-attribute]
    task = asyncio.create_task(cli.listen(argparse.Namespace(ip=host, serial=None), port=fake_halo.server.port))  # ty: ignore[unresolved-attribute]

    await output.wait_for(f"Listening on events from: {host}")
    await fake_halo.send(SYSTEM_EVENT)
    await output.wait_for(json.dumps(SYSTEM_EVENT))

    await fake_halo.websocket.close()
    await output.wait_for(f"Lost connection to {host}, reconnecting")
    await asyncio.wait_for(fake_halo.connections.get(), TIMEOUT)
    await asyncio.wait_for(fake_halo.connections.get(), TIMEOUT)

    await stop(task)
    await asyncio.wait_for(fake_halo.disconnections.get(), TIMEOUT)
    assert fake_halo.received.empty()


async def test_listen_unreachable(unused_tcp_port: int, output: Output) -> None:
    """Test that a Halo that can't be reached is reported while retrying."""
    task = asyncio.create_task(cli.listen(argparse.Namespace(ip="127.0.0.1", serial=None), port=unused_tcp_port))

    await output.wait_for("Unable to connect to 127.0.0.1, retrying")

    await stop(task)


async def test_demo(fake_halo: FakeHalo, output: Output) -> None:
    """Test that the demo sends its configuration and reacts to events."""
    host = fake_halo.server.host  # ty: ignore[unresolved-attribute]
    task = asyncio.create_task(cli.demo(argparse.Namespace(ip=host, serial=None), port=fake_halo.server.port))  # ty: ignore[unresolved-attribute]

    configuration = (await fake_halo.next_message())["configuration"]
    await output.wait_for(f"Demo connected to: {host}")
    assert [page["title"] for page in configuration["pages"]] == ["Kitchen", "Living room"]

    light = configuration["pages"][0]["buttons"][0]
    await fake_halo.send({"event": {"type": "button", "id": light["id"], "state": "released"}})
    assert (await fake_halo.next_message())["update"] == {"type": "button", "id": light["id"], "state": "inactive"}

    await stop(task)


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test running the CLI with `python -m beoremote_halo.cli`."""
    monkeypatch.setattr("sys.argv", ["beoremote-halo", "--version"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("beoremote_halo.cli", run_name="__main__")

    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out
