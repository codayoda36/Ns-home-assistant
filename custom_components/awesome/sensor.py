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
TIMEZONE = pytz.timezone("Europe/Amsterdam")

async def async_track_time_interval(hass, interval, action):
    while True:
        await asyncio.sleep(interval)
        await action()

class ExampleSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, hass: HomeAssistant, api_key: str, from_station: str,
        to_station: str, min_departure_threshold: int, sensor_name: str,
        update_frequency: int, travel_time: str, max_transfers: int
    ):
        self._hass = hass
        self._api_key = api_key
        self._from_station = from_station
        self._to_station = to_station
        self._min_departure_threshold = min_departure_threshold
        self._sensor_name = sensor_name
        self._update_frequency = update_frequency
        self._travel_time = self.parse_time(travel_time)
        self._max_transfers = max_transfers

        self._attributes = {
            "arrival_time_planned": "Unknown",
            "arrival_time_actual": "Unknown",
            "departure_time_planned": "Unknown",
            "departure_time_actual": "Unknown",
            "next_planned_time": "Unknown",
            "departure_delay": "Unknown",
            "arrival_delay": "Unknown",
            "travel_time_actual": "Unknown",
            "travel_time_planned": "Unknown",
            "transfers": "Unknown",
            "departure_platform_planned": 0,
            "departure_platform_actual": 0,
            "arrival_platform_planned": 0,
            "arrival_platform_actual": 0,
            "status": "Unknown",
            "last_updated": None,
            "train_type": "Unknown",
            "punctuality": "Unknown",
            "crowd_forecast": "Unknown",
        }

    def parse_time(self, time_str):
        """Parse the time string and return a datetime object."""
        return datetime.strptime(time_str, "%H:%M").time() if time_str else None

    @property
    def name(self):
        return self._sensor_name

    @property
    def native_value(self):
        return self._attributes["departure_time_planned"]

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_added_to_hass(self):
        """Register state update callback."""
        await self.async_update()  # Initial update
        self._state_update_task = async_track_time_interval(self.hass, self._update_frequency, self.async_update)

    async def async_will_remove_from_hass(self):
        """Unregister state update callback."""
        self._state_update_task.cancel()

    async def async_update(self):
        """Fetch new state data for the sensor."""
        current_time = datetime.now(TIMEZONE).time()
        self._attributes["last_updated"] = datetime.now(TIMEZONE).strftime("%H:%M")

        # Check if the current time is within the specified travel time window
        if self.is_within_travel_window(current_time):
            base_url = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"

            params = {
                "fromStation": self._from_station,
                "toStation": self._to_station
            }

            headers = {"Ocp-Apim-Subscription-Key": self._api_key}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(base_url, params=params, headers=headers) as response:
                        if response.status == 200:
                            trip_data = await response.json()
                            next_trip = self.find_next_trip(trip_data)

                            if next_trip:
                                self.update_attributes(next_trip)

                        else:
                            _LOGGER.debug("Error with the API call: %s", await response.text())

            except Exception as e:
                _LOGGER.error("Error making request to NS API: %s", e)

            self.async_write_ha_state()

    def is_within_travel_window(self, current_time):
        """Check if the current time is within the specified travel time window."""
        if self._travel_time:
            travel_time_start = datetime.combine(datetime.now().date(), self._travel_time) - timedelta(minutes=30)
            travel_time_end = datetime.combine(datetime.now().date(), self._travel_time) + timedelta(minutes=30)
            return travel_time_start.time() <= current_time <= travel_time_end.time()
        else:
            return True

    def find_next_trip(self, trip_data):
        """Find the next eligible trip within the data."""
        for trip in trip_data.get('trips', []):
            if self.is_eligible_trip(trip):
                return trip

    def is_eligible_trip(self, trip):
        """Check if a trip is eligible based on criteria."""
        if self._max_transfers is None or (self._max_transfers is not None and trip.get('transfers', 0) <= self._max_transfers):
            leg = trip.get('legs', [])[0]  # Assuming there is only one leg in the trip
            departure_time_planned = datetime.strptime(leg['origin']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
            return departure_time_planned > datetime.now(TIMEZONE).time() + timedelta(minutes=self._min_departure_threshold)
        return False

    def update_attributes(self, trip):
        """Update sensor attributes based on the trip data."""
        leg = trip['legs'][0]  # Assuming there is only one leg in the trip

        self._attributes["arrival_time_planned"] = leg['destination']['plannedDateTime']
        self._attributes["arrival_time_actual"] = leg['destination'].get('actualDateTime', self._attributes["arrival_time_planned"])
        self._attributes["departure_time_planned"] = leg['origin']['plannedDateTime']
        self._attributes["departure_time_actual"] = leg['origin'].get('actualDateTime', self._attributes["departure_time_planned"])
        self._attributes["departure_delay"] = (self._attributes["departure_time_actual"] - self._attributes["departure_time_planned"]).total_seconds() / 60 if self._attributes["departure_time_actual"] else 0
        self._attributes["arrival_delay"] = (self._attributes["arrival_time_actual"] - self._attributes["arrival_time_planned"]).total_seconds() / 60 if self._attributes["arrival_time_actual"] else 0
        self._attributes["travel_time_actual"] = trip.get('actualDurationInMinutes', self._attributes["travel_time_actual"])
        self._attributes["travel_time_planned"] = trip.get('plannedDurationInMinutes', self._attributes["travel_time_planned"])
        self._attributes["status"] = trip.get('status', self._attributes["status"])
        self._attributes["route"] = ' -> '.join([stop['name'] for stop in leg.get('stops', [])])
        self._attributes["train_type"] = leg['product'].get('displayName', self._attributes["train_type"])
        self._attributes["crowd_forecast"] = leg.get('crowdForecast', self._attributes["crowd_forecast"])
        self._attributes["punctuality"] = leg.get('punctuality', self._attributes["punctuality"])
        self._attributes["transfers"] = trip.get('transfers', self._attributes["transfers"])
        self._attributes["departure_platform_planned"] = leg['origin']['plannedTrack']
        self._attributes["departure_platform_actual"] = leg['origin'].get('actualTrack', 'Not available')
        self._attributes["arrival_platform_planned"] = leg['destination']['plannedTrack']
        self._attributes["arrival_platform_actual"] = leg['destination'].get('actualTrack', 'Not available')
        self._attributes["next_planned_time"] = self.find_next_planned_time(trip)

    def find_next_planned_time(self, trip):
        """Find the planned departure time of the next trip after the current one."""
        current_trip_index = trip.get('index', 0)

        while current_trip_index + 1 < len(trip['trips']):
            next_trip_after_current = trip['trips'][current_trip_index + 1]

            if self.is_eligible_trip(next_trip_after_current):
                next_planned_time = datetime.strptime(next_trip_after_current['legs'][0]['origin']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                return next_planned_time.strftime('%H:%M')

            current_trip_index += 1

        return "No routes found after the current one"
