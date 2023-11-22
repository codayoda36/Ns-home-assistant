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
    min_departure_threshold = config.get("min_departure_threshold", 5)
    update_frequency = config.get("update_frequency", 120)
    max_trips_showen = config.get("max_trips_showen", 3)
    trips_based_on_departure_time_actual = config.get("trips_based_on_departure_time_actual", True) 
    routes = config.get("routes", [])

    sensors = []
    for route in routes:
        from_station = route.get("from_station", "")
        to_station = route.get("to_station", "")
        sensor_name = route.get("sensor_name", "")
        start_time = route.get("start_time")
        end_time = route.get("end_time")
        sensors.append(ExampleSensor(hass, api_key, from_station, to_station, min_departure_threshold, sensor_name, update_frequency, max_trips_showen, trips_based_on_departure_time_actual, start_time, end_time))


    add_entities(sensors)

class ExampleSensor(SensorEntity):
    """Representation of a Sensor."""
    _common_attribute_names = [
        "last_updated",
        "trips_showen",
    ]

    _unique_attribute_names = [
        "arrival_time_planned",
        "arrival_time_actual",
        "departure_time_planned",
        "departure_time_actual",
        "departure_delay",
        "arrival_delay",
        "travel_time_actual",
        "travel_time_planned",
        "transfers",
        "departure_platform_planned",
        "departure_platform_actual",
        "arrival_platform_planned",
        "arrival_platform_actual",
        "status",
        "train_type",
        "punctuality",
        "crowd_forecast",
        "route",
    ]

    def __init__(self, hass: HomeAssistant, api_key: str, from_station: str, to_station: str, min_departure_threshold: int, sensor_name: str, update_frequency: int, max_trips_showen: int, trips_based_on_departure_time_actual: bool, start_time: str, end_time: str):
        #Setup config values
        self._hass = hass
        self._api_key = api_key
        self._from_station = from_station
        self._to_station = to_station
        self._min_departure_threshold = min_departure_threshold
        self._sensor_name = sensor_name
        self._update_frequency = update_frequency
        self._max_trips_showen = max_trips_showen
        self._trips_based_on_departure_time_actual = trips_based_on_departure_time_actual
        self._start_time = start_time
        self._end_time = end_time

        #Setup the attributes for the sensor
        self._route_attribute_names = [f"route_trip_{i}" for i in range(1, self._max_trips_showen + 1)]

    def initialize_attributes(self):
        for attr_name in self._common_attribute_names:
            setattr(self, f"_{attr_name}_attribute", None)

        for route_num in range(1, self._max_trips_showen + 1):
            for attr_name in self._unique_attribute_names:
                setattr(self, f"{attr_name}_trip_{route_num}", "Undefined")

    @property
    def name(self):
        return self._sensor_name

    @property
    def native_value(self):
        return self._last_updated_attribute

    @property
    def extra_state_attributes(self):
        attributes = {}
        for attr_name in self._common_attribute_names:
            attributes[attr_name] = getattr(self, f"_{attr_name}_attribute")

        for route_num in range(1, self._max_trips_showen + 1):
            for attr_name in self._unique_attribute_names:
                attributes[f"{attr_name}_trip_{route_num}"] = getattr(self, f"{attr_name}_trip_{route_num}")

        return attributes

    def set_attribute(self, attr_name, value):
        setattr(self, f"_{attr_name}_attribute", value)

    def set_route_attribute(self, route_num, attr_name, value):
        setattr(self, f"{attr_name}_trip_{route_num}", value)

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.initialize_attributes()
        self._state_update_task = async_track_time_interval(self.hass, self._update_frequency, self.async_update)

    async def async_will_remove_from_hass(self):
        """Unregister state update callback."""
        self._state_update_task.cancel()

    def _is_within_time_range(self):
        """Check if the current time is within the specified range."""
        if not self._start_time or not self._end_time:
            # If start time or end time is not defined, always return True
            return True

        current_time = datetime.now(pytz.timezone("Europe/Amsterdam")).strftime("%H:%M")
        return self._start_time <= current_time <= self._end_time

    async def async_update(self):
        """Fetch new state data for the sensor."""
        base_url = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"

        params = {
            "fromStation": self._from_station,
            "toStation": self._to_station
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key
        }

        try:
            if not self._is_within_time_range():
                _LOGGER.debug(
                    "Skipping update for %s. Current time is outside the specified range.",
                    self._sensor_name,
                )
                return
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        trip_data = await response.json()

                        # Function to format time
                        def format_time(time_str):
                            return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")
            
                        next_trip = None
                        tripNumber = 0

                        for i, trip in enumerate(trip_data['trips']):
                            leg = trip['legs'][0]  # Assuming there is only one leg in the trip

                            departure_time_planned = format_time(leg['origin']['plannedDateTime'])
                            departure_time_actual = format_time(leg['origin']['actualDateTime']) if 'actualDateTime' in leg['origin'] else departure_time_planned

                            if self._trips_based_on_departure_time_actual:
                                if departure_time_actual > datetime.now(pytz.timezone("Europe/Amsterdam")) + timedelta(minutes=self._min_departure_threshold):
                                    next_trip = trip
                                    break
                            else:
                                if departure_time_planned > datetime.now(pytz.timezone("Europe/Amsterdam")) + timedelta(minutes=self._min_departure_threshold):
                                    next_trip = trip
                                    break

                        if next_trip:
                            # Get the index of the current trip
                            current_trip_index = trip_data['trips'].index(next_trip)
                            
                            self.set_attribute("last_updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            self.set_attribute("trips_showen", self._max_trips_showen)

                            # Display information for the next trips
                            for i, trip in enumerate(trip_data['trips'][current_trip_index:]):
                                if self._max_trips_showen and i >= self._max_trips_showen:
                                    break

                                tripNumber = tripNumber + 1
                                leg = trip['legs'][0]

                                departure_time_planned = format_time(leg['origin']['plannedDateTime'])
                                departure_time_actual = format_time(leg['origin']['actualDateTime']) if 'actualDateTime' in leg['origin'] else departure_time_planned

                                arrival_time_planned = format_time(leg['destination']['plannedDateTime'])
                                arrival_time_actual = format_time(leg['destination']['actualDateTime']) if 'actualDateTime' in leg['destination'] else arrival_time_planned

                                actual_duration_in_minutes = trip.get('actualDurationInMinutes')
                                planned_duration_in_minutes = trip.get('plannedDurationInMinutes')

                                # Update attributes for the current route
                                self.set_route_attribute(tripNumber, "departure_time_planned", departure_time_planned.strftime('%H:%M'))
                                self.set_route_attribute(tripNumber, "departure_time_actual", departure_time_actual.strftime('%H:%M'))
                                self.set_route_attribute(tripNumber, "departure_delay", (departure_time_actual - departure_time_planned).total_seconds() / 60 if departure_time_actual else None)
                                self.set_route_attribute(tripNumber, "departure_platform_planned", leg['origin']['plannedTrack'])
                                self.set_route_attribute(tripNumber, "departure_platform_actual", leg['origin']['actualTrack'] if 'actualTrack' in leg['origin'] else 'Not available')

                                self.set_route_attribute(tripNumber, "arrival_time_planned", arrival_time_planned.strftime('%H:%M'))
                                self.set_route_attribute(tripNumber, "arrival_time_actual", arrival_time_actual.strftime('%H:%M'))
                                self.set_route_attribute(tripNumber, "arrival_delay", (arrival_time_actual - arrival_time_planned).total_seconds() / 60 if arrival_time_actual else None)
                                self.set_route_attribute(tripNumber, "arrival_platform_planned", leg['destination']['plannedTrack'])
                                self.set_route_attribute(tripNumber, "arrival_platform_actual", leg['destination']['actualTrack'] if 'actualTrack' in leg['destination'] else 'Not available')

                                self.set_route_attribute(tripNumber, "travel_time_planned", planned_duration_in_minutes)
                                self.set_route_attribute(tripNumber, "travel_time_actual", actual_duration_in_minutes)

                                self.set_route_attribute(tripNumber, "transfers", trip['transfers'])
                                self.set_route_attribute(tripNumber, "status", trip.get('status'))
                                self.set_route_attribute(tripNumber, "train_type", leg['product'].get('displayName', ''))
                                self.set_route_attribute(tripNumber, "punctuality", leg.get('punctuality'))
                                self.set_route_attribute(tripNumber, "crowd_forecast", leg.get('crowdForecast'))
                                self.set_route_attribute(tripNumber, "route", [stop['name'] for stop in leg['stops']])


                        else:
                            print(f"No upcoming trips from {self._from_station} to {self._to_station}.")        

                    else:
                       _LOGGER.debug("Error with the api call: %s", await response.text())    
        except Exception as e:
                _LOGGER.error("Error making request to NS API: %s", e)
