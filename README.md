# hysen

Home Assistant support for Broadlink Hysen thermostat controllers

## Introduction

This repository implements Home Assistant support for Broadlink Hysen
thermostat controllers. Eventual goal is to have the main module
integrated to the Home Assistant project.

Discussion on the module (and the preceding `broadlinkHysen.py` module)
can be found at https://community.home-assistant.io/t/beta-for-hysen-thermostats-powered-by-broadlink/56267/1 .

## Installation

THIS CODE ONLY WORK ON VERSION 0.80 AND ABOVE OF HA

1. Download the hysen directory of files.

As of 0.88 of Home Assistant

2. Copy the `climate.py` file into your home-assistant installation
   'custom_components/hysen' folder.

(NOTE: for earlier HA versions >=0.80, create directory `custom_components/climate`,
 download `climate.py` into it and rename it to `hysen.py`.)

## Configuration

Add something similar to the following in your `configuration.yaml` file:

    climate:
      - platform: hysen
        devices:
          main_thermostat:
            name: Main Thermostat
            host: 192.168.X.X
            mac: "XX:XX:XX:XX:XX:XX"
          secondary_thermostat:
            name: Secondary Thermostat
            mac: "YY:YY:YY:YY:YY:YY"

NOTE : At the moment, you may have to setup the device Wifi connection with
the horrible "Room Heat" app, that was supplied with the device.
In test, if you setup the above with no IP and valid mac, e.g. 30:30:30:30:30:30 the service will fail to load the device, but will setup services that can be called to enable you to setup the device wifi properly.

Once it fails in the log follow the
To get the hysen thermostat in the mode to allow setting of the Wi-fi parameters.
With the device off Press and hold on the“power” button, then press the “time” button
Enter to the advanced setting, then press the “auto” button 9 times until “FAC” appears on the display
Press the “up” button up to “32”, then Press the “power” key, and the thermostat will be shutdown.
Press and hold on the “power” button, then press the “time”, the wifi icon beging flashing WiFi fast flashing show.

From Developer tools in HA select the climate.hysen_config_wifi service enter the JSON {"ssid":"yourssid","password":"yourpassword","sectype":4}
Security mode options are (0 - none, 1 = WEP, 2 = WPA1, 3 = WPA2, 4 = WPA1/2)
run call service, the wifi icon on the device should stop fast flashing and go stable.
In the HA log file you should see "Discovered Broadlink Hysen device : "XX:XX:XX:XX:XX:XX, at 192.xxx.xxx.xxx"
In your router find the thermostat and set it to have a fixed IP, then set it up in your HA config file as host: and mac: above

Please read comments in the climate.py file for more information on services to set parameters and schedule of the thermostat.

### Setting up template sensors

The thermostat doesn't natively expose any sensors, but many can be set up
using Home Assistant templates.

An example follows::

    sensor:
    - platform: template
       sensors:
        house_thermostat_main_house_temp:
         icon_template: mdi:thermometer-lines
         friendly_name: "House Temperature"
         value_template: |
            "{{states.climate.house_thermostat.attributes.current_temperature}}"
         unit_of_measurement: "°C"
        house_thermostat_heating_state:
         icon_template: mdi:fire
         friendly_name: "Heating Demand"
         value_template: |
            "{% if states.climate.house_thermostat.attributes.heating_active == 1 %}On{% else %}Off{% endif %}"
        house_thermostat_auto_override:
         icon_template: mdi:flash-outline
         friendly_name: "Auto Override"
         value_template: "{% if states.climate.house_thermostat.attributes.auto_override == 1 %}On{% else %}Off{% endif %}"
        house_thermostat_externalsensortemp:
         icon_template: mdi:thermometer-lines
         friendly_name: "External Sensor Temp"
         value_template: "{{states.climate.house_thermostat.attributes.external_temp}}"
         unit_of_measurement: "°C"

### Setting up template switches

Like sensors, device configuration attributes can be exposed via templates::

      switch:
      - platform: template
         switches:
           thermostat_remote_lock:
              friendly_name: Keypad Lock
              value_template: "{{ is_state_attr('climate.house_thermostat', 'remote_lock', 1) }}"
              turn_on:
                service: climate.hysen_set_remotelock
                data:
                  entity_id: climate.house_thermostat
                  remotelock: 1
              turn_off:
                service: climate.hysen_set_remotelock
                data:
                  entity_id: climate.house_thermostat
                  remotelock: 0
