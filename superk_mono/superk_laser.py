"""
Communicate with a SuperK Fianium laser from NKT Photonics.
"""
from ctypes import c_ubyte
from enum import IntEnum

from msl.equipment.resources.nkt import PortStatusTypes
from msl.equipment.resources import NKT

from . import (
    logger,
    BaseEquipment,
)


class ID60(IntEnum):
    """The register ID's for a SuperK Fianium laser (module type 0x60)."""

    # SuperK Fianium
    INLET_TEMPERATURE = 0x11
    EMISSION = 0x30
    MODE = 0x31
    INTERLOCK = 0x32
    PULSE_PICKER_RATIO = 0x34
    WATCHDOG_INTERVAL = 0x36
    POWER_LEVEL = 0x37
    CURRENT_LEVEL = 0x38
    NIM_DELAY = 0x39
    SERIAL_NUMBER = 0x65
    STATUS_BITS = 0x66
    SYSTEM_TYPE = 0x6B
    USER_TEXT = 0x6C

    # Front Panel
    FRONT_PANEL = 0x01
    PANEL_LOCK = 0x3D
    DISPLAY_TEXT = 0x72
    ERROR_FLASH = 0x8D


class ID88(IntEnum):
    """The register ID's for a SuperK Fianium laser (module type 0x88)."""
    # SuperK G3 Mainboard
    INLET_TEMPERATURE = 0x11
    EMISSION = 0x30
    MODE = 0x31
    INTERLOCK = 0x32
    DATETIME = 0x33
    PULSE_PICKER_RATIO = 0x34
    WATCHDOG_INTERVAL = 0x36
    CURRENT_LEVEL = 0x37
    PULSE_PICKER_NIM_DELAY = 0x39
    MAINBOARD_NIM_DELAY = 0x3A
    USER_CONFIG = 0x3B
    MAX_PULSE_PICKER_RATIO = 0x3D
    STATUS_BITS = 0x66
    ERROR_CODE = 0x67
    USER_TEXT = 0x8D


class OperatingModes(IntEnum):
    """The operating modes for a SuperK Fianium laser."""
    CONSTANT_CURRENT = 0
    CONSTANT_POWER = 1
    MODULATED_CURRENT = 2
    MODULATED_POWER = 3
    POWER_LOCK = 4


def nkt_callbacks(superk):
    """Prepare the callbacks from the SDK from NKT Photonics.

    Creates the objects necessary to handle callbacks from the SDK.

    Parameters
    ----------
    superk : :class:`.SuperK`
        The equipment subclass.

    Returns
    -------
    :class:`tuple`
        The Device, Register and Port callback functions.
    """
    def get_callback_data(length, address):
        # 'address' is an integer and represents the address of c_void_p from the callback
        try:
            return bytearray((c_ubyte * length).from_address(address)[:])  # noqa
        except ValueError:
            return bytearray()

    @NKT.DeviceStatusCallback
    def device_status_callback(port, dev_id, status, length, address):
        data = get_callback_data(length, address)
        logger.info(f'device_status_callback: port={port} dev_id={dev_id} '
                    f'status={status} length={length} address={address} data={data}')
        # superk.emit_notification(port, dev_id, status, data)

    @NKT.RegisterStatusCallback
    def register_status_callback(port, dev_id, reg_id, reg_status, reg_type, length, address):
        data = get_callback_data(length, address)
        logger.info(f'register_status_callback: port={port} dev_id={dev_id} reg_id={reg_id} '
                    f'reg_status={reg_status} reg_type={reg_type} length={length} '
                    f'address={address} data={data}')
        # superk.emit_notification(port, dev_id, reg_id, reg_status, reg_type, data)

    @NKT.PortStatusCallback
    def port_status_callback(port, status, cur_scan, max_scan, device):
        logger.info(f'port_status_callback: port={port} status={status} cur_scan={cur_scan} '
                    f'max_scan={max_scan} device={device}')
        # superk.emit_notification(port, status, cur_scan, max_scan, device)

    return device_status_callback, register_status_callback, port_status_callback


