"""
By default all registry tests that actually modify the registry are skipped.
You must set the environment variable `CASEMENT_TEST_WRITE_ENV` to `1` to enable
running the skipped tests.

Registry modification tests should only affect casement specific registry keys
that don't affect anything. They should contain `CASEMENT_DELETE_ME` in the name.
When testing finishes all of these registry keys should be removed. All write
tests should be done on user hives not system ones.

Here are the registry keys that are modified when write testing is enabled.
- `HKEY_CURRENT_USER\\Software\\Classes\\CASEMENT_DELETE_ME` and children

Note: See test_env_var.py to see how testing Environment variables are handled.
"""
# TODO: Look into using a custom testing registry hive to handle all testing
# without the need for the host to actually have these registry keys. We should
# only enable testing of registry modifications once this is resolved.
# Ie don't running casement tests should not modify the host registry.
from __future__ import absolute_import

from contextlib import contextmanager

import pytest
import six
from six.moves import winreg

from casement.registry import REG_LOCATIONS, RegKey

from . import ENABLE_ENV_VAR, reg_write_skipif


@contextmanager
def remove_reg_keys(items):
    """Ensures the requested registry keys are removed before and after the
    with context code is run. This ensures a consistent testing environment
    even if a previous test was killed without cleaning up after itself.

    Items is a list of registry (key, sub_key) items. If removing parents and
    children ensure the children are passed after the parents.
    """
    items = reversed(items)
    for key, sub_key in items:
        reg = RegKey(key, sub_key)
        # Ensure the registry key is removed, in case a previous test failed
        # or was killed before the registry key was removed normally.
        if reg.exists():
            reg.delete()

    try:
        yield
    finally:
        for key, sub_key in items:
            reg = RegKey(key, sub_key)
            # Ensure the variables are cleaned up after the test runs
            if reg.exists():
                reg.delete()


@pytest.mark.parametrize(
    'key,sub_key,hkey',
    [
        # Note: Lowercase testing is handled in the test, only use uppercase here
        ('HKEY_LOCAL_MACHINE', 'SOFTWARE\\Microsoft', winreg.HKEY_LOCAL_MACHINE),
        ('HKLM', 'SOFTWARE\\Microsoft', winreg.HKEY_LOCAL_MACHINE),
        ('HKEY_CURRENT_USER', 'SOFTWARE\\Microsoft', winreg.HKEY_CURRENT_USER),
        ('HKCU', 'SOFTWARE\\Microsoft', winreg.HKEY_CURRENT_USER),
        ('HKEY_CLASSES_ROOT', '*', winreg.HKEY_CLASSES_ROOT),
        ('HKCR', 'Directory', winreg.HKEY_CLASSES_ROOT),
        ('HKEY_USERS', '.DEFAULT\\Software\\Microsoft', winreg.HKEY_USERS),
        ('HKU', '.DEFAULT\\Software\\Microsoft', winreg.HKEY_USERS),
    ],
)
def test_reg_open(key, sub_key, hkey):
    # TEST passing split key an sub_key's
    # key and sub_key are passed in as 2 arguments
    regkey = RegKey(key, sub_key)
    assert regkey.key == hkey
    assert regkey.sub_key == sub_key
    # Key is lower cased
    regkey = RegKey(key.lower(), sub_key)
    assert regkey.key == hkey
    assert regkey.sub_key == sub_key

    # Test passing just key argument with sub_key attached
    regkey = RegKey('{}\\{}'.format(key, sub_key))
    assert regkey.key == hkey
    assert regkey.sub_key == sub_key


def test_child_names():
    # Test valid registry key
    reg = RegKey('HKLM\\SOFTWARE\\Microsoft\\Windows')
    names = list(reg.child_names())
    assert 'Notepad' in names
    assert 'Shell' in names

    # Test invalid registry key
    reg = RegKey('HKLM\\SOFTWARE\\InvalidName')
    assert list(reg.child_names()) == []


