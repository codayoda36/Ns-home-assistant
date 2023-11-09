from datetime import datetime, timedelta
import requests
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle
import voluptuous as vol

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the departure sensor."""
    api_key = config[CONF_API_KEY]

    sensors = []
    for departure in config.get(CONF_ROUTES, {}):
        sensors.append(
            NSDepartureSensor(
                api_key,
                departure.get(CONF_NAME),
                departure.get(CONF_FROM),
                departure.get(CONF_TO),
                departure.get(CONF_VIA),
                departure.get(CONF_TIME),
            )
        )
    add_entities(sensors, True)


class NSDepartureSensor(SensorEntity):
    """Implementation of a NS Departure Sensor."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"

    def __init__(self, api_key, name, departure, heading, via, time):
        """Initialize the sensor."""
        self._api_key = api_key
        self._name = name
        self._departure = departure
        self._via = via
        self._heading = heading
        self._time = time
        self._state = None
        self._trips = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self._trips:
            return

        if self._trips[0].trip_parts:
            route = [self._trips[0].departure]
            for k in self._trips[0].trip_parts:
                route.append(k.destination)

        # Static attributes
        attributes = {
            "going": self._trips[0].going,
            "departure_time_planned": None,
            "departure_time_actual": None,
            "departure_delay": False,
            "departure_platform_planned": self._trips[0].departure_platform_planned,
            "departure_platform_actual": self._trips[0].departure_platform_actual,
            "arrival_time_planned": None,
            "arrival_time_actual": None,
            "arrival_delay": False,
            "arrival_platform_planned": self._trips[0].arrival_platform_planned,
            "arrival_platform_actual": self._trips[0].arrival_platform_actual,
            "next": None,
            "status": self._trips[0].status.lower(),
            "transfers": self._trips[0].nr_transfers,
            "route": route,
            "remarks": None,
        }

        # Planned departure attributes
        if self._trips[0].departure_time_planned is not None:
            attributes["departure_time_planned"] = self._trips[
                0
            ].departure_time_planned.strftime("%H:%M")

        # Actual departure attributes
        if self._trips[0].departure_time_actual is not None:
            attributes["departure_time_actual"] = self._trips[
                0
            ].departure_time_actual.strftime("%H:%M")

        # Delay departure attributes
        if (
            attributes["departure_time_planned"]
            and attributes["departure_time_actual"]
            and attributes["departure_time_planned"]
            != attributes["departure_time_actual"]
        ):
            attributes["departure_delay"] = True

        # Planned arrival attributes
        if self._trips[0].arrival_time_planned is not None:
            attributes["arrival_time_planned"] = self._trips[
                0
            ].arrival_time_planned.strftime("%H:%M")

        # Actual arrival attributes
        if self._trips[0].arrival_time_actual is not None:
            attributes["arrival_time_actual"] = self._trips[
                0
            ].arrival_time_actual.strftime("%H:%M")

        # Delay arrival attributes
        if (
            attributes["arrival_time_planned"]
            and attributes["arrival_time_actual"]
            and attributes["arrival_time_planned"] != attributes["arrival_time_actual"]
        ):
            attributes["arrival_delay"] = True

        # Next attributes
        if len(self._trips) > 1:
            if self._trips[1].departure_time_actual is not None:
                attributes["next"] = self._trips[1].departure_time_actual.strftime(
                    "%H:%M"
                )
            elif self._trips[1].departure_time_planned is not None:
                attributes["next"] = self._trips[1].departure_time_planned.strftime(
                    "%H:%M"
                )

        return attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the trip information."""
        current_time = datetime.now()
        min_departure_threshold = 5  # Minimum departure time threshold in minutes

        # Check if the current time is less than 5 minutes before the specified departure time
        if self._trips and self._trips[0].departure_time_actual:
            actual_departure_time = self._trips[0].departure_time_actual
            time_difference = actual_departure_time - current_time

            if time_difference.total_seconds() / 60 <= min_departure_threshold:
             # If the departure is within the threshold, update the state to None and return
                self._state = None
                self._trips = None
                return

        # Set the search parameter to search from a specific trip time or to just search for the next trip.
        if self._time:
            trip_time = (
                datetime.today()
                .replace(hour=self._time.hour, minute=self._time.minute)
                .strftime("%d-%m-%Y %H:%M")
            )
        else:
            trip_time = datetime.now().strftime("%d-%m-%Y %H:%M")

        try:
            self._trips = self._nsapi.get_trips(
               trip_time, self._departure, self._via, self._heading, True, 0, 2
            )
            if self._trips:
                if self._trips[0].departure_time_actual is None:
                    planned_time = self._trips[0].departure_time_planned
                    self._state = planned_time.strftime("%H:%M")
                else:
                    actual_time = self._trips[0].departure_time_actual
                    self._state = actual_time.strftime("%H:%M")
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as error:
            _LOGGER.error("Couldn't fetch trip info: %s", error)
