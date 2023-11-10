import asyncio
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
    api_key = config.get("api_key", "")
    from_station = config.get("from_station", "")
    to_station = config.get("to_station", "")
    min_departure_threshold = config.get("min_departure_threshold", 5)
    sensor_name = config.get("sensor_name", "")

    add_entities([ExampleSensor(hass, api_key, from_station, to_station, min_departure_threshold, sensor_name)])

class ExampleSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, hass: HomeAssistant, api_key: str, from_station: str, to_station: str, min_departure_threshold: int, sensor_name: str):
        self._hass = hass
        self._api_key = api_key
        self._from_station = from_station
        self._to_station = to_station
        self._min_departure_threshold = min_departure_threshold
        self._sensor_name = sensor_name

        self._arrival_time_planned_attribute = None
        self._arrival_time_actual_attribute = None
        self._departure_time_planned_attribute = None
        self._departure_time_actual_attribute = None
        self._next_planned_time_attribute = None
        self._departure_delay_attribute = None
        self._arrival_delay_attribute = None
        self._travel_time_attribute = None 
        self._transfers_attribute = None
        self._departure_platform_planned_attribute = 0
        self._departure_platform_actual_attribute = 0
        self._arrival_platform_planned_attribute = 0
        self._arrival_platform_actual_attribute = 0
        self._last_updated = datetime.now(pytz.timezone("Europe/Amsterdam")).strftime("%H:%M")

    @property
    def name(self):
        return self._sensor_name

    @property
    def native_value(self):
        return 23

    @property
    def extra_state_attributes(self):
        attributes = {
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
            "last_updated": self._last_updated,
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
            "fromStation": self._from_station,
            "toStation": self._to_station
            # Add more parameters as needed
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key
            # Replace YOUR_SUBSCRIPTION_KEY with your actual subscription key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        trip_data = await response.json()

                        current_time = datetime.now(pytz.timezone("Europe/Amsterdam"))

                        for trip in trip_data['trips']:
                            leg = trip['legs'][0]  # Assuming there is only one leg in the trip
                            departure_time_planned = datetime.strptime(leg['origin']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                            departure_time_actual = datetime.strptime(leg['origin']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['origin'] else departure_time_planned
                            
                            arrival_time_planned = datetime.strptime(leg['destination']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                            arrival_time_actual = datetime.strptime(leg['destination']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['destination'] else self._arrival_time_planned_attribute

                            if departure_time_planned > current_time + timedelta(minutes=self._min_departure_threshold):
                                next_trip = trip
                                break
                        
                        if 'next_trip' in locals():
                            self._arrival_time_planned_attribute = arrival_time_planned.strftime("%H:%M")
                            self._arrival_time_actual_attribute = arrival_time_actual.strftime("%H:%M")

                            self._departure_time_planned_attribute = departure_time_planned.strftime("%H:%M")
                            self._departure_time_actual_attribute = departure_time_actual.strftime("%H:%M")

                            self._departure_delay_attribute = (departure_time_actual - departure_time_planned).total_seconds() / 60 if departure_time_actual else None
                            self._arrival_delay_attribute = (arrival_time_actual - arrival_time_planned).total_seconds() / 60 if arrival_time_actual else None
                            self._travel_time_attribute = (arrival_time_actual - departure_time_actual).total_seconds() / 60 if arrival_time_actual and departure_time_actual else None

                            self._transfers_attribute = trip['transfers']
                            self._departure_platform_planned_attribute = leg['origin']['plannedTrack']
                            self._departure_platform_actual_attribute = leg['origin']['actualTrack'] if 'actualTrack' in leg['origin'] else 'Not available'
                            self._departure_platform_planned_attribute = leg['destination']['plannedTrack']
                            self._departure_platform_actual_attribute = leg['destination']['actualTrack'] if 'actualTrack' in leg['destination'] else 'Not available'
                            self._last_updated = datetime.now(pytz.timezone("Europe/Amsterdam")).strftime("%H:%M")

                    else:
                        _LOGGER.debug("Error with the api call: %s", await response.text())

        except Exception as e:
            _LOGGER.error("Error making request to NS API: %s", e)
        
        self.async_write_ha_state()