def test_child():
    sub_key = 'SOFTWARE\\Microsoft\\Windows'
    reg = RegKey('HKLM', sub_key)
    notepad = reg.child('Notepad')
    assert notepad._key() is not None
    assert notepad.sub_key == '{}\\Notepad'.format(sub_key)
    shell = reg.child('Shell')
    assert shell._key() is not None
    assert shell.sub_key == '{}\\Shell'.format(sub_key)


def test_entry_names():
    # Test Valid registry key
    reg = RegKey('HKCR\\Directory')
    names = reg.entry_names()
    assert 'AlwaysShowExt' in names

    # Test invalid registry key
    reg = RegKey('HKCR\\InvalidName')
    assert list(reg.entry_names()) == []


def test_entry():
    # Note: This test may break if the host computer has modified Directory
    # settings. Just ensure this test passes when run by github actions.
    reg = RegKey('HKCR\\Directory')
    # `(Default)` entry
    entry = reg.entry()
    txt = 'File Folder'
    assert entry.type() == winreg.REG_SZ
    assert entry.value() == txt
    assert entry.value_info() == (txt, winreg.REG_SZ)

    # Binary value type
    entry = reg.entry('EditFlags')
    assert entry.type() == winreg.REG_BINARY
    assert entry.value() == b'\xd2\x01\x00\x00'

    # String data type
    entry = reg.entry('PreviewTitle')
    assert entry.type() == winreg.REG_SZ
    assert isinstance(entry.value(), six.string_types)
    assert entry.value() == 'prop:System.ItemNameDisplay;System.ItemTypeText'

    # Expanding string data type
    entry = reg.entry('FriendlyTypeName')
    assert entry.type() == winreg.REG_EXPAND_SZ
    assert isinstance(entry.value(), six.string_types)


def test_sam():
    assert RegKey._sam(32) == winreg.KEY_WOW64_32KEY
    assert RegKey._sam(64) == winreg.KEY_WOW64_64KEY
    assert RegKey._sam(0) == 0
    assert RegKey._sam(16) == 0


@reg_write_skipif()
def test_write():
    key, root = REG_LOCATIONS['user']['classes']
    root = '{}\\CASEMENT_DELETE_ME'.format(root)
    child_names = ('CASEMENT_DELETE_ME_CHILD1', 'CASEMENT_DELETE_ME_CHILD2')
    child1 = '{}\\{}'.format(root, child_names[0])
    child2 = '{}\\{}'.format(root, child_names[1])

    with remove_reg_keys(((key, root), (key, child1), (key, child2))):
        reg = RegKey(key, root)
        assert not reg.exists()

        # Test deleting a key that doesn't exist
        ret = reg.delete()
        assert ret is False

        # Test creating a new key
        reg.create()
        assert reg.exists()

        # Ensure we raise a useful exception if trying to delete a key with a child
        creg1 = RegKey(key, child1)
        assert not creg1.exists()
        creg1.create()
        assert creg1.exists()
        with pytest.raises(RuntimeError) as excinfo:
            reg.delete()
        assert str(excinfo.value).startswith("Unable to delete key")

        # Test child and child_names by adding a second child
        creg2 = reg.child(child_names[1])
        assert not creg2.exists()
        creg2.create()

        assert set(reg.child_names()) == set(child_names)

        # Test getting/setting an Entry value
        entry_name = 'CASEMENT_DELETE_ME_ENTRY'
        entry = creg1.entry(entry_name)
        assert entry.key == creg1
        assert entry.name == entry_name

        value = '[%{}%]'.format(ENABLE_ENV_VAR)
        entry.set(value, "REG_EXPAND_SZ")
        assert entry.value() == value
        assert entry.type() == winreg.REG_EXPAND_SZ
        assert entry.value_info() == (value, winreg.REG_EXPAND_SZ)
        entry.set(value, winreg.REG_SZ)
        assert entry.value_info() == (value, winreg.REG_SZ)

        # Remove the children so we can actually delete the parent
        creg1.delete()
        assert not creg1.exists()
        creg2.delete()
        assert not creg2.exists()

        # Test deleting a key that exists
        ret = reg.delete()
        assert ret is True
        assert not reg.exists()

        # Check child_names if the key doesn't exist
        assert not set(reg.child_names())
