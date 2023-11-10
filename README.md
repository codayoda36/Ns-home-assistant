# NS Reisinformatie Sensor for Home Assistant

This custom sensor integration provides real-time travel information for train journeys in the Netherlands. It utilizes the NS (Nederlandse Spoorwegen) Reisinformatie API to fetch and display relevant data.

## Installation

1. Copy the `custom_components` folder to your Home Assistant configuration directory.

    ```
    /config
    ├── custom_components
    │   └── ns_reisinformatie
    │       └── __init__.py
    │       └── sensor.py
    ```

2. Add the following to your `configuration.yaml` file:

    ```yaml
    sensor:
      - platform: ns_reisinformatie
        api_key: YOUR_NS_API_KEY
        min_departure_threshold: 5
        update_frequency: 120
        routes:
          - from_station: "Amsterdam"
            to_station: "Utrecht"
            sensor_name: "amsterdam_to_utrecht"
            travel_time: "08:00"
          - from_station: "Utrecht"
            to_station: "Amsterdam"
            sensor_name: "utrecht_to_amsterdam"
    ```

## Configuration

### Required Configuration Options:

- `api_key`: Your NS API key. You can obtain it by [creating an account on the NS API portal](https://apiportal.ns.nl/).

### Optional Configuration Options:

- `min_departure_threshold`: Minimum time (in minutes) before departure to start fetching data. Default is `5` minutes.

- `update_frequency`: Frequency (in seconds) to update the sensor data. Default is `120` seconds.

- `routes`: List of dictionaries representing different routes. Each dictionary should contain the following mandatory parameters:

  - `from_station`: Departure station.
  
  - `to_station`: Arrival station.
  
  - `sensor_name`: Name of the sensor.

  - `travel_time`: Departure time for the journey (optional).

### Example Configuration:

```yaml
sensor:
  - platform: ns_reisinformatie
    api_key: YOUR_NS_API_KEY
    min_departure_threshold: 5
    update_frequency: 120
    routes:
      - from_station: "Amsterdam"
        to_station: "Utrecht"
        sensor_name: "amsterdam_to_utrecht"
        travel_time: "08:00"
      - from_station: "Utrecht"
        to_station: "Amsterdam"
        sensor_name: "utrecht_to_amsterdam"
