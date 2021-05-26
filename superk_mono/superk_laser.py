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


class ID(IntEnum):
    """The register ID's for a SuperK Fianium laser."""
    DEVICE = 0x0F
    FRONT_PANEL = 0x01

    # Main Module (Device)
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
    PANEL_LOCK = 0x3D
    DISPLAY_TEXT = 0x72
    ERROR_FLASH = 0x8D


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
        The Qt signaler and the Device, Register and Port callback functions.
    """
    def get_callback_data(length, address):
        # 'address' is an integer and represents the address of c_void_p from the callback
        try:
            return bytearray((c_ubyte * length).from_address(address)[:])
        except ValueError:
            return bytearray()

    @NKT.DeviceStatusCallback
    def device_status_callback(port, dev_id, status, length, address):
        logger.debug(f'device_status_callback: port={port} dev_id={dev_id} '
                     f'status={status} length={length} address={address}')
        data = get_callback_data(length, address)
        superk.emit_notification(port, dev_id, status, data)

    @NKT.RegisterStatusCallback
    def register_status_callback(port, dev_id, reg_id, reg_status, reg_type, length, address):
        logger.debug(f'register_status_callback: port={port} dev_id={dev_id} reg_id={reg_id} '
                     f'reg_status={reg_status} reg_type={reg_type} length={length} address={address}')
        data = get_callback_data(length, address)
        superk.emit_notification(port, dev_id, reg_id, reg_status, reg_type, data)

    @NKT.PortStatusCallback
    def port_status_callback(port, status, cur_scan, max_scan, device):
        logger.debug(f'port_status_callback: port={port} status={status} cur_scan={cur_scan} '
                     f'max_scan={max_scan} device={device}')
        superk.emit_notification(port, status, cur_scan, max_scan, device)

    return device_status_callback, register_status_callback, port_status_callback


class SuperK(BaseEquipment):

    def __init__(self, record):
        """Communicate with a SuperK Fianium laser from NKT Photonics.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        """
        super(SuperK, self).__init__(record, name='superk')

        self._modes = {
            'Constant current': OperatingModes.CONSTANT_CURRENT,
            'Current modulation': OperatingModes.MODULATED_CURRENT,
            'Power lock': OperatingModes.POWER_LOCK,
            # 'Power modulation ': OperatingModes.MODULATED_POWER,
            # 'Constant power': OperatingModes.CONSTANT_POWER,
        }

        self._device_callback, self._register_callback, self._port_callback = nkt_callbacks(self)

        # TODO callbacks are not triggered when running as a Service
        self.connection.set_callback_device_status(self._device_callback)
        self.connection.set_callback_register_status(self._register_callback)
        self.connection.set_callback_port_status(self._port_callback)

        status = self.connection.get_port_status()
        if status != PortStatusTypes.PortReady:
            self.connection.raise_exception(f'{self.alias!r} port status is {status!r}')

        self.ensure_interlock_ok()
        self.lock_front_panel(record.connection.properties.get('lock_front_panel', False))

    def ensure_interlock_ok(self) -> bool:
        """Make sure that the interlock is okay.

        Raises an exception if it is not okay and it cannot be reset.
        """
        status = self.connection.register_read_u16(ID.DEVICE, ID.INTERLOCK)
        if status == 2:
            self.logger.debug(f'{self.alias!r} interlock is okay')
            return True

        if status == 1:  # then requires an interlock reset
            self.logger.debug(f'resetting the {self.alias!r} interlock... ')
            status = self.connection.register_write_read_u16(ID.DEVICE, ID.INTERLOCK, 1)
            if status == 2:
                self.logger.debug(f'{self.alias!r} interlock is okay')
                return True

        self.connection.raise_exception(f'Invalid {self.alias!r} interlock status code {status}. '
                                        f'Is the key switch off?')

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
        return OperatingModes(self.connection.register_read_u16(ID.DEVICE, ID.MODE))

    def get_operating_modes(self) -> dict:
        """Get all valid operating modes.

        Returns
        -------
        :class:`dict`
            The operating modes.
        """
        return self._modes

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
        if self.connection.register_write_read_u16(ID.DEVICE, ID.MODE, mode.value) != mode.value:
            self.connection.raise_exception(f'Cannot set {self.alias!r} to {mode!r}')
        self.logger.info(f'set {self.alias!r} to {mode!r}')
        for name, value in self._modes.items():
            if value == mode.value:
                self.emit_notification(mode=name)  # notify all linked Clients

    def get_temperature(self) -> float:
        """Get the temperature of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_s16(ID.DEVICE, ID.INLET_TEMPERATURE) * 0.1

    def get_power_level(self) -> float:
        """Get the constant/modulated power level of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_u16(ID.DEVICE, ID.POWER_LEVEL) * 0.1

    def get_current_level(self) -> float:
        """Get the constant/modulated current level of the laser."""
        # the documentation indicates that there is a scaling factor of 0.1
        return self.connection.register_read_u16(ID.DEVICE, ID.CURRENT_LEVEL) * 0.1

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
        if percentage < 0 or percentage > 100:
            self.connection.raise_exception(f'Invalid {self.alias!r} power level of {percentage}. '
                                            f'Must be in range [0, 100].')

        # the documentation indicates that there is a scaling factor of 0.1
        self.logger.info(f'set {self.alias!r} power level to {percentage}%')
        val = self.connection.register_write_read_u16(ID.DEVICE, ID.POWER_LEVEL, int(percentage * 10))
        actual = float(val) * 0.1
        self.emit_notification(level=actual)  # notify all linked Clients
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
            self.connection.raise_exception(f'Invalid {self.alias!r} current level of {percentage}. '
                                            f'Must be in range [0, 100].')

        # the documentation indicates that there is a scaling factor of 0.1
        val = self.connection.register_write_read_u16(ID.DEVICE, ID.CURRENT_LEVEL, int(percentage * 10))
        actual = float(val) * 0.1
        self.emit_notification(level=actual)  # notify all linked Clients
        return actual

    def is_emission_on(self) -> bool:
        """Check if the laser emission is on or off.

        Returns
        -------
        :class:`bool`
            Whether the laser emission is on (:data:`True`) or off (:data:`False`).
        """
        return bool(self.connection.register_read_u8(ID.DEVICE, ID.EMISSION))

    def emission(self, on: bool) -> None:
        """Turn the laser emission on or off.

        Parameters
        ----------
        on : :class:`bool`
            Whether to turn the laser emission on (:data:`True`) or off (:data:`False`).

        Returns
        -------
        :class:`bool`
            Whether the laser emission is on (:data:`True`) or off (:data:`False`).
        """
        state, text = (3, 'on') if on else (0, 'off')
        try:
            self.connection.register_write_u8(ID.DEVICE, ID.EMISSION, state)
        except OSError:
            pass  # raise custom error message below
        else:
            self.logger.info(f'turn {self.alias!r} emission {text}')
            self.emit_notification(emission=bool(state))  # notify all linked Clients
            return

        self.connection.raise_exception(f'Cannot turn the {self.alias!r} emission {text}')

    def lock_front_panel(self, on: bool) -> None:
        """Lock the front panel so that the current or power level cannot be changed.

        Parameters
        ----------
        on : :class:`bool`
            Whether to lock (:data:`True`) or unlock (:data:`False`) the front panel.
        """
        text = 'locked' if on else 'unlocked'
        try:
            self.connection.register_write_u8(ID.FRONT_PANEL, ID.PANEL_LOCK, int(on))
        except OSError:
            pass  # raise custom error message below
        else:
            self.logger.info(f'{text} the front panel of the {self.alias!r}')
            return

        self.connection.raise_exception(f'Cannot {text[:-2]} the front panel of the {self.alias!r}')

    def disconnect(self):
        """Unlock the front panel and close the port."""
        self.lock_front_panel(False)
        self.connection.close_ports(self.record.connection.address)
        self.connection.disconnect()
