"""Custom sensor for Home Assistant."""

from homeassistant.helpers.entity import Entity

DOMAIN = "example_sensor"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    async_add_entities([MyCustomSensor()])

class MyCustomSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None
        self._attribute1 = None
        self._attribute2 = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "My Custom Sensor"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "attribute1": self._attribute1,
            "attribute2": self._attribute2
        }

    def update(self):
        """Fetch new state data for the sensor."""
        # Update the state and attributes here
        self._state = "New State"
        self._attribute1 = "Value 1"
        self._attribute2 = "Value 2"
