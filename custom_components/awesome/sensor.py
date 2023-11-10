import asyncio
import random
import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

async def async_track_time_interval(hass, interval, action):
    while True:
        await asyncio.sleep(interval)
        await action()

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    add_entities([ExampleSensor()])


class ExampleSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Examplesensor"

    _test_attribute = random.choice("abcdefghijklmnopqrstuvwxyz")

    @property
    def name(self):
        return "Examplesensor"

    @property
    def native_value(self):
        return 23

    @property
    def extra_state_attributes(self):
        attributes = {
            "testAttirbute": self._test_attribute,
        }
        return attributes

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._state_update_task = async_track_time_interval(self.hass, 30, self.async_update)

    async def async_will_remove_from_hass(self):
        """Unregister state update callback."""
        self._state_update_task.cancel()

    async def async_update(self):
        """Fetch new state data for the sensor.
        _LOGGER.debug("Updating atributes")
        This is the only method that should fetch new data for Home Assistant.
        """
        base_url = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"

        params = {
            "fromStation": "alm",
            "toStation": "shl"
            # Add more parameters as needed
        }
        _LOGGER.debug("Setting params")
        headers = {
            "Ocp-Apim-Subscription-Key": "8437a73330144f1b82320e22b351af61"
            # Replace YOUR_SUBSCRIPTION_KEY with your actual subscription key
        }
        _LOGGER.debug("Setting headers")

        try:
            response = requests.get(base_url, params=params, headers=headers)

            if response.status_code == 200:
                trip_data = response.json()

                min_departure_threshold = 5  # Minimum departure time threshold in minutes
                current_time = datetime.now(pytz.timezone("Europe/Amsterdam"))

                for trip in trip_data['trips']:
                    leg = trip['legs'][0]  # Assuming there is only one leg in the trip
                    departure_time_planned = datetime.strptime(leg['origin']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                    departure_time_actual = datetime.strptime(leg['origin']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['origin'] else None

                    _LOGGER.debug("Setting attribute value")
                    self._test_attribute = random.choice("abcdefghijkl")
            else:
                _LOGGER.debug("Error with the api call: %s", response.text)

        except Exception as e:
            _LOGGER.debug("A exception occured: %s", e)
            self._test_attribute = random.choice("mnopqrstuvwxyz")
        self.async_write_ha_state()