class SuperK(BaseEquipment):

    DEVICE_ID = 0x0F
    MODULE_TYPE_0x60 = 0x60
    MODULE_TYPE_0x88 = 0x88

    def __init__(self, record):
        """Communicate with a SuperK Fianium laser from NKT Photonics.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        """
        super(SuperK, self).__init__(record, name='superk')

        serial = self.connection.device_get_module_serial_number_str(SuperK.DEVICE_ID)
        if serial and serial != record.serial:
            raise ValueError(f'SuperK serial number mismatch {serial} != {record.serial}')

        # different SuperK's have different mainboard registry values
        self.MODULE_TYPE = self.connection.device_get_type(SuperK.DEVICE_ID)
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x60:
            self.ID = ID60
            self.MODES = {
                'Constant current': OperatingModes.CONSTANT_CURRENT,
                'Current modulation': OperatingModes.MODULATED_CURRENT,
                'Power lock': OperatingModes.POWER_LOCK,
            }
        elif self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.ID = ID88
            self.MODES = {
                'Constant current': OperatingModes.CONSTANT_CURRENT,
                'Power lock': OperatingModes.POWER_LOCK,
            }
        else:
            raise ValueError(f'Unsupported module type 0x{self.MODULE_TYPE:x}')

        self._device_callback, self._register_callback, self._port_callback = nkt_callbacks(self)

        # TODO callbacks are not triggered when running as a Service
        self.connection.set_callback_device_status(self._device_callback)
        self.connection.set_callback_register_status(self._register_callback)
        self.connection.set_callback_port_status(self._port_callback)

        status = self.connection.get_port_status()
        if status != PortStatusTypes.PortReady:
            self.connection.raise_exception(f'{self.alias!r} port status is {status!r}')

        self.ensure_interlock_ok()
        if record.connection.properties.get('lock_front_panel', False):
            self.lock_front_panel(True)

    def ensure_interlock_ok(self) -> bool:
        """Make sure that the interlock is okay.

        Raises an exception if it is not okay and it cannot be reset.
        """
        status = self.connection.register_read_u16(SuperK.DEVICE_ID, self.ID.INTERLOCK)
        if status == 2:
            self.logger.info(f'{self.alias!r} interlock is okay')
            return True

        if status == 1:  # then requires an interlock reset
            self.logger.info(f'resetting the {self.alias!r} interlock... ')
            status = self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.INTERLOCK, 1)
            if status == 2:
                self.logger.info(f'{self.alias!r} interlock is okay')
                return True

        self.connection.raise_exception(
            f'Invalid {self.alias!r} interlock status code {status}. '
            f'Is the key in the off position?'
        )

    def is_constant_current_mode(self) -> bool:
        """Is the laser in constant current mode?"""
        return self.get_operating_mode() == OperatingModes.CONSTANT_CURRENT

    def is_constant_power_mode(self) -> bool:
        """Is the laser in constant power mode?"""
        return self.get_operating_mode() == OperatingModes.CONSTANT_POWER

    def is_modulated_current_mode(self) -> bool:
        """Is the laser in modulated current mode?"""
        return self.get_operating_mode() == OperatingModes.MODULATED_CURRENT

    def is_modulated_power_mode(self) -> bool:
        """Is the laser in modulated power mode?"""
        return self.get_operating_mode() == OperatingModes.MODULATED_POWER

    def is_power_lock_mode(self) -> bool:
        """Is the laser in power lock (external feedback) mode?"""
        return self.get_operating_mode() == OperatingModes.POWER_LOCK

    def get_operating_mode(self) -> int:
        """Get the operating mode of the laser.

        Returns
        -------
        :class:`OperatingModes`
            The operating mode.
        """
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x60:
            read = self.connection.register_read_u16
        else:
            read = self.connection.register_read_u8
        return OperatingModes(read(SuperK.DEVICE_ID, self.ID.MODE))

    def get_operating_modes(self) -> dict:
        """Get all valid operating modes.

        Returns
        -------
        :class:`dict`
            The operating modes.
        """
        return self.MODES

    def enable_constant_current_mode(self) -> None:
        """Set the laser to be in constant current mode."""
        self.set_operating_mode(OperatingModes.CONSTANT_CURRENT)

    def enable_constant_power_mode(self) -> None:
        """Set the laser to be in constant power mode."""
        self.set_operating_mode(OperatingModes.CONSTANT_POWER)

    def enable_modulated_current_mode(self) -> None:
        """Set the laser to be in modulated current mode."""
        self.set_operating_mode(OperatingModes.MODULATED_CURRENT)

    def enable_modulated_power_mode(self) -> None:
        """Set the laser to be in modulated power mode."""
        self.set_operating_mode(OperatingModes.MODULATED_POWER)

    def enable_power_lock_mode(self) -> None:
        """Set the laser to be power lock (external feedback) mode."""
        self.set_operating_mode(OperatingModes.POWER_LOCK)

    def set_operating_mode(self, mode) -> None:
        """Set the operating mode of the laser.

        Parameters
        ----------
        mode : :class:`int`, :class:`str` or :class:`OperatingModes`
            The operating mode as an :class:`OperatingModes` value or member name.
        """
        mode = self.convert_to_enum(mode, OperatingModes, to_upper=True)
        self.emission(False)
        if self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.MODE, mode.value) != mode.value:
            self.connection.raise_exception(f'Cannot set {self.alias!r} to {mode!r}')
        self.logger.info(f'set {self.alias!r} to {mode!r}')
        # for name, value in self.MODES.items():
        #     if value == mode.value:
        #         self.emit_notification(mode=name)  # notify all linked Clients
        #         break

    def get_temperature(self) -> float:
        """Get the temperature of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_s16(SuperK.DEVICE_ID, self.ID.INLET_TEMPERATURE) * 0.1

    def get_power_level(self) -> float:
        """Get the constant/modulated power level of the laser."""
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.connection.raise_exception(
                f'{self.alias!r} does not support power levels'
            )

        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_u16(SuperK.DEVICE_ID, self.ID.POWER_LEVEL) * 0.1  # noqa

    def get_current_level(self) -> float:
        """Get the constant/modulated current level of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_u16(SuperK.DEVICE_ID, self.ID.CURRENT_LEVEL) * 0.1

    def get_feedback_level(self) -> float:
        """Get the power lock (external feedback) level of the laser."""
        return self.get_current_level()

    def set_power_level(self, percentage: float) -> float:
        """Set the constant/modulated power level of the laser.

        Parameters
        ----------
        percentage : :class:`float`
            The power level as a percentage 0 - 100. Resolution 0.1.

        Returns
        -------
        :class:`float`
            The actual power level.
        """
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.connection.raise_exception(
                f'{self.alias!r} does not support power levels'
            )

        if percentage < 0 or percentage > 100:
            self.connection.raise_exception(
                f'Invalid {self.alias!r} power level of {percentage}. '
                f'Must be in range [0, 100].'
            )

        # the documentation indicates that there is a scaling factor of 0.1
        self.logger.info(f'set {self.alias!r} power level to {percentage}%')
        val = self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.POWER_LEVEL, int(percentage * 10))  # noqa
        actual = float(val) * 0.1
        # self.emit_notification(level=actual)  # notify all linked Clients
        return actual

    def set_current_level(self, percentage: float) -> float:
        """Set the constant/modulated current level of the laser.

        Parameters
        ----------
        percentage : :class:`float`
            The current level as a percentage 0 - 100. Resolution 0.1.

        Returns
        -------
        :class:`float`
            The actual current level.
        """
        self.logger.info(f'set {self.alias!r} current level to {percentage}%')
        return self._set_current_level(percentage)

    def set_feedback_level(self, percentage: float) -> float:
        """Set the power lock (external feedback) level of the laser.

        Parameters
        ----------
        percentage : :class:`float`
            The power lock level as a percentage 0 - 100. Resolution 0.1.

        Returns
        -------
        :class:`float`
            The actual power lock level.
        """
        self.logger.info(f'set {self.alias!r} power lock level to {percentage}%')
        return self._set_current_level(percentage)

    def _set_current_level(self, percentage):
        if percentage < 0 or percentage > 100:
            self.connection.raise_exception(
                f'Invalid {self.alias!r} current level of {percentage}. '
                f'Must be in the range [0, 100].'
            )

        # the documentation indicates that there is a scaling factor of 0.1
        val = self.connection.register_write_read_u16(SuperK.DEVICE_ID, self.ID.CURRENT_LEVEL, int(percentage * 10))
        actual = float(val) * 0.1
        # self.emit_notification(level=actual)  # notify all linked Clients
        return actual

    def is_emission_on(self) -> bool:
        """Check if the laser emission is on or off.

        Returns
        -------
        :class:`bool`
            Whether the laser emission is on (:data:`True`) or off (:data:`False`).
        """
        return bool(self.connection.register_read_u8(SuperK.DEVICE_ID, self.ID.EMISSION))

    def emission(self, on: bool) -> None:
        """Turn the laser emission on or off.

        Parameters
        ----------
        on : :class:`bool`
            Whether to turn the laser emission on (:data:`True`) or off (:data:`False`).
        """
        state, text = (3, 'on') if on else (0, 'off')
        self.logger.info(f'turn {self.alias!r} emission {text}')
        try:
            self.connection.register_write_u8(SuperK.DEVICE_ID, self.ID.EMISSION, state)
        except OSError as e:
            error = str(e)
        else:
            # self.emit_notification(emission=bool(state))  # notify all linked Clients
            return

        self.connection.raise_exception(
            f'Cannot turn the {self.alias!r} emission {text}\n'
            f'{error}'
        )

    def lock_front_panel(self, on: bool) -> bool:
        """Lock the front panel so that the current or power level cannot be changed.

        Parameters
        ----------
        on : :class:`bool`
            Whether to lock (:data:`True`) or unlock (:data:`False`) the front panel.

        Returns
        -------
        :class:`bool`
            Whether the request to (un)lock the front panel was successful. The
            laser with a module type 0x88 does not permit the front panel to be
            (un)locked and therefore this method will always return :data:`False`
            for this laser mainboard.
        """
        text = 'lock' if on else 'unlock'
        if self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            self.logger.info(f'the {self.alias!r} does not support {text}ing the front panel')
            return False

        try:
            self.connection.register_write_u8(self.ID.FRONT_PANEL, self.ID.PANEL_LOCK, int(on))  # noqa
        except (OSError, AttributeError) as e:
            self.logger.error(f'Cannot {text} the front panel of the {self.alias!r}, '
                              f'{e.__class__.__name__}: {e}')
            return False
        else:
            # self.emit_notification(locked=bool(on))  # notify all linked Clients
            self.logger.info(f'{text}ed the front panel of the {self.alias!r}')
            return True

    def disconnect(self):
        """Unlock the front panel, set the user text to an empty string and close the port."""
        self.lock_front_panel(False)
        self.set_user_text('')
        self.connection.close_ports(self.record.connection.address)
        self.connection.disconnect()

    def get_user_text(self) -> str:
        """Get the custom user-text value.

        Returns
        -------
        :class:`str`
            The user text.
        """
        return self.connection.register_read_ascii(SuperK.DEVICE_ID, self.ID.USER_TEXT)

    def set_user_text(self, text: str) -> str:
        """Set the custom user-text value.

        Parameters
        ----------
        text : :class:`str`
            The text to write to the laser's firmware. Only ASCII characters are
            allowed. The maximum number of characters is 20 for the laser with
            module type 0x60 and 240 characters for module type 0x88. The laser
            with module type 0x60 will display the text on the front panel.

        Returns
        -------
        :class:`str`
            The user text that was actually stored in the laser's firmware.
        """
        if not text and self.MODULE_TYPE == SuperK.MODULE_TYPE_0x88:
            # module type 0x88 requires at least 1 character to be written
            text = ' '
        self.logger.info(f'set the {self.alias!r} front-panel text to {text!r}')
        return self.connection.register_write_read_ascii(SuperK.DEVICE_ID, self.ID.USER_TEXT, text, False)
