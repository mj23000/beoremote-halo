# Beoremote Halo Open API

[![build](https://github.com/bang-olufsen/beoremote-halo/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/bang-olufsen/beoremote-halo/actions/workflows/ci.yaml)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Version](https://img.shields.io/pypi/v/beoremote-halo?color=g)](https://pypi.org/project/beoremote-halo)
[![Downloads](https://img.shields.io/pypi/dm/beoremote-halo)](https://pypi.org/project/beoremote-halo)

[<img src="https://github.com/bang-olufsen/beoremote-halo/raw/main/docs/images/Beoremote_Halo.png" width="30%" alt="Beoremote Halo">](https://www.bang-olufsen.com/en/us/accessories/beoremote-halo)

The [Beoremote Halo](https://www.bang-olufsen.com/en/us/accessories/beoremote-halo) Open API is an open source async API that allows you to interact with a Beoremote Halo from a home automation system.

Using a WebSocket to communicate with the Beoremote Halo, it is possible to create a configuration of buttons to interact with your home automation to control your home applications.

Beoremote Halo supports buttons with icons or text for most general home automation applications.
You can find a list of the [supported icons](https://github.com/bang-olufsen/beoremote-halo/wiki/Icons) on our wiki pages.
For further details on the Open API list of commands please refer to the [API description](https://bang-olufsen.github.io/beoremote-halo/).

## Installation

The Python package `beoremote-halo` requires [Python 3.11](https://www.python.org/downloads/) or higher and contains a library for communicating with Beoremote Halo and a CLI tool for discovering Beoremote Halo on the network.

Install using pip:

```sh
pip3 install beoremote-halo
```

Upgrading from version 1.x? See the [migration guide](MIGRATION.md).

## Basic Usage

In the following example a client connects to a Beoremote Halo, configures it with a single page containing a button, and listens for events. When the button is released, the `on_button_event` callback toggles the button between active and inactive. Please refer to the [API](https://bang-olufsen.github.io/beoremote-halo) for details on each type of event.

```python
import asyncio

from beoremote_halo.halo import Halo
from beoremote_halo.helpers import get_button_from_id
from beoremote_halo.models import (
    BaseConfiguration,
    Button,
    ButtonEvent,
    ButtonEventState,
    ButtonState,
    Configuration,
    Icon,
    Icons,
    Page,
    Update,
    UpdateButton,
)

lights = Button("Lights", Icon(Icons.LIGHTS), state=ButtonState.INACTIVE)
configuration = BaseConfiguration(Configuration([Page("Living room", [lights])]))
halo = Halo("192.168.1.57", configuration)


async def on_button_event(event: ButtonEvent) -> None:
    if event.state is ButtonEventState.RELEASED:
        button = get_button_from_id(halo.configuration, event.uuid_id)
        state = ButtonState.INACTIVE if button.state is ButtonState.ACTIVE else ButtonState.ACTIVE
        await halo.update(Update(UpdateButton(state=state, id_=button.uuid_id)))


async def main() -> None:
    halo.get_button_event(on_button_event)
    await halo.connect(reconnect=True)
    # Keep listening for events until stopped
    await asyncio.Event().wait()


asyncio.run(main())
```

Callbacks can be either regular functions or coroutines. Sending an `UpdateButton` also updates the client's copy of the configuration, which is sent to the Beoremote Halo again if the connection is lost and re-established.

`connect` sends the configuration as soon as the connection is made, replacing the Beoremote Halo's current configuration. This works in any state, also while the Beoremote Halo is asleep, and it keeps the configuration for as long as the client stays connected. `halo.configuration_accepted` is set once the Beoremote Halo has accepted it. To only listen for events, use `await halo.connect(send_configuration=False)`.

If the Beoremote Halo rejects the configuration as invalid, `halo.configuration_rejected` is set, and the client stops reconnecting until a new configuration is set with `set_configuration`.

To use an existing `aiohttp.ClientSession`, for example one shared by your application, pass it as `Halo(host, configuration, session=session)`. The client never closes a session passed to it.

## Example

Use the `beoremote-halo` CLI tool to discover and then run a demo by connecting to your Beoremote Halo.

First, locate Beoremote Halo on the network.

```sh
beoremote-halo scan
```

Afterwards the CLI demo is run by passing the serial number of the discovered Beoremote Halo.

```sh
beoremote-halo demo --serial xxxxxxxx
```

The demo configures the Beoremote Halo and reacts to events received from Halo. The callbacks each handle a specific type of [event](https://bang-olufsen.github.io/beoremote-halo/#message-event).

`on_system_event` is provided but unused in this example.

`on_wheel_event` changes the indicator ring on the centered/controlled button.

`on_button_event` changes the active/inactive state of a button, will start/pause/resume the timer if the "Oven Timer" button is pressed.

To print the events sent by a Beoremote Halo, without changing its configuration, use `listen`.

```sh
beoremote-halo listen --serial xxxxxxxx
```

Each command also accepts `--ip` instead of `--serial`. Use `beoremote-halo --help` to list all commands and options.
