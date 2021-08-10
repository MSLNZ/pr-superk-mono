"""
Communicate with a HRS500M Monochromator from Princeton Instruments.
"""
from enum import IntEnum

from . import BaseEquipment


class Slit(IntEnum):
    FRONT_ENTRANCE = 2
    FRONT_EXIT = 3


class HRSMonochromator(BaseEquipment):

    FRONT_ENTRANCE_SLIT = Slit.FRONT_ENTRANCE
    FRONT_EXIT_SLIT = Slit.FRONT_EXIT

    def __init__(self, record):
        """Communicate with a HRS500M Monochromator from Princeton Instruments.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        """
        super(HRSMonochromator, self).__init__(record, name='mono-hrs')

        gratings = record.user_defined.get('gratings')
        if not gratings:
            gratings = {
                position: {
                    'blaze': self.connection.get_mono_grating_blaze(position),
                    'density': '{}/mm'.format(self.connection.get_mono_grating_density(position)),
                }
                for position in [1, 2, 3]
            }
        self._grating_info = gratings

        filters = record.user_defined.get('filters')
        if not filters:
            filters = {
                1: 'None (open)',
                2: '320 nm',
                3: '590 nm',
                4: '665 nm',
                5: '715 nm',
                6: 'Blank (closed)',
            }
        self._filter_info = filters

    def home_filter_wheel(self) -> int:
        """Home the filter wheel.

        Returns
        -------
        :class:`int`
            The filter wheel position after homing.
        """
        self.connection.mono_filter_home()
        self.logger.info(f'home the filter wheel of {self.alias!r}')
        position = self.get_filter_position()
        # self.emit_notification(filter_wheel_position=position)
        return position

    def home_front_entrance_slit(self) -> int:
        """Home the front entrance slit.

        Returns
        -------
        :class:`int`
            The slit width in microns after homing.
        """
        self.connection.mono_slit_home(self.FRONT_ENTRANCE_SLIT)
        self.logger.info(f'home the front entrance slit of {self.alias!r}')
        width = self.get_front_entrance_slit_width()
        # self.emit_notification(front_entrance_slit_width=width)
        return width

    def home_front_exit_slit(self) -> int:
        """Home the front exit slit.

        Returns
        -------
        :class:`int`
            The slit width in microns after homing.
        """
        self.connection.mono_slit_home(self.FRONT_EXIT_SLIT)
        self.logger.info(f'home the front exit slit of {self.alias!r}')
        width = self.get_front_exit_slit_width()
        # self.emit_notification(front_exit_slit_width=width)
        return width

    def get_front_entrance_slit_width(self) -> int:
        """Get the front entrance slit width.

        Returns
        -------
        :class:`int`
            The slit width in microns.
        """
        return self.connection.get_mono_slit_width(self.FRONT_ENTRANCE_SLIT)

    def get_front_exit_slit_width(self) -> int:
        """Get the front exit slit width.

        Returns
        -------
        :class:`int`
            The slit width in microns.
        """
        return self.connection.get_mono_slit_width(self.FRONT_EXIT_SLIT)

    def set_front_entrance_slit_width(self, um: int) -> int:
        """Set the front entrance slit width.

        Parameters
        ----------
        um : :class:`int`
            The slit width in microns.

        Returns
        -------
        :class:`int`
            The actual slit width in microns.
        """
        width = int(um)
        self._set_slit_width(self.FRONT_ENTRANCE_SLIT, width)
        actual = self.get_front_entrance_slit_width()
        assert actual == width
        # self.emit_notification(front_entrance_slit_width=actual)
        return actual

    def set_front_exit_slit_width(self, um: int) -> int:
        """Set the front exit slit width.

        Parameters
        ----------
        um : :class:`int`
            The slit width in microns.

        Returns
        -------
        :class:`int`
            The actual slit width in microns.
        """
        width = int(um)
        self._set_slit_width(self.FRONT_EXIT_SLIT, width)
        actual = self.get_front_exit_slit_width()
        assert actual == width
        # self.emit_notification(front_exit_slit_width=actual)
        return actual

    def _set_slit_width(self, port, um):
        if not (10 <= um <= 3000):
            self.connection.raise_exception(
                f'Invalid {self.alias!r} slit width of {um}. '
                f'Must be in the range [10, 3000].'
            )

        self.connection.set_mono_slit_width(port, um)
        text = 'entrance' if port == self.FRONT_ENTRANCE_SLIT else 'exit'
        self.logger.info(f'set {self.alias!r} front {text} slit width to {um} microns')

    def get_wavelength(self) -> float:
        """Get the current wavelength value.

        Returns
        -------
        :class:`float`
            The wavelength in nm.
        """
        return self.connection.get_mono_wavelength_nm()

    def set_wavelength(self, nm: float) -> float:
        """Set the wavelength.

        Parameters
        ----------
        nm : :class:`float`
            The wavelength in nm.

        Returns
        -------
        :class:`float`
            The actual wavelength in nm.
        """
        requested = round(nm, 3)

        if not (-2800 <= requested <= 2800):
            self.connection.raise_exception(
                f'Invalid {self.alias!r} wavelength of {nm} nm. '
                f'Must be in the range [-2800, 2800].'
            )

        self.connection.set_mono_wavelength_nm(requested)
        encoder = self.get_wavelength()
        self.logger.info(f'set {self.alias!r} wavelength to {requested} nm [encoder={encoder} nm]')
        # self.emit_notification(wavelength={'requested': requested, 'encoder': encoder})
        return encoder

    def get_filter_position(self) -> int:
        """Get the filter position.

        Returns
        -------
        :class:`int`
            The filter position, in the range [1, 6].
        """
        return self.connection.get_mono_filter_position()

    def set_filter_position(self, position: int) -> int:
        """Set the filter wheel position.

        Parameters
        ----------
        position : :class:`int`
            The filter wheel position, in the range [1, 6].

        Returns
        -------
        :class:`int`
            The actual filter wheel position.
        """
        pos = int(position)
        if not (1 <= pos <= 6):
            self.connection.raise_exception(
                f'Invalid {self.alias!r} filter position {position}. '
                f'Must be in the range [1, 6].'
            )

        self.connection.set_mono_filter_position(pos)
        actual = self.get_filter_position()
        assert actual == pos
        self.logger.info(f'set {self.alias!r} filter position to {pos} [{self._filter_info[pos]}]')
        # self.emit_notification(filter_wheel_position=actual)
        return actual

    def grating_info(self) -> dict:
        """Get the information about each grating.

        Returns
        -------
        :class:`dict`
            The density and blaze values for each grating. The keys are the
            positions of each grating.
        """
        return self._grating_info

    def filter_info(self) -> dict:
        """Get the information about each filter.

        Returns
        -------
        :class:`dict`
            A description of which filters are installed in each position. The
            keys are the positions of each filter.
        """
        return self._filter_info

    def get_grating_position(self) -> int:
        """Get the grating position.

        Returns
        -------
        :class:`int`
            The grating position. Either 1, 2 or 3.
        """
        return self.connection.get_mono_grating()

    def set_grating_position(self, position: int) -> int:
        """Set the grating position.

        Parameters
        ----------
        position : :class:`int`
            The grating position. Either 1, 2 or 3.

        Returns
        -------
        :class:`int`
            The actual grating position.
        """
        pos = int(position)

        if not (1 <= pos <= 3):
            self.connection.raise_exception(
                f'Invalid {self.alias!r} grating position {position}. '
                f'Must be either 1, 2 or 3.'
            )

        self.connection.set_mono_grating(pos)
        actual = self.get_grating_position()
        assert actual == pos
        self.logger.info(f'set {self.alias!r} grating to position {pos} [{self._grating_info[pos]}]')
        # self.emit_notification(grating_position=actual)
        return actual
