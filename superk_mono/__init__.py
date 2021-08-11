import re
import sys
import logging
from collections import namedtuple

from msl.network import Service
from msl.equipment import Config
from msl.equipment.utils import convert_to_enum

__author__ = 'Measurement Standards Laboratory of New Zealand'
__copyright__ = '\xa9 2021, ' + __author__
__version__ = '0.1.0.dev0'

_v = re.search(r'(\d+)\.(\d+)\.(\d+)[.-]?(.*)', __version__).groups()

version_info = namedtuple('version_info', 'major minor micro releaselevel')(int(_v[0]), int(_v[1]), int(_v[2]), _v[3])
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro, releaselevel) tuple."""


logger = logging.getLogger('superk-mono')


class BaseEquipment(Service):

    def __init__(self, record, name=None, max_clients=1):
        """Base class for all equipment connections.

        Parameters
        ----------
        record : :class:`~msl.equipment.record_types.EquipmentRecord`
            The equipment record.
        name : :class:`str`, optional
            The name of the :class:`msl.network.service.Service` as it will appear
            on the Network :class:`~msl.network.manager.Manager`. If not specified then
            uses the name of the class.
        max_clients : :class:`int`, optional
            The maximum number of :class:`~msl.network.client.Client`\\s that can be linked
            with this :class:`msl.network.service.Service`. A value :math:`\\leq` 0 or
            :data:`None` means that there is no limit.
        """
        super(BaseEquipment, self).__init__(
            name=name,
            max_clients=max_clients,
            ignore_attributes=['connection', 'logger', 'record']
        )

        self.record = record
        """:class:`~msl.equipment.record_types.EquipmentRecord`: The equipment record."""

        self.connection = record.connect()
        """The :class:`~msl.equipment.connection.Connection` subclass."""

    @property
    def alias(self):
        """:class:`str`: The alias of the :attr:`.record`"""
        return self.record.alias

    @property
    def logger(self):
        """Reference to the package logger."""
        return logger

    def record_to_json(self) -> dict:
        """Convert the :class:`~msl.equipment.record_types.EquipmentRecord` to be JSON serializable.

        Returns
        -------
        :class:`dict`
            The :class:`~msl.equipment.record_types.EquipmentRecord`.
        """
        return self.record.to_json()

    @staticmethod
    def convert_to_enum(obj, enum, prefix=None, to_upper=False, strict=True):
        """See :func:`~msl.equipment.utils.convert_to_enum` for more details."""
        return convert_to_enum(obj, enum, prefix=prefix, to_upper=to_upper, strict=strict)

    def disconnect(self):
        """Disconnect from the equipment."""
        self.connection.disconnect()


def parse_args():
    import os

    args = sys.argv[1:]
    if not args:
        input('You must specify the path to a config.xml file\n\nPress <ENTER> to exit ...')
        sys.exit(1)

    if not os.path.isfile(args[0]):
        input(f'File not found: {args[0]}\n\nPress <ENTER> to exit ...')
        sys.exit(1)

    return args


def start_manager():
    import subprocess

    path, *ignore = parse_args()
    config = Config(path)

    cmd = ['msl-network', 'start']
    port = config.value('manager/port')
    if port:
        cmd.extend(['--port', str(port)])

    if config.value('manager/disable_tls'):
        cmd.append('--disable-tls')

    if config.value('manager/debug'):
        cmd.append('--debug')

    try:
        subprocess.run(cmd)
    except (SystemExit, KeyboardInterrupt):
        pass


def start_service():
    from msl.loadlib.utils import wait_for_server

    from .superk_laser import SuperK
    from .hrs_monochromator import HRSMonochromator
    from .thorlabs_nd_filter_wheel import FW212CNEB

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-5s] %(message)s')
    logger.setLevel(logging.INFO)

    path, alias = parse_args()

    config = Config(path)
    db = config.database()

    try:
        record = db.equipment[alias]
    except KeyError:
        input(f'There is no equipment record with alias {alias!r}\n\nPress <ENTER> to exit ...')
        sys.exit(1)

    try:
        if alias == 'superk':
            service = SuperK(record)
        elif alias == 'mono-hrs':
            service = HRSMonochromator(record)
        elif alias == 'nd-wheel':
            service = FW212CNEB(record)
        else:
            input(f'Unhandled equipment alias {alias!r}\n\nPress <ENTER> to exit ...')
            sys.exit(1)
    except Exception as e:
        input(f'{e}\n\nPress <ENTER> to exit ...')
        sys.exit(1)

    port = config.value('manager/port')
    wait_for_server('localhost', port, 10)

    try:
        service.start(
            port=port,
            disable_tls=config.value('manager/disable_tls'),
            debug=False,
        )
    except Exception as e:
        input(f'{e}\n\nPress <ENTER> to exit ...')
    finally:
        service.disconnect()


from .superk_laser import SuperK
from .hrs_monochromator import HRSMonochromator
from .thorlabs_nd_filter_wheel import FW212CNEB
