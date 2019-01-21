"""
Platform for Hysen Electronic heating Thermostats power by broadlink.
(Beok, Floureon, Decdeal) 
discussed in https://community.home-assistant.io/t/floor-heat-thermostat/29908
21/01/2019"""

import logging
import binascii
import socket
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import inspect
import datetime 

#*****************************************************************************************************************************
# Example Homeassitant Config

#climate:
#  - platform: hysen
#    name: House Thermostat
#    host: 192.168.0.201
#    mac: '34:EA:34:87:5B:7B'
#    target_temp_default: 20
#    target_temp_step: 0.5
#    scan_interval: 15
#    sync_clock_time_per_day: True
#    update_timeout:5

#- platform: template
#   sensors:
#    house_thermostat_mainhousetemp:
#     icon_template: mdi:thermometer-lines
#     friendly_name: "House Temprature"
#     value_template: "{{states.climate.house_thermostat.attributes.current_temperature}}"
#     unit_of_measurement: "°C"
#    house_thermostat_heating_state:
#     icon_template: mdi:fire
#     friendly_name: "Heating Demand"
#     value_template: "{% if states.climate.house_thermostat.attributes.heating_active == 1 %}On{% else %}Off{% endif %}"
#    house_thermostat_auto_override:
#     icon_template: mdi:flash-outline
#     friendly_name: "Auto Override"
#     value_template: "{% if states.climate.house_thermostat.attributes.auto_override == 1 %}On{% else %}Off{% endif %}"
#    house_thermostat_externalsensortemp:
#     icon_template: mdi:thermometer-lines
#     friendly_name: "External Sensor Temp"
#     value_template: "{{states.climate.house_thermostat.attributes.external_temp}}"
#     unit_of_measurement: "°C"
#*****************************************************************************************************************************

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE,
                                              ATTR_TEMPERATURE,
                                              SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF)

from homeassistant.const import (ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT,
                                 CONF_NAME, CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_CUSTOMIZE,STATE_OFF,STATE_ON)

REQUIREMENTS = ['broadlink==0.9.0']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF

CONF_TARGET_TEMP = 'target_temp_default'
CONF_TARGET_TEMP_STEP = 'target_temp_step'
CONF_TIMEOUT = 'update_timeout'
CONF_SYNC_CLOCK_TIME_ONCE_PER_DAY = 'sync_clock_time_per_day'


STATE_HEAT = "heat"
STATE_AUTO = "auto"

HYSEN_POWERON = 1
HYSEN_POWEROFF = 0
HYSEN_MANUALMODE = 0
HYSEN_AUTOMODE = 1


