from __future__ import annotations

from datetime import datetime, timedelta
import logging

import ns_api
from ns_api import RequestParametersError
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

CONF_ROUTES = "routes"
CONF_FROM = "from"
CONF_TO = "to"
CONF_VIA = "via"
CONF_TIME = "time"

ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_VIA): cv.string,
        vol.Optional(CONF_TIME): cv.time,
    }
)

ROUTES_SCHEMA = vol.All(cv.ensure_list, [ROUTE_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Optional(CONF_ROUTES): ROUTES_SCHEMA}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor."""

    nsapi = ns_api.NSAPI(config[CONF_API_KEY])

    try:
        stations = nsapi.get_stations()
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
    ) as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise PlatformNotReady() from error
    except RequestParametersError as error:
        _LOGGER.error("Could not fetch stations, please check configuration: %s", error)
        return

    sensors = []
    for departure in config.get(CONF_ROUTES, {}):
        if not valid_stations(
            stations,
            [departure.get(CONF_FROM), departure.get(CONF_VIA), departure.get(CONF_TO)],
        ):
            continue
        sensors.append(
            NSDepartureSensor(
                hass,  # Pass the Home Assistant instance
                nsapi,
                departure.get(CONF_NAME),
                departure.get(CONF_FROM),
                departure.get(CONF_TO),
                departure.get(CONF_VIA),
                departure.get(CONF_TIME),
            )
        )
    add_entities(sensors, True)


def valid_stations(stations, given_stations):
    """Verify the existence of the given station codes."""
    for station in given_stations:
        if station is None:
            continue
        if not any(s.code == station.upper() for s in stations):
            _LOGGER.warning("Station '%s' is not a valid station", station)
            return False
    return True


class NSDepartureSensor(SensorEntity):
    """Implementation of a NS Departure Sensor."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"

    def __init__(self, hass, nsapi, name, departure, heading, via, time):
        """Initialize the sensor."""
        self.hass = hass
        self._nsapi = nsapi
        self._name = name
        self._departure = departure
        self._via = via
        self._heading = heading
        self._time = time
        self._state = None
        self._trips = None
        self.entity_id = f"sensor.ns_departure_{name.lower().replace(' ', '_')}"
        self.update_manager = NSDepartureSensorUpdateManager(self)

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

    async def async_update(self) -> None:
        """Async update method."""
        await self.update_manager.async_refresh()

class NSDepartureSensorUpdateManager(DataUpdateCoordinator):
    """NS Departure Sensor Update Manager."""

    def __init__(self, sensor):
        """Initialize the update manager."""
        self.sensor = sensor
        update_interval = timedelta(minutes=1)
        super().__init__(
            sensor.hass,
            _LOGGER,
            name=f"NS Departure Sensor Update Manager - {sensor.name}",
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from the sensor."""
        await self.sensor._async_update()
        return self.sensor._trips

def update_callback(self, data):
    """Update callback for the NS Departure Sensor Update Manager."""
    self._trips = data
    if self._trips is not None:  # Check if _trips is not None
        if self._trips[0].departure_time_actual is None:
            planned_time = self._trips[0].departure_time_planned
            self._state = planned_time.strftime("%H:%M")
        else:
            actual_time = self._trips[0].departure_time_actual
            self._state = actual_time.strftime("%H:%M")

# ... (remaining code)
