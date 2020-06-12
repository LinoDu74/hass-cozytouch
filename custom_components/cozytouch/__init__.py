"""The cozytouch component."""
import asyncio
import logging

import voluptuous as vol
from cozytouchpy import CozytouchClient
from cozytouchpy.exception import AuthentificationFailed, CozytouchException
from cozytouchpy.constant import DeviceType
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers import device_registry as dr

from .const import (
    COMPONENTS,
    COZYTOUCH_ACTUATOR,
    CONF_COZYTOUCH_ACTUATOR,
    COZYTOUCH_DATAS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SENSOR_TYPES,
    DEFAULT_COZYTOUCH_ACTUATOR,
    SCHEMA_HEATER,
    SCHEMA_HEATINGCOOLINGZONE,
    SCHEMA_HEATINGZONE,
    HVAC_MODE_LIST,
    PRESET_MODE_LIST,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
                vol.Optional(
                    CONF_COZYTOUCH_ACTUATOR, default=DEFAULT_COZYTOUCH_ACTUATOR
                ): vol.In(SENSOR_TYPES),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Load configuration for Cozytouch component."""
    hass.data.setdefault(DOMAIN, {})

    if hass.config_entries.async_entries(DOMAIN) or DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Cozytouch as config entry."""
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                "model": config_entry.data.get(
                    CONF_COZYTOUCH_ACTUATOR, DEFAULT_COZYTOUCH_ACTUATOR
                )
            },
        )

    try:
        setup = await async_connect(hass, config_entry.data)
        if setup is None:
            return False
    except CozytouchException:
        return False

    hass.data[DOMAIN][config_entry.entry_id] = {COZYTOUCH_DATAS: setup}
    hass.data[DOMAIN][COZYTOUCH_ACTUATOR] = config_entry.options[
        CONF_COZYTOUCH_ACTUATOR
    ]

    device_registry = await dr.async_get_registry(hass)
    for gateway in setup.data.get("gateways"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, gateway["placeOID"]), (DOMAIN, gateway["gatewayId"])},
            manufacturer="Atlantic/Thermor",
            name="Cozytouch",
            sw_version=gateway["connectivity"]["protocolVersion"],
        )

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return True


async def async_connect(hass, parameters):
    """Connect to cozytouch."""
    try:
        cozytouch = CozytouchClient(
            parameters[CONF_USERNAME],
            parameters[CONF_PASSWORD],
            parameters[CONF_TIMEOUT],
        )
        await cozytouch.connect()
        return await cozytouch.get_setup()
    except AuthentificationFailed as e:
        raise AuthentificationFailed(e)
    except CozytouchException as e:
        raise CozytouchException(e)


class ClimateSchema:
    """Determine schema for a climate."""

    def __init__(self, model):
        """Get model."""
        self._model = model

    def hvac_list(self):
        """Return HVAC Mode List."""
        if DeviceType.HEATER == self._model:
            return SCHEMA_HEATER.get(HVAC_MODE_LIST)
        if DeviceType.APC_HEATING_ZONE == self._model:
            return SCHEMA_HEATINGZONE.get(HVAC_MODE_LIST)
        if DeviceType.APC_HEATING_COOLING_ZONE == self._model:
            return SCHEMA_HEATINGCOOLINGZONE.get(HVAC_MODE_LIST)

    def preset_list(self):
        """Return HVAC Mode List."""
        if DeviceType.HEATER == self._model:
            return SCHEMA_HEATER.get(PRESET_MODE_LIST)
        if DeviceType.APC_HEATING_ZONE == self._model:
            return SCHEMA_HEATINGZONE.get(PRESET_MODE_LIST)
        if DeviceType.APC_HEATING_COOLING_ZONE == self._model:
            return SCHEMA_HEATINGCOOLINGZONE.get(PRESET_MODE_LIST)
