# hysen

Home Assistant support for Broadlink Hysen thermostat controllers

## Introduction

This repository implements Home Assistant support for Broadlink Hysen
thermostat controllers. Eventual goal is to have the main module
integrated to the Home Assistant project.

Discussion on the module (and the preceding `broadlinkHysen.py` module)
can be found at https://community.home-assistant.io/t/beta-for-hysen-thermostats-powered-by-broadlink/56267/1 .

## Installation

1. Download the `hysen.py` file.
2. Copy the file into your home-assistant installation 
   `custom_components/climate` folder.

## Configuration

At the moment, you have to setup the device Wifi connection with
the horrible "Room Heat" app. Good luck with that. :-(

Once you can successfully access the device with the app,
add the following in your `configuration.yaml` file:

    - platform: hysen
      name: Main Thermostat
      host: 192.168.X.X
      mac: "XX:XX:XX:XX:XX:XX"

If you are using the device with an external temperature sensor, add the following:

    use_external_sensor: true

