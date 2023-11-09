import logging
from datetime import datetime, timedelta
import pytz
import requests

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    api_key = config.get("api_key")
    from_station = config.get("from_station")
    to_station = config.get("to_station")
    via_station = config.get("via_station")

    add_entities([NsTripsSensor(api_key, from_station, to_station, via_station)])


class NsTripsSensor(Entity):
    def __init__(self, api_key, from_station, to_station, via_station=None):
        self._api_key = api_key
        self._from_station = from_station
        self._to_station = to_station
        self._via_station = via_station
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return "ns_trips_sensor"

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return self._attributes

    def update(self):
        base_url = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"

        params = {
            "fromStation": self._from_station,
            "toStation": self._to_station,
            "viaStation": self._via_station
            # Add more parameters as needed
        }

        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key
        }

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

                    if departure_time_planned > current_time + timedelta(minutes=min_departure_threshold):
                        next_trip = trip
                        break

                if 'next_trip' in locals():
                    arrival_time_planned = datetime.strptime(leg['destination']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z")
                    arrival_time_actual = datetime.strptime(leg['destination']['actualDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'actualDateTime' in leg['destination'] else None
                    next_planned_time = datetime.strptime(leg['nextExpected']['plannedDateTime'], "%Y-%m-%dT%H:%M:%S%z") if 'nextExpected' in leg else None

                    departure_delay = (departure_time_actual - departure_time_planned).total_seconds() / 60 if departure_time_actual else None
                    arrival_delay = (arrival_time_actual - arrival_time_planned).total_seconds() / 60 if arrival_time_actual else None
                    travel_time = (arrival_time_actual - departure_time_actual).total_seconds() / 60 if arrival_time_actual and departure_time_actual else None

                    transfers = trip['transfers']
                    departure_platform_planned = leg['origin']['plannedTrack']
                    departure_platform_actual = leg['origin']['actualTrack'] if 'actualTrack' in leg['origin'] else 'Not available'
                    arrival_platform_planned = leg['destination']['plannedTrack']
                    arrival_platform_actual = leg['destination']['actualTrack'] if 'actualTrack' in leg['destination'] else 'Not available'

                    self._state = "Next Trip"
                    self._attributes = {
                        "departure_time_planned": departure_time_planned.strftime('%H:%M'),
                        "departure_time_actual": departure_time_actual.strftime('%H:%M') if departure_time_actual else 'Not available',
                        "departure_delay": departure_delay,
                        "departure_platform_planned": departure_platform_planned,
                        "departure_platform_actual": departure_platform_actual,
                        "arrival_time_planned": arrival_time_planned.strftime('%H:%M'),
                        "arrival_time_actual": arrival_time_actual.strftime('%H:%M') if arrival_time_actual else 'Not available',
                        "arrival_delay": arrival_delay,
                        "arrival_platform_planned": arrival_platform_planned,
                        "arrival_platform_actual": arrival_platform_actual,
                        "next": next_planned_time.strftime('%H:%M') if next_planned_time else 'Not available',
                        "transfers": transfers,
                        "route": ' -> '.join([stop['name'] for stop in leg['stops']])
                    }

                else:
                    self._state = "No upcoming trips"
                    self._attributes = {}

            else:
                _LOGGER.error(f"Error {response.status_code}: {response.text}")

        except Exception as e:
            _LOGGER.error(f"An error occurred: {e}")
