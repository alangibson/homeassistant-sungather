"""Sungrow Inverter config flow."""
from __future__ import annotations

import logging
from typing import Any
from pprint import pformat
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.selector import selector
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_SLAVE
)

from .const import DOMAIN, DEFAULT_NAME

from .inverter import connect_inverter


logger = logging.getLogger(__name__)

# This is the schema that used to display the UI to the user.
# TODO add CONF_SCAN_INTERVAL
DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT, default=8082): int,
    vol.Required(CONF_TIMEOUT, default=3): int,
    vol.Required(CONF_SLAVE, default=0x01): int,
    vol.Required("connection", default='http'): selector({
        "select": {
            "options": ["http", "modbus", "sungrow"],
        }
    }),
    vol.Optional("model"): str,
    vol.Optional("use_local_time"): bool,
    vol.Optional("smart_meter"): bool,
    vol.Optional("level", default=2): int
})


class SungrowInverterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sungrow Inverter config flow."""

    VERSION = 1

    async def validate_input(self, hass: HomeAssistant, config_inverter: dict = None) -> dict[str, Any]:
        """Validate that the user input allows us to connect to the inverter.
        Data has the keys from DATA_SCHEMA with values provided by the user.
        """

        logger.debug(f'validate_input config_inverter={pformat(config_inverter)}')

        # Accumulate validation errors. Key is name of field from DATA_SCHEMA
        errors = {}

        # Don't do anything if we don't have a configuration
        if not config_inverter:
            logger.debug(f'validate_input returning None due to no config')
            return None

        # Validate the data can be used to set up a connection.
        logger.debug(f'validate_input creating SungrowInverter')
        is_success, inverter = await hass.async_add_executor_job(connect_inverter(config_inverter))
        # If we can't connect, set a value indicating this so we can tell the user
        logger.debug(
            f'validate_input inverter.connect() is_success={is_success}')
        if not is_success:
            errors['base'] = 'cannot_connect'

        logger.debug(f'validate_input errors={pformat(errors)}')

        return (errors, inverter)

    async def async_step_user(self, user_input=None):
        """Initial configuration step
        Either show config data entry form to the user, or create a config entry.
        """

        logger.debug(f'async_step_user user_input={pformat(user_input)}')

        # Either show modal form, or create config entry then move on
        if not user_input: # Just show the modal form and return if no user input
            logger.debug('async_step_user displaying user data entry form')
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
        else: # We got user input, so do something with it
            # Validate inputs and do a test connection/scrape of the inverter
            # Both info and errors are None when config flow is first invoked
            errors, inverter = await self.validate_input(self.hass, user_input)
            logger.debug(f'async_step_user errors={pformat(errors)}')

            # Either display errors in form, or create config entry and close form
            if not errors or not len(errors.keys()):
                # Figure out a unique id (that never changes!) for the device
                unique_device_id = inverter.latest_scrape.get('serial_number')
                logger.debug(f'async_step_user assigning unique_id {unique_device_id}')
                # self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                # await self.async_set_unique_id(unique_device_id)
                user_input['device_id'] = unique_device_id

                # Create the config entry
                logger.debug(f'async_step_user calling async_create_entry with unique_id {unique_device_id}')
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
            else:
                # If there is no user input or there were errors, show the form again,
                # including any errors that were found with the input.
                logger.debug(
                    f'async_step_user calling async_show_form step_id="user"')
                return self.async_show_form(
                    step_id="user", data_schema=DATA_SCHEMA, errors=errors
                )
