import os

import pytest
from msl.equipment import Config

from superk_mono import SuperK
from superk_mono.superk_laser import OperatingModes

cfg = Config(os.path.join('resources', 'config.xml'))
superk = SuperK(cfg.database().equipment['superk'])
superk.emission(False)


def test_is_emission_on():
    assert not superk.is_emission_on()


def test_interlock():
    assert superk.ensure_interlock_ok()


def test_constant_current_mode():
    superk.set_operating_mode(OperatingModes.CONSTANT_CURRENT)
    assert superk.get_operating_mode() == OperatingModes.CONSTANT_CURRENT
    assert superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert not superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()

    superk.enable_constant_current_mode()
    assert superk.get_operating_mode() == OperatingModes.CONSTANT_CURRENT
    assert superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert not superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()


@pytest.mark.skipif(superk.MODULE_TYPE == superk.MODULE_TYPE_0x88, reason='modulated-current mode not supported')
def test_modulated_current_mode():
    superk.set_operating_mode(OperatingModes.MODULATED_CURRENT)
    assert superk.get_operating_mode() == OperatingModes.MODULATED_CURRENT
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()

    superk.enable_modulated_current_mode()
    assert superk.get_operating_mode() == OperatingModes.MODULATED_CURRENT
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()


def test_power_lock_mode():
    superk.set_operating_mode(OperatingModes.POWER_LOCK)
    assert superk.get_operating_mode() == OperatingModes.POWER_LOCK
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert not superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert superk.is_power_lock_mode()

    superk.enable_power_lock_mode()
    assert superk.get_operating_mode() == OperatingModes.POWER_LOCK
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert not superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert superk.is_power_lock_mode()


def test_temperature():
    assert 15 < superk.get_temperature() < 25


def test_level():
    superk.enable_power_lock_mode()
    assert superk.set_feedback_level(90) == 90
    assert superk.get_feedback_level() == 90

    superk.enable_constant_current_mode()
    assert superk.set_current_level(10) == 10
    assert superk.get_current_level() == 10


@pytest.mark.skipif(superk.MODULE_TYPE == superk.MODULE_TYPE_0x88, reason='front-panel (un)locking not supported')
def test_lock_front_panel():
    # these should not raise an error, the return value is irrelevant
    assert superk.lock_front_panel(True) is None
    assert superk.lock_front_panel(False) is None


def test_user_text():
    assert superk.set_user_text('Hello') == 'Hello'
    assert superk.get_user_text() == 'Hello'

    if superk.MODULE_TYPE == superk.MODULE_TYPE_0x60:
        # 20 character limit
        assert superk.set_user_text('012345678901234567890123') == '01234567890123456789'
    else:
        # 240 character limit
        assert superk.set_user_text('a'*256) == 'a'*240

    expect = '' if superk.MODULE_TYPE == superk.MODULE_TYPE_0x60 else ' '
    assert superk.set_user_text('') == expect
