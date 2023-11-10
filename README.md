# NS Reisinformatie Sensor for Home Assistant

This custom sensor integration provides real-time travel information for train journeys in the Netherlands. It utilizes the NS (Nederlandse Spoorwegen) Reisinformatie API to fetch and display relevant data.

## Installation

1. Add the following link to you hacs installation https://github.com/codayoda36/Ns-home-assistant/tree/master and restart home assistant 

2. Add the following to your `configuration.yaml` file:

    ```yaml
    sensor:
      - platform: ns_reisinformatie
        api_key: YOUR_NS_API_KEY
        min_departure_threshold: 5
        update_frequency: 120
        routes:
          - from_station: "alm"
            to_station: "shl"
            sensor_name: "almere_to_schiphol"
            travel_time: "08:00"
          - from_station: "shl"
            to_station: "alm"
            sensor_name: "schiphol_to_almere"
    ```

## Configuration

### Station Codes:
- `station codes`: For the sations you need to use the sation code you can get those [here](https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland).
- 
### Configuration Options:

- `api_key`: Your NS API key. You can obtain it by [creating an account on the NS API portal](https://apiportal.ns.nl/).
- `min_departure_threshold (Optional)`: Time before the next trip is showen so if this is set to 5 if the train leaves in 5 minutes or less the next train is showen. Default is `5` minutes.
- `update_frequency (Optional)`: Frequency (in seconds) to update the sensor data. Default is `120` seconds.
- `routes`: List of dictionaries representing different routes. Each dictionary should contain the following parameters:

  - `from_station`: Departure station.
  
  - `to_station`: Arrival station.
  
  - `sensor_name`: Name of the sensor.

  - `travel_time (Optional)`: Departure time for the journey.
 
### Sensor Attributes

- `arrival_time_planned`: Planned arrival time at the destination.

- `arrival_time_actual`: Actual arrival time at the destination.

- `departure_time_planned`: Planned departure time from the origin.

- `departure_time_actual`: Actual departure time from the origin.

- `departure_delay`: Departure delay in minutes.

- `arrival_delay`: Arrival delay in minutes.

- `travel_time_actual`: Actual travel time in minutes.

- `travel_time_planned`: Planned travel time in minutes.

- `transfers`: Number of transfers.

- `departure_platform_planned`: Planned departure platform.

- `departure_platform_actual`: Actual departure platform.

- `arrival_platform_planned`: Planned arrival platform.

- `arrival_platform_actual`: Actual arrival platform.

- `status`: Current status of the journey.

- `last_updated`: Time when the sensor was last updated.
