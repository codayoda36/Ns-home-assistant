import asyncio
import random
import logging
from datetime import datetime, timedelta
import pytz
import aiohttp
from homeassistant.components.sensor import SensorEntity
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
    add_entities([ExampleSensor(hass)])

class ExampleSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_name = "Examplesensor"

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        # self._test_attribute = random.choice("abcdefghijklmnopqrstuvwxyz")
        self._arrival_time_planned_attribute = None
        self._arrival_time_actual_attribute = None
        self._departure_time_planned_attribute = None
        self._departure_time_actual_attribute = None
        self._next_planned_time_attribute = None
        self._departure_delay_attribute = None
        self._arrival_delay_attribute = None
        self._travel_time_attribute = None 
        self._transfers_attribute = None
        self._departure_platform_planned_attribute = None
        self._departure_platform_actual_attribute = None
        self._arrival_platform_planned_attribute = None
        self._arrival_platform_actual_attribute = None

    @property
    def name(self):
        return "Examplesensor"

    @property
    def native_value(self):
        return 23

    @property
    def extra_state_attributes(self):
        attributes = {
            # "testAttribute": self._test_attribute,
            "arrival_time_planned": self._arrival_time_planned_attribute,
            "arrival_time_actual": self._arrival_time_actual_attribute,
            "departure_time_planned": self._departure_time_planned_attribute,
            "departure_time_actual": self._departure_time_actual_attribute,
            "departure_delay": self._departure_delay_attribute,
            "arrival_delay": self._arrival_delay_attribute,
            "travel_time": self._travel_time_attribute,
            "tranfers": self._transfers_attribute,
            "departure_platform_planned": self._departure_platform_planned_attribute,
            "departure_platform_actual": self._departure_platform_actual_attribute,
            "arrival_platform_planned": self._arrival_platform_planned_attribute,
            "arrival_platform_actual": self._arrival_platform_actual_attribute,
        }
        return attributes

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._state_update_task = async_track_time_interval(self.hass, 30, self.async_update)

    async def async_will_remove_from_hass(self):
        """Unregister state update callback."""
        self._state_update_task.cancel()

    async def async_update(self):
        """Fetch new state data for the sensor."""
        base_url = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"

        params = {
            "fromStation": "alm",
            "toStation": "shl"
            # Add more parameters as needed
        }
        headers = {
            "Ocp-Apim-Subscription-Key": "8437a73330144f1b82320e22b351af61"
            # Replace YOUR_SUBSCRIPTION_KEY with your actual subscription key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        trip_data = await response.json()

                        min_departure_threshold = 5  # Minimum departure time threshold in minutes
                        current_time = datetime.now(pytz.timezone("Europe/Amsterdam"))

                        for trip in trip_data['trips']:
                            leg = trip['legs'][0]  # Assuming there is only one leg in the trip
                            departure_time_planned = datetime.strptime(leg['origin']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                            departure_time_actual = datetime.strptime(leg['origin']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['origin'] else departure_time_planned

                            if departure_time_planned > current_time + timedelta(minutes=min_departure_threshold):
                                next_trip = trip
                                break
                        
                        if 'next_trip' in locals():
                            self._arrival_time_planned_attribute = datetime.strptime(leg['destination']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                            self._arrival_time_actual_attribute = datetime.strptime(leg['destination']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['destination'] else self._arrival_time_planned_attribute

                            self._departure_time_planned_attribute = departure_time_planned
                            self._departure_time_actual_attribute = departure_time_actual

                            self._departure_delay_attribute = (departure_time_actual - departure_time_planned).total_seconds() / 60 if departure_time_actual else None
                            self._arrival_delay_attribute = (self._arrival_time_actual_attribute - self._arrival_time_planned_attribute).total_seconds() / 60 if self._arrival_time_actual_attribute else None
                            self._travel_time_attribute = (self._arrival_time_actual_attribute - departure_time_actual).total_seconds() / 60 if self._arrival_time_actual_attribute and departure_time_actual else None

                            self._transfers_attribute = trip['transfers']
                            self._departure_platform_planned_attribute = leg['origin']['plannedTrack']
                            self._departure_platform_actual_attribute = leg['origin']['actualTrack'] if 'actualTrack' in leg['origin'] else 'Not available'
                            self._departure_platform_planned_attribute = leg['destination']['plannedTrack']
                            self._departure_platform_actual_attribute = leg['destination']['actualTrack'] if 'actualTrack' in leg['destination'] else 'Not available'
                            # self._test_attribute = random.choice("abcdefghijkl")
                    else:
                        _LOGGER.debug("Error with the api call: %s", await response.text())

        except Exception as e:
            _LOGGER.error("Error making request to NS API: %s", e)
            self._test_attribute = "error"
        
        self.async_write_ha_state()
