"""
Communicate with an FW212CNEB ND filter wheel from Thorlabs.
"""
from . import BaseEquipment


class FW212CNEB(BaseEquipment):

    def __init__(self, record):
        """Communicate an FW212CNEB ND filter wheel from Thorlabs.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        """
        super(FW212CNEB, self).__init__(record, name='nd-filter-wheel')

        self._max_position = self.connection.get_position_count()

        # key (position number), value (optical density)
        filters = record.user_defined.get('filters')
        if not filters:
            filters = {
                1: None,  # empty
                2: 0.1,
                3: 0.2,
                4: 0.3,
                5: 0.4,
                6: 0.5,
                7: 0.6,
                8: 1.0,
                9: 1.3,
                10: 2.0,
                11: 3.0,
                12: 4.0,
            }

        if len(filters) != self._max_position:
            raise ValueError(
                f'The number of items in the OD filter map [{len(filters)}] does not equal the '
                f'number of positions that the filter wheel supports [{self._max_position}].'
            )

        self._od_map = filters

    def filter_info(self) -> dict:
        """Get the optical densities of all ND filters at each position.

        Returns
        -------
        :class:`dict`
            The position number is the key and the OD is the value.
        """
        return self._od_map

    def get_position(self) -> int:
        """Get the current position."""
        return self.connection.get_position()

    def set_position(self, position: int) -> int:
        """Set the position number of the ND filter wheel.

        Parameters
        ----------
        position : :class:`int`
            The position number. The first position is 1 (not 0).

        Returns
        -------
        :class:`int`
            The position of the ND filter wheel after it has moved.
        """
        pos = int(position)
        if not (1 <= pos <= self._max_position):
            raise ValueError(
                f'Invalid position {position}. Must be between [1, {self._max_position}]'
            )

        self.connection.set_position(position)
        return self.get_position()