DEFAULT_NAME = 'Broadlink Hysen Climate'
DEFAULT_TIMEOUT = 5
DEFAULT_RETRY = 2
DEFAULT_TARGET_TEMP = 20
DEFAULT_TARGET_TEMP_STEP = 1
DEFAULT_CONF_SYNC_CLOCK_TIME_ONCE_PER_DAY = False
DEFAULT_OPERATION_LIST = [STATE_HEAT, STATE_AUTO,STATE_OFF]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): cv.positive_int,
    vol.Optional(CONF_TARGET_TEMP_STEP, default=DEFAULT_TARGET_TEMP_STEP): cv.positive_int,
    vol.Optional(CONF_SYNC_CLOCK_TIME_ONCE_PER_DAY, default=DEFAULT_CONF_SYNC_CLOCK_TIME_ONCE_PER_DAY): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Broadlink Hysen Climate platform."""
    name = config.get(CONF_NAME)
    ip_addr = config.get(CONF_HOST)
    mac_addr = binascii.unhexlify(config.get(
        CONF_MAC).encode().replace(b':', b''))
    operation_list = DEFAULT_OPERATION_LIST
    target_temp_default = config.get(CONF_TARGET_TEMP)
    target_temp_step = config.get(CONF_TARGET_TEMP_STEP)
    sync_clock_time_per_day = config.get(CONF_SYNC_CLOCK_TIME_ONCE_PER_DAY)

    import broadlink

    broadlink_device = broadlink.hysen((ip_addr, 80), mac_addr, None)
    broadlink_device.timeout = config.get(CONF_TIMEOUT)

    try:
        broadlink_device.auth()
        async_add_devices([
            BroadlinkHysenClimate(
                hass, name, broadlink_device, target_temp_default,
                target_temp_step, operation_list,sync_clock_time_per_day)
            ])
    except socket.timeout:
        _LOGGER.error(
            "Failed to connect to Broadlink Hysen Device IP:%s", ip_addr)


class BroadlinkHysenClimate(ClimateDevice):

    def __init__(self, hass, name, broadlink_device, target_temp_default, 
                 target_temp_step, operation_list,sync_clock_time_per_day):
        """Initialize the Broadlink Hysen Climate device."""
        self._hass = hass
        self._name = name
        self._HysenData = []
        self._broadlink_device = broadlink_device

        self._sync_clock_time_per_day = sync_clock_time_per_day
        self._current_day_of_week = 0

        self._target_temperature = target_temp_default
        self._target_temperature_step = target_temp_step
        self._unit_of_measurement = hass.config.units.temperature_unit

        self._power_state = HYSEN_POWEROFF     # On = 1  #Off = 0
        self._auto_state = HYSEN_MANUALMODE    # Manual =0   #Auto, =1
        self._current_operation = STATE_OFF
        self._operation_list = operation_list
        self._is_heating_active = 0            # Demand = 1, No Demand = 0
        self._auto_override = 0                # Yes = 1, No = 0
        self._remote_lock = 0                  # Lock the local thermostat keypad 0 = No, Yes =1  

        self._loop_mode = 0  # 12345,67 = 0   123456,7 = 1  1234567 = 2 
                             # loop_mode refers to index in [ "12345,67", "123456,7", "1234567" ] 
                             # loop_mode = 0 ("12345,67") means Saturday and Sunday follow the "weekend" schedule 
                             # loop_mode = 2 ("1234567") means every day (including Saturday and Sunday) follows the "weekday" schedule

        self._sensor_mode = 0  # Sensor mode (SEN) sensor = 0 for internal sensor, 
                               # 1 for external sensor, 2 for internal control temperature, external limit temperature. Factory default: 0.

        self._max_temp = 35                  # Upper temperature limit for internal sensor (SVH) svh = 5..99. Factory default: 35C
        self._min_temp = 5                   # Lower temperature limit for internal sensor (SVL) svl = 5..99. Factory default: 5C
        self._external_sensor_temprange = 42 # Set temperature range for external sensor (OSV) osv = 5..99. Factory default: 42C
        self._deadzone_sensor_temprange = 2  # Deadzone for floor temprature (dIF) dif = 1..9. Factory default: 2C
        self._roomtemp_offset = 0            # Actual temperature calibration (AdJ) adj = -0.5. Prescision 0.1C
        self._anti_freeze_function = 1       # Anti-freezing function (FrE) fre = 0 for anti-freezing function shut down, 1 for anti-freezing function open. Factory default: 0
        self._poweron_mem = 1                # Power on memory (POn) poweronmem = 0 for power on memory off, 1 for power on memory on. Factory default: 0

        self._room_temp = 0
        self._external_temp = 0

        self._clock_hour = 0
        self._clock_min = 0
        self._clock_sec = 0
        self._day_of_week = 0
        self._week_day = ""
        self._week_end = ""

#       ******TOBE DONE ALLOW THERMOSTAT PERAMETERS TO BE SETUP FROM HOMEASSISTANT CONFIG*****
        # Setup the Thermostat 
#        self.set_advanced(self._loop_mode, self._sensor_mode, self._external_sensor_temprange, self._deadzone_sensor_temprange, self._max_temp, self._min_temp, self._roomtemp_offset, self._anti_freeze_function, self._poweron_mem)

        self._available = False  # should become True after first update()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await self._hass.async_add_executor_job(self._broadlink_device.auth)

    @property
    def available(self) -> bool:
        """Return True if the device is currently available."""
        return self._available

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        # sensor = 0 for internal sensor, 1 for external sensor, 2 for internal control temperature, external limit temperature.
        if self._sensor_mode == 1:
            return self._external_temp
        else:
            return self._room_temp

    @property
    def min_temp(self):
        """Return the polling state."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the polling state."""
        return self._max_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._target_temperature_step

    @property
    def current_operation(self):
        """Return current operation ie. heat, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}
        attr['power_state'] = self._power_state
        attr['sensor_mode'] = self._sensor_mode        
        attr['room_temp'] = self._room_temp
        attr['external_temp'] = self._external_temp        
        attr['heating_active'] = self._is_heating_active
        attr['auto_override'] = self._auto_override
        attr['external_sensor_temprange'] = self._external_sensor_temprange
        attr['deadzone_sensor_temprange'] = self._deadzone_sensor_temprange
        attr['loop_mode'] = self._loop_mode
        attr['roomtemp_offset'] = self._roomtemp_offset
        attr['anti_freeze_function'] = self._anti_freeze_function
        attr['poweron_mem'] = self._poweron_mem
        attr['remote_lock'] = self._remote_lock
        attr['clock_hour'] = self._clock_hour
        attr['clock_min'] = self._clock_min
        attr['clock_sec'] = self._clock_sec
        attr['day_of_week'] = self._day_of_week
        attr['week_day'] = str(self._week_day)
        attr['week_end'] = str(self._week_end)
        return attr

    @property
    def is_on(self):
        if self._power_state == HYSEN_POWERON:
            return True
        else:
            return False

    def turn_on(self):
        self._broadlink_device.set_power(HYSEN_POWERON)
        return True

    def turn_off(self):
        self._broadlink_device.set_power(HYSEN_POWEROFF)
        return True

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
            if (self._power_state == HYSEN_POWERON):
                self.send_tempset_command(kwargs.get(ATTR_TEMPERATURE))
            self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new opmode """
        self._current_operation = operation_mode
        self.set_operation_mode_command(operation_mode)
        self.schedule_update_ha_state()

    def send_tempset_command(self, target_temperature):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_temp(target_temperature)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                        if retry == DEFAULT_RETRY-1:
                            _LOGGER.error(
                                "Failed to send SetTemp command to Broadlink Hysen Device")

    def send_power_command(self, target_state):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_power(target_state)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send Power command to Broadlink Hysen Device")

    def send_mode_command(self, target_state, loopmode, sensor):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_mode(target_state, loopmode, sensor)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send OpMode-Heat/Manual command to Broadlink Hysen Device")

    # Change controller mode
    def set_operation_mode_command(self, operation_mode):
        if operation_mode == STATE_HEAT:
            if self._power_state == HYSEN_POWEROFF:
                self.send_power_command(HYSEN_POWERON)
            self.send_mode_command(HYSEN_MANUALMODE, self._loop_mode,self._sensor_mode)
        elif operation_mode == STATE_AUTO:
            if self._power_state == HYSEN_POWEROFF:
                self.send_power_command(HYSEN_POWERON)
            self.send_mode_command(HYSEN_AUTOMODE, self._loop_mode,self._sensor_mode)
        elif operation_mode == STATE_OFF:
                  self.send_power_command(HYSEN_POWEROFF)
        else:
            _LOGGER.error("Unknown command for Broadlink Hysen Device")
        return

    # set time on device
    # n.b. day=1 is Monday, ..., day=7 is Sunday

    def set_time(self, hour, minute, second, day):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_time(hour, minute, second, day)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send Set Time command to Broadlink Hysen Device")

    # Advanced settings
    # Sensor mode (SEN) sensor = 0 for internal sensor, 1 for external sensor, 2 for internal control temperature, external limit temperature. Factory default: 0.
    # Set temperature range for external sensor (OSV) osv = 5..99. Factory default: 42C
    # Deadzone for floor temprature (dIF) dif = 1..9. Factory default: 2C
    # Upper temperature limit for internal sensor (SVH) svh = 5..99. Factory default: 35C
    # Lower temperature limit for internal sensor (SVL) svl = 5..99. Factory default: 5C
    # Actual temperature calibration (AdJ) adj = -0.5. Prescision 0.1C
    # Anti-freezing function (FrE) fre = 0 for anti-freezing function shut down, 1 for anti-freezing function open. Factory default: 0
    # Power on memory (POn) poweronmem = 0 for power on memory off, 1 for power on memory on. Factory default: 0
    # loop_mode refers to index in [ "12345,67", "123456,7", "1234567" ]
    # E.g. loop_mode = 0 ("12345,67") means Saturday and Sunday follow the "weekend" schedule
    # loop_mode = 2 ("1234567") means every day (including Saturday and Sunday) follows the "weekday" schedule

    def set_advanced(self, loop_mode=None, sensor=None, osv=None, dif=None,
                     svh=None, svl=None, adj=None, fre=None, poweronmem=None):
        loop_mode = self._loop_mode if loop_mode is None else loop_mode
        sensor = self._sensor_mode if sensor is None else sensor
        osv = self._external_sensor_temprange if osv is None else osv
        dif = self._deadzone_sensor_temprange if dif is None else dif
        svh = self._max_temp if svh is None else svh
        svl = self._min_temp if svl is None else svl
        adj = self._roomtemp_offset if adj is None else adj
        fre = self._anti_freeze_function if fre is None else fre
        poweronmem = self._poweron_mem if poweronmem is None else poweronmem

        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_advanced(
                    loop_mode, sensor, osv, dif, svh, svl, adj, fre, poweronmem)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send Set Advanced to Broadlink Hysen Device")

    # Set timer schedule
    # Format is the same as you get from get_full_status.
    # weekday is a list (ordered) of 6 dicts like:
    # {'start_hour':17, 'start_minute':30, 'temp': 22 }
    # Each one specifies the thermostat temp that will become effective at start_hour:start_minute
    # weekend is similar but only has 2 (e.g. switch on in morning and off in afternoon)
    def set_schedule(self, weekday, weekend):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_schedule(weekday, weekend)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send Set Advanced to Broadlink Hysen Device")

    def set_lock(self, remote_lock):
        for retry in range(DEFAULT_RETRY):
            try:
                self._broadlink_device.set_power(
                    self, self._power_state, remote_lock=0)
                break
            except (socket.timeout, ValueError):
                try:
                    self._broadlink_device.auth()
                except socket.timeout:
                    if retry == DEFAULT_RETRY-1:
                        _LOGGER.error(
                            "Failed to send Set Lock to Broadlink Hysen Device")

    def update(self):
        """Get the latest data from the sensor."""
        for retry in range(DEFAULT_RETRY):
            try:
                self._HysenData = self._broadlink_device.get_full_status()
                if self._HysenData is not None:
                    self._room_temp = self._HysenData['room_temp']
                    self._target_temperature = self._HysenData['thermostat_temp']
                    self._min_temp = self._HysenData['svl']
                    self._max_temp = self._HysenData['svh']
                    self._loop_mode = int(self._HysenData['loop_mode'])-1
                    self._power_state = self._HysenData['power']
                    self._auto_state = self._HysenData['auto_mode']
                    self._is_heating_active = self._HysenData['active']

                    self._remote_lock = self._HysenData['remote_lock']
                    self._auto_override = self._HysenData['temp_manual']
                    self._sensor_mode = self._HysenData['sensor']
                    self._external_sensor_temprange = self._HysenData['osv']
                    self._deadzone_sensor_temprange = self._HysenData['dif']
                    self._roomtemp_offset = self._HysenData['room_temp_adj']
                    self._anti_freeze_function = self._HysenData['fre']
                    self._poweron_mem = self._HysenData['poweron']
                    self._external_temp = self._HysenData['external_temp']
                    self._clock_hour = self._HysenData['hour']
                    self._clock_min = self._HysenData['min']
                    self._clock_sec = self._HysenData['sec']
                    self._day_of_week = self._HysenData['dayofweek']
                    self._week_day = self._HysenData['weekday']
                    self._week_end = self._HysenData['weekend']

                    if self._power_state == HYSEN_POWERON:
                        if self._auto_state == HYSEN_AUTOMODE:
                            self._current_operation = STATE_AUTO
                        else:
                            self._current_operation = STATE_HEAT
                    else:
                        self._target_temperature = self._min_temp
                        self._current_operation = STATE_OFF

                    self._available = True

            except socket.timeout as error:
                if retry < 1:
                    _LOGGER.error(
                        "Failed to get Data from Hysen Device:%s", error)
                    self._power_state = HYSEN_POWEROFF
                    self._current_operation = STATE_OFF
                    self._room_temp = 0
                    self._external_temp = 0
                    self._min_temp = 0
                return
            except (vol.Invalid, vol.MultipleInvalid) as error:
                _LOGGER.warning("%s %s", error, error.__str__)
                pass

        """Sync the clock once per day."""
        if self._sync_clock_time_per_day == True:
            now_day_of_the_week = (datetime.datetime.today().weekday()) + 1
            if self._current_day_of_week < now_day_of_the_week:
                currentDT = datetime.datetime.now()
                self.set_time(currentDT.hour, currentDT.minute, currentDT.second, now_day_of_the_week)
                self._current_day_of_week = now_day_of_the_week
                _LOGGER.warning("Broadlink Hysen Device Clock Sync Success....")