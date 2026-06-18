"""Constants used by tests."""

from uuid import UUID

from beoremote_halo import BaseConfiguration, Button, ButtonState, Configuration, Icon, Icons, Page, Text

CHANDELIER_BUTTON = Button(
    "Chandelier",
    Icon(Icons.LIGHTS),
    "20%",
    20,
    ButtonState.ACTIVE,
    True,
    id_=UUID("3c494ca3-5bbb-420e-babc-0752838b457d"),
)
DINING_ROOM_PAGE = Page("Dining room", [CHANDELIER_BUTTON], id_=UUID("8b836136-b71d-4611-b7f0-d136e68ceb0f"))

DOOR_BUTTON = Button("Door", Icon(Icons.DOOR), "Opening", 60, ButtonState.ACTIVE, id_=UUID("eb8996b6-0b00-4634-a844-35fd3b0ce3fe"))
LIGHT_BUTTON = Button("Light", Text("Off"), subtitle="0%", state=ButtonState.INACTIVE, id_=UUID("d60e0927-6863-4eb1-a073-f4d2d45899e8"))
GARAGE_PAGE = Page("Garage", [DOOR_BUTTON, LIGHT_BUTTON], id_=UUID("11aa7fbf-853d-40e7-8f6c-7625bfec8736"))

UNUSED_BUTTON = Button("Unused", Icon(Icons.BATH_TUB))
UNUSED_PAGE = Page("unused", [UNUSED_BUTTON], id_=UUID("3e54e203-988a-4bfb-bc7c-b1cb0c950fb7"))


CONFIGURATION = BaseConfiguration(Configuration([DINING_ROOM_PAGE, GARAGE_PAGE], id_=UUID("1b8decea-af8c-4837-9fbc-4261644492df")))
