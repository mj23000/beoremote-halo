# Migrating from 1.x to 2.0

Version 2.0 of `beoremote-halo` is a rewrite. The client is now based on `asyncio`, and the models are validated with pydantic. Almost every import, class and method has changed, so this guide maps each part of the 1.x API to its 2.0 replacement.

## Requirements

- Python 3.11 or newer (1.x supported Python 3.9).
- The package is still installed with `pip3 install beoremote-halo`, but it's imported as `beoremote_halo` instead of `beoremote`.
- Dependencies: `websocket-client`, `rel` and `click` have been replaced by `aiohttp` and `pydantic`. `zeroconf` is still used, for the CLI's `scan` command.

## Example

A client that configures a page with one button, and toggles the button when it's released.

### 1.x

```python
import uuid

from beoremote.configuration import Configuration
from beoremote.events.buttonEvent import ButtonEvent
from beoremote.events.icons import Icons
from beoremote.events.update import Update
from beoremote.events.updateButton import UpdateButton
from beoremote.halo import Halo

lights = Configuration.Pages.Buttons(
    str(uuid.uuid4()), "Lights", "Off", 0, Configuration.Pages.Buttons.State.INACTIVE, Icons(Icons.Icon.LIGHTS)
)
configuration = Configuration(str(uuid.uuid4()), [Configuration.Pages("Living room", str(uuid.uuid4()), [lights])])


def on_button_event(client: Halo, event: ButtonEvent) -> None:
    button = configuration[event.id]
    if button and event.state == ButtonEvent.State.released:
        button.toggle_state()
        client.send(Update(UpdateButton(button.id, state=button.state)))


remote = Halo("192.168.1.57")
remote.set_configuration(configuration)
remote.set_on_button_event_callback(on_button_event)
remote.connect()
```

### 2.0

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

lights = Button("Lights", Icon(Icons.LIGHTS), "Off", 0, ButtonState.INACTIVE)
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

The main differences:

- Imports come from the modules of `beoremote_halo`: `halo`, `models` and `helpers`.
- Callbacks receive only the event, not the client.
- `connect`, `update` and the other client methods are coroutines, and `connect` returns once connected instead of blocking.
- IDs are generated automatically.
- `update` also updates the client's copy of the configuration, so there's no need to change the button yourself.

## Imports

The client is in `beoremote_halo.halo`, the models in `beoremote_halo.models`, and the functions for changing a configuration in `beoremote_halo.helpers`. Constants, such as the length limits, are in `beoremote_halo.const`.

| 1.x | 2.0 |
| --- | --- |
| `from beoremote.halo import Halo` | `from beoremote_halo.halo import Halo` |
| `from beoremote.configuration import Configuration` | `from beoremote_halo.models import BaseConfiguration, Configuration, Page, Button` |
| `from beoremote.events.icons import Icons` | `from beoremote_halo.models import Icon, Icons` |
| `from beoremote.events.text import Text` | `from beoremote_halo.models import Text` |
| `from beoremote.events.<module> import <Event or Update class>` | `from beoremote_halo.models import <Event or Update class>` |

All public names can also be imported directly from `beoremote_halo`.

## Connecting

The 1.x client ran its own event loop, and `connect` blocked until the connection ended. In 2.0, the client runs in your `asyncio` event loop.

| 1.x | 2.0 |
| --- | --- |
| `Halo(host)` | `Halo(host, configuration=None, port=8080, session=None)` |
| `remote.connect()` (blocks) | `await halo.connect(reconnect=False, send_configuration=True)` (returns once connected) |
| `remote.close_connection()` | `await halo.disconnect()` |
| `remote.set_auto_reconnect(reconnect, attempts)` | `await halo.connect(reconnect=True)` |
| `remote.set_reconnect_backoff_timeout(timeout)` | No replacement, see below |

Behaviour that has changed:

- **Waiting for the connection.** `connect` waits for the first connection attempt. Without `reconnect`, it raises `aiohttp.ClientError` or `TimeoutError` if that attempt fails. With `reconnect`, a failed attempt is retried in the background, and `connect` returns.
- **Reconnecting.** It's now off by default (1.x enabled it by default). When enabled, the client retries every 5 seconds without limit, instead of 3 times with 30 seconds between attempts. The delay and the number of attempts can't be changed.
- **Connection state.** It's available as `halo.websocket_connected` and `halo.connection_state`.
- **Sessions.** To use your application's `aiohttp.ClientSession`, pass it as `session`. The client never closes a session passed to it.

## Configuration

| 1.x | 2.0 |
| --- | --- |
| `remote.set_configuration(configuration)` | `Halo(host, configuration)`, or `await halo.set_configuration(configuration)` |
| `Configuration(configuration_id, pages)` | `BaseConfiguration(Configuration(pages, id_=configuration_id))` |
| `Configuration.Pages(title, page_id, buttons)` | `Page(title, buttons, id_=page_id)` |
| `Configuration.Pages.Buttons(button_id, title, subtitle, value, state, content, default)` | `Button(title, content, subtitle, value, state, default, id_=button_id)` |
| `Configuration.Pages.Buttons.State.ACTIVE` | `ButtonState.ACTIVE` |
| `Icons(Icons.Icon.LIGHTS)` | `Icon(Icons.LIGHTS)` |
| `Text("21°C")` | `Text("21°C")` |
| `configuration[button_id]` | `get_button_from_id(configuration, button_id)` |
| `button.toggle_state()` | Set `button.state`, or send an `UpdateButton` with `halo.update` |
| `Configuration.APIVersion` | `API_VERSION`, from `beoremote_halo.const` |

Behaviour that has changed:

- **Argument order.** `content` is now the second argument of `Button`, and every ID is the keyword-only `id_` argument, at the end.
- **IDs.** They're generated automatically when omitted. They're stored as `uuid.UUID`, and also accept strings. Use `.uuid_id` or `.str_id` to get one as a `UUID` or a string.
- **Wrapper object.** The configuration sent to the Halo is a `BaseConfiguration` that wraps a `Configuration`.
- **Lookups.** `get_button_from_id` raises `ValueError` for an unknown ID, where 1.x returned `None`.
- **Validation.** The models check lengths, value ranges, the number of pages and buttons, and that only one button is the default. They raise `pydantic.ValidationError` (a `ValueError`) when constructed or changed with invalid values.
- **Sending the configuration.** The client sends it as soon as each connection is made. 1.x sent it once the Halo reported being active. To only listen to events without replacing the Halo's configuration, use `await halo.connect(send_configuration=False)`.
- **Accepted and rejected configurations.** `halo.configuration_accepted` is set when the Halo accepts the configuration. If the Halo rejects it, `halo.configuration_rejected` is set, and the client stops reconnecting until a new configuration is set.

`beoremote_halo.helpers` has functions for changing a configuration: `update_button`, `update_page`, `delete_button`, `delete_page`, `clear_default_button`, plus lookups such as `get_page_from_id` and `get_all_buttons`.

## Updates

| 1.x | 2.0 |
| --- | --- |
| `remote.send(update)` | `await halo.update(update)` |
| `remote.send(configuration)` | `await halo.set_configuration(configuration)` |
| `UpdateButton(id, title, subtitle, value, state, content)` | `UpdateButton(state=..., value=..., title=..., subtitle=..., content=..., id_=id)` |
| `UpdateButton.State.active` | `ButtonState.ACTIVE` |
| `UpdateDisplayPage(pageid, buttonid)` | `UpdateDisplayPage(page_id=..., button_id=...)` |
| `UpdateNotification(id, title, subtitle)` | `UpdateNotification(title, message, id_=id)` |

Behaviour that has changed:

- **Keyword arguments.** Pass the `UpdateButton` fields as keywords, as their order has changed.
- **Notification text.** The text of a notification is now called `message`. It's still sent to the Halo as `subtitle`.
- **Return value.** `update` returns `False` instead of queuing the update when the client isn't connected, so updates are never sent late after a reconnect.
- **Configuration copy.** An `UpdateButton` also updates the client's copy of the configuration, which is resent after reconnecting. Pass `update_configuration=False` to only send the update.
- **Raw messages.** `send` accepted any string. In 2.0, only `Update` and `BaseConfiguration` objects can be sent.

## Events

Callbacks can be regular functions or coroutines, and are called with the event only.

| 1.x | 2.0 |
| --- | --- |
| `set_on_button_event_callback(fn(client, event))` | `get_button_event(fn(event))` |
| `set_on_wheel_event_callback(fn(client, event))` | `get_wheel_event(fn(event))` |
| `set_on_system_event_callback(fn(client, event))` | `get_system_event(fn(event))` |
| `set_on_status_event_callback(fn(client, event))` | `get_status_event(fn(event))` |
| `set_on_power_event_callback(fn(client, event))` | `get_power_event(fn(event))` |
| `set_on_connected(fn())` | `get_on_connection(fn())` |
| `set_on_websocket_close_callback(fn(close_status_code, close_msg))` | `get_on_connection_lost(fn())` |

There are also new callbacks for all events: `get_all_events(fn(event, event_type))`, and `get_all_events_raw(fn(event_dict))`, which receives the event as a `dict`.

The event fields have changed:

| 1.x | 2.0 |
| --- | --- |
| `event.type` (`str`) | `event.type_` (`EventTypes`) |
| `event.id` (`str`) | `event.uuid_id` (`UUID`), or `event.str_id` (`str`) |
| `WheelEvent.counts` (`int`) | `WheelEvent.counts` (`WheelEventValues`, use `.value` for the `int`) |
| `ButtonEvent.State.released` | `ButtonEventState.RELEASED` |
| `StatusEvent.State.ok` | `StatusEventState.OK` |
| `SystemEvent.State.active` | `SystemEventState.ACTIVE` |
| `PowerEvent.State.low` | `PowerEventState.LOW` |

Behaviour that has changed:

- **Comparing IDs.** IDs are `UUID` objects, so compare them with other `UUID`s, for example `button.uuid_id`, or use `event.str_id`.
- **Unexpected events.** An event that doesn't match its type is logged and skipped, but is still passed to `get_all_events_raw`.
- **Missing callbacks.** No warning is logged for events without a callback.
- **Callback errors.** An exception raised in a callback is logged, and doesn't affect the connection.

## Serialization

| 1.x | 2.0 |
| --- | --- |
| `entity.to_json()`, `str(entity)` | `model.to_json()` |
| `Entity.from_json(data)` | `Model.from_json(data)` |
| None | `model.to_dict()`, `Model.from_dict(data)` |

The JSON sent to and received from the Halo hasn't changed.

## CLI

The `beoremote-halo` command still has the `scan`, `listen` and `demo` commands, with `--ip`/`--serial`, `--log` and `--version`.

- **`listen`.** It prints each event as JSON, and no longer replaces the Halo's configuration with an empty one.
- **`scan`.** It has a new `--timeout SECONDS` option, for scanning without waiting for enter.
- **`--log`.** It now defaults to `INFO`, as its help text always stated (1.x used `DEBUG`).
- **Errors.** Invalid arguments and a serial number that can't be found exit with a non-zero exit code. IPv4 addresses are validated properly.
- **`--version`.** It prints the package and API versions. The separate CLI version is gone.
