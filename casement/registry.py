"""
key: Nodes in tree
Each node in the tree is called a key.
Each key can contain both subkeys and data entries called values.
"""
import six
from six.moves import winreg


def _generate_key_map():
    """Creates a map of strings to winreg.HKEY_* objects."""
    key_map = {}

    for key in dir(winreg):
        if key.startswith('HKEY_'):
            # Add the long names
            key_map[key] = getattr(winreg, key)
            # Add the winreg value so we can lookup nice names for keys
            key_map[getattr(winreg, key)] = key
            # Generate shortnames
            short = 'HK' + ''.join([s[0] for s in key.split('_')[1:]])
            if short not in key_map:
                key_map[short] = key_map[key]
    return key_map


key_map = _generate_key_map()

"""Stores commonly looked up locations in the registry."""
REG_LOCATIONS = {
    "system": {
        "classes": (winreg.HKEY_LOCAL_MACHINE, 'Software\\Classes'),
        "env_var": (
            winreg.HKEY_LOCAL_MACHINE,
            'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment',
        ),
        "uninstall": (
            winreg.HKEY_LOCAL_MACHINE,
            'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
        ),
    },
    "user": {
        "classes": (winreg.HKEY_CURRENT_USER, 'Software\\Classes'),
        "env_var": (winreg.HKEY_CURRENT_USER, 'Environment'),
    },
}


class RegKey(object):
    def __init__(self, key, sub_key=None, computer_name=None, architecture=64):
        # If sub_key is not passed, it must be part of key
        if sub_key is None:
            key, sub_key = key.split('\\', 1)

        # Convert key strings into winreg keys
        if isinstance(key, six.string_types):
            key = key.upper()
            key = key_map[key]

        self.architecture = architecture
        self.computer_name = computer_name
        self.key = key
        self.sub_key = sub_key

    def __str__(self):
        return 'RegKey({!r}, {!r}, {!r}, {})'.format(
            key_map.get(self.key, self.key),
            self.sub_key,
            self.computer_name,
            self.architecture,
        )

    def _key(self, write=False, create=False, delete=False):
        """Returns a winreg.OpenKeyEx or None.

        Returns:
            A winreg handle object
        """
        connection = winreg.ConnectRegistry(None, self.key)
        sam = self._sam(self.architecture)
        access = winreg.KEY_READ
        if write:
            access = winreg.KEY_WRITE

        if create:
            func = winreg.CreateKeyEx
        else:
            func = winreg.OpenKeyEx

        try:
            return func(connection, self.sub_key, 0, access | sam)
        except OSError:
            return None

    @classmethod
    def _sam(cls, architecture):
        """Return the correct wow64 key for the requested architecture."""
        if architecture == 32:
            return winreg.KEY_WOW64_32KEY
        elif architecture == 64:
            return winreg.KEY_WOW64_64KEY
        return 0

    def child(self, name):
        """Returns a RegKey for a sub_key with the given name.

        Args:
            name (str): The name of the child key to return.
        """
        cls = type(self)
        sub_key = '{}\\{}'.format(self.sub_key, name)
        return cls(
            self.key,
            sub_key=sub_key,
            computer_name=self.computer_name,
            architecture=self.architecture,
        )

    def child_names(self):
        """Generator returning the name for all sub_keys of this key."""
        reg_key = self._key()
        if not reg_key:
            return

        index = 0
        while True:
            try:
                yield winreg.EnumKey(reg_key, index)
                index += 1
            except OSError:
                break

    def create(self):
        self._key(create=True)

    def delete(self):
        """Delete the entire registry key. Raises a RuntimeError if the key has
        child keys."""
        # If the key doesn't exist, there is nothing to do
        if not self.exists():
            return False

        # TODO: add recursive delete?
        for child in self.child_names():
            # We can't delete this key if it has sub-keys. Using for loop instead
            # of using next() so this can be used inside a contextmanager
            if child:
                msg = "Unable to delete key, it has sub-keys. {}".format(self)
                raise RuntimeError(msg)

        sam = self._sam(self.architecture)
        winreg.DeleteKeyEx(self.key, self.sub_key, sam)
        return True

    def entry(self, name=None):
        """Returns a RegEntry for the given name. To access the (Default) entry
        pass an empty string or None.

        Args:
            name (str, optional): The name of the entry to return.
        """
        return RegEntry(self, name)

    def entry_names(self):
        """Generator returning the name for all entry's stored on this key."""
        reg_key = self._key()
        if not reg_key:
            return

        _, count, _ = winreg.QueryInfoKey(reg_key)
        for index in range(count):
            name, _, _ = winreg.EnumValue(reg_key, index)
            yield name

    def exists(self):
        """Returns True if the key exists in the registry."""
        key = self._key()
        return key is not None


class RegEntry(object):
    def __init__(self, key, name):
        self.key = key
        self.name = name

    def delete(self):
        key = self.key._key(write=True)
        winreg.DeleteValue(key, self.name)
        winreg.CloseKey(key)

    def type(self):
        """Returns the winreg value type."""
        return self.value_info()[1]

    def set(self, value, value_type=None):
        key = self.key._key(write=True, create=True)

        if isinstance(value_type, six.string_types):
            value_type = getattr(winreg, value_type)

        winreg.SetValueEx(key, self.name, 0, value_type, value)
        winreg.CloseKey(key)
        # TODO: add notify, or keep that in EnvVar?

    def value(self):
        """Returns the data value."""
        value, _ = self.value_info()
        # We may need to do some conversion based on type in the future.
        return value

    def value_info(self):
        """Returns the entry value and value type.

        Returns:
            object: Value stored in key
            int: registry type for value. See winreg's Value Types
        """
        return winreg.QueryValueEx(self.key._key(), self.name)
